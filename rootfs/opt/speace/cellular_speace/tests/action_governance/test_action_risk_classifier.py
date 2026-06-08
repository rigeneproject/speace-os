import pytest
from speace_core.cellular_brain.action_governance.action_governance_models import (
    ActionRiskClass,
    ExternalActionProposal,
    ExternalActionType,
)
from speace_core.cellular_brain.action_governance.action_risk_classifier import (
    ActionRiskClassifier,
)


def test_classify_observe_only_low_risk():
    classifier = ActionRiskClassifier()
    p = ExternalActionProposal(
        proposal_id="p1", action_type=ExternalActionType.OBSERVE_ONLY, estimated_risk=0.0
    )
    assessment = classifier.classify_action_risk(p)
    assert assessment.risk_class == ActionRiskClass.LOW
    assert assessment.requires_human_review is False


def test_classify_actuate_external_critical():
    classifier = ActionRiskClassifier()
    p = ExternalActionProposal(
        proposal_id="p1", action_type=ExternalActionType.ACTUATE_EXTERNAL, estimated_risk=0.5
    )
    assessment = classifier.classify_action_risk(p)
    assert assessment.risk_class == ActionRiskClass.CRITICAL
    assert assessment.blocked_reason is not None


def test_classify_connect_external_critical():
    classifier = ActionRiskClassifier()
    p = ExternalActionProposal(
        proposal_id="p1", action_type=ExternalActionType.CONNECT_EXTERNAL, estimated_risk=0.5
    )
    assessment = classifier.classify_action_risk(p)
    assert assessment.risk_class == ActionRiskClass.CRITICAL


def test_detect_external_actuation_risk():
    classifier = ActionRiskClassifier()
    p = ExternalActionProposal(proposal_id="p1", action_type=ExternalActionType.ACTUATE_EXTERNAL)
    assert classifier.detect_external_actuation_risk(p) is True


def test_detect_connection_attempt_risk():
    classifier = ActionRiskClassifier()
    p = ExternalActionProposal(proposal_id="p1", action_type=ExternalActionType.CONNECT_EXTERNAL)
    assert classifier.detect_connection_attempt_risk(p) is True


def test_requires_human_review_for_high():
    classifier = ActionRiskClassifier()
    assessment = classifier.classify_action_risk(
        ExternalActionProposal(proposal_id="p1", action_type=ExternalActionType.ISOLATE_SIMULATED, estimated_risk=1.0, estimated_urgency=1.0, uncertainty_score=1.0)
    )
    assert assessment.risk_class == ActionRiskClass.HIGH
    assert classifier.requires_human_review(assessment) is True


def test_compute_aggregate_risk():
    classifier = ActionRiskClassifier()
    a1 = classifier.classify_action_risk(
        ExternalActionProposal(proposal_id="p1", action_type=ExternalActionType.OBSERVE_ONLY)
    )
    a2 = classifier.classify_action_risk(
        ExternalActionProposal(proposal_id="p2", action_type=ExternalActionType.RECOMMEND, estimated_risk=0.3)
    )
    agg = classifier.compute_aggregate_risk([a1, a2])
    assert 0.0 <= agg <= 1.0


def test_classify_resource_shift_moderate():
    classifier = ActionRiskClassifier()
    p = ExternalActionProposal(
        proposal_id="p1", action_type=ExternalActionType.RESOURCE_SHIFT_SIMULATED, estimated_risk=0.55
    )
    assessment = classifier.classify_action_risk(p)
    assert assessment.risk_class == ActionRiskClass.MODERATE
