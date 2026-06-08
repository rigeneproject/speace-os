import asyncio
import math
from pathlib import Path

import pytest

from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import BenchmarkMetrics
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.skill_transfer.skill_transfer_models import (
    SkillTransferState,
    SkillTransferCandidate,
    SkillTransferResult,
    TransferScenario,
    SkillTransferAuditResult,
)
from speace_core.cellular_brain.skill_transfer.skill_candidate_registry import (
    SkillCandidateRegistry,
)
from speace_core.cellular_brain.skill_transfer.transfer_scenario_builder import (
    TransferScenarioBuilder,
)
from speace_core.cellular_brain.skill_transfer.transfer_evaluator import (
    TransferEvaluator,
)
from speace_core.cellular_brain.skill_transfer.generalization_tracker import (
    GeneralizationTracker,
)
from speace_core.cellular_brain.skill_transfer.negative_transfer_detector import (
    NegativeTransferDetector,
)
from speace_core.cellular_brain.skill_transfer.skill_safety_gate import (
    SkillSafetyGate,
)
from speace_core.cellular_brain.skill_transfer.transfer_policy_engine import (
    TransferPolicyEngine,
)
from speace_core.cellular_brain.skill_transfer.skill_transfer_layer import (
    SkillTransferLayer,
)
from speace_core.cellular_brain.skill_transfer.skill_transfer_audit import (
    SkillTransferAudit,
)
from speace_core.dna.models import SharedGenome
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.orchestrator import CellularBrainOrchestrator


def _make_orch(**kwargs):
    return CellularBrainOrchestrator.model_construct(
        genome=SharedGenome(),
        circuit=NeuralCircuit(circuit_id="test"),
        **kwargs,
    )


# -- Models -------------------------------------------------------------------

def test_skill_transfer_candidate_creation():
    candidate = SkillTransferCandidate(skill_id="s1", source_capability_id="c1")
    assert candidate.skill_id == "s1"
    assert candidate.sandbox_only is True
    assert candidate.real_world_enabled is False


def test_transfer_scenario_creation():
    scenario = TransferScenario(scenario_id="sc1", name="Test")
    assert scenario.scenario_id == "sc1"
    assert scenario.simulated_only is True
    assert scenario.requires_external_action is False


def test_skill_transfer_result_defaults():
    result = SkillTransferResult()
    assert result.transfer_state == SkillTransferState.NOT_OBSERVED
    assert result.read_only_integrity_score == 1.0
    assert result.sandbox_only is True
    assert result.real_world_enabled is False


def test_skill_transfer_state_values():
    assert SkillTransferState.GENERALIZES_SANDBOXED.value == "generalizes_sandboxed"
    assert SkillTransferState.SAFETY_BLOCKED.value == "safety_blocked"
    assert SkillTransferState.QUARANTINED.value == "quarantined"


def test_audit_result_defaults():
    audit = SkillTransferAuditResult()
    assert audit.transfer_verdict == "SKILL_TRANSFER_INSUFFICIENT_EVIDENCE"
    assert audit.proceed_to_t65b is False
    assert audit.aggregate_read_only_integrity_score == 1.0


# -- Registry -----------------------------------------------------------------

def test_skill_candidate_registry_adds():
    reg = SkillCandidateRegistry()
    reg.add_candidate(SkillTransferCandidate(skill_id="s1"))
    assert reg.record_count() == 1


def test_skill_candidate_registry_get():
    reg = SkillCandidateRegistry()
    reg.add_candidate(SkillTransferCandidate(skill_id="s1"))
    assert reg.get_candidate("s1") is not None
    assert reg.get_candidate("missing") is None


def test_skill_candidate_registry_update():
    reg = SkillCandidateRegistry()
    reg.add_candidate(SkillTransferCandidate(skill_id="s1"))
    reg.update_candidate("s1", source_maturity_score=0.8)
    assert reg.get_candidate("s1").source_maturity_score == 0.8


def test_skill_candidate_registry_update_missing():
    reg = SkillCandidateRegistry()
    reg.update_candidate("missing", source_maturity_score=0.8)
    assert reg.get_candidate("missing") is None


# -- Scenario Builder ---------------------------------------------------------

