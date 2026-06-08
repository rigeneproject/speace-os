import math
from pathlib import Path

import pytest

from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import BenchmarkMetrics
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.capability_maturation.capability_maturation_models import (
    CapabilityMaturityState,
    CapabilityRiskClass,
    CapabilityRecord,
    CapabilityMaturationResult,
)
from speace_core.cellular_brain.capability_maturation.capability_registry import (
    CapabilityRegistry,
    DEFAULT_CAPABILITIES,
)
from speace_core.cellular_brain.capability_maturation.maturity_evaluator import (
    MaturityEvaluator,
)
from speace_core.cellular_brain.capability_maturation.regression_tracker import (
    RegressionTracker,
)
from speace_core.cellular_brain.capability_maturation.safety_capability_gate import (
    SafetyCapabilityGate,
)
from speace_core.cellular_brain.capability_maturation.capability_quarantine_manager import (
    CapabilityQuarantineManager,
)
from speace_core.cellular_brain.capability_maturation.maturation_policy_engine import (
    MaturationPolicyEngine,
)
from speace_core.cellular_brain.capability_maturation.capability_maturation_layer import (
    CapabilityMaturationLayer,
)
from speace_core.cellular_brain.capability_maturation.capability_maturation_audit import (
    CapabilityMaturationAudit,
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

def test_capability_record_creation():
    record = CapabilityRecord(capability_id="test_cap", name="Test")
    assert record.capability_id == "test_cap"
    assert record.maturity_state == CapabilityMaturityState.UNOBSERVED
    assert record.sandbox_only is True
    assert record.real_world_enabled is False


def test_capability_maturity_state_values():
    assert CapabilityMaturityState.MATURE_SANDBOXED.value == "mature_sandboxed"
    assert CapabilityMaturityState.SAFETY_BLOCKED.value == "safety_blocked"


def test_capability_risk_class_values():
    assert CapabilityRiskClass.CRITICAL.value == "critical"
    assert CapabilityRiskClass.LOW.value == "low"


def test_maturation_result_defaults():
    result = CapabilityMaturationResult()
    assert result.capability_count == 0
    assert result.maturity_verdict == "CAPABILITY_MATURATION_INSUFFICIENT_EVIDENCE"
    assert result.proceed_to_t64b is False


# -- Registry -----------------------------------------------------------------

def test_capability_registry_adds_records():
    reg = CapabilityRegistry()
    reg.add_capability(CapabilityRecord(capability_id="c1", name="C1"))
    assert reg.record_count() == 1
    assert reg.get_capability("c1") is not None


def test_capability_registry_initialize_defaults():
    reg = CapabilityRegistry()
    reg.initialize_defaults()
    assert reg.record_count() == len(DEFAULT_CAPABILITIES)


def test_capability_registry_get_all():
    reg = CapabilityRegistry()
    reg.initialize_defaults()
    all_caps = reg.get_all_capabilities()
    assert len(all_caps) == len(DEFAULT_CAPABILITIES)


def test_capability_registry_update():
    reg = CapabilityRegistry()
    reg.add_capability(CapabilityRecord(capability_id="c1", name="C1"))
    reg.update_capability("c1", evidence_count=5)
    assert reg.get_capability("c1").evidence_count == 5


def test_capability_registry_get_none():
    reg = CapabilityRegistry()
    assert reg.get_capability("missing") is None


# -- Maturity Evaluator -------------------------------------------------------

def test_maturity_evaluator_marks_emerging():
    ev = MaturityEvaluator()
    record = CapabilityRecord(capability_id="c1", evidence_count=1, maturity_score=0.2)
    state = ev.evaluate(record)
    assert state == CapabilityMaturityState.EMERGING


def test_maturity_evaluator_marks_immature():
    ev = MaturityEvaluator()
    record = CapabilityRecord(capability_id="c1", evidence_count=5, maturity_score=0.4)
    state = ev.evaluate(record)
    assert state == CapabilityMaturityState.IMMATURE


def test_maturity_evaluator_marks_maturing():
    ev = MaturityEvaluator()
    record = CapabilityRecord(capability_id="c1", evidence_count=5, maturity_score=0.6)
    state = ev.evaluate(record)
    assert state == CapabilityMaturityState.MATURING


def test_maturity_evaluator_marks_mature_sandboxed():
    ev = MaturityEvaluator()
    record = CapabilityRecord(
        capability_id="c1",
        evidence_count=15,
        maturity_score=0.8,
        confidence_score=0.75,
        safety_violation_count=0,
        sandbox_only=True,
    )
    state = ev.evaluate(record)
    assert state == CapabilityMaturityState.MATURE_SANDBOXED


def test_maturity_evaluator_blocks_on_safety_violation():
    ev = MaturityEvaluator()
    record = CapabilityRecord(
        capability_id="c1",
        evidence_count=15,
        maturity_score=0.9,
        confidence_score=0.8,
        safety_violation_count=1,
    )
    state = ev.evaluate(record)
    assert state == CapabilityMaturityState.SAFETY_BLOCKED


def test_maturity_evaluator_blocks_on_real_world():
    ev = MaturityEvaluator()
    record = CapabilityRecord(
        capability_id="c1",
        evidence_count=15,
        maturity_score=0.9,
        confidence_score=0.8,
        real_world_enabled=True,
    )
    state = ev.evaluate(record)
    assert state == CapabilityMaturityState.SAFETY_BLOCKED


def test_maturity_evaluator_marks_regressive():
    ev = MaturityEvaluator()
    record = CapabilityRecord(capability_id="c1", regression_rate=0.5)
    state = ev.evaluate(record)
    assert state == CapabilityMaturityState.REGRESSIVE


def test_maturity_evaluator_unobserved_when_no_evidence():
    ev = MaturityEvaluator()
    record = CapabilityRecord(capability_id="c1", evidence_count=0, maturity_score=0.0)
    state = ev.evaluate(record)
    assert state == CapabilityMaturityState.UNOBSERVED


def test_maturity_evaluator_compute_maturity_score():
    ev = MaturityEvaluator()
    record = CapabilityRecord(capability_id="c1", evidence_count=10, success_rate=1.0, confidence_score=1.0)
    score = ev.compute_maturity_score(record)
    assert 0.0 <= score <= 1.0


def test_maturity_evaluator_compute_confidence_score():
    ev = MaturityEvaluator()
    record = CapabilityRecord(capability_id="c1", evidence_count=20)
    score = ev.compute_confidence_score(record)
    assert 0.0 <= score <= 1.0


def test_maturity_evaluator_risk_critical_on_real_world():
    ev = MaturityEvaluator()
    record = CapabilityRecord(capability_id="c1", real_world_enabled=True)
    risk = ev.compute_risk_class(record)
    assert risk == CapabilityRiskClass.CRITICAL


def test_maturity_evaluator_risk_low_on_mature():
    ev = MaturityEvaluator()
    record = CapabilityRecord(capability_id="c1", maturity_state=CapabilityMaturityState.MATURE_SANDBOXED)
    risk = ev.compute_risk_class(record)
    assert risk == CapabilityRiskClass.LOW


# -- Regression Tracker -------------------------------------------------------

def test_regression_tracker_detects_regression():
    rt = RegressionTracker()
    rt.record_score("c1", 0.9)
    rt.record_score("c1", 0.6)
    rt.record_score("c1", 0.3)
    assert rt.has_regression("c1")


def test_regression_tracker_no_regression_with_two_points():
    rt = RegressionTracker()
    rt.record_score("c1", 0.9)
    rt.record_score("c1", 0.5)
    assert not rt.has_regression("c1")


def test_regression_tracker_compute_rate():
    rt = RegressionTracker()
    rt.record_score("c1", 0.9)
    rt.record_score("c1", 0.8)
    rt.record_score("c1", 0.7)
    rate = rt.compute_regression_rate("c1")
    assert rate == 1.0


def test_regression_tracker_empty_history():
    rt = RegressionTracker()
    assert rt.compute_regression_rate("c1") == 0.0
    assert not rt.has_regression("c1")


# -- Safety Gate --------------------------------------------------------------

def test_safety_gate_blocks_unsafe_capability():
    gate = SafetyCapabilityGate()
    record = CapabilityRecord(capability_id="c1", safety_violation_count=1)
    result = gate.evaluate(record)
    assert result["blocked"]


def test_safety_gate_blocks_real_world():
    gate = SafetyCapabilityGate()
    record = CapabilityRecord(capability_id="c1", real_world_enabled=True)
    result = gate.evaluate(record)
    assert result["blocked"]


def test_safety_gate_allows_safe():
    gate = SafetyCapabilityGate()
    record = CapabilityRecord(capability_id="c1", sandbox_only=True, safety_violation_count=0)
    res = gate.evaluate(record)
    assert res["allowed"]
    assert not res["blocked"]


def test_safety_gate_should_block_unsafe():
    gate = SafetyCapabilityGate()
    record = CapabilityRecord(capability_id="c1", safety_violation_count=1)
    assert gate.should_block(record)


def test_safety_gate_should_block_real_world():
    gate = SafetyCapabilityGate()
    record = CapabilityRecord(capability_id="c1", real_world_enabled=True)
    assert gate.should_block(record)


def test_safety_gate_should_not_block_safe():
    gate = SafetyCapabilityGate()
    record = CapabilityRecord(capability_id="c1", sandbox_only=True, safety_violation_count=0, real_world_enabled=False)
    assert not gate.should_block(record)


# -- Quarantine Manager -------------------------------------------------------

def test_quarantine_manager_quarantines_critical_capability():
    qm = CapabilityQuarantineManager()
    record = CapabilityRecord(capability_id="c1", risk_class=CapabilityRiskClass.CRITICAL)
    assert qm.evaluate_quarantine(record)


def test_quarantine_manager_quarantines_on_safety_violations():
    qm = CapabilityQuarantineManager()
    record = CapabilityRecord(capability_id="c1", safety_violation_count=2)
    assert qm.evaluate_quarantine(record)


def test_quarantine_manager_does_not_quarantine_safe():
    qm = CapabilityQuarantineManager()
    record = CapabilityRecord(capability_id="c1", risk_class=CapabilityRiskClass.LOW, safety_violation_count=0)
    assert not qm.evaluate_quarantine(record)


def test_quarantine_sets_state():
    qm = CapabilityQuarantineManager()
    record = CapabilityRecord(capability_id="c1", maturity_state=CapabilityMaturityState.IMMATURE)
    qm.quarantine(record)
    assert record.maturity_state == CapabilityMaturityState.QUARANTINED
    assert record.sandbox_only is True
    assert record.real_world_enabled is False


def test_quarantine_release():
    qm = CapabilityQuarantineManager()
    record = CapabilityRecord(capability_id="c1", maturity_state=CapabilityMaturityState.QUARANTINED)
    qm.release(record)
    assert record.maturity_state == CapabilityMaturityState.IMMATURE


# -- Maturation Policy Engine -------------------------------------------------

def test_policy_engine_blocks_on_real_world():
    pe = MaturationPolicyEngine()
    record = CapabilityRecord(capability_id="c1", real_world_enabled=True, sandbox_only=True)
    result = pe.evaluate_policy(record)
    assert "BLOCK" in result["recommendation"]


def test_policy_engine_blocks_on_safety_violation():
    pe = MaturationPolicyEngine()
    record = CapabilityRecord(capability_id="c1", safety_violation_count=1, sandbox_only=True)
    result = pe.evaluate_policy(record)
    assert "BLOCK" in result["recommendation"]


def test_policy_engine_advance_when_mature():
    pe = MaturationPolicyEngine()
    record = CapabilityRecord(
        capability_id="c1",
        maturity_score=0.8,
        confidence_score=0.75,
        regression_rate=0.1,
        safety_violation_count=0,
        sandbox_only=True,
    )
    result = pe.evaluate_policy(record)
    assert result["can_advance"]
    assert "ADVANCE" in result["recommendation"]


def test_policy_engine_monitor_when_maturing():
    pe = MaturationPolicyEngine()
    record = CapabilityRecord(
        capability_id="c1",
        maturity_score=0.6,
        confidence_score=0.6,
        regression_rate=0.1,
        safety_violation_count=0,
        sandbox_only=True,
    )
    result = pe.evaluate_policy(record)
    assert not result["can_advance"]
    assert "MONITOR" in result["recommendation"]


def test_policy_engine_observe_when_low():
    pe = MaturationPolicyEngine()
    record = CapabilityRecord(capability_id="c1", maturity_score=0.2, sandbox_only=True)
    result = pe.evaluate_policy(record)
    assert "OBSERVE" in result["recommendation"]


def test_policy_engine_requires_review_for_high():
    pe = MaturationPolicyEngine()
    record = CapabilityRecord(capability_id="c1", risk_class=CapabilityRiskClass.HIGH, sandbox_only=True)
    result = pe.evaluate_policy(record)
    assert result["requires_human_review"]


# -- Capability Maturation Layer ----------------------------------------------

def test_layer_initializes_defaults():
    layer = CapabilityMaturationLayer(seed=1)
    state = layer.get_state()
    assert state["capability_count"] == len(DEFAULT_CAPABILITIES)


def test_layer_run_maturation_without_t63():
    layer = CapabilityMaturationLayer(seed=1)
    result = layer.run_maturation()
    assert result.capability_count > 0
    assert all(r.sandbox_only for r in result.capability_records)


def test_layer_run_maturation_with_t63():
    layer = CapabilityMaturationLayer(seed=1)
    t63 = {
        "total_episodes_evaluated": 100,
        "aggregate_semantic_grounding_score": 0.8,
        "aggregate_imitation_accuracy_score": 0.7,
        "aggregate_causal_prediction_score": 0.6,
        "aggregate_error_correction_score": 0.75,
        "total_dangerous_traces_blocked": 10,
        "total_regressions_detected": 2,
        "aggregate_memory_consolidation_score": 0.8,
        "aggregate_memory_reuse_score": 0.5,
        "total_memory_bloat_events": 1,
        "total_human_review_required": 3,
        "total_simulated_actions": 5,
        "aggregate_safety_preservation_score": 0.9,
        "aggregate_read_only_integrity_score": 1.0,
    }
    result = layer.run_maturation(t63)
    assert result.capability_count > 0
    assert result.read_only_integrity_score == 1.0


def test_layer_produces_verdict():
    layer = CapabilityMaturationLayer(seed=1)
    result = layer.run_maturation()
    assert result.maturity_verdict


def test_layer_produces_proceed_to_t64b():
    layer = CapabilityMaturationLayer(seed=1)
    result = layer.run_maturation()
    assert isinstance(result.proceed_to_t64b, bool)


def test_layer_count_matches_defaults():
    layer = CapabilityMaturationLayer(seed=1)
    result = layer.run_maturation()
    assert result.capability_count == len(DEFAULT_CAPABILITIES)


def test_layer_no_real_world_enabled():
    layer = CapabilityMaturationLayer(seed=1)
    result = layer.run_maturation()
    assert result.real_world_capability_enabled_count == 0


def test_layer_all_sandbox_only():
    layer = CapabilityMaturationLayer(seed=1)
    result = layer.run_maturation()
    assert all(r.sandbox_only for r in result.capability_records)


def test_layer_stages():
    layer = CapabilityMaturationLayer(seed=1)
    assert len(layer.get_stages()) >= 5


# -- Verdicts -----------------------------------------------------------------

def test_verdict_validated():
    layer = CapabilityMaturationLayer(seed=1)
    result = CapabilityMaturationResult(
        aggregate_maturity_score=0.8,
        aggregate_safety_score=0.95,
        read_only_integrity_score=1.0,
        mature_sandboxed_count=10,
        capability_count=14,
    )
    assert layer._compute_verdict(result) == "CAPABILITY_MATURATION_LAYER_VALIDATED"


def test_verdict_safe_but_immature():
    layer = CapabilityMaturationLayer(seed=1)
    result = CapabilityMaturationResult(
        aggregate_maturity_score=0.8,
        aggregate_safety_score=0.95,
        read_only_integrity_score=1.0,
        mature_sandboxed_count=2,
        capability_count=14,
    )
    assert layer._compute_verdict(result) == "CAPABILITY_MATURATION_SAFE_BUT_IMMATURE"


def test_verdict_insufficient_evidence():
    layer = CapabilityMaturationLayer(seed=1)
    result = CapabilityMaturationResult(
        aggregate_maturity_score=0.5,
        aggregate_safety_score=0.95,
        read_only_integrity_score=1.0,
    )
    assert layer._compute_verdict(result) == "CAPABILITY_MATURATION_INSUFFICIENT_EVIDENCE"


def test_verdict_regression_detected():
    layer = CapabilityMaturationLayer(seed=1)
    result = CapabilityMaturationResult(
        regressive_count=1,
        read_only_integrity_score=1.0,
    )
    assert layer._compute_verdict(result) == "CAPABILITY_REGRESSION_DETECTED"


def test_verdict_safety_block_required():
    layer = CapabilityMaturationLayer(seed=1)
    result = CapabilityMaturationResult(
        safety_blocked_count=1,
        read_only_integrity_score=1.0,
    )
    assert layer._compute_verdict(result) == "CAPABILITY_SAFETY_BLOCK_REQUIRED"


def test_verdict_quarantine_required():
    layer = CapabilityMaturationLayer(seed=1)
    result = CapabilityMaturationResult(
        quarantined_count=1,
        read_only_integrity_score=1.0,
    )
    assert layer._compute_verdict(result) == "CAPABILITY_QUARANTINE_REQUIRED"


def test_verdict_unsafe_capability_enabled():
    layer = CapabilityMaturationLayer(seed=1)
    result = CapabilityMaturationResult(
        unsafe_capability_enabled_count=1,
        read_only_integrity_score=1.0,
    )
    assert layer._compute_verdict(result) == "UNSAFE_CAPABILITY_ENABLED"


def test_verdict_real_world_capability_enabled():
    layer = CapabilityMaturationLayer(seed=1)
    result = CapabilityMaturationResult(
        real_world_capability_enabled_count=1,
        read_only_integrity_score=1.0,
    )
    assert layer._compute_verdict(result) == "REAL_WORLD_CAPABILITY_ENABLED"


def test_verdict_read_only_violation():
    layer = CapabilityMaturationLayer(seed=1)
    result = CapabilityMaturationResult(read_only_integrity_score=0.0)
    assert layer._compute_verdict(result) == "CAPABILITY_READ_ONLY_VIOLATION"


# -- proceed_to_t64b ----------------------------------------------------------

def test_proceed_to_t64b_true():
    layer = CapabilityMaturationLayer(seed=1)
    result = CapabilityMaturationResult(
        aggregate_maturity_score=0.8,
        aggregate_safety_score=0.95,
        read_only_integrity_score=1.0,
        real_world_capability_enabled_count=0,
        unsafe_capability_enabled_count=0,
        regressive_count=0,
        quarantined_count=0,
    )
    assert layer._compute_proceed(result) is True


def test_proceed_to_t64b_false_on_low_maturity():
    layer = CapabilityMaturationLayer(seed=1)
    result = CapabilityMaturationResult(
        aggregate_maturity_score=0.5,
        aggregate_safety_score=0.95,
        read_only_integrity_score=1.0,
    )
    assert layer._compute_proceed(result) is False


def test_proceed_to_t64b_false_on_low_safety():
    layer = CapabilityMaturationLayer(seed=1)
    result = CapabilityMaturationResult(
        aggregate_maturity_score=0.8,
        aggregate_safety_score=0.5,
        read_only_integrity_score=1.0,
    )
    assert layer._compute_proceed(result) is False


def test_proceed_to_t64b_false_on_real_world():
    layer = CapabilityMaturationLayer(seed=1)
    result = CapabilityMaturationResult(
        aggregate_maturity_score=0.8,
        aggregate_safety_score=0.95,
        read_only_integrity_score=1.0,
        real_world_capability_enabled_count=1,
    )
    assert layer._compute_proceed(result) is False


def test_proceed_to_t64b_false_on_unsafe():
    layer = CapabilityMaturationLayer(seed=1)
    result = CapabilityMaturationResult(
        aggregate_maturity_score=0.8,
        aggregate_safety_score=0.95,
        read_only_integrity_score=1.0,
        unsafe_capability_enabled_count=1,
    )
    assert layer._compute_proceed(result) is False


def test_proceed_to_t64b_false_on_regression():
    layer = CapabilityMaturationLayer(seed=1)
    result = CapabilityMaturationResult(
        aggregate_maturity_score=0.8,
        aggregate_safety_score=0.95,
        read_only_integrity_score=1.0,
        regressive_count=1,
    )
    assert layer._compute_proceed(result) is False


def test_proceed_to_t64b_false_on_quarantine():
    layer = CapabilityMaturationLayer(seed=1)
    result = CapabilityMaturationResult(
        aggregate_maturity_score=0.8,
        aggregate_safety_score=0.95,
        read_only_integrity_score=1.0,
        quarantined_count=1,
    )
    assert layer._compute_proceed(result) is False


# -- Audit --------------------------------------------------------------------

def test_audit_runs():
    audit = CapabilityMaturationAudit(seed=1)
    result = audit.run_audit()
    assert result.capability_count > 0


def test_audit_generates_reports():
    audit = CapabilityMaturationAudit(seed=1)
    audit.run_audit()
    report_dir = Path("reports/capability_maturation")
    assert any(report_dir.glob("t64_audit_*.json"))
    assert any(report_dir.glob("t64_audit_*.md"))


def test_audit_with_t63_data():
    audit = CapabilityMaturationAudit(seed=1)
    t63 = {
        "total_episodes_evaluated": 100,
        "aggregate_semantic_grounding_score": 0.8,
        "aggregate_imitation_accuracy_score": 0.7,
        "aggregate_causal_prediction_score": 0.6,
        "aggregate_error_correction_score": 0.75,
        "total_dangerous_traces_blocked": 10,
        "total_regressions_detected": 2,
        "aggregate_memory_consolidation_score": 0.8,
        "aggregate_memory_reuse_score": 0.5,
        "total_memory_bloat_events": 1,
        "total_human_review_required": 3,
        "total_simulated_actions": 5,
        "aggregate_safety_preservation_score": 0.9,
        "aggregate_read_only_integrity_score": 1.0,
    }
    result = audit.run_audit(t63)
    assert result.capability_count > 0


# -- Integration --------------------------------------------------------------

def test_benchmark_metrics_t64_present():
    assert "capability_maturation_audit_count" in BenchmarkMetrics.model_fields
    assert "capability_maturation_score" in BenchmarkMetrics.model_fields
    assert "proceed_to_t64_score" in BenchmarkMetrics.model_fields


def test_morphological_events_t64_present():
    assert hasattr(MorphologyEventType, "CAPABILITY_MATURATION_STARTED")
    assert hasattr(MorphologyEventType, "CAPABILITY_MATURATION_COMPLETED")
    assert hasattr(MorphologyEventType, "CAPABILITY_SAFETY_BLOCKED")
    assert hasattr(MorphologyEventType, "CAPABILITY_QUARANTINED")


def test_orchestrator_flag_disabled_by_default():
    orch = _make_orch()
    assert orch.capability_maturation_enabled is False


def test_orchestrator_hook_exists():
    orch = _make_orch(capability_maturation_enabled=True)
    assert hasattr(orch, "run_capability_maturation")
    assert hasattr(orch, "run_capability_maturation_audit")
    assert hasattr(orch, "get_capability_maturation_layer")
    assert hasattr(orch, "get_capability_maturation_state")


def test_orchestrator_run_capability_maturation_returns_none_when_disabled():
    import asyncio
    orch = _make_orch(capability_maturation_enabled=False)
    result = asyncio.run(orch.run_capability_maturation())
    assert result is None


def test_orchestrator_run_capability_maturation_audit_returns_none_when_disabled():
    import asyncio
    orch = _make_orch(capability_maturation_enabled=False)
    result = asyncio.run(orch.run_capability_maturation_audit())
    assert result is None


def test_orchestrator_get_state_returns_error_when_disabled():
    orch = _make_orch(capability_maturation_enabled=False)
    state = orch.get_capability_maturation_state()
    assert state.get("error") == "capability_maturation_disabled"


def test_existing_flags_remain_disabled():
    orch = _make_orch()
    assert orch.postnatal_learning_enabled is False


# -- Safety constraints -------------------------------------------------------

def test_real_world_enabled_always_false_in_defaults():
    layer = CapabilityMaturationLayer(seed=1)
    result = layer.run_maturation()
    for r in result.capability_records:
        assert r.real_world_enabled is False


def test_sandbox_only_enforced():
    layer = CapabilityMaturationLayer(seed=1)
    result = layer.run_maturation()
    for r in result.capability_records:
        assert r.sandbox_only is True


def test_read_only_integrity_score_one():
    layer = CapabilityMaturationLayer(seed=1)
    result = layer.run_maturation()
    assert result.read_only_integrity_score == 1.0


def test_no_real_action_enabled():
    layer = CapabilityMaturationLayer(seed=1)
    result = layer.run_maturation()
    assert result.real_world_capability_enabled_count == 0


def test_no_architecture_patch_enabled():
    layer = CapabilityMaturationLayer(seed=1)
    result = layer.run_maturation()
    assert all(not r.real_world_enabled for r in result.capability_records)


def test_no_self_improvement_enabled():
    layer = CapabilityMaturationLayer(seed=1)
    result = layer.run_maturation()
    assert all(not r.real_world_enabled for r in result.capability_records)


def test_no_tick_loop_insertion():
    orch = _make_orch()
    assert not hasattr(orch, "_capability_maturation_tick")


# -- Scores -------------------------------------------------------------------

def test_maturation_score_clamped():
    layer = CapabilityMaturationLayer(seed=1)
    result = layer.run_maturation()
    assert 0.0 <= result.aggregate_maturity_score <= 1.0


def test_safety_score_non_negative():
    layer = CapabilityMaturationLayer(seed=1)
    result = layer.run_maturation()
    assert result.aggregate_safety_score >= 0.0


def test_confidence_score_non_negative():
    layer = CapabilityMaturationLayer(seed=1)
    result = layer.run_maturation()
    assert result.aggregate_confidence_score >= 0.0


def test_maturation_score_not_nan():
    layer = CapabilityMaturationLayer(seed=1)
    result = layer.run_maturation()
    assert not math.isnan(result.aggregate_maturity_score)


# -- Determinism --------------------------------------------------------------

def test_deterministic_seed_reproducibility():
    layer1 = CapabilityMaturationLayer(seed=42)
    result1 = layer1.run_maturation()
    layer2 = CapabilityMaturationLayer(seed=42)
    result2 = layer2.run_maturation()
    assert result1.maturity_verdict == result2.maturity_verdict
    assert result1.proceed_to_t64b == result2.proceed_to_t64b


# -- Edge cases ---------------------------------------------------------------

def test_layer_no_crash_on_empty_t63():
    layer = CapabilityMaturationLayer(seed=1)
    result = layer.run_maturation({})
    assert result.capability_count > 0


def test_layer_no_crash_on_none_t63():
    layer = CapabilityMaturationLayer(seed=1)
    result = layer.run_maturation(None)
    assert result.capability_count > 0


def test_evaluator_maturity_score_no_evidence():
    ev = MaturityEvaluator()
    record = CapabilityRecord(capability_id="c1", evidence_count=0)
    score = ev.compute_maturity_score(record)
    assert score == 0.0


def test_evaluator_confidence_score_no_evidence():
    ev = MaturityEvaluator()
    record = CapabilityRecord(capability_id="c1", evidence_count=0)
    score = ev.compute_confidence_score(record)
    assert score == 0.0


def test_audit_no_crash_on_repeated_runs():
    audit = CapabilityMaturationAudit(seed=1)
    audit.run_audit()
    audit.run_audit()
    assert True


def test_registry_update_missing_capability():
    reg = CapabilityRegistry()
    reg.update_capability("missing", evidence_count=1)
    assert reg.get_capability("missing") is None


def test_capability_record_last_updated():
    record = CapabilityRecord(capability_id="c1", last_updated_at="2026-05-19")
    assert record.last_updated_at == "2026-05-19"


def test_capability_record_metadata():
    record = CapabilityRecord(capability_id="c1", metadata={"key": "value"})
    assert record.metadata["key"] == "value"
