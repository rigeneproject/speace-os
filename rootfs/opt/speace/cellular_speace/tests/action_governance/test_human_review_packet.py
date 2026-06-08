import pytest
from speace_core.cellular_brain.action_governance.action_governance_models import (
    ActionGovernanceDecision,
    ActionGovernanceMode,
    ActionRiskAssessment,
    ActionRiskClass,
    ExternalActionProposal,
    ExternalActionType,
    ReversibilityAssessment,
)
from speace_core.cellular_brain.action_governance.human_review_packet import (
    HumanReviewPacketBuilder,
)


def test_build_review_packet():
    builder = HumanReviewPacketBuilder()
    proposal = ExternalActionProposal(proposal_id="p1", action_type=ExternalActionType.RECOMMEND)
    risk = ActionRiskAssessment(assessment_id="r1", proposal_id="p1", risk_class=ActionRiskClass.HIGH)
    rev = ReversibilityAssessment(assessment_id="rev1", proposal_id="p1", reversible=True)
    decision = ActionGovernanceDecision(
        decision_id="d1", proposal_id="p1", governance_mode=ActionGovernanceMode.HUMAN_REVIEW_ONLY, requires_human_review=True
    )
    impact = {"proposal_id": "p1"}
    packet = builder.build_review_packet(proposal, risk, rev, decision, impact)
    assert packet.packet_id.startswith("pkt_")
    assert packet.proposal_id == "p1"
    assert packet.human_review_required is True
    assert packet.contains_real_execution_credentials is False


def test_verify_no_execution_payload_safe():
    builder = HumanReviewPacketBuilder()
    packet = builder.build_review_packet(
        ExternalActionProposal(proposal_id="p1"),
        ActionRiskAssessment(assessment_id="r1", proposal_id="p1"),
        ReversibilityAssessment(assessment_id="rev1", proposal_id="p1"),
        ActionGovernanceDecision(decision_id="d1", proposal_id="p1"),
        {},
    )
    unsafe, reason = builder.verify_no_execution_payload(packet)
    assert unsafe is False


def test_verify_no_execution_payload_unsafe():
    builder = HumanReviewPacketBuilder()
    packet = builder.build_review_packet(
        ExternalActionProposal(proposal_id="p1"),
        ActionRiskAssessment(assessment_id="r1", proposal_id="p1"),
        ReversibilityAssessment(assessment_id="rev1", proposal_id="p1"),
        ActionGovernanceDecision(decision_id="d1", proposal_id="p1"),
        {"api_endpoint": "http://example.com"},
    )
    unsafe, reason = builder.verify_no_execution_payload(packet)
    assert unsafe is True


def test_export_packet_dict():
    builder = HumanReviewPacketBuilder()
    packet = builder.build_review_packet(
        ExternalActionProposal(proposal_id="p1"),
        ActionRiskAssessment(assessment_id="r1", proposal_id="p1"),
        ReversibilityAssessment(assessment_id="rev1", proposal_id="p1"),
        ActionGovernanceDecision(decision_id="d1", proposal_id="p1"),
        {},
    )
    d = builder.export_packet_dict(packet)
    assert isinstance(d, dict)
    assert d["proposal_id"] == "p1"


def test_sanitize_packet_with_unsafe():
    builder = HumanReviewPacketBuilder()
    packet = builder.build_review_packet(
        ExternalActionProposal(proposal_id="p1"),
        ActionRiskAssessment(assessment_id="r1", proposal_id="p1"),
        ReversibilityAssessment(assessment_id="rev1", proposal_id="p1"),
        ActionGovernanceDecision(decision_id="d1", proposal_id="p1"),
        {"api_endpoint": "http://example.com"},
    )
    sanitized = builder.sanitize_packet(packet)
    assert "SANITIZED" in sanitized.summary
