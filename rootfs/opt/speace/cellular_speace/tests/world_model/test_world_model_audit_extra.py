import pytest
from speace_core.cellular_brain.world_model.world_model_audit import WorldModelAudit


def test_audit_suite_generates_json_and_md():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    from pathlib import Path
    reports_dir = Path("reports/world_model")
    assert any(reports_dir.glob("t61_audit_*.json"))
    assert any(reports_dir.glob("t61_audit_*.md"))


def test_audit_profile_result_has_scores():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    for pr in suite.profile_results:
        assert isinstance(pr.world_model_sandbox_score, float)
        assert 0.0 <= pr.world_model_sandbox_score <= 1.0


def test_audit_aggregate_scores_non_negative():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.aggregate_world_model_coherence_score >= 0.0
    assert suite.aggregate_prediction_quality_score >= 0.0
    assert suite.aggregate_safety_preservation_score >= 0.0


def test_audit_real_action_attempts_blocked_non_negative():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_real_action_attempts_blocked >= 0


def test_audit_read_only_violations_zero():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_read_only_violations == 0


def test_audit_unsafe_simulated_actions_blocked_positive():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_unsafe_simulated_actions_blocked >= 1


def test_audit_causal_chains_detected_non_negative():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_causal_chains_detected >= 0


def test_audit_contradictions_detected_positive():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_contradictions_detected >= 1


def test_audit_constraint_violations_detected_positive():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_constraint_violations_detected >= 1


def test_audit_bus_publications_positive():
    audit = WorldModelAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_bus_publications >= 1
