import uuid

from speace_core.cellular_brain.action_governance.action_governance_models import (
    ExternalActionProposal,
    ExternalActionType,
    ReversibilityAssessment,
)


class ReversibilityAnalyzer:
    """Assesses reversibility of simulated action proposals."""

    def assess_reversibility(self, proposal: ExternalActionProposal) -> ReversibilityAssessment:
        rev_score = self.compute_reversibility_score(proposal)
        irreversible = self.detect_irreversible_effects(proposal)
        rollback = not irreversible
        complexity = self.estimate_rollback_complexity(proposal)
        return ReversibilityAssessment(
            assessment_id=f"rev_{uuid.uuid4().hex[:8]}",
            proposal_id=proposal.proposal_id,
            reversible=not irreversible,
            reversibility_score=rev_score,
            rollback_available=rollback,
            rollback_complexity_score=complexity,
            irreversible_effect_detected=irreversible,
        )

    def compute_reversibility_score(self, proposal: ExternalActionProposal) -> float:
        if proposal.action_type == ExternalActionType.OBSERVE_ONLY:
            return 1.0
        if proposal.action_type in (ExternalActionType.ACTUATE_EXTERNAL, ExternalActionType.CONNECT_EXTERNAL):
            return 0.0
        if proposal.action_type == ExternalActionType.ISOLATE_SIMULATED:
            return 0.5
        if proposal.action_type == ExternalActionType.RESOURCE_SHIFT_SIMULATED:
            return 0.7
        if proposal.action_type in (ExternalActionType.RECONFIGURE_SIMULATED, ExternalActionType.THROTTLE_SIMULATED):
            return 0.6
        return 0.8

    def detect_irreversible_effects(self, proposal: ExternalActionProposal) -> bool:
        if proposal.action_type in (ExternalActionType.ACTUATE_EXTERNAL, ExternalActionType.CONNECT_EXTERNAL):
            return True
        if proposal.action_type == ExternalActionType.ISOLATE_SIMULATED and proposal.estimated_risk > 0.6:
            return True
        return False

    def estimate_rollback_complexity(self, proposal: ExternalActionProposal) -> float:
        if proposal.action_type == ExternalActionType.OBSERVE_ONLY:
            return 0.0
        if proposal.action_type in (ExternalActionType.ACTUATE_EXTERNAL, ExternalActionType.CONNECT_EXTERNAL):
            return 1.0
        if proposal.action_type == ExternalActionType.ISOLATE_SIMULATED:
            return 0.6
        if proposal.action_type == ExternalActionType.RESOURCE_SHIFT_SIMULATED:
            return 0.4
        return 0.3