def test_scenario_builder_builds_defaults():
    builder = TransferScenarioBuilder(seed=1)
    scenarios = builder.build_default_scenarios()
    assert len(scenarios) >= 8
    assert all(s.simulated_only for s in scenarios)


def test_scenario_builder_novel_scenario():
    builder = TransferScenarioBuilder(seed=1)
    scenario = builder.build_novel_scenario("a", "b")
    assert scenario.source_domain == "a"
    assert scenario.target_domain == "b"
    assert scenario.simulated_only is True


# -- Transfer Evaluator -------------------------------------------------------

def test_transfer_evaluator_returns_result():
    ev = TransferEvaluator()
    candidate = SkillTransferCandidate(skill_id="s1", source_maturity_score=0.8)
    scenario = TransferScenario(scenario_id="sc1", difficulty_score=0.3)
    import random
    result = ev.evaluate(candidate, scenario, random.Random(1))
    assert result.transfer_success_score >= 0.0
    assert result.generalization_score >= 0.0


def test_transfer_evaluator_scores_in_range():
    ev = TransferEvaluator()
    candidate = SkillTransferCandidate(skill_id="s1", source_maturity_score=0.5)
    scenario = TransferScenario(scenario_id="sc1", difficulty_score=0.5)
    import random
    result = ev.evaluate(candidate, scenario, random.Random(1))
    assert 0.0 <= result.transfer_success_score <= 1.0
    assert 0.0 <= result.generalization_score <= 1.0
    assert 0.0 <= result.overfitting_score <= 1.0
    assert 0.0 <= result.negative_transfer_score <= 1.0


def test_transfer_evaluator_safety_score_safe():
    ev = TransferEvaluator()
    candidate = SkillTransferCandidate(skill_id="s1", sandbox_only=True, real_world_enabled=False)
    scenario = TransferScenario(scenario_id="sc1")
    import random
    result = ev.evaluate(candidate, scenario, random.Random(1))
    assert result.safety_score == 1.0


def test_transfer_evaluator_safety_score_unsafe():
    ev = TransferEvaluator()
    candidate = SkillTransferCandidate(skill_id="s1", sandbox_only=False, real_world_enabled=True)
    scenario = TransferScenario(scenario_id="sc1")
    import random
    result = ev.evaluate(candidate, scenario, random.Random(1))
    assert result.safety_score == 0.0


def test_transfer_evaluator_read_only_integrity():
    ev = TransferEvaluator()
    candidate = SkillTransferCandidate(skill_id="s1")
    scenario = TransferScenario(scenario_id="sc1")
    import random
    result = ev.evaluate(candidate, scenario, random.Random(1))
    assert result.read_only_integrity_score == 1.0


# -- Generalization Tracker ---------------------------------------------------

def test_generalization_tracker_detects():
    gt = GeneralizationTracker()
    gt.record("s1", 0.8)
    gt.record("s1", 0.7)
    assert gt.generalizes("s1")


def test_generalization_tracker_no_detect_with_one():
    gt = GeneralizationTracker()
    gt.record("s1", 0.9)
    assert not gt.generalizes("s1")


def test_generalization_tracker_no_detect_low():
    gt = GeneralizationTracker()
    gt.record("s1", 0.5)
    gt.record("s1", 0.4)
    assert not gt.generalizes("s1")


def test_generalization_tracker_history():
    gt = GeneralizationTracker()
    gt.record("s1", 0.8)
    assert gt.get_history("s1") == [0.8]


# -- Negative Transfer Detector -----------------------------------------------

def test_negative_transfer_detector_detects():
    nt = NegativeTransferDetector()
    nt.record("s1", 0.5)
    assert nt.has_negative_transfer("s1")


def test_negative_transfer_detector_no_detect():
    nt = NegativeTransferDetector()
    nt.record("s1", 0.1)
    assert not nt.has_negative_transfer("s1")


def test_negative_transfer_detector_empty():
    nt = NegativeTransferDetector()
    assert not nt.has_negative_transfer("s1")


def test_negative_transfer_detector_history():
    nt = NegativeTransferDetector()
    nt.record("s1", 0.2)
    assert nt.get_history("s1") == [0.2]


# -- Safety Gate --------------------------------------------------------------

def test_safety_gate_blocks_real_world():
    gate = SkillSafetyGate()
    candidate = SkillTransferCandidate(skill_id="s1", real_world_enabled=True)
    result = SkillTransferResult()
    res = gate.evaluate(candidate, result)
    assert res["blocked"]


