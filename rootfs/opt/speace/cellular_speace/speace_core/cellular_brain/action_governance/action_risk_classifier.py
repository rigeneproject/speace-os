import uuid
from typing import Optional

from typing import Optional

from speace_core.cellular_brain.action_governance.action_governance_models import (
    ActionRiskAssessment,
    ActionRiskClass,
    ExternalActionProposal,
    ExternalActionType,
)


class ActionRiskClassifier:
    """Classifies action risk and detects external actuation/connection risks."""

    def classify_action_risk(self, proposal: ExternalActionProposal, risk_class_override: Optional[ActionRiskClass] = None) -> ActionRiskAssessment:
        assessment_id = f"risk_{uuid.uuid4().hex[:8]}"
        safety = self._compute_safety_risk(proposal)
        infra = self._compute_infrastructure_risk(proposal)
        energy = self._compute_energy_risk(proposal)
        rev = self._compute_reversibility_risk(proposal)
        unc = proposal.uncertainty_score
        ext = self._compute_externality_risk(proposal)
        aggregate = min(1.0, (safety + infra + energy + rev + unc + ext) / 6.0)
        blocked_reason = None
        if proposal.action_type in (ExternalActionType.ACTUATE_EXTERNAL, ExternalActionType.CONNECT_EXTERNAL):
            risk_class = ActionRiskClass.CRITICAL
            requires_human = True
            blocked_reason = "external_actuation_or_connection_attempt"
        elif risk_class_override is not None:
            risk_class = risk_class_override
            requires_human = risk_class in (ActionRiskClass.HIGH, ActionRiskClass.CRITICAL)
        else:
            risk_class = self._risk_class_from_score(aggregate)
            requires_human = risk_class in (ActionRiskClass.HIGH, ActionRiskClass.CRITICAL)
        return ActionRiskAssessment(
            assessment_id=assessment_id,
            proposal_id=proposal.proposal_id,
            risk_class=risk_class,
            safety_risk_score=safety,
            infrastructure_risk_score=infra,
            energy_risk_score=energy,
            reversibility_risk_score=rev,
            uncertainty_risk_score=unc,
            externality_risk_score=ext,
            aggregate_risk_score=aggregate,
            requires_human_review=requires_human,
            blocked_reason=blocked_reason,
        )

    def compute_aggregate_risk(self, assessments: list[ActionRiskAssessment]) -> float:
        if not assessments:
            return 0.0
        return min(1.0, sum(a.aggregate_risk_score for a in assessments) / len(assessments))

    def requires_human_review(self, assessment: ActionRiskAssessment) -> bool:
        return assessment.risk_class in (ActionRiskClass.HIGH, ActionRiskClass.CRITICAL)

    def detect_external_actuation_risk(self, proposal: ExternalActionProposal) -> bool:
        return proposal.action_type == ExternalActionType.ACTUATE_EXTERNAL

    def detect_connection_attempt_risk(self, proposal: ExternalActionProposal) -> bool:
        return proposal.action_type == ExternalActionType.CONNECT_EXTERNAL

    def _compute_safety_risk(self, proposal: ExternalActionProposal) -> float:
        if proposal.action_type == ExternalActionType.OBSERVE_ONLY:
            return 0.0
        if proposal.action_type in (ExternalActionType.ACTUATE_EXTERNAL, ExternalActionType.CONNECT_EXTERNAL):
            return 1.0
        return min(1.0, proposal.estimated_risk * 0.8 + proposal.estimated_urgency * 0.2)

    def _compute_infrastructure_risk(self, proposal: ExternalActionProposal) -> float:
        if proposal.action_type in (
            ExternalActionType.RECONFIGURE_SIMULATED,
            ExternalActionType.ISOLATE_SIMULATED,
        ):
            return min(1.0, proposal.estimated_risk + 0.15)
        if proposal.action_type in (ExternalActionType.ACTUATE_EXTERNAL, ExternalActionType.CONNECT_EXTERNAL):
            return 1.0
        return proposal.estimated_risk * 0.5

    def _compute_energy_risk(self, proposal: ExternalActionProposal) -> float:
        if proposal.action_type == ExternalActionType.RESOURCE_SHIFT_SIMULATED:
            return min(1.0, proposal.estimated_risk + 0.1)
        return proposal.estimated_risk * 0.3

    def _compute_reversibility_risk(self, proposal: ExternalActionProposal) -> float:
        if proposal.action_type == ExternalActionType.ISOLATE_SIMULATED:
            return 0.3
        if proposal.action_type in (ExternalActionType.ACTUATE_EXTERNAL, ExternalActionType.CONNECT_EXTERNAL):
            return 0.9
        return 0.1

    def _compute_externality_risk(self, proposal: ExternalActionProposal) -> float:
        if proposal.requested_real_execution:
            return 1.0
        return proposal.estimated_risk * 0.4

    def _risk_class_from_score(self, score: float) -> ActionRiskClass:
        if score < 0.25:
            return ActionRiskClass.LOW
        if score < 0.5:
            return ActionRiskClass.MODERATE
        if score < 0.75:
            return ActionRiskClass.HIGH
        return ActionRiskClass.CRITICAL
