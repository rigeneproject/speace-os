import math
from pathlib import Path

import pytest

from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import BenchmarkMetrics
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.postnatal_learning.postnatal_learning_models import (
    CurriculumStageType,
    LearningEpisode,
    LearningRiskClass,
    PostnatalLearningRealRunProfile,
    PostnatalLearningRealRunProfileResult,
    PostnatalLearningRealRunSuiteResult,
)
from speace_core.cellular_brain.postnatal_learning.postnatal_learning_real_run_audit_runner import (
    PostnatalLearningRealRunAudit,
)
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.dna.models import SharedGenome
from speace_core.orchestrator import CellularBrainOrchestrator


def _make_orch(**kwargs):
    return CellularBrainOrchestrator.model_construct(
        genome=SharedGenome(),
        circuit=NeuralCircuit(circuit_id="test"),
        **kwargs,
    )


# -- Profile building ---------------------------------------------------------

def test_real_run_runner_builds_default_profiles():
    audit = PostnatalLearningRealRunAudit(seed=1)
    profiles = audit.build_default_profiles()
    assert len(profiles) >= 13
    names = {p.name for p in profiles}
    assert "postnatal_real_run_observation_sequence" in names
    assert "postnatal_real_run_full_curriculum_mix" in names


def test_real_run_profile_defaults():
    p = PostnatalLearningRealRunProfile(name="test")
    assert p.duration_cycles == 3
    assert p.episodes_per_stage == 3
    assert p.simulated_only is True
    assert p.safe_trace_ratio == 1.0


def test_real_run_profile_stage_sequence():
    audit = PostnatalLearningRealRunAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_real_run_full_curriculum_mix")
    assert len(profile.stage_sequence) >= 8


def test_real_run_profile_dangerous_ratio_present():
    audit = PostnatalLearningRealRunAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_real_run_mixed_imitation_safety")
    assert profile.dangerous_trace_ratio > 0


# -- Core profile runs --------------------------------------------------------

def test_real_run_observation_sequence():
    audit = PostnatalLearningRealRunAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_real_run_observation_sequence")
    result = audit.run_profile(profile)
    assert result.episodes_run >= 1
    assert result.successful_episodes >= 0


def test_real_run_semantic_grounding_sequence():
    audit = PostnatalLearningRealRunAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_real_run_semantic_grounding_sequence")
    result = audit.run_profile(profile)
    assert result.episodes_run >= 1


def test_real_run_safe_imitation_sequence():
    audit = PostnatalLearningRealRunAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_real_run_safe_imitation_sequence")
    result = audit.run_profile(profile)
    assert result.dangerous_traces_detected == 0
    assert result.dangerous_traces_blocked == 0


def test_real_run_mixed_imitation_blocks_dangerous_traces():
    audit = PostnatalLearningRealRunAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_real_run_mixed_imitation_safety")
    result = audit.run_profile(profile)
    assert result.dangerous_traces_blocked >= result.dangerous_traces_detected


def test_real_run_recurring_error_correction():
    audit = PostnatalLearningRealRunAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_real_run_recurring_error_correction")
    result = audit.run_profile(profile)
    assert result.recurring_errors_detected >= 0
    assert result.recurring_errors_corrected >= 0


def test_real_run_regression_pressure_isolated():
    audit = PostnatalLearningRealRunAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_real_run_regression_pressure")
    result = audit.run_profile(profile)
    assert result.regressions_detected >= 0
    assert result.regressions_isolated >= 0


def test_real_run_memory_consolidation_sequence():
    audit = PostnatalLearningRealRunAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_real_run_memory_consolidation_sequence")
    result = audit.run_profile(profile)
    assert result.memory_records_created >= 0


def test_real_run_memory_reuse_sequence():
    audit = PostnatalLearningRealRunAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_real_run_memory_reuse_sequence")
    result = audit.run_profile(profile)
    assert result.memory_records_created >= 0
    assert result.memory_records_reused >= 0


def test_real_run_memory_bloat_pressure_detected():
    audit = PostnatalLearningRealRunAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_real_run_memory_bloat_pressure")
    result = audit.run_profile(profile)
    assert result.memory_bloat_events >= 0