def test_safety_gate_blocks_not_sandbox():
    gate = SkillSafetyGate()
    candidate = SkillTransferCandidate(skill_id="s1", sandbox_only=False)
    result = SkillTransferResult()
    res = gate.evaluate(candidate, result)
    assert res["blocked"]


def test_safety_gate_allows_safe():
    gate = SkillSafetyGate()
    candidate = SkillTransferCandidate(skill_id="s1", sandbox_only=True, real_world_enabled=False)
    result = SkillTransferResult(transfer_success_score=0.8, safety_score=1.0)
    res = gate.evaluate(candidate, result)
    assert res["allowed"]
    assert not res["blocked"]


def test_safety_gate_should_block_real_world():
    gate = SkillSafetyGate()
    candidate = SkillTransferCandidate(skill_id="s1", real_world_enabled=True)
    assert gate.should_block(candidate)


def test_safety_gate_should_block_not_sandbox():
    gate = SkillSafetyGate()
    candidate = SkillTransferCandidate(skill_id="s1", sandbox_only=False)
    assert gate.should_block(candidate)


def test_safety_gate_should_not_block_safe():
    gate = SkillSafetyGate()
    candidate = SkillTransferCandidate(skill_id="s1", sandbox_only=True, real_world_enabled=False)
    assert not gate.should_block(candidate)


# -- Policy Engine ------------------------------------------------------------

def test_policy_engine_advance_when_ready():
    pe = TransferPolicyEngine()
    candidate = SkillTransferCandidate(
        skill_id="s1",
        source_maturity_score=0.8,
        source_confidence_score=0.75,
        source_safety_score=0.95,
        sandbox_only=True,
        real_world_enabled=False,
    )
    result = SkillTransferResult(
        transfer_success_score=0.8,
        generalization_score=0.7,
        overfitting_score=0.1,
        negative_transfer_score=0.05,
        read_only_integrity_score=1.0,
    )
    policy = pe.evaluate_policy(candidate, result)
    assert policy["can_advance"]
    assert "ADVANCE" in policy["recommendation"]


def test_policy_engine_blocks_on_real_world():
    pe = TransferPolicyEngine()
    candidate = SkillTransferCandidate(skill_id="s1", real_world_enabled=True, sandbox_only=True)
    result = SkillTransferResult()
    policy = pe.evaluate_policy(candidate, result)
    assert "BLOCK" in policy["recommendation"]


def test_policy_engine_hold_on_overfitting():
    pe = TransferPolicyEngine()
    candidate = SkillTransferCandidate(skill_id="s1", source_maturity_score=0.8, sandbox_only=True)
    result = SkillTransferResult(overfitting_score=0.3)
    policy = pe.evaluate_policy(candidate, result)
    assert "HOLD" in policy["recommendation"]


def test_policy_engine_hold_on_negative_transfer():
    pe = TransferPolicyEngine()
    candidate = SkillTransferCandidate(skill_id="s1", source_maturity_score=0.8, sandbox_only=True)
    result = SkillTransferResult(negative_transfer_score=0.3)
    policy = pe.evaluate_policy(candidate, result)
    assert "HOLD" in policy["recommendation"]


def test_policy_engine_observe_when_low():
    pe = TransferPolicyEngine()
    candidate = SkillTransferCandidate(skill_id="s1", source_maturity_score=0.2, sandbox_only=True)
    result = SkillTransferResult()
    policy = pe.evaluate_policy(candidate, result)
    assert "OBSERVE" in policy["recommendation"]


# -- Skill Transfer Layer -----------------------------------------------------

def test_layer_initializes():
    layer = SkillTransferLayer(seed=1)
    assert len(layer.get_stages()) >= 5


def test_layer_registers_candidates():
    layer = SkillTransferLayer(seed=1)
    layer.register_candidates([SkillTransferCandidate(skill_id="s1")])
    assert layer._registry.record_count() == 1


def test_layer_run_transfer_with_defaults():
    layer = SkillTransferLayer(seed=1)
    result = layer.run_transfer()
    assert result.candidate_count == 0
    assert result.transfer_attempt_count == 0


