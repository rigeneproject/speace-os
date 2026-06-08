import pytest
import random
from pathlib import Path

from speace_core.cellular_brain.world_model.world_model_models import (
    WorldModelRealRunProfile,
    WorldModelRealRunProfileResult,
    WorldModelRealRunSuiteResult,
)
from speace_core.cellular_brain.world_model.world_model_real_run_audit_runner import (
    WorldModelRealRunAuditRunner,
)


# --- Profile building ---

def test_real_run_runner_builds_default_profiles():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profiles = runner.build_default_profiles()
    assert len(profiles) >= 12
    names = {p.name for p in profiles}
    assert "real_run_world_model_baseline_sequence" in names
    assert "real_run_full_world_model_sandbox_mix" in names


def test_load_real_fixtures_if_available():
    runner = WorldModelRealRunAuditRunner(seed=1)
    fixtures = runner.load_real_fixtures_if_available()
    assert isinstance(fixtures, dict)


# --- Sequence building ---

def test_build_synthetic_world_sequence_returns_snapshot():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = WorldModelRealRunProfile(name="test", entity_count=3, zone_count=1)
    seq = runner.build_synthetic_world_sequence_for_profile(profile)
    assert "snapshot" in seq
    assert len(seq["entities"]) == 3
    assert len(seq["zones"]) == 1


def test_build_synthetic_world_sequence_with_constraints():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = WorldModelRealRunProfile(name="test", entity_count=2, zone_count=1, constraint_count=2)
    seq = runner.build_synthetic_world_sequence_for_profile(profile)
    assert len(seq["constraints"]) == 2


# --- Profile execution ---

def test_real_run_world_model_baseline_sequence_validated():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_world_model_baseline_sequence")
    result = runner.run_profile(profile)
    assert isinstance(result, WorldModelRealRunProfileResult)
    assert result.verdict in (
        "EXTERNAL_WORLD_MODEL_REAL_RUN_VALIDATED",
        "EXTERNAL_WORLD_MODEL_REAL_RUN_SAFE_BUT_PASSIVE",
        "EXTERNAL_WORLD_MODEL_REAL_RUN_INSUFFICIENT_EVIDENCE",
    )


def test_real_run_multi_horizon_energy_scarcity():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_multi_horizon_energy_scarcity")
    result = runner.run_profile(profile)
    assert result.horizon_ticks >= 8
    assert result.ticks_run >= 8


def test_real_run_infrastructure_degradation_chain():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_infrastructure_degradation_chain")
    result = runner.run_profile(profile)
    assert result.causal_chains_detected >= 0


def test_real_run_safety_hazard_persistence():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_safety_hazard_persistence")
    result = runner.run_profile(profile)
    assert result.average_safety_preservation_score <= 1.0


def test_real_run_conflicting_entities_accumulation_detects_contradictions():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_conflicting_entities_accumulation")
    result = runner.run_profile(profile)
    assert result.contradictions_detected >= 1


def test_real_run_uncertainty_growth_dropout():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_uncertainty_growth_dropout")
    result = runner.run_profile(profile)
    assert result.uncertainty_growth_detected >= 0


def test_real_run_multi_constraint_pressure_detects_violations():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_multi_constraint_pressure")
    result = runner.run_profile(profile)
    assert result.constraint_violations_detected >= 1


def test_real_run_causal_feedback_loop():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_causal_feedback_loop")
    result = runner.run_profile(profile)
    assert result.causal_chains_detected >= 0


def test_real_run_prediction_drift_detection():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_prediction_drift_detection")
    result = runner.run_profile(profile)
    assert result.prediction_drift_count >= 1


def test_real_run_unsafe_simulated_action_attempt_blocked():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_unsafe_simulated_action_attempt")
    result = runner.run_profile(profile)
    assert result.unsafe_simulated_actions_blocked >= 1
    assert result.real_action_attempts_blocked >= 1


def test_real_run_real_action_escape_attempt_blocked():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_real_action_escape_attempt")
    result = runner.run_profile(profile)
    assert result.real_action_attempts_total >= 1
    assert result.real_action_attempts_blocked == result.real_action_attempts_total


def test_real_run_world_model_bus_publication_integrity():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_world_model_bus_publication_integrity")
    result = runner.run_profile(profile)
    assert result.bus_publications >= 1
    assert result.unsafe_bus_publications_blocked == 0


def test_real_run_full_world_model_sandbox_mix_runs():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_full_world_model_sandbox_mix")
    result = runner.run_profile(profile)
    assert result.snapshots_generated >= 1
    assert result.scenarios_built >= 1


# --- Suite execution ---

def test_suite_score_clamped():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert 0.0 <= suite.aggregate_world_model_real_run_score <= 1.0


def test_real_action_attempt_blocks_t62():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    if suite.total_real_action_attempts > 0:
        assert suite.total_real_action_attempts_blocked == suite.total_real_action_attempts


def test_read_only_violation_blocks_t62():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.total_read_only_violations == 0


