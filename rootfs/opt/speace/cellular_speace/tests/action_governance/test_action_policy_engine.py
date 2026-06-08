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
from speace_core.cellular_brain.action_governance.action_policy_engine import (
    ActionPolicyEngine,
)


def make_risk(risk_class: ActionRiskClass) -> ActionRiskAssessment:
    return ActionRiskAssessment(
        assessment_id="r1",
        proposal_id="p1",
        risk_class=risk_class,
        aggregate_risk_score=0.5,
    )


def make_rev(reversible: bool = True) -> ReversibilityAssessment:
    return ReversibilityAssessment(
        assessment_id="rev1", proposal_id="p1", reversible=reversible, reversibility_score=0.8
    )


def test_evaluate_actuate_external_blocked():
    engine = ActionPolicyEngine()
    p = ExternalActionProposal(proposal_id="p1", action_type=ExternalActionType.ACTUATE_EXTERNAL)
    d = engine.evaluate_action_proposal(p, make_risk(ActionRiskClass.LOW), make_rev())
    assert d.governance_mode == ActionGovernanceMode.BLOCKED
    assert d.blocked is True
    assert d.allowed_for_real_execution is False


def test_evaluate_connect_external_blocked():
    engine = ActionPolicyEngine()
    p = ExternalActionProposal(proposal_id="p1", action_type=ExternalActionType.CONNECT_EXTERNAL)
    d = engine.evaluate_action_proposal(p, make_risk(ActionRiskClass.LOW), make_rev())
    assert d.governance_mode == ActionGovernanceMode.BLOCKED


def test_evaluate_real_execution_blocked():
    engine = ActionPolicyEngine()
    p = ExternalActionProposal(
        proposal_id="p1", action_type=ExternalActionType.RECOMMEND, requested_real_execution=True
    )
    d = engine.evaluate_action_proposal(p, make_risk(ActionRiskClass.LOW), make_rev())
    assert d.governance_mode == ActionGovernanceMode.BLOCKED


def test_evaluate_critical_blocked():
    engine = ActionPolicyEngine()
    p = ExternalActionProposal(proposal_id="p1", action_type=ExternalActionType.RESOURCE_SHIFT_SIMULATED)
    d = engine.evaluate_action_proposal(p, make_risk(ActionRiskClass.CRITICAL), make_rev())
    assert d.governance_mode == ActionGovernanceMode.BLOCKED


def test_evaluate_high_human_review():
    engine = ActionPolicyEngine()
    p = ExternalActionProposal(proposal_id="p1", action_type=ExternalActionType.RESOURCE_SHIFT_SIMULATED)
    d = engine.evaluate_action_proposal(p, make_risk(ActionRiskClass.HIGH), make_rev())
    assert d.governance_mode == ActionGovernanceMode.HUMAN_REVIEW_ONLY
    assert d.requires_human_review is True


def test_evaluate_moderate_simulation_only():
    engine = ActionPolicyEngine()
    p = ExternalActionProposal(proposal_id="p1", action_type=ExternalActionType.RECOMMEND)
    d = engine.evaluate_action_proposal(p, make_risk(ActionRiskClass.MODERATE), make_rev())
    assert d.governance_mode == ActionGovernanceMode.SIMULATION_ONLY


def test_evaluate_low_safe_noop():
    engine = ActionPolicyEngine()
    p = ExternalActionProposal(proposal_id="p1", action_type=ExternalActionType.OBSERVE_ONLY)
    d = engine.evaluate_action_proposal(p, make_risk(ActionRiskClass.LOW), make_rev())
    assert d.governance_mode == ActionGovernanceMode.SAFE_NOOP


def test_block_real_execution_attempt():
    engine = ActionPolicyEngine()
    p = ExternalActionProposal(proposal_id="p1", requested_real_execution=True)
    blocked, reason = engine.block_real_execution_attempt(p)
    assert blocked is True
    assert reason is not None


def test_verify_read_only_integrity():
    engine = ActionPolicyEngine()
    d = ActionGovernanceDecision(decision_id="d1", proposal_id="p1", allowed_for_real_execution=False)
    assert engine.verify_read_only_integrity(d) is True


def test_verify_bus_publication_safety():
    engine = ActionPolicyEngine()
    safe, _ = engine.verify_bus_publication_safety({"read_only": True})
    assert safe is True


def test_verify_bus_publication_unsafe_action_type():
    engine = ActionPolicyEngine()
    safe, reason = engine.verify_bus_publication_safety({"action_type": "actuate_external"})
    assert safe is False


def test_enforce_simulation_only():
    engine = ActionPolicyEngine()
    p = ExternalActionProposal(proposal_id="p1")
    d = engine.enforce_simulation_only(p)
    assert d.governance_mode == ActionGovernanceMode.SIMULATION_ONLY


def test_enforce_human_review_only():
    engine = ActionPolicyEngine()
    p = ExternalActionProposal(proposal_id="p1")
    d = engine.enforce_human_review_only(p)
    assert d.governance_mode == ActionGovernanceMode.HUMAN_REVIEW_ONLY