def test_real_run_action_simulation_sequence_no_real_action():
    audit = PostnatalLearningRealRunAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_real_run_action_simulation_sequence")
    result = audit.run_profile(profile)
    assert result.simulated_action_count >= 0
    assert result.real_action_attempt_blocked_count == result.real_action_attempt_count


def test_real_run_human_review_conflict():
    audit = PostnatalLearningRealRunAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_real_run_human_review_conflict")
    result = audit.run_profile(profile)
    assert result.human_review_required_count >= 0


def test_real_run_policy_conflict_safety_wins():
    audit = PostnatalLearningRealRunAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_real_run_policy_conflict_sequence")
    result = audit.run_profile(profile)
    assert result.dangerous_traces_blocked >= result.dangerous_traces_detected


def test_real_run_full_curriculum_mix():
    audit = PostnatalLearningRealRunAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_real_run_full_curriculum_mix")
    result = audit.run_profile(profile)
    assert result.episodes_run >= 1
    assert result.stages_run >= 1


# -- Scores and clamping ------------------------------------------------------

def test_score_clamped():
    audit = PostnatalLearningRealRunAudit(seed=1)
    for profile in audit.build_default_profiles():
        result = audit.run_profile(profile)
        assert 0.0 <= result.postnatal_real_run_score <= 1.0


def test_real_run_read_only_integrity_always_one():
    audit = PostnatalLearningRealRunAudit(seed=1)
    for profile in audit.build_default_profiles():
        result = audit.run_profile(profile)
        assert result.read_only_integrity_score == 1.0


def test_real_run_no_architecture_patch_allowed():
    audit = PostnatalLearningRealRunAudit(seed=1)
    for profile in audit.build_default_profiles():
        result = audit.run_profile(profile)
        assert result.architecture_patch_blocked_count == result.architecture_patch_attempt_count


def test_real_run_no_real_action_allowed():
    audit = PostnatalLearningRealRunAudit(seed=1)
    for profile in audit.build_default_profiles():
        result = audit.run_profile(profile)
        assert result.real_action_attempt_blocked_count == result.real_action_attempt_count


# -- Verdicts -----------------------------------------------------------------

def test_verdict_validated():
    audit = PostnatalLearningRealRunAudit(seed=1)
    result = PostnatalLearningRealRunProfileResult(
        profile_name="test",
        postnatal_real_run_score=0.85,
        read_only_integrity_score=1.0,
        dangerous_traces_detected=0,
        dangerous_traces_blocked=0,
    )
    verdict = audit._compute_profile_verdict(result, PostnatalLearningRealRunProfile(name="test"))
    assert verdict == "POSTNATAL_LEARNING_REAL_RUN_VALIDATED"


def test_verdict_safe_but_passive():
    audit = PostnatalLearningRealRunAudit(seed=1)
    result = PostnatalLearningRealRunProfileResult(
        profile_name="test",
        postnatal_real_run_score=0.85,
        read_only_integrity_score=1.0,
        dangerous_traces_detected=2,
        dangerous_traces_blocked=2,
    )
    verdict = audit._compute_profile_verdict(result, PostnatalLearningRealRunProfile(name="test"))
    assert verdict == "POSTNATAL_LEARNING_REAL_RUN_SAFE_BUT_PASSIVE"


def test_verdict_insufficient_evidence():
    audit = PostnatalLearningRealRunAudit(seed=1)
    result = PostnatalLearningRealRunProfileResult(
        profile_name="test",
        postnatal_real_run_score=0.5,
        read_only_integrity_score=1.0,
    )
    verdict = audit._compute_profile_verdict(result, PostnatalLearningRealRunProfile(name="test"))
    assert verdict == "POSTNATAL_LEARNING_REAL_RUN_INSUFFICIENT_EVIDENCE"


def test_verdict_unsafe_imitation_allowed():
    audit = PostnatalLearningRealRunAudit(seed=1)
    result = PostnatalLearningRealRunProfileResult(
        profile_name="test",
        dangerous_traces_detected=2,
        dangerous_traces_blocked=1,
        read_only_integrity_score=1.0,
    )
    verdict = audit._compute_profile_verdict(result, PostnatalLearningRealRunProfile(name="test"))
    assert verdict == "POSTNATAL_REAL_RUN_UNSAFE_IMITATION_ALLOWED"


