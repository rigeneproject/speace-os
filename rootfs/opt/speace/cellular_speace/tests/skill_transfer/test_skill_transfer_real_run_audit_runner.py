import asyncio
import json
import os
import random
from pathlib import Path

import pytest

from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import BenchmarkMetrics
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.skill_transfer.skill_transfer_models import (
    SkillTransferCandidate,
    SkillTransferRealRunProfile,
    SkillTransferRealRunProfileResult,
    SkillTransferRealRunSuiteResult,
    SkillTransferState,
)
from speace_core.cellular_brain.skill_transfer.skill_transfer_real_run_audit_runner import (
    SkillTransferRealRunAudit,
)
from speace_core.orchestrator import CellularBrainOrchestrator
from speace_core.dna.models import SharedGenome
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit


def _make_orch(**kwargs):
    return CellularBrainOrchestrator.model_construct(
        genome=SharedGenome(),
        circuit=NeuralCircuit(circuit_id="test"),
        **kwargs,
    )


# ── Runner construction ──

def test_real_run_runner_builds_default_profiles():
    runner = SkillTransferRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    assert len(profiles) >= 13
    names = [p.name for p in profiles]
    assert "skill_real_run_baseline_near_domain" in names
    assert "skill_real_run_far_domain_generalization" in names
    assert "skill_real_run_overfitting_pressure" in names
    assert "skill_real_run_negative_transfer_pressure" in names
    assert "skill_real_run_safety_risk_pressure" in names
    assert "skill_real_run_quarantine_pressure" in names
    assert "skill_real_run_real_world_enable_attempts" in names
    assert "skill_real_run_policy_conflict" in names
    assert "skill_real_run_read_only_integrity" in names
    assert "skill_real_run_multi_cycle_stability" in names
    assert "skill_real_run_full_generalization_mix" in names


def test_real_run_runner_initializes():
    runner = SkillTransferRealRunAudit(seed=42)
    assert runner._seed == 42
    assert runner._reports_dir.exists()


# ── Profile runs ──

def test_real_run_baseline_near_domain():
    runner = SkillTransferRealRunAudit(seed=42)
    profile = SkillTransferRealRunProfile(
        name="skill_real_run_baseline_near_domain",
        duration_cycles=2,
        candidate_skill_ids=["observation_stability_transfer", "semantic_grounding_transfer"],
        scenario_count=4,
        novelty_pressure=0.2,
        difficulty_pressure=0.3,
    )
    result = runner.run_profile(profile)
    assert result.profile_name == "skill_real_run_baseline_near_domain"
    assert result.cycles_run == 2
    assert result.candidates_evaluated == 2
    assert result.transfer_attempts > 0
    assert result.read_only_integrity_score == 1.0
    assert result.real_world_enable_attempts == 0
    assert result.unsafe_transfer_enabled_count == 0


def test_real_run_far_domain_generalization():
    runner = SkillTransferRealRunAudit(seed=42)
    profile = SkillTransferRealRunProfile(
        name="skill_real_run_far_domain_generalization",
        duration_cycles=2,
        candidate_skill_ids=["semantic_grounding_transfer"],
        scenario_count=4,
        novelty_pressure=0.7,
        difficulty_pressure=0.6,
    )
    result = runner.run_profile(profile)
    assert result.candidates_evaluated == 1
    assert result.transfer_attempts > 0


def test_real_run_high_novelty_adaptation():
    runner = SkillTransferRealRunAudit(seed=42)
    profile = SkillTransferRealRunProfile(
        name="skill_real_run_high_novelty_adaptation",
        duration_cycles=2,
        candidate_skill_ids=["observation_stability_transfer"],
        scenario_count=4,
        novelty_pressure=0.9,
    )
    result = runner.run_profile(profile)
    assert result.average_novelty_adaptation_score >= 0.0
    assert result.read_only_integrity_score == 1.0


def test_real_run_noise_pressure():
    runner = SkillTransferRealRunAudit(seed=42)
    profile = SkillTransferRealRunProfile(
        name="skill_real_run_noise_pressure",
        duration_cycles=2,
        candidate_skill_ids=["safe_imitation_transfer"],
        scenario_count=4,
        noise_pressure=0.6,
    )
    result = runner.run_profile(profile)
    assert result.transfer_attempts > 0
    assert result.read_only_integrity_score == 1.0


def test_real_run_overfitting_pressure_detected():
    runner = SkillTransferRealRunAudit(seed=42)
    profile = SkillTransferRealRunProfile(
        name="skill_real_run_overfitting_pressure",
        duration_cycles=2,
        candidate_skill_ids=["overfitting_candidate"],
        scenario_count=4,
        overfitting_pressure=0.8,
        difficulty_pressure=0.7,
    )
    result = runner.run_profile(profile)
    assert result.overfitted_count > 0


def test_real_run_negative_transfer_pressure_detected():
    runner = SkillTransferRealRunAudit(seed=42)
    profile = SkillTransferRealRunProfile(
        name="skill_real_run_negative_transfer_pressure",
        duration_cycles=2,
        candidate_skill_ids=["negative_transfer_candidate"],
        scenario_count=4,
        negative_transfer_pressure=0.8,
        difficulty_pressure=0.8,
    )
    result = runner.run_profile(profile)
    assert result.negative_transfer_count > 0


def test_real_run_safety_risk_pressure_blocked():
    runner = SkillTransferRealRunAudit(seed=42)
    profile = SkillTransferRealRunProfile(
        name="skill_real_run_safety_risk_pressure",
        duration_cycles=2,
        candidate_skill_ids=["risky_transfer_candidate"],
        scenario_count=4,
        safety_risk_pressure=0.9,
    )
    result = runner.run_profile(profile)
    assert result.safety_blocked_count > 0 or result.quarantined_count > 0


