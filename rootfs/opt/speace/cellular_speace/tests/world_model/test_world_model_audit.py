import pytest
from speace_core.cellular_brain.world_model.world_model_audit import WorldModelAudit


def test_run_audit_suite_profile_count():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.profile_count >= 12
    assert len(suite.profile_results) == suite.profile_count


def test_run_audit_suite_snapshots_generated():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_snapshots_generated >= suite.profile_count


def test_run_audit_suite_scenarios_built():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_scenarios_built >= suite.profile_count


def test_run_audit_suite_simulations_run():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_simulations_run >= suite.profile_count


def test_run_audit_suite_reports_exist():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    import json
    from pathlib import Path
    reports_dir = Path("reports/world_model")
    json_files = list(reports_dir.glob("t61_audit_*.json"))
    assert len(json_files) >= 1
    data = json.loads(json_files[-1].read_text(encoding="utf-8"))
    assert data["aggregate_verdict"] == suite.aggregate_verdict


def test_aggregate_verdict_not_real_action_attempted():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.aggregate_verdict != "WORLD_MODEL_REAL_ACTION_ATTEMPTED"


def test_proceed_to_t61b_boolean():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    assert isinstance(suite.proceed_to_t61b, bool)


def test_world_model_baseline_profile():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    baseline = next((p for p in suite.profile_results if p.profile_name == "world_model_baseline_snapshot"), None)
    assert baseline is not None
    assert baseline.snapshots_generated >= 1


def test_world_model_multi_entity_environment_profile():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    p = next((pr for pr in suite.profile_results if pr.profile_name == "world_model_multi_entity_environment"), None)
    assert p is not None


def test_world_model_energy_scarcity_profile():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    p = next((pr for pr in suite.profile_results if pr.profile_name == "world_model_energy_scarcity_scenario"), None)
    assert p is not None


def test_world_model_infrastructure_stress_profile():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    p = next((pr for pr in suite.profile_results if pr.profile_name == "world_model_infrastructure_stress_scenario"), None)
    assert p is not None


def test_world_model_safety_hazard_profile():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    p = next((pr for pr in suite.profile_results if pr.profile_name == "world_model_safety_hazard_scenario"), None)
    assert p is not None


def test_world_model_conflicting_entities_profile():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    p = next((pr for pr in suite.profile_results if pr.profile_name == "world_model_conflicting_entities"), None)
    assert p is not None
    assert p.contradictions_detected >= 1


def test_world_model_constraint_violation_profile():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    p = next((pr for pr in suite.profile_results if pr.profile_name == "world_model_constraint_violation_detection"), None)
    assert p is not None
    assert p.constraint_violations_detected >= 1


def test_world_model_causal_chain_profile():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    p = next((pr for pr in suite.profile_results if pr.profile_name == "world_model_causal_chain_prediction"), None)
    assert p is not None


def test_world_model_uncertainty_growth_profile():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    p = next((pr for pr in suite.profile_results if pr.profile_name == "world_model_uncertainty_growth"), None)
    assert p is not None


def test_world_model_simulated_action_blocked_profile():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    p = next((pr for pr in suite.profile_results if pr.profile_name == "world_model_simulated_action_blocked"), None)
    assert p is not None
    assert p.unsafe_simulated_actions_blocked >= 1
    assert p.real_action_attempts_blocked >= 1


def test_world_model_bus_publication_profile():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    p = next((pr for pr in suite.profile_results if pr.profile_name == "world_model_bus_publication_read_only"), None)
    assert p is not None
    assert p.bus_publications >= 1


def test_world_model_full_sandbox_mix_profile():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    p = next((pr for pr in suite.profile_results if pr.profile_name == "world_model_full_sandbox_mix"), None)
    assert p is not None


def test_sandbox_score_clamped():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    assert 0.0 <= suite.aggregate_world_model_sandbox_score <= 1.0


def test_read_only_integrity_perfect():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.aggregate_read_only_integrity_score == 1.0


def test_deterministic_seed_reproducibility():
    audit1 = WorldModelAudit(seed=42)
    suite1 = audit1.run_audit_suite()
    import random
    state = random.getstate()
    audit2 = WorldModelAudit(seed=42)
    suite2 = audit2.run_audit_suite()
    random.setstate(state)
    assert suite1.aggregate_verdict == suite2.aggregate_verdict
    assert suite1.profile_count == suite2.profile_count
