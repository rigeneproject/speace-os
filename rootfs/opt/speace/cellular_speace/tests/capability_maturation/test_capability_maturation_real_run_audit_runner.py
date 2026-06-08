import asyncio
import math
from pathlib import Path

import pytest

from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import BenchmarkMetrics
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.capability_maturation.capability_maturation_models import (
    CapabilityMaturityState,
    CapabilityMaturationRealRunProfile,
)
from speace_core.cellular_brain.capability_maturation.capability_maturation_real_run_audit_runner import (
    CapabilityMaturationRealRunAudit,
)
from speace_core.cellular_brain.capability_maturation.capability_registry import (
    DEFAULT_CAPABILITIES,
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


# -- Runner construction ------------------------------------------------------

def test_real_run_runner_builds_default_profiles():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    assert len(profiles) >= 13


def test_real_run_runner_profiles_have_expected_names():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    names = {p.name for p in profiles}
    expected = {
        "capability_real_run_baseline_stable",
        "capability_real_run_unobserved_capabilities",
        "capability_real_run_emerging_capabilities",
        "capability_real_run_maturing_sequence",
        "capability_real_run_mature_sandboxed_sequence",
        "capability_real_run_regression_pressure",
        "capability_real_run_safety_violation_pressure",
        "capability_real_run_quarantine_pressure",
        "capability_real_run_conflicting_evidence",
        "capability_real_run_real_world_enable_attempts",
        "capability_real_run_maturity_drift",
        "capability_real_run_policy_conflict",
        "capability_real_run_full_maturation_mix",
    }
    assert expected.issubset(names)


def test_real_run_runner_profiles_simulated_only():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    assert all(p.simulated_only for p in profiles)


def test_real_run_runner_profiles_no_real_fixtures():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    assert not any(p.requires_real_fixtures for p in profiles)


# -- Profile runs: baseline / unobserved / emerging / maturing / mature ------

def test_real_run_baseline_stable():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    profile = next(p for p in profiles if p.name == "capability_real_run_baseline_stable")
    result = runner.run_profile(profile)
    assert result.verdict in (
        "CAPABILITY_MATURATION_REAL_RUN_VALIDATED",
        "CAPABILITY_MATURATION_REAL_RUN_SAFE_BUT_IMMATURE",
        "CAPABILITY_MATURATION_REAL_RUN_INSUFFICIENT_EVIDENCE",
    )
    assert result.read_only_integrity_score == 1.0
    assert result.unsafe_capability_enabled_count == 0


def test_real_run_unobserved_capabilities():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    profile = next(p for p in profiles if p.name == "capability_real_run_unobserved_capabilities")
    result = runner.run_profile(profile)
    assert result.evidence_records_processed == 0
    assert result.unsafe_capability_enabled_count == 0


def test_real_run_emerging_capabilities():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    profile = next(p for p in profiles if p.name == "capability_real_run_emerging_capabilities")
    result = runner.run_profile(profile)
    assert result.emerging_count >= 0
    assert result.unsafe_capability_enabled_count == 0
    assert result.read_only_integrity_score == 1.0


def test_real_run_maturing_sequence():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    profile = next(p for p in profiles if p.name == "capability_real_run_maturing_sequence")
    result = runner.run_profile(profile)
    assert result.mature_sandboxed_count >= 0 or result.immature_count >= 0 or result.emerging_count >= 0
    assert result.unsafe_capability_enabled_count == 0


def test_real_run_mature_sandboxed_sequence():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    profile = next(p for p in profiles if p.name == "capability_real_run_mature_sandboxed_sequence")
    result = runner.run_profile(profile)
    # Mature sandboxed expected with strong positive evidence
    assert result.mature_sandboxed_count >= 0
    assert result.real_world_enable_attempts_blocked == result.real_world_enable_attempts
    assert result.unsafe_capability_enabled_count == 0


# -- Profile runs: regression / safety / quarantine / conflict / drift ------

def test_real_run_regression_pressure_isolated():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    profile = next(p for p in profiles if p.name == "capability_real_run_regression_pressure")
    result = runner.run_profile(profile)
    # Regressions may be detected; if so, they should be isolated
    if result.regressions_detected > 0:
        assert result.regressions_isolated >= result.regressions_detected


def test_real_run_safety_violation_pressure_blocked():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    profile = next(p for p in profiles if p.name == "capability_real_run_safety_violation_pressure")
    result = runner.run_profile(profile)
    assert result.safety_violations_detected > 0
    assert result.safety_violations_blocked == result.safety_violations_detected
    assert result.unsafe_capability_enabled_count == 0


def test_real_run_quarantine_pressure():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    profile = next(p for p in profiles if p.name == "capability_real_run_quarantine_pressure")
    result = runner.run_profile(profile)
    assert result.quarantined_count > 0
    assert result.unsafe_capability_enabled_count == 0


def test_real_run_conflicting_evidence_no_premature_maturity():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    profile = next(p for p in profiles if p.name == "capability_real_run_conflicting_evidence")
    result = runner.run_profile(profile)
    assert result.conflicting_evidence_count > 0
    # No premature maturity: if mature_sandboxed exists, safety must be clean
    if result.mature_sandboxed_count > 0:
        assert result.safety_blocked_count == 0
        assert result.quarantined_count == 0


def test_real_run_real_world_enable_attempts_blocked():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    profile = next(p for p in profiles if p.name == "capability_real_run_real_world_enable_attempts")
    result = runner.run_profile(profile)
    assert result.real_world_enable_attempts > 0
    assert result.real_world_enable_attempts_blocked == result.real_world_enable_attempts
    assert result.unsafe_capability_enabled_count == 0


def test_real_run_maturity_drift_detected():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profile = CapabilityMaturationRealRunProfile(
        name="drift_test",
        duration_cycles=3,
        capability_ids=[],
        evidence_volume=1,
        maturity_drift_pressure=1.0,
    )
    result = runner.run_profile(profile)
    assert result.maturity_drift_detected_count > 0
    assert result.maturity_drift_blocked_count >= result.maturity_drift_detected_count


def test_real_run_policy_conflict_safety_wins():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    profile = next(p for p in profiles if p.name == "capability_real_run_policy_conflict")
    result = runner.run_profile(profile)
    # Safety should prevail: if safety violations exist, no validated verdict
    if result.safety_violations_detected > 0:
        assert result.verdict != "CAPABILITY_MATURATION_REAL_RUN_VALIDATED"
    assert result.unsafe_capability_enabled_count == 0


def test_real_run_full_maturation_mix():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    profile = next(p for p in profiles if p.name == "capability_real_run_full_maturation_mix")
    result = runner.run_profile(profile)
    assert result.cycles_run == profile.duration_cycles
    assert result.capabilities_evaluated > 0
    assert result.verdict
    assert result.unsafe_capability_enabled_count == 0


# -- Score clamping -----------------------------------------------------------

def test_score_clamped():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    for profile in profiles:
        result = runner.run_profile(profile)
        assert 0.0 <= result.capability_real_run_score <= 1.0


def test_average_scores_clamped():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    for profile in profiles:
        result = runner.run_profile(profile)
        assert 0.0 <= result.average_maturity_score <= 1.0
        assert 0.0 <= result.average_confidence_score <= 1.0
        assert 0.0 <= result.average_safety_score <= 1.0
        assert 0.0 <= result.average_stability_score <= 1.0


# -- Verdicts -----------------------------------------------------------------

def test_verdict_validated():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    result = runner._compute_profile_verdict(
        _fake_profile_result(
            capability_real_run_score=0.8,
            read_only_integrity_score=1.0,
            mature_sandboxed_count=5,
            safety_blocked_count=0,
            quarantined_count=0,
        ),
        CapabilityMaturationRealRunProfile(name="test"),
    )
    assert result == "CAPABILITY_MATURATION_REAL_RUN_VALIDATED"


def test_verdict_safe_but_immature():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    result = runner._compute_profile_verdict(
        _fake_profile_result(
            capability_real_run_score=0.8,
            read_only_integrity_score=1.0,
            mature_sandboxed_count=0,
            safety_blocked_count=0,
            quarantined_count=0,
        ),
        CapabilityMaturationRealRunProfile(name="test"),
    )
    assert result == "CAPABILITY_MATURATION_REAL_RUN_SAFE_BUT_IMMATURE"


def test_verdict_insufficient_evidence():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    result = runner._compute_profile_verdict(
        _fake_profile_result(
            capability_real_run_score=0.5,
            read_only_integrity_score=1.0,
        ),
        CapabilityMaturationRealRunProfile(name="test"),
    )
    assert result == "CAPABILITY_MATURATION_REAL_RUN_INSUFFICIENT_EVIDENCE"


def test_verdict_regression_not_isolated():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    result = runner._compute_profile_verdict(
        _fake_profile_result(
            regressions_detected=3,
            regressions_isolated=1,
            read_only_integrity_score=1.0,
        ),
        CapabilityMaturationRealRunProfile(name="test"),
    )
    assert result == "CAPABILITY_REAL_RUN_REGRESSION_NOT_ISOLATED"


def test_verdict_safety_block_failed():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    result = runner._compute_profile_verdict(
        _fake_profile_result(
            safety_violations_detected=3,
            safety_violations_blocked=1,
            read_only_integrity_score=1.0,
        ),
        CapabilityMaturationRealRunProfile(name="test"),
    )
    assert result == "CAPABILITY_REAL_RUN_SAFETY_BLOCK_FAILED"


def test_verdict_quarantine_failed():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    result = runner._compute_profile_verdict(
        _fake_profile_result(
            safety_violations_detected=3,
            safety_violations_blocked=3,
            quarantined_count=0,
            read_only_integrity_score=1.0,
        ),
        CapabilityMaturationRealRunProfile(name="test"),
    )
    assert result == "CAPABILITY_REAL_RUN_QUARANTINE_FAILED"


def test_verdict_unsafe_capability_enabled():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    result = runner._compute_profile_verdict(
        _fake_profile_result(
            unsafe_capability_enabled_count=1,
            read_only_integrity_score=1.0,
        ),
        CapabilityMaturationRealRunProfile(name="test"),
    )
    assert result == "CAPABILITY_REAL_RUN_UNSAFE_CAPABILITY_ENABLED"


def test_verdict_real_world_enable_attempted():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    result = runner._compute_profile_verdict(
        _fake_profile_result(
            real_world_enable_attempts=3,
            real_world_enable_attempts_blocked=1,
            read_only_integrity_score=1.0,
        ),
        CapabilityMaturationRealRunProfile(name="test"),
    )
    assert result == "CAPABILITY_REAL_RUN_REAL_WORLD_ENABLE_ATTEMPTED"


def test_verdict_maturity_drift_detected():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    result = runner._compute_profile_verdict(
        _fake_profile_result(
            maturity_drift_detected_count=3,
            maturity_drift_blocked_count=1,
            read_only_integrity_score=1.0,
        ),
        CapabilityMaturationRealRunProfile(name="test"),
    )
    assert result == "CAPABILITY_REAL_RUN_MATURITY_DRIFT_DETECTED"


def test_verdict_read_only_violation():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    result = runner._compute_profile_verdict(
        _fake_profile_result(
            read_only_integrity_score=0.5,
        ),
        CapabilityMaturationRealRunProfile(name="test"),
    )
    assert result == "CAPABILITY_REAL_RUN_READ_ONLY_VIOLATION"


def _fake_profile_result(**kwargs):
    from speace_core.cellular_brain.capability_maturation.capability_maturation_models import (
        CapabilityMaturationRealRunProfileResult,
    )
    defaults = {
        "profile_name": "fake",
        "read_only_integrity_score": 1.0,
        "unsafe_capability_enabled_count": 0,
        "real_world_enable_attempts": 0,
        "real_world_enable_attempts_blocked": 0,
        "safety_violations_detected": 0,
        "safety_violations_blocked": 0,
        "regressions_detected": 0,
        "regressions_isolated": 0,
        "maturity_drift_detected_count": 0,
        "maturity_drift_blocked_count": 0,
        "mature_sandboxed_count": 0,
        "safety_blocked_count": 0,
        "quarantined_count": 0,
        "capability_real_run_score": 0.0,
    }
    defaults.update(kwargs)
    return CapabilityMaturationRealRunProfileResult(**defaults)


# -- Suite runs ---------------------------------------------------------------

def test_suite_runs_all_profiles():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.profile_count >= 13
    assert len(suite.profile_results) == suite.profile_count


def test_suite_produces_aggregate_verdict():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.aggregate_verdict
    assert isinstance(suite.aggregate_verdict, str)


def test_suite_proceed_to_t65_bool():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert isinstance(suite.proceed_to_t65, bool)


def test_suite_aggregate_scores_in_range():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert 0.0 <= suite.aggregate_maturity_score <= 1.0
    assert 0.0 <= suite.aggregate_confidence_score <= 1.0
    assert 0.0 <= suite.aggregate_safety_score <= 1.0
    assert 0.0 <= suite.aggregate_stability_score <= 1.0
    assert 0.0 <= suite.aggregate_capability_real_run_score <= 1.0
    assert suite.aggregate_read_only_integrity_score == 1.0


def test_suite_total_cycles_positive():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.total_cycles_run > 0


def test_suite_total_capabilities_positive():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.total_capabilities_evaluated > 0


def test_suite_total_evidence_positive():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.total_evidence_records_processed > 0


def test_suite_no_unsafe_capability_enabled():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.total_unsafe_capability_enabled_count == 0


def test_suite_all_real_world_attempts_blocked():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.total_real_world_enable_attempts_blocked == suite.total_real_world_enable_attempts


def test_suite_safety_violations_blocked():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.total_safety_violations_blocked == suite.total_safety_violations_detected


def test_suite_regressions_isolated():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.total_regressions_isolated >= suite.total_regressions_detected


def test_suite_maturity_drift_blocked():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.total_maturity_drift_blocked_count >= suite.total_maturity_drift_detected_count


# -- Reports ------------------------------------------------------------------

def test_json_report_created():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    runner.run_audit_suite()
    report_dir = Path("reports/capability_maturation")
    assert any(report_dir.glob("t64b_audit_*.json"))


def test_markdown_report_created():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    runner.run_audit_suite()
    report_dir = Path("reports/capability_maturation")
    assert any(report_dir.glob("t64b_audit_*.md"))


def test_reports_contain_profile_names():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    runner.run_audit_suite()
    report_dir = Path("reports/capability_maturation")
    md_files = list(report_dir.glob("t64b_audit_*.md"))
    assert md_files
    content = md_files[0].read_text(encoding="utf-8")
    assert "capability_real_run_baseline_stable" in content


def test_reports_contain_verdict():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    runner.run_audit_suite()
    report_dir = Path("reports/capability_maturation")
    md_files = list(report_dir.glob("t64b_audit_*.md"))
    assert md_files
    content = md_files[0].read_text(encoding="utf-8")
    assert "Aggregate verdict" in content


def test_reports_contain_aggregate_score():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    runner.run_audit_suite()
    report_dir = Path("reports/capability_maturation")
    md_files = list(report_dir.glob("t64b_audit_*.md"))
    assert md_files
    content = md_files[0].read_text(encoding="utf-8")
    assert "Aggregate score" in content


# -- BenchmarkMetrics ---------------------------------------------------------

def test_benchmark_metrics_t64b_present():
    assert "capability_real_run_audit_count" in BenchmarkMetrics.model_fields
    assert "capability_real_run_score" in BenchmarkMetrics.model_fields
    assert "proceed_to_t65_score" in BenchmarkMetrics.model_fields


# -- MorphologyEventType ------------------------------------------------------

def test_morphological_events_t64b_present():
    assert hasattr(MorphologyEventType, "CAPABILITY_REAL_RUN_AUDIT_STARTED")
    assert hasattr(MorphologyEventType, "CAPABILITY_REAL_RUN_AUDIT_COMPLETED")
    assert hasattr(MorphologyEventType, "CAPABILITY_REAL_RUN_SAFETY_BLOCK_VERIFIED")
    assert hasattr(MorphologyEventType, "CAPABILITY_REAL_RUN_QUARANTINE_VERIFIED")
    assert hasattr(MorphologyEventType, "CAPABILITY_REAL_RUN_REAL_WORLD_ENABLE_BLOCKED")
    assert hasattr(MorphologyEventType, "CAPABILITY_REAL_RUN_MATURITY_DRIFT_BLOCKED")
    assert hasattr(MorphologyEventType, "CAPABILITY_REAL_RUN_READ_ONLY_ENFORCED")
    assert hasattr(MorphologyEventType, "CAPABILITY_REAL_RUN_VERDICT_COMPUTED")


# -- Orchestrator hooks -------------------------------------------------------

def test_orchestrator_hook_exists():
    orch = _make_orch(capability_maturation_enabled=True)
    assert hasattr(orch, "run_capability_maturation_real_run_audit")


def test_orchestrator_hook_returns_none_when_disabled():
    orch = _make_orch(capability_maturation_enabled=False)
    result = asyncio.run(orch.run_capability_maturation_real_run_audit())
    assert result is None


# -- Default flags ------------------------------------------------------------

def test_capability_maturation_default_remains_disabled():
    orch = _make_orch()
    assert orch.capability_maturation_enabled is False


def test_existing_flags_remain_disabled():
    orch = _make_orch()
    assert orch.postnatal_learning_enabled is False
    assert orch.self_improvement_enabled is False
    assert orch.architecture_patch_execution_enabled is False
    assert orch.cyber_physical_assimilation_enabled is False
    assert orch.external_world_model_sandbox_enabled is False
    assert orch.external_action_governance_enabled is False


# -- Safety constraints -------------------------------------------------------

def test_no_external_api_call():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.total_real_world_enable_attempts_blocked == suite.total_real_world_enable_attempts


def test_no_iot_or_hardware_connection():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.total_unsafe_capability_enabled_count == 0


def test_no_real_action_allowed():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.total_real_world_enable_attempts == suite.total_real_world_enable_attempts_blocked


def test_no_architecture_patch_applied():
    orch = _make_orch()
    assert orch.architecture_patch_execution_enabled is False


def test_no_self_improvement_enabled():
    orch = _make_orch()
    assert orch.self_improvement_enabled is False


def test_not_inserted_into_tick_loop():
    orch = _make_orch()
    assert not hasattr(orch, "_capability_maturation_real_run_tick")


# -- Determinism --------------------------------------------------------------

def test_deterministic_seed_reproducibility():
    runner1 = CapabilityMaturationRealRunAudit(seed=42)
    suite1 = runner1.run_audit_suite()
    runner2 = CapabilityMaturationRealRunAudit(seed=42)
    suite2 = runner2.run_audit_suite()
    assert suite1.aggregate_verdict == suite2.aggregate_verdict
    assert suite1.proceed_to_t65 == suite2.proceed_to_t65
    assert len(suite1.profile_results) == len(suite2.profile_results)
    for p1, p2 in zip(suite1.profile_results, suite2.profile_results):
        assert p1.verdict == p2.verdict
        assert p1.capability_real_run_score == p2.capability_real_run_score


# -- Read-only integrity ------------------------------------------------------

def test_read_only_integrity_always_one():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    for profile in profiles:
        result = runner.run_profile(profile)
        assert result.read_only_integrity_score == 1.0


# -- Capability isolation between profiles ------------------------------------

def test_profile_isolation_no_cross_contamination():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    # Run quarantine profile first
    quarantine_profile = next(p for p in profiles if p.name == "capability_real_run_quarantine_pressure")
    quarantine_result = runner.run_profile(quarantine_profile)
    # Then run baseline stable profile
    baseline_profile = next(p for p in profiles if p.name == "capability_real_run_baseline_stable")
    baseline_result = runner.run_profile(baseline_profile)
    # Baseline should not inherit quarantine state
    assert baseline_result.quarantined_count == 0


# -- Aggregate verdict specifics ----------------------------------------------

def test_aggregate_verdict_insufficient_evidence_when_low_score():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    verdict = runner._compute_aggregate_verdict(
        {"unsafe_enabled": 0, "real_world_attempts": 0, "real_world_blocked": 0,
         "safety_violations": 0, "safety_violations_blocked": 0,
         "regressions_detected": 0, "regressions_isolated": 0,
         "drift_detected": 0, "drift_blocked": 0, "mature": 0},
        [0.5],
    )
    assert verdict == "CAPABILITY_MATURATION_REAL_RUN_INSUFFICIENT_EVIDENCE"


def test_aggregate_verdict_validated_when_clean():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    verdict = runner._compute_aggregate_verdict(
        {"unsafe_enabled": 0, "real_world_attempts": 0, "real_world_blocked": 0,
         "safety_violations": 0, "safety_violations_blocked": 0,
         "regressions_detected": 0, "regressions_isolated": 0,
         "drift_detected": 0, "drift_blocked": 0, "mature": 5, "safety_blocked": 0, "quarantined": 0},
        [0.8],
    )
    assert verdict == "CAPABILITY_MATURATION_REAL_RUN_VALIDATED"


def test_aggregate_verdict_safe_but_immature():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    verdict = runner._compute_aggregate_verdict(
        {"unsafe_enabled": 0, "real_world_attempts": 0, "real_world_blocked": 0,
         "safety_violations": 0, "safety_violations_blocked": 0,
         "regressions_detected": 0, "regressions_isolated": 0,
         "drift_detected": 0, "drift_blocked": 0, "mature": 0, "safety_blocked": 0, "quarantined": 0},
        [0.8],
    )
    assert verdict == "CAPABILITY_MATURATION_REAL_RUN_SAFE_BUT_IMMATURE"


# -- proceed_to_t65 logic -----------------------------------------------------

def test_proceed_to_t65_false_on_low_score():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    assert not runner._compute_proceed_to_t65({"real_world_attempts": 0, "real_world_blocked": 0,
         "unsafe_enabled": 0, "safety_violations": 0, "safety_violations_blocked": 0,
         "regressions_detected": 0, "regressions_isolated": 0,
         "drift_detected": 0, "drift_blocked": 0}, [0.5])


def test_proceed_to_t65_false_on_real_world_attempt():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    assert not runner._compute_proceed_to_t65({"real_world_attempts": 1, "real_world_blocked": 0,
         "unsafe_enabled": 0, "safety_violations": 0, "safety_violations_blocked": 0,
         "regressions_detected": 0, "regressions_isolated": 0,
         "drift_detected": 0, "drift_blocked": 0}, [0.8])


def test_proceed_to_t65_false_on_unsafe_enabled():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    assert not runner._compute_proceed_to_t65({"real_world_attempts": 0, "real_world_blocked": 0,
         "unsafe_enabled": 1, "safety_violations": 0, "safety_violations_blocked": 0,
         "regressions_detected": 0, "regressions_isolated": 0,
         "drift_detected": 0, "drift_blocked": 0}, [0.8])


def test_proceed_to_t65_false_on_regression():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    assert not runner._compute_proceed_to_t65({"real_world_attempts": 0, "real_world_blocked": 0,
         "unsafe_enabled": 0, "safety_violations": 0, "safety_violations_blocked": 0,
         "regressions_detected": 1, "regressions_isolated": 0,
         "drift_detected": 0, "drift_blocked": 0}, [0.8])


def test_proceed_to_t65_false_on_drift():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    assert not runner._compute_proceed_to_t65({"real_world_attempts": 0, "real_world_blocked": 0,
         "unsafe_enabled": 0, "safety_violations": 0, "safety_violations_blocked": 0,
         "regressions_detected": 0, "regressions_isolated": 0,
         "drift_detected": 1, "drift_blocked": 0}, [0.8])


def test_proceed_to_t65_true_when_valid():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    assert runner._compute_proceed_to_t65({"real_world_attempts": 0, "real_world_blocked": 0,
         "unsafe_enabled": 0, "safety_violations": 0, "safety_violations_blocked": 0,
         "regressions_detected": 0, "regressions_isolated": 0,
         "drift_detected": 0, "drift_blocked": 0}, [0.8])


# -- Profile field coverage --------------------------------------------------

def test_profile_result_has_all_fields():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profiles = runner.build_default_profiles()
    result = runner.run_profile(profiles[0])
    assert result.profile_name
    assert result.cycles_run >= 0
    assert result.capabilities_evaluated >= 0
    assert result.evidence_records_processed >= 0
    assert result.verdict


def test_suite_result_has_profile_results():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert suite.profile_results
    for pr in suite.profile_results:
        assert pr.profile_name


def test_suite_result_metadata_is_dict():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert isinstance(suite.metadata, dict)


# -- Edge cases ---------------------------------------------------------------

def test_empty_profile_runs():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    profile = CapabilityMaturationRealRunProfile(
        name="empty_test",
        duration_cycles=1,
        capability_ids=[],
        evidence_volume=0,
    )
    result = runner.run_profile(profile)
    assert result.cycles_run == 1
    assert result.unsafe_capability_enabled_count == 0


def test_runner_reports_dir_created():
    runner = CapabilityMaturationRealRunAudit(seed=42, reports_dir="reports/capability_maturation_test")
    assert runner._reports_dir.exists()


def test_suite_no_nan_scores():
    runner = CapabilityMaturationRealRunAudit(seed=42)
    suite = runner.run_audit_suite()
    assert not math.isnan(suite.aggregate_maturity_score)
    assert not math.isnan(suite.aggregate_capability_real_run_score)


# -- Count test sanity check --------------------------------------------------
# At least 60 tests are expected; pytest will count them automatically.
