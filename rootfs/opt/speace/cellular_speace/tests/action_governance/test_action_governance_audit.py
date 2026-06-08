import pytest
from pathlib import Path

from speace_core.cellular_brain.action_governance.action_governance_audit import (
    ActionGovernanceAudit,
)
from speace_core.cellular_brain.action_governance.action_governance_models import (
    ActionGovernanceAuditProfile,
    ActionGovernanceMode,
    ActionRiskClass,
    ExternalActionType,
)


def test_build_default_profiles():
    audit = ActionGovernanceAudit(seed=1)
    profiles = audit.build_default_profiles()
    assert len(profiles) >= 12
    names = {p.name for p in profiles}
    assert "action_governance_observe_only_baseline" in names
    assert "action_governance_full_sandbox_mix" in names


def test_run_profile_observe_only():
    audit = ActionGovernanceAudit(seed=1)
    profile = next(p for p in audit.build_default_profiles() if p.name == "action_governance_observe_only_baseline")
    result = audit.run_profile(profile)
    assert result.proposals_generated >= 1
    assert result.proposals_blocked == 0


def test_run_profile_actuate_external_blocked():
    audit = ActionGovernanceAudit(seed=1)
    profile = next(p for p in audit.build_default_profiles() if p.name == "action_governance_external_actuation_attempt_blocked")
    result = audit.run_profile(profile)
    assert result.real_execution_attempts >= 1
    assert result.real_execution_attempts_blocked == result.real_execution_attempts


def test_run_profile_connect_external_blocked():
    audit = ActionGovernanceAudit(seed=1)
    profile = next(p for p in audit.build_default_profiles() if p.name == "action_governance_external_connection_attempt_blocked")
    result = audit.run_profile(profile)
    assert result.real_execution_attempts >= 1
    assert result.real_execution_attempts_blocked == result.real_execution_attempts


def test_run_profile_high_uncertainty():
    audit = ActionGovernanceAudit(seed=1)
    profile = next(p for p in audit.build_default_profiles() if p.name == "action_governance_high_uncertainty_blocks_action")
    result = audit.run_profile(profile)
    assert result.proposals_generated >= 1


def test_run_profile_irreversible_blocked():
    audit = ActionGovernanceAudit(seed=1)
    profile = next(p for p in audit.build_default_profiles() if p.name == "action_governance_irreversible_action_blocked")
    result = audit.run_profile(profile)
    assert result.proposals_blocked >= 1


def test_run_profile_review_packet_generated():
    audit = ActionGovernanceAudit(seed=1)
    profile = next(p for p in audit.build_default_profiles() if p.name == "action_governance_review_packet_generated")
    result = audit.run_profile(profile)
    assert result.review_packets_generated >= 1


def test_run_profile_bus_publication():
    audit = ActionGovernanceAudit(seed=1)
    profile = next(p for p in audit.build_default_profiles() if p.name == "action_governance_bus_publication_read_only")
    result = audit.run_profile(profile)
    assert result.bus_publications >= 1
    assert result.unsafe_bus_publications_blocked == 0


def test_run_profile_safety_hazard():
    audit = ActionGovernanceAudit(seed=1)
    profile = next(p for p in audit.build_default_profiles() if p.name == "action_governance_safety_hazard_response")
    result = audit.run_profile(profile)
    assert result.proposals_generated >= 1
    assert result.real_execution_attempts == 0


def test_run_profile_full_sandbox_mix():
    audit = ActionGovernanceAudit(seed=1)
    profile = next(p for p in audit.build_default_profiles() if p.name == "action_governance_full_sandbox_mix")
    result = audit.run_profile(profile)
    assert result.proposals_generated >= 1


def test_run_audit_suite():
    audit = ActionGovernanceAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.profile_count >= 12
    assert 0.0 <= suite.aggregate_action_governance_sandbox_score <= 1.0


def test_suite_verdict_not_real_execution_attempted():
    audit = ActionGovernanceAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.aggregate_verdict != "ACTION_GOVERNANCE_REAL_EXECUTION_ATTEMPTED"


def test_suite_real_execution_blocked():
    audit = ActionGovernanceAudit(seed=1)
    suite = audit.run_audit_suite()
    if suite.total_real_execution_attempts > 0:
        assert suite.total_real_execution_attempts_blocked == suite.total_real_execution_attempts