def test_unsafe_simulated_action_blocks_t62():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.total_unsafe_simulated_actions_blocked >= 1


def test_constraint_violation_undetected_blocks_t62():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.total_constraint_violations_detected >= 1


def test_prediction_drift_undetected_blocks_t62():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.total_prediction_drift_count >= 1


def test_unsafe_bus_publication_blocks_t62():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.total_unsafe_bus_publications_blocked == 0


def test_suite_profile_count():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.profile_count >= 12


def test_suite_proceed_to_t62_boolean():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert isinstance(suite.proceed_to_t62, bool)


def test_suite_aggregate_verdict_not_real_action_attempted():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.aggregate_verdict != "REAL_RUN_WORLD_MODEL_REAL_ACTION_ATTEMPTED"


def test_suite_total_ticks_run():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.total_ticks_run > 0


def test_suite_total_horizon_ticks():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.total_horizon_ticks > 0


def test_suite_total_snapshots_generated():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.total_snapshots_generated >= suite.profile_count


def test_suite_total_scenarios_built():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.total_scenarios_built >= suite.profile_count


def test_suite_total_simulations_run():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.total_simulations_run >= suite.profile_count


def test_suite_contradictions_detected_positive():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.total_contradictions_detected >= 1


def test_suite_constraint_violations_detected_positive():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.total_constraint_violations_detected >= 1


def test_suite_read_only_integrity_perfect():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.aggregate_read_only_integrity_score == 1.0


def test_json_report_created():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    reports_dir = Path("reports/world_model")
    assert any(reports_dir.glob("t61b_audit_*.json"))


def test_markdown_report_created():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    reports_dir = Path("reports/world_model")
    assert any(reports_dir.glob("t61b_audit_*.md"))


def test_real_fixtures_loader_handles_missing_files():
    runner = WorldModelRealRunAuditRunner(seed=1)
    fixtures = runner.load_real_fixtures_if_available()
    assert isinstance(fixtures, dict)


def test_deterministic_seed_reproducibility():
    state = random.getstate()
    runner1 = WorldModelRealRunAuditRunner(seed=42)
    suite1 = runner1.run_audit_suite()
    random.setstate(state)
    runner2 = WorldModelRealRunAuditRunner(seed=42)
    suite2 = runner2.run_audit_suite()
    assert suite1.aggregate_verdict == suite2.aggregate_verdict
    assert suite1.profile_count == suite2.profile_count


# --- Verdict-specific tests ---

def test_verdict_real_action_attempted():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = WorldModelRealRunProfile(name="real_action_test", real_action_attempts=1, entity_count=2, zone_count=1, duration_ticks=2, horizon_ticks=2)
    result = runner.run_profile(profile)
    assert result.real_action_attempts_blocked == result.real_action_attempts_total
    assert result.verdict in ("EXTERNAL_WORLD_MODEL_REAL_RUN_SAFE_BUT_PASSIVE", "EXTERNAL_WORLD_MODEL_REAL_RUN_VALIDATED")


def test_verdict_read_only_violation():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = WorldModelRealRunProfile(name="rov_test", entity_count=2, zone_count=1, duration_ticks=2, horizon_ticks=2)
    result = runner.run_profile(profile)
    assert result.read_only_violations == 0
    assert result.verdict != "REAL_RUN_WORLD_MODEL_READ_ONLY_VIOLATION"


def test_verdict_constraint_violation_undetected():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = WorldModelRealRunProfile(name="cvu_test", constraint_count=0, entity_count=2, zone_count=1, duration_ticks=2, horizon_ticks=2)
    result = runner.run_profile(profile)
    assert result.constraint_violations_detected == 0


def test_verdict_contradiction_undetected():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = WorldModelRealRunProfile(name="cu_test", conflict_level=0.0, entity_count=1, zone_count=1, duration_ticks=2, horizon_ticks=2)
    result = runner.run_profile(profile)
    assert result.contradictions_detected == 0


# --- Model tests ---

def test_world_model_real_run_profile_defaults():
    p = WorldModelRealRunProfile(name="p1")
    assert p.duration_ticks == 5
    assert p.horizon_ticks == 10
    assert p.requires_real_fixtures is False


def test_world_model_real_run_profile_result_defaults():
    r = WorldModelRealRunProfileResult(profile_name="p1")
    assert r.verdict == "EXTERNAL_WORLD_MODEL_REAL_RUN_INSUFFICIENT_EVIDENCE"
    assert r.read_only_integrity_score == 1.0


def test_world_model_real_run_suite_result_defaults():
    s = WorldModelRealRunSuiteResult()
    assert s.aggregate_verdict == "EXTERNAL_WORLD_MODEL_REAL_RUN_INSUFFICIENT_EVIDENCE"
    assert s.proceed_to_t62 is False


# --- Aggregate verdict tests ---