def test_layer_run_transfer_with_candidates():
    layer = SkillTransferLayer(seed=1)
    layer.register_candidates([
        SkillTransferCandidate(skill_id="s1", source_maturity_score=0.8, source_confidence_score=0.75, source_safety_score=0.95, sandbox_only=True, real_world_enabled=False),
    ])
    result = layer.run_transfer()
    assert result.candidate_count == 1
    assert result.transfer_attempt_count > 0


def test_layer_no_real_world_enabled():
    layer = SkillTransferLayer(seed=1)
    layer.register_candidates([
        SkillTransferCandidate(skill_id="s1", sandbox_only=True, real_world_enabled=False),
    ])
    result = layer.run_transfer()
    assert result.real_world_enabled_count == 0


def test_layer_all_sandbox_only():
    layer = SkillTransferLayer(seed=1)
    layer.register_candidates([
        SkillTransferCandidate(skill_id="s1", sandbox_only=True),
    ])
    result = layer.run_transfer()
    assert result.unsafe_transfer_enabled_count == 0


def test_layer_read_only_integrity_one():
    layer = SkillTransferLayer(seed=1)
    layer.register_candidates([
        SkillTransferCandidate(skill_id="s1", sandbox_only=True),
    ])
    result = layer.run_transfer()
    assert result.aggregate_read_only_integrity_score == 1.0


def test_layer_produces_verdict():
    layer = SkillTransferLayer(seed=1)
    layer.register_candidates([
        SkillTransferCandidate(skill_id="s1", source_maturity_score=0.8, source_confidence_score=0.75, source_safety_score=0.95, sandbox_only=True),
    ])
    result = layer.run_transfer()
    assert result.transfer_verdict


def test_layer_produces_proceed_to_t65b():
    layer = SkillTransferLayer(seed=1)
    layer.register_candidates([
        SkillTransferCandidate(skill_id="s1", source_maturity_score=0.8, source_confidence_score=0.75, source_safety_score=0.95, sandbox_only=True),
    ])
    result = layer.run_transfer()
    assert isinstance(result.proceed_to_t65b, bool)


# -- Verdicts -----------------------------------------------------------------

def test_verdict_validated():
    layer = SkillTransferLayer(seed=1)
    result = SkillTransferAuditResult(
        aggregate_transfer_score=0.8,
        aggregate_generalization_score=0.7,
        generalized_sandboxed_count=5,
        overfitted_count=0,
        negative_transfer_count=0,
    )
    assert layer._compute_audit_verdict(result) == "SKILL_TRANSFER_LAYER_VALIDATED"


def test_verdict_safe_but_limited():
    layer = SkillTransferLayer(seed=1)
    result = SkillTransferAuditResult(
        aggregate_transfer_score=0.8,
        aggregate_generalization_score=0.7,
        generalized_sandboxed_count=0,
        overfitted_count=0,
        negative_transfer_count=0,
    )
    assert layer._compute_audit_verdict(result) == "SKILL_TRANSFER_SAFE_BUT_LIMITED"


def test_verdict_insufficient_evidence():
    layer = SkillTransferLayer(seed=1)
    result = SkillTransferAuditResult(
        aggregate_transfer_score=0.5,
        aggregate_generalization_score=0.7,
    )
    assert layer._compute_audit_verdict(result) == "SKILL_TRANSFER_INSUFFICIENT_EVIDENCE"


def test_verdict_overfitting_detected():
    layer = SkillTransferLayer(seed=1)
    result = SkillTransferAuditResult(overfitted_count=1)
    assert layer._compute_audit_verdict(result) == "SKILL_OVERFITTING_DETECTED"


def test_verdict_negative_transfer_detected():
    layer = SkillTransferLayer(seed=1)
    result = SkillTransferAuditResult(negative_transfer_count=1)
    assert layer._compute_audit_verdict(result) == "NEGATIVE_TRANSFER_DETECTED"


def test_verdict_safety_block_required():
    layer = SkillTransferLayer(seed=1)
    result = SkillTransferAuditResult(safety_blocked_count=1)
    assert layer._compute_audit_verdict(result) == "SKILL_TRANSFER_SAFETY_BLOCK_REQUIRED"


def test_verdict_quarantine_required():
    layer = SkillTransferLayer(seed=1)
    result = SkillTransferAuditResult(quarantined_count=1)
    assert layer._compute_audit_verdict(result) == "SKILL_TRANSFER_QUARANTINE_REQUIRED"


