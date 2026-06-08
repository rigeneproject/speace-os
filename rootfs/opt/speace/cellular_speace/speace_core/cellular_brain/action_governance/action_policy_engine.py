import uuid
from typing import Optional, Tuple

from speace_core.cellular_brain.action_governance.action_governance_models import (
    ActionGovernanceDecision,
    ActionGovernanceMode,
    ActionRiskAssessment,
    ActionRiskClass,
    ExternalActionProposal,
    ExternalActionType,
    ReversibilityAssessment,
)


class ActionPolicyEngine:
    """Evaluates proposals, blocks real execution, decides governance mode."""

    def evaluate_action_proposal(
        self,
        proposal: ExternalActionProposal,
        risk: ActionRiskAssessment,
        rev: ReversibilityAssessment,
    ) -> ActionGovernanceDecision:
        decision_id = f"dec_{uuid.uuid4().hex[:8]}"
        if proposal.action_type in (ExternalActionType.ACTUATE_EXTERNAL, ExternalActionType.CONNECT_EXTERNAL):
            return ActionGovernanceDecision(
                decision_id=decision_id,
                proposal_id=proposal.proposal_id,
                governance_mode=ActionGovernanceMode.BLOCKED,
                allowed_as_simulation=False,
                allowed_for_real_execution=False,
                requires_human_review=False,
                blocked=True,
                blocked_reason="external_actuation_or_connection_blocked_by_policy",
                safety_preservation_score=1.0,
                read_only_integrity_score=1.0,
                decision_confidence=1.0,
            )
        if proposal.requested_real_execution:
            return ActionGovernanceDecision(
                decision_id=decision_id,
                proposal_id=proposal.proposal_id,
                governance_mode=ActionGovernanceMode.BLOCKED,
                allowed_as_simulation=False,
                allowed_for_real_execution=False,
                requires_human_review=False,
                blocked=True,
                blocked_reason="real_execution_attempt_blocked",
                safety_preservation_score=1.0,
                read_only_integrity_score=1.0,
                decision_confidence=1.0,
            )
        if risk.risk_class == ActionRiskClass.CRITICAL:
            return ActionGovernanceDecision(
                decision_id=decision_id,
                proposal_id=proposal.proposal_id,
                governance_mode=ActionGovernanceMode.BLOCKED,
                allowed_as_simulation=False,
                allowed_for_real_execution=False,
                requires_human_review=False,
                blocked=True,
                blocked_reason="critical_risk_blocked",
                safety_preservation_score=1.0,
                read_only_integrity_score=1.0,
                decision_confidence=1.0,
            )
        if risk.risk_class == ActionRiskClass.HIGH:
            return ActionGovernanceDecision(
                decision_id=decision_id,
                proposal_id=proposal.proposal_id,
                governance_mode=ActionGovernanceMode.HUMAN_REVIEW_ONLY,
                allowed_as_simulation=True,
                allowed_for_real_execution=False,
                requires_human_review=True,
                blocked=False,
                safety_preservation_score=0.8,
                read_only_integrity_score=1.0,
                decision_confidence=0.8,
            )
        if risk.risk_class == ActionRiskClass.MODERATE:
            return ActionGovernanceDecision(
                decision_id=decision_id,
                proposal_id=proposal.proposal_id,
                governance_mode=ActionGovernanceMode.SIMULATION_ONLY,
                allowed_as_simulation=True,
                allowed_for_real_execution=False,
                requires_human_review=False,
                blocked=False,
                safety_preservation_score=0.9,
                read_only_integrity_score=1.0,
                decision_confidence=0.9,
            )
        return ActionGovernanceDecision(
            decision_id=decision_id,
            proposal_id=proposal.proposal_id,
            governance_mode=ActionGovernanceMode.SAFE_NOOP,
            allowed_as_simulation=True,
            allowed_for_real_execution=False,
            requires_human_review=False,
            blocked=False,
            safety_preservation_score=1.0,
            read_only_integrity_score=1.0,
            decision_confidence=1.0,
        )

    def block_real_execution_attempt(self, proposal: ExternalActionProposal) -> Tuple[bool, Optional[str]]:
        if proposal.requested_real_execution:
            return True, "real_execution_attempt_blocked"
        if proposal.action_type in (ExternalActionType.ACTUATE_EXTERNAL, ExternalActionType.CONNECT_EXTERNAL):
            return True, "external_action_blocked"
        return False, None

    def enforce_simulation_only(self, proposal: ExternalActionProposal) -> ActionGovernanceDecision:
        decision_id = f"dec_{uuid.uuid4().hex[:8]}"
        return ActionGovernanceDecision(
            decision_id=decision_id,
            proposal_id=proposal.proposal_id,
            governance_mode=ActionGovernanceMode.SIMULATION_ONLY,
            allowed_as_simulation=True,
            allowed_for_real_execution=False,
            requires_human_review=False,
            blocked=False,
            safety_preservation_score=0.95,
            read_only_integrity_score=1.0,
            decision_confidence=0.95,
        )

    def enforce_human_review_only(self, proposal: ExternalActionProposal) -> ActionGovernanceDecision:
        decision_id = f"dec_{uuid.uuid4().hex[:8]}"
        return ActionGovernanceDecision(
            decision_id=decision_id,
            proposal_id=proposal.proposal_id,
            governance_mode=ActionGovernanceMode.HUMAN_REVIEW_ONLY,
            allowed_as_simulation=True,
            allowed_for_real_execution=False,
            requires_human_review=True,
            blocked=False,
            safety_preservation_score=0.85,
            read_only_integrity_score=1.0,
            decision_confidence=0.85,
        )

    def verify_read_only_integrity(self, decision: ActionGovernanceDecision) -> bool:
        return not decision.allowed_for_real_execution

    def verify_bus_publication_safety(self, summary: dict) -> Tuple[bool, Optional[str]]:
        if summary.get("contains_real_execution_credentials", False):
            return False, "unsafe_bus_credentials_detected"
        if summary.get("action_type") in ("actuate_external", "connect_external"):
            return False, "unsafe_bus_action_type"
        return True, None