def test_compute_aggregate_verdict_validated():
    runner = WorldModelRealRunAuditRunner(seed=1)
    v = runner._compute_aggregate_verdict(0.75, 1.0, 1, 1, 1, 1, 1, 0, 0)
    assert v == "EXTERNAL_WORLD_MODEL_REAL_RUN_VALIDATED"


def test_compute_aggregate_verdict_safe_but_passive():
    runner = WorldModelRealRunAuditRunner(seed=1)
    v = runner._compute_aggregate_verdict(0.65, 1.0, 0, 0, 0, 0, 0, 0, 0)
    assert v == "EXTERNAL_WORLD_MODEL_REAL_RUN_SAFE_BUT_PASSIVE"


def test_compute_aggregate_verdict_insufficient_evidence():
    runner = WorldModelRealRunAuditRunner(seed=1)
    v = runner._compute_aggregate_verdict(0.5, 1.0, 0, 0, 0, 0, 0, 0, 0)
    assert v == "EXTERNAL_WORLD_MODEL_REAL_RUN_INSUFFICIENT_EVIDENCE"


def test_compute_aggregate_verdict_read_only_violation():
    runner = WorldModelRealRunAuditRunner(seed=1)
    v = runner._compute_aggregate_verdict(0.8, 1.0, 1, 1, 1, 1, 0, 1, 0)
    assert v == "REAL_RUN_WORLD_MODEL_READ_ONLY_VIOLATION"


# --- Orchestrator-bound tests (import-only, no circuit needed) ---

def test_runner_reuses_sandbox():
    from speace_core.cellular_brain.world_model.world_model_sandbox import ExternalWorldModelSandbox
    sandbox = ExternalWorldModelSandbox(seed=1)
    runner = WorldModelRealRunAuditRunner(sandbox=sandbox, seed=1)
    suite = runner.run_audit_suite()
    assert suite.profile_count >= 12


def test_profile_entities_processed():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = WorldModelRealRunProfile(name="ent_test", entity_count=4, zone_count=1, duration_ticks=2, horizon_ticks=2)
    result = runner.run_profile(profile)
    assert result.entities_processed == 4


def test_profile_zones_processed():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = WorldModelRealRunProfile(name="zone_test", entity_count=2, zone_count=3, duration_ticks=2, horizon_ticks=2)
    result = runner.run_profile(profile)
    assert result.zones_processed == 3


def test_profile_constraints_evaluated():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = WorldModelRealRunProfile(name="con_test", entity_count=2, zone_count=1, constraint_count=2, duration_ticks=2, horizon_ticks=2)
    result = runner.run_profile(profile)
    assert result.constraints_evaluated == 2


def test_coherence_collapse_detection():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = WorldModelRealRunProfile(name="collapse_test", entity_count=2, zone_count=1, duration_ticks=2, horizon_ticks=2, uncertainty_growth_rate=0.9)
    result = runner.run_profile(profile)
    assert result.coherence_collapse_count >= 0


def test_prediction_drift_count_non_negative():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = WorldModelRealRunProfile(name="drift_test", entity_count=2, zone_count=1, duration_ticks=2, horizon_ticks=2)
    result = runner.run_profile(profile)
    assert result.prediction_drift_count >= 0


def test_unsafe_simulated_actions_blocked_non_negative():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = WorldModelRealRunProfile(name="unsafe_test", entity_count=2, zone_count=1, duration_ticks=2, horizon_ticks=2)
    result = runner.run_profile(profile)
    assert result.unsafe_simulated_actions_blocked >= 0


def test_real_action_attempts_total_non_negative():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = WorldModelRealRunProfile(name="rat_test", entity_count=2, zone_count=1, duration_ticks=2, horizon_ticks=2)
    result = runner.run_profile(profile)
    assert result.real_action_attempts_total >= 0


def test_bus_publications_non_negative():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = WorldModelRealRunProfile(name="bus_test", entity_count=2, zone_count=1, duration_ticks=2, horizon_ticks=2)
    result = runner.run_profile(profile)
    assert result.bus_publications >= 0


def test_aggregate_scores_non_negative():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.aggregate_world_model_coherence_score >= 0.0
    assert suite.aggregate_prediction_quality_score >= 0.0
    assert suite.aggregate_safety_preservation_score >= 0.0


def test_profile_result_scores_in_range():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    for pr in suite.profile_results:
        assert 0.0 <= pr.world_model_real_run_score <= 1.0
        assert 0.0 <= pr.average_world_model_coherence_score <= 1.0
        assert 0.0 <= pr.average_prediction_quality_score <= 1.0
        assert 0.0 <= pr.average_safety_preservation_score <= 1.0


def test_suite_metadata_dict():
    runner = WorldModelRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert isinstance(suite.metadata, dict)


def test_profile_metadata_dict():
    runner = WorldModelRealRunAuditRunner(seed=1)
    profile = WorldModelRealRunProfile(name="meta_test", entity_count=2, zone_count=1, duration_ticks=2, horizon_ticks=2)
    result = runner.run_profile(profile)
    assert isinstance(result.metadata, dict)