def test_suite_unsafe_actions_blocked():
    audit = ActionGovernanceAudit(seed=1)
    suite = audit.run_audit_suite()
    if suite.total_unsafe_action_attempts > 0:
        assert suite.total_unsafe_action_attempts_blocked == suite.total_unsafe_action_attempts


def test_suite_read_only_integrity():
    audit = ActionGovernanceAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_read_only_violations == 0


def test_suite_unsafe_bus_blocked():
    audit = ActionGovernanceAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_unsafe_bus_publications_blocked == 0


def test_suite_human_review_generated():
    audit = ActionGovernanceAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_review_packets_generated >= 1


def test_suite_score_clamped():
    audit = ActionGovernanceAudit(seed=1)
    suite = audit.run_audit_suite()
    assert 0.0 <= suite.aggregate_action_governance_sandbox_score <= 1.0


def test_json_report_created():
    audit = ActionGovernanceAudit(seed=1)
    suite = audit.run_audit_suite()
    reports_dir = Path("reports/action_governance")
    assert any(reports_dir.glob("t62_audit_*.json"))


def test_markdown_report_created():
    audit = ActionGovernanceAudit(seed=1)
    suite = audit.run_audit_suite()
    reports_dir = Path("reports/action_governance")
    assert any(reports_dir.glob("t62_audit_*.md"))


def test_compute_aggregate_verdict_validated():
    audit = ActionGovernanceAudit(seed=1)
    v = audit._compute_aggregate_verdict(0.75, 0.9, 1, 1, 1, 1, 1, 0, 0)
    assert v == "EXTERNAL_ACTION_GOVERNANCE_SANDBOX_VALIDATED"


def test_compute_aggregate_verdict_safe_but_passive():
    audit = ActionGovernanceAudit(seed=1)
    v = audit._compute_aggregate_verdict(0.65, 0.9, 1, 1, 0, 0, 0, 0, 0)
    assert v == "EXTERNAL_ACTION_GOVERNANCE_SAFE_BUT_PASSIVE"


def test_compute_aggregate_verdict_insufficient_evidence():
    audit = ActionGovernanceAudit(seed=1)
    v = audit._compute_aggregate_verdict(0.5, 0.9, 0, 0, 0, 0, 0, 0, 0)
    assert v == "EXTERNAL_ACTION_GOVERNANCE_INSUFFICIENT_EVIDENCE"


def test_compute_aggregate_verdict_read_only_violation():
    audit = ActionGovernanceAudit(seed=1)
    v = audit._compute_aggregate_verdict(0.8, 0.9, 1, 1, 1, 1, 1, 1, 0)
    assert v == "ACTION_GOVERNANCE_READ_ONLY_VIOLATION"


def test_deterministic_seed_reproducibility():
    import random
    state = random.getstate()
    audit1 = ActionGovernanceAudit(seed=42)
    suite1 = audit1.run_audit_suite()
    random.setstate(state)
    audit2 = ActionGovernanceAudit(seed=42)
    suite2 = audit2.run_audit_suite()
    assert suite1.aggregate_verdict == suite2.aggregate_verdict
    assert suite1.profile_count == suite2.profile_count


def test_profile_verdict_real_execution_attempted():
    audit = ActionGovernanceAudit(seed=1)
    profile = ActionGovernanceAuditProfile(
        name="real_exec_test", action_type=ExternalActionType.ACTUATE_EXTERNAL, requested_real_execution=True
    )
    result = audit.run_profile(profile)
    assert result.real_execution_attempts_blocked == result.real_execution_attempts
    assert result.verdict in ("EXTERNAL_ACTION_GOVERNANCE_SAFE_BUT_PASSIVE", "EXTERNAL_ACTION_GOVERNANCE_SANDBOX_VALIDATED")


def test_profile_verdict_read_only_violation():
    audit = ActionGovernanceAudit(seed=1)
    profile = ActionGovernanceAuditProfile(name="rov_test")
    result = audit.run_profile(profile)
    assert result.read_only_violations == 0
    assert result.verdict != "ACTION_GOVERNANCE_READ_ONLY_VIOLATION"


def test_profile_scores_in_range():
    audit = ActionGovernanceAudit(seed=1)
    suite = audit.run_audit_suite()
    for pr in suite.profile_results:
        assert 0.0 <= pr.action_governance_sandbox_score <= 1.0


def test_suite_metadata_dict():
    audit = ActionGovernanceAudit(seed=1)
    suite = audit.run_audit_suite()
    assert isinstance(suite.metadata, dict)