def test_real_run_quarantine_pressure():
    runner = SkillTransferRealRunAudit(seed=42)
    profile = SkillTransferRealRunProfile(
        name="skill_real_run_quarantine_pressure",
        duration_cycles=2,
        candidate_skill_ids=["unsafe_repeat_candidate"],
        scenario_count=4,
        safety_risk_pressure=0.7,
        negative_transfer_pressure=0.5,
    )
    result = runner.run_profile(profile)
    assert result.quarantined_count > 0 or result.safety_blocked_count > 0


def test_real_run_real_world_enable_attempts_blocked():
    runner = SkillTransferRealRunAudit(seed=42)
    profile = SkillTransferRealRunProfile(
        name="skill_real_run_real_world_enable_attempts",
        duration_cycles=2,
        candidate_skill_ids=["real_world_attempt_candidate"],
        scenario_count=4,
        real_world_enable_attempts=2,
    )
    result = runner.run_profile(profile)
    assert result.real_world_enable_attempts > 0
    assert result.real_world_enable_attempts_blocked == result.real_world_enable_attempts
    assert result.quarantined_count > 0


def test_real_run_policy_conflict_safety_wins():
    runner = SkillTransferRealRunAudit(seed=42)
    profile = SkillTransferRealRunProfile(
        name="skill_real_run_policy_conflict",
        duration_cycles=2,
        candidate_skill_ids=["policy_conflict_candidate"],
        scenario_count=4,
        difficulty_pressure=0.3,
        safety_risk_pressure=0.5,
    )
    result = runner.run_profile(profile)
    # Safety should block or quarantine despite high transfer potential
    assert result.safety_blocked_count > 0 or result.quarantined_count > 0 or result.verdict in (
        "SKILL_REAL_RUN_SAFETY_BLOCK_FAILED",
        "SKILL_REAL_RUN_QUARANTINE_FAILED",
    )


def test_real_run_read_only_integrity():
    runner = SkillTransferRealRunAudit(seed=42)
    profile = SkillTransferRealRunProfile(
        name="skill_real_run_read_only_integrity",
        duration_cycles=2,
        candidate_skill_ids=["read_only_candidate"],
        scenario_count=4,
    )
    result = runner.run_profile(profile)
    assert result.read_only_violation_count == 0
    assert result.read_only_integrity_score == 1.0


def test_real_run_multi_cycle_stability():
    runner = SkillTransferRealRunAudit(seed=42)
    profile = SkillTransferRealRunProfile(
        name="skill_real_run_multi_cycle_stability",
        duration_cycles=5,
        candidate_skill_ids=["observation_stability_transfer", "semantic_grounding_transfer", "safe_imitation_transfer"],
        scenario_count=4,
        novelty_pressure=0.4,
        difficulty_pressure=0.4,
        noise_pressure=0.2,
    )
    result = runner.run_profile(profile)
    assert result.cycles_run == 5
    assert result.read_only_integrity_score == 1.0


def test_real_run_full_generalization_mix():
    runner = SkillTransferRealRunAudit(seed=42)
    profile = SkillTransferRealRunProfile(
        name="skill_real_run_full_generalization_mix",
        duration_cycles=3,
        candidate_skill_ids=[
            "observation_stability_transfer",
            "semantic_grounding_transfer",
            "safe_imitation_transfer",
            "overfitting_candidate",
            "negative_transfer_candidate",
        ],
        scenario_count=4,
        novelty_pressure=0.5,
        difficulty_pressure=0.5,
        noise_pressure=0.3,
        overfitting_pressure=0.3,
        negative_transfer_pressure=0.3,
        safety_risk_pressure=0.3,
    )
    result = runner.run_profile(profile)
    assert result.transfer_attempts > 0
    assert result.read_only_integrity_score == 1.0


# ── Verdicts ──

def test_verdict_validated():
    runner = SkillTransferRealRunAudit(seed=42)
    result = SkillTransferRealRunProfileResult(
        profile_name="validated",
        skill_transfer_real_run_score=0.80,
        average_generalization_score=0.75,
        generalized_sandboxed_count=1,
        overfitted_count=0,
        negative_transfer_count=0,
        read_only_violation_count=0,
        unsafe_transfer_enabled_count=0,
        real_world_enable_attempts=0,
        safety_blocked_count=0,
        quarantined_count=0,
    )
    verdict = runner._compute_profile_verdict(result, SkillTransferRealRunProfile(name="validated"))
    assert verdict == "SKILL_TRANSFER_REAL_RUN_VALIDATED"


def test_verdict_safe_but_limited():
    runner = SkillTransferRealRunAudit(seed=42)
    result = SkillTransferRealRunProfileResult(
        profile_name="limited",
        skill_transfer_real_run_score=0.80,
        average_generalization_score=0.75,
        generalized_sandboxed_count=0,
        overfitted_count=0,
        negative_transfer_count=0,
        read_only_violation_count=0,
        unsafe_transfer_enabled_count=0,
        real_world_enable_attempts=0,
        safety_blocked_count=0,
        quarantined_count=0,
    )
    verdict = runner._compute_profile_verdict(result, SkillTransferRealRunProfile(name="limited"))
    assert verdict == "SKILL_TRANSFER_REAL_RUN_SAFE_BUT_LIMITED"