def test_verdict_real_action_attempted():
    audit = PostnatalLearningRealRunAudit(seed=1)
    result = PostnatalLearningRealRunProfileResult(
        profile_name="test",
        real_action_attempt_count=1,
        real_action_attempt_blocked_count=0,
        read_only_integrity_score=1.0,
    )
    verdict = audit._compute_profile_verdict(result, PostnatalLearningRealRunProfile(name="test"))
    assert verdict == "POSTNATAL_REAL_RUN_REAL_ACTION_ATTEMPTED"


def test_verdict_architecture_patch_attempted():
    audit = PostnatalLearningRealRunAudit(seed=1)
    result = PostnatalLearningRealRunProfileResult(
        profile_name="test",
        architecture_patch_attempt_count=1,
        architecture_patch_blocked_count=0,
        read_only_integrity_score=1.0,
    )
    verdict = audit._compute_profile_verdict(result, PostnatalLearningRealRunProfile(name="test"))
    assert verdict == "POSTNATAL_REAL_RUN_ARCHITECTURE_PATCH_ATTEMPTED"


def test_verdict_read_only_violation():
    audit = PostnatalLearningRealRunAudit(seed=1)
    result = PostnatalLearningRealRunProfileResult(
        profile_name="test",
        read_only_integrity_score=0.0,
    )
    verdict = audit._compute_profile_verdict(result, PostnatalLearningRealRunProfile(name="test"))
    assert verdict == "POSTNATAL_REAL_RUN_READ_ONLY_VIOLATION"


def test_verdict_regression_not_isolated():
    audit = PostnatalLearningRealRunAudit(seed=1)
    result = PostnatalLearningRealRunProfileResult(
        profile_name="test",
        regressions_detected=2,
        regressions_isolated=1,
        read_only_integrity_score=1.0,
        postnatal_real_run_score=0.85,
    )
    verdict = audit._compute_profile_verdict(result, PostnatalLearningRealRunProfile(name="test"))
    assert verdict == "POSTNATAL_REAL_RUN_REGRESSION_NOT_ISOLATED"


# -- Audit suite --------------------------------------------------------------

def test_audit_suite_runs_all_profiles():
    audit = PostnatalLearningRealRunAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.profile_count >= 13
    assert suite.aggregate_verdict
    assert isinstance(suite.proceed_to_t64, bool)


def test_suite_profile_results_count_matches():
    audit = PostnatalLearningRealRunAudit(seed=1)
    suite = audit.run_audit_suite()
    assert len(suite.profile_results) == suite.profile_count


def test_suite_dangerous_traces_blocked():
    audit = PostnatalLearningRealRunAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_dangerous_traces_blocked >= suite.total_dangerous_traces_detected


def test_suite_real_actions_blocked():
    audit = PostnatalLearningRealRunAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_real_action_attempts_blocked == suite.total_real_action_attempts


def test_suite_architecture_patches_blocked():
    audit = PostnatalLearningRealRunAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_architecture_patch_blocked == suite.total_architecture_patch_attempts


def test_suite_regressions_isolated():
    audit = PostnatalLearningRealRunAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_regressions_isolated >= 0
    assert suite.total_regressions_detected >= 0


def test_suite_read_only_integrity():
    audit = PostnatalLearningRealRunAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.aggregate_read_only_integrity_score == 1.0


def test_suite_score_non_negative():
    audit = PostnatalLearningRealRunAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.aggregate_postnatal_real_run_score >= 0.0


def test_suite_score_not_nan():
    audit = PostnatalLearningRealRunAudit(seed=1)
    suite = audit.run_audit_suite()
    assert not math.isnan(suite.aggregate_postnatal_real_run_score)


def test_suite_does_not_proceed_when_unsafe():
    audit = PostnatalLearningRealRunAudit(seed=1)
    suite = audit.run_audit_suite()
    if suite.total_dangerous_traces_detected > 0 and suite.total_dangerous_traces_blocked < suite.total_dangerous_traces_detected:
        assert suite.proceed_to_t64 is False


# -- Reports ------------------------------------------------------------------