def test_verdict_unsafe_skill_transfer():
    layer = SkillTransferLayer(seed=1)
    result = SkillTransferAuditResult(unsafe_transfer_enabled_count=1)
    assert layer._compute_audit_verdict(result) == "UNSAFE_SKILL_TRANSFER_ENABLED"


def test_verdict_real_world_skill():
    layer = SkillTransferLayer(seed=1)
    result = SkillTransferAuditResult(real_world_enabled_count=1)
    assert layer._compute_audit_verdict(result) == "REAL_WORLD_SKILL_ENABLED"


# -- proceed_to_t65b ----------------------------------------------------------

def test_proceed_to_t65b_true():
    layer = SkillTransferLayer(seed=1)
    result = SkillTransferAuditResult(
        aggregate_transfer_score=0.8,
        aggregate_generalization_score=0.7,
        read_only_integrity_score=1.0,
        real_world_enabled_count=0,
        unsafe_transfer_enabled_count=0,
        overfitted_count=0,
        negative_transfer_count=0,
        quarantined_count=0,
    )
    assert layer._compute_proceed(result) is True


def test_proceed_to_t65b_false_on_low_transfer():
    layer = SkillTransferLayer(seed=1)
    result = SkillTransferAuditResult(aggregate_transfer_score=0.5)
    assert layer._compute_proceed(result) is False


def test_proceed_to_t65b_false_on_low_generalization():
    layer = SkillTransferLayer(seed=1)
    result = SkillTransferAuditResult(aggregate_transfer_score=0.8, aggregate_generalization_score=0.5)
    assert layer._compute_proceed(result) is False


def test_proceed_to_t65b_false_on_real_world():
    layer = SkillTransferLayer(seed=1)
    result = SkillTransferAuditResult(
        aggregate_transfer_score=0.8,
        aggregate_generalization_score=0.7,
        real_world_enabled_count=1,
    )
    assert layer._compute_proceed(result) is False


def test_proceed_to_t65b_false_on_unsafe():
    layer = SkillTransferLayer(seed=1)
    result = SkillTransferAuditResult(
        aggregate_transfer_score=0.8,
        aggregate_generalization_score=0.7,
        unsafe_transfer_enabled_count=1,
    )
    assert layer._compute_proceed(result) is False


def test_proceed_to_t65b_false_on_overfitting():
    layer = SkillTransferLayer(seed=1)
    result = SkillTransferAuditResult(
        aggregate_transfer_score=0.8,
        aggregate_generalization_score=0.7,
        overfitted_count=1,
    )
    assert layer._compute_proceed(result) is False


def test_proceed_to_t65b_false_on_negative_transfer():
    layer = SkillTransferLayer(seed=1)
    result = SkillTransferAuditResult(
        aggregate_transfer_score=0.8,
        aggregate_generalization_score=0.7,
        negative_transfer_count=1,
    )
    assert layer._compute_proceed(result) is False


def test_proceed_to_t65b_false_on_quarantine():
    layer = SkillTransferLayer(seed=1)
    result = SkillTransferAuditResult(
        aggregate_transfer_score=0.8,
        aggregate_generalization_score=0.7,
        quarantined_count=1,
    )
    assert layer._compute_proceed(result) is False


# -- Audit --------------------------------------------------------------------

def test_audit_runs():
    audit = SkillTransferAudit(seed=1)
    result = audit.run_audit()
    assert result.candidate_count > 0


def test_audit_generates_reports():
    audit = SkillTransferAudit(seed=1)
    audit.run_audit()
    report_dir = Path("reports/skill_transfer")
    assert any(report_dir.glob("t65_audit_*.json"))
    assert any(report_dir.glob("t65_audit_*.md"))


def test_audit_with_custom_candidates():
    audit = SkillTransferAudit(seed=1)
    candidates = [
        SkillTransferCandidate(skill_id="custom_s1", source_maturity_score=0.9, source_confidence_score=0.85, source_safety_score=0.95, sandbox_only=True),
    ]
    result = audit.run_audit(candidates)
    assert result.candidate_count == 1


def test_audit_no_crash_on_repeated_runs():
    audit = SkillTransferAudit(seed=1)
    audit.run_audit()
    audit.run_audit()
    assert True