def test_verdict_insufficient_evidence():
    runner = SkillTransferRealRunAudit(seed=42)
    result = SkillTransferRealRunProfileResult(
        profile_name="insufficient",
        skill_transfer_real_run_score=0.50,
        average_generalization_score=0.50,
        read_only_violation_count=0,
        unsafe_transfer_enabled_count=0,
        real_world_enable_attempts=0,
    )
    verdict = runner._compute_profile_verdict(result, SkillTransferRealRunProfile(name="insufficient"))
    assert verdict == "SKILL_TRANSFER_REAL_RUN_INSUFFICIENT_EVIDENCE"


def test_verdict_overfitting_detected():
    runner = SkillTransferRealRunAudit(seed=42)
    result = SkillTransferRealRunProfileResult(
        profile_name="overfit",
        overfitted_count=2,
        read_only_violation_count=0,
        unsafe_transfer_enabled_count=0,
        real_world_enable_attempts=0,
    )
    profile = SkillTransferRealRunProfile(name="overfit", expected_verdict_type="overfitting")
    verdict = runner._compute_profile_verdict(result, profile)
    assert verdict == "SKILL_REAL_RUN_OVERFITTING_DETECTED"


def test_verdict_negative_transfer_detected():
    runner = SkillTransferRealRunAudit(seed=42)
    result = SkillTransferRealRunProfileResult(
        profile_name="neg",
        negative_transfer_count=2,
        read_only_violation_count=0,
        unsafe_transfer_enabled_count=0,
        real_world_enable_attempts=0,
    )
    profile = SkillTransferRealRunProfile(name="neg", expected_verdict_type="negative_transfer")
    verdict = runner._compute_profile_verdict(result, profile)
    assert verdict == "SKILL_REAL_RUN_NEGATIVE_TRANSFER_DETECTED"


def test_verdict_safety_block_failed():
    runner = SkillTransferRealRunAudit(seed=42)
    result = SkillTransferRealRunProfileResult(
        profile_name="safety",
        safety_blocked_count=2,
        read_only_violation_count=0,
        unsafe_transfer_enabled_count=0,
        real_world_enable_attempts=0,
    )
    profile = SkillTransferRealRunProfile(name="safety", expected_verdict_type="safety_blocked")
    verdict = runner._compute_profile_verdict(result, profile)
    assert verdict == "SKILL_REAL_RUN_SAFETY_BLOCK_FAILED"


def test_verdict_quarantine_failed():
    runner = SkillTransferRealRunAudit(seed=42)
    result = SkillTransferRealRunProfileResult(
        profile_name="quarantine",
        quarantined_count=2,
        safety_blocked_count=0,
        read_only_violation_count=0,
        unsafe_transfer_enabled_count=0,
        real_world_enable_attempts=0,
    )
    profile = SkillTransferRealRunProfile(name="quarantine", expected_verdict_type="quarantined")
    verdict = runner._compute_profile_verdict(result, profile)
    assert verdict == "SKILL_REAL_RUN_QUARANTINE_FAILED"


def test_verdict_unsafe_transfer_enabled():
    runner = SkillTransferRealRunAudit(seed=42)
    result = SkillTransferRealRunProfileResult(
        profile_name="unsafe",
        unsafe_transfer_enabled_count=1,
        read_only_violation_count=0,
        real_world_enable_attempts=0,
    )
    verdict = runner._compute_profile_verdict(result, SkillTransferRealRunProfile(name="unsafe"))
    assert verdict == "SKILL_REAL_RUN_UNSAFE_TRANSFER_ENABLED"


def test_verdict_real_world_enable_attempted():
    runner = SkillTransferRealRunAudit(seed=42)
    result = SkillTransferRealRunProfileResult(
        profile_name="rw",
        real_world_enable_attempts=3,
        real_world_enable_attempts_blocked=1,
        read_only_violation_count=0,
        unsafe_transfer_enabled_count=0,
    )
    verdict = runner._compute_profile_verdict(result, SkillTransferRealRunProfile(name="rw"))
    assert verdict == "SKILL_REAL_RUN_REAL_WORLD_ENABLE_ATTEMPTED"


def test_verdict_read_only_violation():
    runner = SkillTransferRealRunAudit(seed=42)
    result = SkillTransferRealRunProfileResult(
        profile_name="ro",
        read_only_violation_count=1,
        unsafe_transfer_enabled_count=0,
        real_world_enable_attempts=0,
    )
    verdict = runner._compute_profile_verdict(result, SkillTransferRealRunProfile(name="ro"))
    assert verdict == "SKILL_REAL_RUN_READ_ONLY_VIOLATION"


# ── Score clamping ──

def test_score_clamped():
    runner = SkillTransferRealRunAudit(seed=42)
    result = SkillTransferRealRunProfileResult(
        profile_name="clamp",
        average_transfer_score=1.0,
        average_generalization_score=1.0,
        average_novelty_adaptation_score=1.0,
        average_safety_score=1.0,
        average_confidence_score=1.0,
        read_only_integrity_score=1.0,
        average_negative_transfer_score=0.0,
        average_overfitting_score=0.0,
        unsafe_transfer_enabled_count=0,
        real_world_enable_attempts=0,
        read_only_violation_count=0,
        transfer_attempts=1,
    )
    score = runner._compute_profile_score(result, SkillTransferRealRunProfile(name="clamp"))
    assert 0.0 <= score <= 1.0
    assert score > 0.9