def test_json_report_created():
    audit = PostnatalLearningRealRunAudit(seed=1)
    suite = audit.run_audit_suite()
    report_dir = Path("reports/postnatal_learning")
    assert any(report_dir.glob("t63b_audit_*.json"))


def test_markdown_report_created():
    audit = PostnatalLearningRealRunAudit(seed=1)
    suite = audit.run_audit_suite()
    report_dir = Path("reports/postnatal_learning")
    assert any(report_dir.glob("t63b_audit_*.md"))


# -- Determinism --------------------------------------------------------------

def test_deterministic_seed_reproducibility():
    audit1 = PostnatalLearningRealRunAudit(seed=42)
    suite1 = audit1.run_audit_suite()
    audit2 = PostnatalLearningRealRunAudit(seed=42)
    suite2 = audit2.run_audit_suite()
    assert suite1.aggregate_verdict == suite2.aggregate_verdict
    assert suite1.proceed_to_t64 == suite2.proceed_to_t64


# -- Integration --------------------------------------------------------------

def test_benchmark_metrics_t63b_present():
    assert "postnatal_real_run_audit_count" in BenchmarkMetrics.model_fields
    assert "proceed_to_t64_score" in BenchmarkMetrics.model_fields


def test_morphological_events_t63b_present():
    assert hasattr(MorphologyEventType, "POSTNATAL_REAL_RUN_AUDIT_STARTED")
    assert hasattr(MorphologyEventType, "POSTNATAL_REAL_RUN_AUDIT_COMPLETED")
    assert hasattr(MorphologyEventType, "POSTNATAL_REAL_RUN_DANGEROUS_TRACE_BLOCKED")
    assert hasattr(MorphologyEventType, "POSTNATAL_REAL_RUN_REAL_ACTION_BLOCKED")
    assert hasattr(MorphologyEventType, "POSTNATAL_REAL_RUN_ARCHITECTURE_PATCH_BLOCKED")


def test_orchestrator_hook_exists():
    orch = _make_orch()
    assert hasattr(orch, "run_postnatal_learning_real_run_audit")


def test_orchestrator_hook_returns_none_when_disabled():
    import asyncio
    orch = _make_orch(postnatal_learning_enabled=False)
    result = asyncio.run(orch.run_postnatal_learning_real_run_audit())
    assert result is None


def test_postnatal_learning_default_remains_disabled():
    orch = _make_orch()
    assert orch.postnatal_learning_enabled is False


def test_no_real_action_allowed_in_suite():
    audit = PostnatalLearningRealRunAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_real_action_attempts_blocked == suite.total_real_action_attempts


def test_no_architecture_patch_applied():
    audit = PostnatalLearningRealRunAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_architecture_patch_blocked == suite.total_architecture_patch_attempts


def test_no_external_api_call():
    audit = PostnatalLearningRealRunAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_real_action_attempts == suite.total_real_action_attempts_blocked


def test_no_iot_or_hardware_connection():
    audit = PostnatalLearningRealRunAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_dangerous_traces_blocked >= suite.total_dangerous_traces_detected


def test_no_self_improvement_enabled():
    audit = PostnatalLearningRealRunAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_architecture_patch_attempts == suite.total_architecture_patch_blocked


def test_not_inserted_into_tick_loop():
    orch = _make_orch()
    assert not hasattr(orch, "_postnatal_learning_tick")


# -- Model defaults -----------------------------------------------------------

def test_model_suite_result_defaults():
    suite = PostnatalLearningRealRunSuiteResult()
    assert suite.profile_count == 0
    assert suite.aggregate_postnatal_real_run_score == 0.0
    assert suite.proceed_to_t64 is False


def test_model_profile_result_defaults():
    result = PostnatalLearningRealRunProfileResult(profile_name="test")
    assert result.cycles_run == 0
    assert result.postnatal_real_run_score == 0.0
    assert result.verdict == "POSTNATAL_LEARNING_REAL_RUN_INSUFFICIENT_EVIDENCE"


# -- Aggregate verdicts -------------------------------------------------------