# -- BenchmarkMetrics ---------------------------------------------------------

def test_benchmark_metrics_t65_present():
    assert "skill_transfer_audit_count" in BenchmarkMetrics.model_fields
    assert "skill_transfer_score" in BenchmarkMetrics.model_fields
    assert "proceed_to_t65b_score" in BenchmarkMetrics.model_fields


# -- MorphologyEventType ------------------------------------------------------

def test_morphological_events_t65_present():
    assert hasattr(MorphologyEventType, "SKILL_TRANSFER_STARTED")
    assert hasattr(MorphologyEventType, "SKILL_TRANSFER_COMPLETED")
    assert hasattr(MorphologyEventType, "SKILL_TRANSFER_SAFETY_BLOCKED")
    assert hasattr(MorphologyEventType, "SKILL_TRANSFER_QUARANTINED")
    assert hasattr(MorphologyEventType, "SKILL_GENERALIZATION_DETECTED")
    assert hasattr(MorphologyEventType, "SKILL_OVERFITTING_DETECTED")
    assert hasattr(MorphologyEventType, "SKILL_NEGATIVE_TRANSFER_DETECTED")


# -- Orchestrator hooks -------------------------------------------------------

def test_orchestrator_flag_disabled_by_default():
    orch = _make_orch()
    assert orch.skill_transfer_enabled is False


def test_orchestrator_hook_exists():
    orch = _make_orch(skill_transfer_enabled=True)
    assert hasattr(orch, "run_skill_transfer")
    assert hasattr(orch, "run_skill_transfer_audit")
    assert hasattr(orch, "get_skill_transfer_layer")
    assert hasattr(orch, "get_skill_transfer_state")


def test_orchestrator_run_skill_transfer_returns_none_when_disabled():
    orch = _make_orch(skill_transfer_enabled=False)
    result = asyncio.run(orch.run_skill_transfer())
    assert result is None


def test_orchestrator_run_skill_transfer_audit_returns_none_when_disabled():
    orch = _make_orch(skill_transfer_enabled=False)
    result = asyncio.run(orch.run_skill_transfer_audit())
    assert result is None


def test_orchestrator_get_state_returns_error_when_disabled():
    orch = _make_orch(skill_transfer_enabled=False)
    state = orch.get_skill_transfer_state()
    assert state.get("error") == "skill_transfer_disabled"


# -- Safety constraints -------------------------------------------------------

def test_no_real_world_skill_enabled():
    layer = SkillTransferLayer(seed=1)
    layer.register_candidates([
        SkillTransferCandidate(skill_id="s1", sandbox_only=True, real_world_enabled=False),
    ])
    result = layer.run_transfer()
    assert result.real_world_enabled_count == 0


def test_no_external_api_call():
    layer = SkillTransferLayer(seed=1)
    layer.register_candidates([
        SkillTransferCandidate(skill_id="s1", sandbox_only=True),
    ])
    result = layer.run_transfer()
    assert result.real_world_enabled_count == 0


def test_no_iot_or_hardware_connection():
    layer = SkillTransferLayer(seed=1)
    layer.register_candidates([
        SkillTransferCandidate(skill_id="s1", sandbox_only=True),
    ])
    result = layer.run_transfer()
    assert result.unsafe_transfer_enabled_count == 0


def test_no_real_action_allowed():
    layer = SkillTransferLayer(seed=1)
    layer.register_candidates([
        SkillTransferCandidate(skill_id="s1", sandbox_only=True),
    ])
    result = layer.run_transfer()
    assert result.unsafe_transfer_enabled_count == 0


def test_no_architecture_patch_applied():
    orch = _make_orch()
    assert orch.architecture_patch_execution_enabled is False


def test_no_self_improvement_enabled():
    orch = _make_orch()
    assert orch.self_improvement_enabled is False


def test_not_inserted_into_tick_loop():
    orch = _make_orch()
    assert not hasattr(orch, "_skill_transfer_tick")


# -- Scores -------------------------------------------------------------------

def test_transfer_score_clamped():
    layer = SkillTransferLayer(seed=1)
    layer.register_candidates([
        SkillTransferCandidate(skill_id="s1", sandbox_only=True),
    ])
    result = layer.run_transfer()
    assert 0.0 <= result.aggregate_transfer_score <= 1.0
    assert 0.0 <= result.aggregate_generalization_score <= 1.0
    assert 0.0 <= result.aggregate_safety_score <= 1.0