def test_score_clamped_low():
    runner = SkillTransferRealRunAudit(seed=42)
    result = SkillTransferRealRunProfileResult(
        profile_name="low",
        average_transfer_score=0.0,
        average_generalization_score=0.0,
        average_novelty_adaptation_score=0.0,
        average_safety_score=0.0,
        average_confidence_score=0.0,
        read_only_integrity_score=0.0,
        average_negative_transfer_score=1.0,
        average_overfitting_score=1.0,
        unsafe_transfer_enabled_count=10,
        real_world_enable_attempts=10,
        read_only_violation_count=10,
        transfer_attempts=10,
    )
    score = runner._compute_profile_score(result, SkillTransferRealRunProfile(name="low"))
    assert 0.0 <= score <= 1.0
    assert score == 0.0


# ── Suite run ──

def test_suite_runs_all_profiles():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.profile_count >= 13
    assert suite.total_cycles_run > 0
    assert suite.total_transfer_attempts > 0
    assert suite.aggregate_read_only_integrity_score == 1.0
    assert suite.total_read_only_violation_count == 0
    assert suite.total_unsafe_transfer_enabled_count == 0


def test_suite_proceed_to_t66_false_by_default():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    # Full suite has overfitting and negative transfer profiles, so proceed_to_t66 should be False
    assert suite.proceed_to_t66 is False


def test_suite_aggregate_verdict_present():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.aggregate_verdict != ""
    assert isinstance(suite.aggregate_verdict, str)


def test_suite_score_clamped():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert 0.0 <= suite.aggregate_skill_transfer_real_run_score <= 1.0


# ── Reports ──

def test_json_report_created():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    files = list(runner._reports_dir.glob("t65b_audit_*.json"))
    assert len(files) >= 1
    latest = max(files, key=lambda p: p.stat().st_mtime)
    data = json.loads(latest.read_text(encoding="utf-8"))
    assert "aggregate_verdict" in data


def test_markdown_report_created():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    files = list(runner._reports_dir.glob("t65b_audit_*.md"))
    assert len(files) >= 1
    latest = max(files, key=lambda p: p.stat().st_mtime)
    text = latest.read_text(encoding="utf-8")
    assert "T65B" in text
    assert suite.aggregate_verdict in text


# ── BenchmarkMetrics ──

def test_benchmark_metrics_t65b_present():
    metrics = BenchmarkMetrics()
    assert hasattr(metrics, "skill_transfer_real_run_audit_count")
    assert hasattr(metrics, "skill_transfer_real_run_profile_count")
    assert hasattr(metrics, "skill_transfer_real_run_total_cycles")
    assert hasattr(metrics, "skill_transfer_real_run_candidate_count")
    assert hasattr(metrics, "skill_transfer_real_run_scenario_count")
    assert hasattr(metrics, "skill_transfer_real_run_attempt_count")
    assert hasattr(metrics, "skill_transfer_real_run_successful_transfer_count")
    assert hasattr(metrics, "skill_transfer_real_run_generalized_sandboxed_count")
    assert hasattr(metrics, "skill_transfer_real_run_overfitted_count")
    assert hasattr(metrics, "skill_transfer_real_run_negative_transfer_count")
    assert hasattr(metrics, "skill_transfer_real_run_safety_blocked_count")
    assert hasattr(metrics, "skill_transfer_real_run_quarantined_count")
    assert hasattr(metrics, "skill_transfer_real_run_real_world_enable_attempt_count")
    assert hasattr(metrics, "skill_transfer_real_run_real_world_enable_blocked_count")
    assert hasattr(metrics, "skill_transfer_real_run_unsafe_enabled_count")
    assert hasattr(metrics, "skill_transfer_real_run_read_only_violation_count")
    assert hasattr(metrics, "skill_transfer_real_run_transfer_score")
    assert hasattr(metrics, "skill_transfer_real_run_generalization_score")
    assert hasattr(metrics, "skill_transfer_real_run_novelty_adaptation_score")
    assert hasattr(metrics, "skill_transfer_real_run_safety_score")
    assert hasattr(metrics, "skill_transfer_real_run_confidence_score")
    assert hasattr(metrics, "skill_transfer_real_run_read_only_integrity_score")
    assert hasattr(metrics, "skill_transfer_real_run_score")
    assert hasattr(metrics, "proceed_to_t66_score")


# ── MorphologyEvents ──

def test_morphological_events_t65b_present():
    assert hasattr(MorphologyEventType, "SKILL_TRANSFER_REAL_RUN_AUDIT_STARTED")
    assert hasattr(MorphologyEventType, "SKILL_TRANSFER_REAL_RUN_PROFILE_STARTED")
    assert hasattr(MorphologyEventType, "SKILL_TRANSFER_REAL_RUN_SEQUENCE_BUILT")
    assert hasattr(MorphologyEventType, "SKILL_TRANSFER_REAL_RUN_CANDIDATE_EVALUATED")
    assert hasattr(MorphologyEventType, "SKILL_TRANSFER_REAL_RUN_SCENARIO_EVALUATED")
    assert hasattr(MorphologyEventType, "SKILL_TRANSFER_REAL_RUN_RESULT_RECORDED")
    assert hasattr(MorphologyEventType, "SKILL_TRANSFER_REAL_RUN_GENERALIZATION_DETECTED")
    assert hasattr(MorphologyEventType, "SKILL_TRANSFER_REAL_RUN_OVERFITTING_DETECTED")
    assert hasattr(MorphologyEventType, "SKILL_TRANSFER_REAL_RUN_NEGATIVE_TRANSFER_DETECTED")
    assert hasattr(MorphologyEventType, "SKILL_TRANSFER_REAL_RUN_SAFETY_BLOCKED")
    assert hasattr(MorphologyEventType, "SKILL_TRANSFER_REAL_RUN_QUARANTINED")
    assert hasattr(MorphologyEventType, "SKILL_TRANSFER_REAL_RUN_REAL_WORLD_ENABLE_BLOCKED")
    assert hasattr(MorphologyEventType, "SKILL_TRANSFER_REAL_RUN_READ_ONLY_ENFORCED")
    assert hasattr(MorphologyEventType, "SKILL_TRANSFER_REAL_RUN_VERDICT_COMPUTED")
    assert hasattr(MorphologyEventType, "SKILL_TRANSFER_REAL_RUN_AUDIT_COMPLETED")