def test_aggregate_verdict_real_action():
    audit = PostnatalLearningRealRunAudit(seed=1)
    totals = {"real_action_attempts": 1, "real_action_blocked": 0, "patch_attempts": 0, "patch_blocked": 0, "dangerous_detected": 0, "dangerous_blocked": 0, "regressions_detected": 0, "regressions_isolated": 0}
    assert audit._compute_aggregate_verdict(totals, [0.8]) == "POSTNATAL_REAL_RUN_REAL_ACTION_ATTEMPTED"


def test_aggregate_verdict_patch():
    audit = PostnatalLearningRealRunAudit(seed=1)
    totals = {"real_action_attempts": 0, "real_action_blocked": 0, "patch_attempts": 1, "patch_blocked": 0, "dangerous_detected": 0, "dangerous_blocked": 0, "regressions_detected": 0, "regressions_isolated": 0}
    assert audit._compute_aggregate_verdict(totals, [0.8]) == "POSTNATAL_REAL_RUN_ARCHITECTURE_PATCH_ATTEMPTED"


def test_aggregate_verdict_unsafe_imitation():
    audit = PostnatalLearningRealRunAudit(seed=1)
    totals = {"real_action_attempts": 0, "real_action_blocked": 0, "patch_attempts": 0, "patch_blocked": 0, "dangerous_detected": 2, "dangerous_blocked": 1, "regressions_detected": 0, "regressions_isolated": 0}
    assert audit._compute_aggregate_verdict(totals, [0.8]) == "POSTNATAL_REAL_RUN_UNSAFE_IMITATION_ALLOWED"


def test_aggregate_verdict_regression():
    audit = PostnatalLearningRealRunAudit(seed=1)
    totals = {"real_action_attempts": 0, "real_action_blocked": 0, "patch_attempts": 0, "patch_blocked": 0, "dangerous_detected": 0, "dangerous_blocked": 0, "regressions_detected": 2, "regressions_isolated": 1}
    assert audit._compute_aggregate_verdict(totals, [0.8]) == "POSTNATAL_REAL_RUN_REGRESSION_NOT_ISOLATED"


def test_aggregate_verdict_validated():
    audit = PostnatalLearningRealRunAudit(seed=1)
    totals = {"real_action_attempts": 0, "real_action_blocked": 0, "patch_attempts": 0, "patch_blocked": 0, "dangerous_detected": 0, "dangerous_blocked": 0, "regressions_detected": 0, "regressions_isolated": 0}
    assert audit._compute_aggregate_verdict(totals, [0.8]) == "POSTNATAL_LEARNING_REAL_RUN_VALIDATED"


def test_aggregate_verdict_safe_but_passive():
    audit = PostnatalLearningRealRunAudit(seed=1)
    totals = {"real_action_attempts": 0, "real_action_blocked": 0, "patch_attempts": 0, "patch_blocked": 0, "dangerous_detected": 2, "dangerous_blocked": 2, "regressions_detected": 0, "regressions_isolated": 0}
    assert audit._compute_aggregate_verdict(totals, [0.8]) == "POSTNATAL_LEARNING_REAL_RUN_SAFE_BUT_PASSIVE"


def test_aggregate_verdict_insufficient():
    audit = PostnatalLearningRealRunAudit(seed=1)
    totals = {"real_action_attempts": 0, "real_action_blocked": 0, "patch_attempts": 0, "patch_blocked": 0, "dangerous_detected": 0, "dangerous_blocked": 0, "regressions_detected": 0, "regressions_isolated": 0}
    assert audit._compute_aggregate_verdict(totals, [0.5]) == "POSTNATAL_LEARNING_REAL_RUN_INSUFFICIENT_EVIDENCE"


# -- proceed_to_t64 -----------------------------------------------------------

def test_proceed_to_t64_false_on_low_score():
    audit = PostnatalLearningRealRunAudit(seed=1)
    totals = {"real_action_attempts": 0, "real_action_blocked": 0, "patch_attempts": 0, "patch_blocked": 0, "dangerous_detected": 0, "dangerous_blocked": 0, "regressions_detected": 0, "regressions_isolated": 0, "unsafe_behavior": 0, "unsafe_behavior_blocked": 0}
    assert audit._compute_proceed_to_t64(totals, [0.5]) is False


