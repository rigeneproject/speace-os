import pytest
from speace_core.cellular_brain.action_governance.action_governance_models import (
    ActionGovernanceAuditProfile,
    ActionGovernanceAuditResult,
    ActionGovernanceDecision,
    ActionGovernanceMode,
    ActionGovernanceSuiteResult,
    ActionReviewPacket,
    ActionRiskAssessment,
    ActionRiskClass,
    ExternalActionProposal,
    ExternalActionType,
    ReversibilityAssessment,
)


def test_external_action_type_values():
    assert ExternalActionType.OBSERVE_ONLY == "observe_only"
    assert ExternalActionType.ACTUATE_EXTERNAL == "actuate_external"
    assert ExternalActionType.CONNECT_EXTERNAL == "connect_external"
    assert ExternalActionType.UNKNOWN == "unknown"


def test_action_governance_mode_values():
    assert ActionGovernanceMode.BLOCKED == "blocked"
    assert ActionGovernanceMode.SIMULATION_ONLY == "simulation_only"
    assert ActionGovernanceMode.HUMAN_REVIEW_ONLY == "human_review_only"
    assert ActionGovernanceMode.SAFE_NOOP == "safe_noop"


def test_action_risk_class_values():
    assert ActionRiskClass.LOW == "low"
    assert ActionRiskClass.MODERATE == "moderate"
    assert ActionRiskClass.HIGH == "high"
    assert ActionRiskClass.CRITICAL == "critical"
    assert ActionRiskClass.UNKNOWN == "unknown"


def test_external_action_proposal_defaults():
    p = ExternalActionProposal(proposal_id="p1")
    assert p.simulated_only is True
    assert p.requested_real_execution is False
    assert p.action_type == ExternalActionType.UNKNOWN
    assert p.metadata == {}


def test_action_risk_assessment_defaults():
    a = ActionRiskAssessment(assessment_id="a1", proposal_id="p1")
    assert a.risk_class == ActionRiskClass.UNKNOWN
    assert a.requires_human_review is False
    assert a.aggregate_risk_score == 0.0


def test_reversibility_assessment_defaults():
    r = ReversibilityAssessment(assessment_id="r1", proposal_id="p1")
    assert r.reversible is True
    assert r.reversibility_score == 0.0
    assert r.irreversible_effect_detected is False


def test_action_governance_decision_defaults():
    d = ActionGovernanceDecision(decision_id="d1", proposal_id="p1")
    assert d.governance_mode == ActionGovernanceMode.BLOCKED
    assert d.allowed_for_real_execution is False
    assert d.blocked is False


def test_action_review_packet_defaults():
    pkt = ActionReviewPacket(packet_id="pkt1", proposal_id="p1", decision_id="d1")
    assert pkt.contains_real_execution_credentials is False
    assert pkt.human_review_required is False


def test_action_governance_audit_result_defaults():
    res = ActionGovernanceAuditResult(profile_name="test")
    assert res.verdict == "EXTERNAL_ACTION_GOVERNANCE_INSUFFICIENT_EVIDENCE"
    assert res.action_governance_sandbox_score == 0.0


def test_action_governance_suite_result_defaults():
    suite = ActionGovernanceSuiteResult()
    assert suite.aggregate_verdict == "EXTERNAL_ACTION_GOVERNANCE_INSUFFICIENT_EVIDENCE"
    assert suite.proceed_to_t62b is False
    assert suite.profile_results == []


def test_action_governance_audit_profile_defaults():
    profile = ActionGovernanceAuditProfile(name="test")
    assert profile.simulated_only is True
    assert profile.requested_real_execution is False
    assert profile.conflict_level == 0.0


def test_model_metadata_is_dict():
    p = ExternalActionProposal(proposal_id="p1", metadata={"key": "value"})
    assert isinstance(p.metadata, dict)