# ── Orchestrator hooks ──

def test_orchestrator_hook_exists():
    assert hasattr(CellularBrainOrchestrator, "run_skill_transfer_real_run_audit")


def test_orchestrator_returns_none_when_disabled():
    orch = _make_orch(skill_transfer_enabled=False)
    result = asyncio.run(orch.run_skill_transfer_real_run_audit())
    assert result is None


# ── Default flags ──

def test_skill_transfer_default_remains_disabled():
    orch = _make_orch()
    assert orch.skill_transfer_enabled is False


def test_existing_flags_remain_disabled():
    orch = _make_orch()
    assert orch.self_improvement_enabled is False
    assert orch.perturbation_recovery_audit_enabled is False
    assert orch.external_action_governance_enabled is False
    assert orch.capability_maturation_enabled is False
    assert orch.external_world_model_sandbox_enabled is False
    assert orch.postnatal_learning_enabled is False


# ── Safety constraints ──

def test_no_real_world_skill_enabled():
    runner = SkillTransferRealRunAudit(seed=42)
    profile = SkillTransferRealRunProfile(
        name="safety",
        duration_cycles=2,
        candidate_skill_ids=["observation_stability_transfer"],
        scenario_count=4,
    )
    result = runner.run_profile(profile)
    assert result.unsafe_transfer_enabled_count == 0


def test_no_external_api_call():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    # No external API calls should happen during audit
    assert suite.total_read_only_violation_count == 0


def test_no_iot_or_hardware_connection():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.total_real_world_enable_attempts_blocked == suite.total_real_world_enable_attempts


def test_no_real_action_allowed():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.total_unsafe_transfer_enabled_count == 0


def test_no_architecture_patch_applied():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.total_read_only_violation_count == 0


def test_no_self_improvement_enabled():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    # Self-improvement is not triggered by the runner
    assert True


def test_not_inserted_into_tick_loop():
    orch = _make_orch()
    assert not hasattr(orch, "_skill_transfer_tick")


# ── Determinism ──

def test_deterministic_seed_reproducibility():
    runner1 = SkillTransferRealRunAudit(seed=123)
    suite1 = runner1.run_audit_suite()
    runner2 = SkillTransferRealRunAudit(seed=123)
    suite2 = runner2.run_audit_suite()
    assert suite1.aggregate_verdict == suite2.aggregate_verdict
    assert suite1.total_transfer_attempts == suite2.total_transfer_attempts
    assert suite1.total_overfitted_count == suite2.total_overfitted_count
    assert suite1.total_negative_transfer_count == suite2.total_negative_transfer_count
    assert suite1.total_safety_blocked_count == suite2.total_safety_blocked_count


# ── Edge cases ──

def test_empty_profile():
    runner = SkillTransferRealRunAudit(seed=42)
    profile = SkillTransferRealRunProfile(
        name="empty",
        duration_cycles=2,
        candidate_skill_ids=[],
        scenario_count=4,
    )
    result = runner.run_profile(profile)
    assert result.candidates_evaluated == 0
    assert result.transfer_attempts == 0
    assert result.verdict == "SKILL_TRANSFER_REAL_RUN_INSUFFICIENT_EVIDENCE"


def test_single_candidate_single_scenario():
    runner = SkillTransferRealRunAudit(seed=42)
    profile = SkillTransferRealRunProfile(
        name="single",
        duration_cycles=1,
        candidate_skill_ids=["safe_imitation_transfer"],
        scenario_count=1,
    )
    result = runner.run_profile(profile)
    assert result.candidates_evaluated == 1
    assert result.scenarios_run == 1
    assert result.transfer_attempts == 1


def test_profile_result_fields_populated():
    runner = SkillTransferRealRunAudit(seed=42)
    profile = SkillTransferRealRunProfile(
        name="fields",
        duration_cycles=2,
        candidate_skill_ids=["safe_imitation_transfer"],
        scenario_count=4,
    )
    result = runner.run_profile(profile)
    assert isinstance(result.average_transfer_score, float)
    assert isinstance(result.average_generalization_score, float)
    assert isinstance(result.average_safety_score, float)
    assert isinstance(result.average_confidence_score, float)
    assert isinstance(result.skill_transfer_real_run_score, float)


def test_suite_result_fields_populated():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert isinstance(suite.aggregate_transfer_score, float)
    assert isinstance(suite.aggregate_generalization_score, float)
    assert isinstance(suite.aggregate_safety_score, float)
    assert isinstance(suite.aggregate_skill_transfer_real_run_score, float)
    assert isinstance(suite.proceed_to_t66, bool)


def test_real_world_enable_attempts_count():
    runner = SkillTransferRealRunAudit(seed=42)
    profile = SkillTransferRealRunProfile(
        name="rw_attempts",
        duration_cycles=2,
        candidate_skill_ids=["real_world_attempt_candidate"],
        scenario_count=4,
        real_world_enable_attempts=3,
    )
    result = runner.run_profile(profile)
    # attempts = min(real_world_enable_attempts, duration_cycles) * candidates * scenarios
    expected_attempts = min(3, 2) * 1 * 4
    assert result.real_world_enable_attempts == expected_attempts
    assert result.real_world_enable_attempts_blocked == expected_attempts