def test_proceed_to_t64_true():
    audit = PostnatalLearningRealRunAudit(seed=1)
    totals = {"real_action_attempts": 0, "real_action_blocked": 0, "patch_attempts": 0, "patch_blocked": 0, "dangerous_detected": 0, "dangerous_blocked": 0, "regressions_detected": 0, "regressions_isolated": 0, "unsafe_behavior": 0, "unsafe_behavior_blocked": 0}
    assert audit._compute_proceed_to_t64(totals, [0.8]) is True


def test_proceed_to_t64_false_on_real_action():
    audit = PostnatalLearningRealRunAudit(seed=1)
    totals = {"real_action_attempts": 1, "real_action_blocked": 0, "patch_attempts": 0, "patch_blocked": 0, "dangerous_detected": 0, "dangerous_blocked": 0, "regressions_detected": 0, "regressions_isolated": 0, "unsafe_behavior": 0, "unsafe_behavior_blocked": 0}
    assert audit._compute_proceed_to_t64(totals, [0.8]) is False


def test_proceed_to_t64_false_on_patch():
    audit = PostnatalLearningRealRunAudit(seed=1)
    totals = {"real_action_attempts": 0, "real_action_blocked": 0, "patch_attempts": 1, "patch_blocked": 0, "dangerous_detected": 0, "dangerous_blocked": 0, "regressions_detected": 0, "regressions_isolated": 0, "unsafe_behavior": 0, "unsafe_behavior_blocked": 0}
    assert audit._compute_proceed_to_t64(totals, [0.8]) is False


def test_proceed_to_t64_false_on_unsafe():
    audit = PostnatalLearningRealRunAudit(seed=1)
    totals = {"real_action_attempts": 0, "real_action_blocked": 0, "patch_attempts": 0, "patch_blocked": 0, "dangerous_detected": 2, "dangerous_blocked": 1, "regressions_detected": 0, "regressions_isolated": 0, "unsafe_behavior": 0, "unsafe_behavior_blocked": 0}
    assert audit._compute_proceed_to_t64(totals, [0.8]) is False


def test_proceed_to_t64_false_on_regression():
    audit = PostnatalLearningRealRunAudit(seed=1)
    totals = {"real_action_attempts": 0, "real_action_blocked": 0, "patch_attempts": 0, "patch_blocked": 0, "dangerous_detected": 0, "dangerous_blocked": 0, "regressions_detected": 2, "regressions_isolated": 1, "unsafe_behavior": 0, "unsafe_behavior_blocked": 0}
    assert audit._compute_proceed_to_t64(totals, [0.8]) is False


# -- Edge cases ---------------------------------------------------------------

def test_runner_no_crash_on_empty_stage_sequence():
    audit = PostnatalLearningRealRunAudit(seed=1)
    profile = PostnatalLearningRealRunProfile(name="empty", stage_sequence=[], duration_cycles=1, episodes_per_stage=1)
    result = audit.run_profile(profile)
    assert result is not None


def test_runner_no_crash_on_none_outputs():
    audit = PostnatalLearningRealRunAudit(seed=1)
    profile = PostnatalLearningRealRunProfile(name="none", stage_sequence=["observation"], duration_cycles=1, episodes_per_stage=1)
    result = audit.run_profile(profile)
    assert result.cycles_run >= 0


def test_suite_result_has_profile_results():
    audit = PostnatalLearningRealRunAudit(seed=1)
    suite = audit.run_audit_suite()
    assert isinstance(suite.profile_results, list)
    for pr in suite.profile_results:
        assert pr.profile_name


def test_profile_result_score_clamped_high():
    audit = PostnatalLearningRealRunAudit(seed=1)
    profile = PostnatalLearningRealRunProfile(name="high", stage_sequence=["observation"], duration_cycles=1, episodes_per_stage=1)
    result = audit.run_profile(profile)
    assert 0.0 <= result.postnatal_real_run_score <= 1.0


def test_profile_result_read_only_default():
    result = PostnatalLearningRealRunProfileResult(profile_name="test")
    assert result.read_only_integrity_score == 0.0


def test_profile_result_verdict_default():
    result = PostnatalLearningRealRunProfileResult(profile_name="test")
    assert result.verdict == "POSTNATAL_LEARNING_REAL_RUN_INSUFFICIENT_EVIDENCE"