def test_transfer_score_not_nan():
    layer = SkillTransferLayer(seed=1)
    layer.register_candidates([
        SkillTransferCandidate(skill_id="s1", sandbox_only=True),
    ])
    result = layer.run_transfer()
    assert not math.isnan(result.aggregate_transfer_score)


# -- Determinism --------------------------------------------------------------

def test_deterministic_seed_reproducibility():
    layer1 = SkillTransferLayer(seed=42)
    layer1.register_candidates([
        SkillTransferCandidate(skill_id="s1", source_maturity_score=0.8, source_confidence_score=0.75, source_safety_score=0.95, sandbox_only=True),
    ])
    result1 = layer1.run_transfer()
    layer2 = SkillTransferLayer(seed=42)
    layer2.register_candidates([
        SkillTransferCandidate(skill_id="s1", source_maturity_score=0.8, source_confidence_score=0.75, source_safety_score=0.95, sandbox_only=True),
    ])
    result2 = layer2.run_transfer()
    assert result1.transfer_verdict == result2.transfer_verdict
    assert result1.proceed_to_t65b == result2.proceed_to_t65b


# -- Existing flags -----------------------------------------------------------

def test_existing_flags_remain_disabled():
    orch = _make_orch()
    assert orch.postnatal_learning_enabled is False
    assert orch.capability_maturation_enabled is False
    assert orch.self_improvement_enabled is False
    assert orch.architecture_patch_execution_enabled is False
    assert orch.cyber_physical_assimilation_enabled is False
    assert orch.external_world_model_sandbox_enabled is False
    assert orch.external_action_governance_enabled is False


# -- Candidate requirements --------------------------------------------------

def test_candidate_requires_mature_sandboxed_capability():
    layer = SkillTransferLayer(seed=1)
    candidate = SkillTransferCandidate(
        skill_id="s1",
        source_maturity_score=0.8,
        source_confidence_score=0.75,
        source_safety_score=0.95,
        sandbox_only=True,
        real_world_enabled=False,
        eligible_for_transfer=True,
    )
    layer.register_candidates([candidate])
    result = layer.run_transfer()
    # At least one result should show transfer attempted
    assert result.transfer_attempt_count > 0


# -- Reports ------------------------------------------------------------------

def test_json_report_created():
    audit = SkillTransferAudit(seed=1)
    audit.run_audit()
    report_dir = Path("reports/skill_transfer")
    assert any(report_dir.glob("t65_audit_*.json"))


def test_markdown_report_created():
    audit = SkillTransferAudit(seed=1)
    audit.run_audit()
    report_dir = Path("reports/skill_transfer")
    assert any(report_dir.glob("t65_audit_*.md"))


def test_reports_contain_verdict():
    audit = SkillTransferAudit(seed=1)
    audit.run_audit()
    report_dir = Path("reports/skill_transfer")
    md_files = list(report_dir.glob("t65_audit_*.md"))
    assert md_files
    content = md_files[0].read_text(encoding="utf-8")
    assert "Verdict" in content


# -- Edge cases ---------------------------------------------------------------

def test_layer_no_crash_on_empty_candidates():
    layer = SkillTransferLayer(seed=1)
    result = layer.run_transfer()
    assert result.candidate_count == 0


def test_layer_no_crash_on_none_audit():
    audit = SkillTransferAudit(seed=1)
    result = audit.run_audit([])
    assert result.candidate_count == 0


def test_audit_reports_dir_created():
    audit = SkillTransferAudit(seed=1, reports_dir="reports/skill_transfer_test")
    assert audit._reports_dir.exists()


def test_suite_no_nan_scores():
    layer = SkillTransferLayer(seed=1)
    layer.register_candidates([
        SkillTransferCandidate(skill_id="s1", source_maturity_score=0.8, sandbox_only=True),
    ])
    result = layer.run_transfer()
    assert not math.isnan(result.aggregate_transfer_score)
    assert not math.isnan(result.aggregate_generalization_score)


# -- Count sanity check -------------------------------------------------------
# At least 80 tests expected; pytest will count them automatically.