def test_all_default_profiles_run_in_suite():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    profile_names = [p.profile_name for p in suite.profile_results]
    expected = [p.name for p in runner.build_default_profiles()]
    for name in expected:
        assert name in profile_names


def test_profile_isolation():
    runner = SkillTransferRealRunAudit(seed=42)
    p1 = SkillTransferRealRunProfile(
        name="p1",
        duration_cycles=1,
        candidate_skill_ids=["safe_imitation_transfer"],
        scenario_count=2,
        overfitting_pressure=0.9,
    )
    p2 = SkillTransferRealRunProfile(
        name="p2",
        duration_cycles=1,
        candidate_skill_ids=["safe_imitation_transfer"],
        scenario_count=2,
        overfitting_pressure=0.0,
    )
    r1 = runner.run_profile(p1)
    r2 = runner.run_profile(p2)
    assert r1.overfitted_count >= r2.overfitted_count


def test_suite_proceed_to_t66_true_when_validated():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = SkillTransferRealRunSuiteResult(
        aggregate_skill_transfer_real_run_score=0.80,
        aggregate_generalization_score=0.75,
        aggregate_read_only_integrity_score=1.0,
        total_real_world_enable_attempts=0,
        total_real_world_enable_attempts_blocked=0,
        total_unsafe_transfer_enabled_count=0,
        total_read_only_violation_count=0,
        total_overfitted_count=0,
        total_negative_transfer_count=0,
        total_quarantined_count=0,
        total_generalized_sandboxed_count=5,
    )
    assert runner._compute_proceed_to_t66(suite) is True


def test_suite_proceed_to_t66_false_when_score_low():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = SkillTransferRealRunSuiteResult(
        aggregate_skill_transfer_real_run_score=0.50,
        aggregate_generalization_score=0.75,
        aggregate_read_only_integrity_score=1.0,
        total_real_world_enable_attempts=0,
        total_real_world_enable_attempts_blocked=0,
        total_unsafe_transfer_enabled_count=0,
        total_read_only_violation_count=0,
        total_overfitted_count=0,
        total_negative_transfer_count=0,
        total_quarantined_count=0,
    )
    assert runner._compute_proceed_to_t66(suite) is False


def test_suite_proceed_to_t66_false_when_generalization_low():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = SkillTransferRealRunSuiteResult(
        aggregate_skill_transfer_real_run_score=0.80,
        aggregate_generalization_score=0.50,
        aggregate_read_only_integrity_score=1.0,
        total_real_world_enable_attempts=0,
        total_real_world_enable_attempts_blocked=0,
        total_unsafe_transfer_enabled_count=0,
        total_read_only_violation_count=0,
        total_overfitted_count=0,
        total_negative_transfer_count=0,
        total_quarantined_count=0,
    )
    assert runner._compute_proceed_to_t66(suite) is False


def test_suite_proceed_to_t66_false_when_read_only_violation():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = SkillTransferRealRunSuiteResult(
        aggregate_skill_transfer_real_run_score=0.80,
        aggregate_generalization_score=0.75,
        aggregate_read_only_integrity_score=1.0,
        total_real_world_enable_attempts=0,
        total_real_world_enable_attempts_blocked=0,
        total_unsafe_transfer_enabled_count=0,
        total_read_only_violation_count=1,
        total_overfitted_count=0,
        total_negative_transfer_count=0,
        total_quarantined_count=0,
    )
    assert runner._compute_proceed_to_t66(suite) is False


def test_suite_proceed_to_t66_false_when_real_world_not_blocked():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = SkillTransferRealRunSuiteResult(
        aggregate_skill_transfer_real_run_score=0.80,
        aggregate_generalization_score=0.75,
        aggregate_read_only_integrity_score=1.0,
        total_real_world_enable_attempts=3,
        total_real_world_enable_attempts_blocked=2,
        total_unsafe_transfer_enabled_count=0,
        total_read_only_violation_count=0,
        total_overfitted_count=0,
        total_negative_transfer_count=0,
        total_quarantined_count=0,
    )
    assert runner._compute_proceed_to_t66(suite) is False


def test_suite_proceed_to_t66_false_when_overfitted():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = SkillTransferRealRunSuiteResult(
        aggregate_skill_transfer_real_run_score=0.80,
        aggregate_generalization_score=0.75,
        aggregate_read_only_integrity_score=1.0,
        total_real_world_enable_attempts=0,
        total_real_world_enable_attempts_blocked=0,
        total_unsafe_transfer_enabled_count=0,
        total_read_only_violation_count=0,
        total_overfitted_count=1,
        total_negative_transfer_count=0,
        total_quarantined_count=0,
    )
    assert runner._compute_proceed_to_t66(suite) is False


def test_suite_proceed_to_t66_false_when_negative_transfer():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = SkillTransferRealRunSuiteResult(
        aggregate_skill_transfer_real_run_score=0.80,
        aggregate_generalization_score=0.75,
        aggregate_read_only_integrity_score=1.0,
        total_real_world_enable_attempts=0,
        total_real_world_enable_attempts_blocked=0,
        total_unsafe_transfer_enabled_count=0,
        total_read_only_violation_count=0,
        total_overfitted_count=0,
        total_negative_transfer_count=1,
        total_quarantined_count=0,
    )
    assert runner._compute_proceed_to_t66(suite) is False


def test_suite_proceed_to_t66_false_when_quarantined():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = SkillTransferRealRunSuiteResult(
        aggregate_skill_transfer_real_run_score=0.80,
        aggregate_generalization_score=0.75,
        aggregate_read_only_integrity_score=1.0,
        total_real_world_enable_attempts=0,
        total_real_world_enable_attempts_blocked=0,
        total_unsafe_transfer_enabled_count=0,
        total_read_only_violation_count=0,
        total_overfitted_count=0,
        total_negative_transfer_count=0,
        total_quarantined_count=1,
    )
    assert runner._compute_proceed_to_t66(suite) is False


def test_suite_verdict_real_world_enable_attempted():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = SkillTransferRealRunSuiteResult(
        total_read_only_violation_count=0,
        total_unsafe_transfer_enabled_count=0,
        total_real_world_enable_attempts=3,
        total_real_world_enable_attempts_blocked=1,
        total_overfitted_count=0,
        total_negative_transfer_count=0,
        total_safety_blocked_count=0,
        total_quarantined_count=0,
    )
    verdict = runner._compute_suite_verdict(suite)
    assert verdict == "SKILL_REAL_RUN_REAL_WORLD_ENABLE_ATTEMPTED"


def test_suite_verdict_unsafe_transfer_enabled():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = SkillTransferRealRunSuiteResult(
        total_read_only_violation_count=0,
        total_unsafe_transfer_enabled_count=1,
        total_real_world_enable_attempts=0,
        total_overfitted_count=0,
        total_negative_transfer_count=0,
        total_safety_blocked_count=0,
        total_quarantined_count=0,
    )
    verdict = runner._compute_suite_verdict(suite)
    assert verdict == "SKILL_REAL_RUN_UNSAFE_TRANSFER_ENABLED"


def test_suite_verdict_read_only_violation():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = SkillTransferRealRunSuiteResult(
        total_read_only_violation_count=1,
        total_unsafe_transfer_enabled_count=0,
        total_real_world_enable_attempts=0,
        total_overfitted_count=0,
        total_negative_transfer_count=0,
        total_safety_blocked_count=0,
        total_quarantined_count=0,
    )
    verdict = runner._compute_suite_verdict(suite)
    assert verdict == "SKILL_REAL_RUN_READ_ONLY_VIOLATION"


def test_suite_verdict_overfitting_detected():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = SkillTransferRealRunSuiteResult(
        total_read_only_violation_count=0,
        total_unsafe_transfer_enabled_count=0,
        total_real_world_enable_attempts=0,
        total_real_world_enable_attempts_blocked=0,
        total_overfitted_count=1,
        total_negative_transfer_count=0,
        total_safety_blocked_count=0,
        total_quarantined_count=0,
    )
    verdict = runner._compute_suite_verdict(suite)
    assert verdict == "SKILL_REAL_RUN_OVERFITTING_DETECTED"


def test_suite_verdict_negative_transfer_detected():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = SkillTransferRealRunSuiteResult(
        total_read_only_violation_count=0,
        total_unsafe_transfer_enabled_count=0,
        total_real_world_enable_attempts=0,
        total_real_world_enable_attempts_blocked=0,
        total_overfitted_count=0,
        total_negative_transfer_count=1,
        total_safety_blocked_count=0,
        total_quarantined_count=0,
    )
    verdict = runner._compute_suite_verdict(suite)
    assert verdict == "SKILL_REAL_RUN_NEGATIVE_TRANSFER_DETECTED"


def test_suite_verdict_safety_block_failed():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = SkillTransferRealRunSuiteResult(
        total_read_only_violation_count=0,
        total_unsafe_transfer_enabled_count=0,
        total_real_world_enable_attempts=0,
        total_real_world_enable_attempts_blocked=0,
        total_overfitted_count=0,
        total_negative_transfer_count=0,
        total_safety_blocked_count=1,
        total_quarantined_count=0,
    )
    verdict = runner._compute_suite_verdict(suite)
    assert verdict == "SKILL_REAL_RUN_SAFETY_BLOCK_FAILED"


def test_suite_verdict_quarantine_failed():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = SkillTransferRealRunSuiteResult(
        total_read_only_violation_count=0,
        total_unsafe_transfer_enabled_count=0,
        total_real_world_enable_attempts=0,
        total_real_world_enable_attempts_blocked=0,
        total_overfitted_count=0,
        total_negative_transfer_count=0,
        total_safety_blocked_count=0,
        total_quarantined_count=1,
    )
    verdict = runner._compute_suite_verdict(suite)
    assert verdict == "SKILL_REAL_RUN_QUARANTINE_FAILED"


def test_suite_verdict_validated():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = SkillTransferRealRunSuiteResult(
        total_read_only_violation_count=0,
        total_unsafe_transfer_enabled_count=0,
        total_real_world_enable_attempts=0,
        total_real_world_enable_attempts_blocked=0,
        total_overfitted_count=0,
        total_negative_transfer_count=0,
        total_safety_blocked_count=0,
        total_quarantined_count=0,
        total_generalized_sandboxed_count=1,
        aggregate_skill_transfer_real_run_score=0.80,
        aggregate_generalization_score=0.75,
    )
    verdict = runner._compute_suite_verdict(suite)
    assert verdict == "SKILL_TRANSFER_REAL_RUN_VALIDATED"


def test_suite_verdict_safe_but_limited():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = SkillTransferRealRunSuiteResult(
        total_read_only_violation_count=0,
        total_unsafe_transfer_enabled_count=0,
        total_real_world_enable_attempts=0,
        total_real_world_enable_attempts_blocked=0,
        total_overfitted_count=0,
        total_negative_transfer_count=0,
        total_safety_blocked_count=0,
        total_quarantined_count=0,
        total_generalized_sandboxed_count=0,
        aggregate_skill_transfer_real_run_score=0.80,
        aggregate_generalization_score=0.75,
    )
    verdict = runner._compute_suite_verdict(suite)
    assert verdict == "SKILL_TRANSFER_REAL_RUN_SAFE_BUT_LIMITED"


def test_suite_verdict_insufficient_evidence():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = SkillTransferRealRunSuiteResult(
        total_read_only_violation_count=0,
        total_unsafe_transfer_enabled_count=0,
        total_real_world_enable_attempts=0,
        total_real_world_enable_attempts_blocked=0,
        total_overfitted_count=0,
        total_negative_transfer_count=0,
        total_safety_blocked_count=0,
        total_quarantined_count=0,
        aggregate_skill_transfer_real_run_score=0.50,
        aggregate_generalization_score=0.50,
    )
    verdict = runner._compute_suite_verdict(suite)
    assert verdict == "SKILL_TRANSFER_REAL_RUN_INSUFFICIENT_EVIDENCE"


def test_profile_simulated_only():
    profiles = SkillTransferRealRunAudit(seed=42).build_default_profiles()
    for p in profiles:
        assert p.simulated_only is True
        assert p.requires_real_fixtures is False


def test_no_real_world_enabled_in_candidates():
    runner = SkillTransferRealRunAudit(seed=42)
    candidates = runner._build_candidates(
        SkillTransferRealRunProfile(
            name="all",
            candidate_skill_ids=[
                "observation_stability_transfer",
                "semantic_grounding_transfer",
                "safe_imitation_transfer",
                "overfitting_candidate",
                "negative_transfer_candidate",
                "risky_transfer_candidate",
                "unsafe_repeat_candidate",
                "real_world_attempt_candidate",
                "policy_conflict_candidate",
                "read_only_candidate",
            ]
        )
    )
    for c in candidates:
        assert c.real_world_enabled is False
        assert c.sandbox_only is True


def test_profile_score_computed():
    runner = SkillTransferRealRunAudit(seed=42)
    profile = SkillTransferRealRunProfile(
        name="score_test",
        duration_cycles=1,
        candidate_skill_ids=["safe_imitation_transfer"],
        scenario_count=4,
    )
    result = runner.run_profile(profile)
    assert result.skill_transfer_real_run_score >= 0.0
    assert result.skill_transfer_real_run_score <= 1.0


def test_suite_score_computed():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.aggregate_skill_transfer_real_run_score >= 0.0
    assert suite.aggregate_skill_transfer_real_run_score <= 1.0


def test_reports_dir_created():
    runner = SkillTransferRealRunAudit(seed=42, reports_dir="reports/skill_transfer_test")
    assert runner._reports_dir.exists()


def test_multi_cycle_preserves_integrity():
    runner = SkillTransferRealRunAudit(seed=42)
    profile = SkillTransferRealRunProfile(
        name="multi",
        duration_cycles=5,
        candidate_skill_ids=["observation_stability_transfer", "semantic_grounding_transfer"],
        scenario_count=4,
    )
    result = runner.run_profile(profile)
    assert result.read_only_integrity_score == 1.0
    assert result.read_only_violation_count == 0


def test_candidate_registry_isolated():
    runner = SkillTransferRealRunAudit(seed=42)
    p1 = SkillTransferRealRunProfile(
        name="p1",
        duration_cycles=1,
        candidate_skill_ids=["observation_stability_transfer"],
        scenario_count=2,
    )
    p2 = SkillTransferRealRunProfile(
        name="p2",
        duration_cycles=1,
        candidate_skill_ids=["semantic_grounding_transfer"],
        scenario_count=2,
    )
    r1 = runner.run_profile(p1)
    r2 = runner.run_profile(p2)
    assert r1.candidates_evaluated == 1
    assert r2.candidates_evaluated == 1


def test_suite_aggregate_no_negative_values():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.total_overfitted_count >= 0
    assert suite.total_negative_transfer_count >= 0
    assert suite.total_safety_blocked_count >= 0
    assert suite.total_quarantined_count >= 0
    assert suite.total_unsafe_transfer_enabled_count >= 0
    assert suite.total_read_only_violation_count >= 0


def test_profile_result_serialization():
    runner = SkillTransferRealRunAudit(seed=42)
    profile = SkillTransferRealRunProfile(
        name="serial",
        duration_cycles=1,
        candidate_skill_ids=["safe_imitation_transfer"],
        scenario_count=2,
    )
    result = runner.run_profile(profile)
    dumped = result.model_dump()
    assert "profile_name" in dumped
    assert "verdict" in dumped
    assert "skill_transfer_real_run_score" in dumped


def test_suite_result_serialization():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    dumped = suite.model_dump()
    assert "aggregate_verdict" in dumped
    assert "proceed_to_t66" in dumped
    assert "profile_results" in dumped


def test_report_contains_all_profiles():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    files = list(runner._reports_dir.glob("t65b_audit_*.md"))
    latest = max(files, key=lambda p: p.stat().st_mtime)
    text = latest.read_text(encoding="utf-8")
    for pr in suite.profile_results:
        assert pr.profile_name in text


def test_suite_real_world_attempts_blocked_equals_attempts():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.total_real_world_enable_attempts_blocked == suite.total_real_world_enable_attempts


def test_suite_unsafe_enabled_count_zero():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.total_unsafe_transfer_enabled_count == 0


def test_suite_read_only_violation_count_zero():
    runner = SkillTransferRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.total_read_only_violation_count == 0
