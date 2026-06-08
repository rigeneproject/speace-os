import uuid
from typing import Any, Dict

from speace_core.cellular_brain.action_governance.action_governance_models import (
    ActionGovernanceDecision,
    ActionReviewPacket,
    ActionRiskAssessment,
    ExternalActionProposal,
    ReversibilityAssessment,
)


class HumanReviewPacketBuilder:
    """Builds sanitized ActionReviewPackets without execution payloads or credentials."""

    def build_review_packet(
        self,
        proposal: ExternalActionProposal,
        risk: ActionRiskAssessment,
        rev: ReversibilityAssessment,
        decision: ActionGovernanceDecision,
        impact_summary: Dict[str, Any],
    ) -> ActionReviewPacket:
        packet = ActionReviewPacket(
            packet_id=f"pkt_{uuid.uuid4().hex[:8]}",
            proposal_id=proposal.proposal_id,
            decision_id=decision.decision_id,
            summary=self._build_summary(proposal, risk, decision),
            risk_assessment=risk.model_dump(),
            reversibility_assessment=rev.model_dump(),
            impact_summary=impact_summary,
            human_review_required=decision.requires_human_review,
            recommended_human_decision=decision.governance_mode.value,
            contains_real_execution_credentials=False,
        )
        return self.sanitize_packet(packet)

    def sanitize_packet(self, packet: ActionReviewPacket) -> ActionReviewPacket:
        unsafe, reason = self.verify_no_execution_payload(packet)
        if not unsafe:
            return packet
        packet.summary = f"[SANITIZED] {packet.summary}"
        packet.contains_real_execution_credentials = True
        packet.metadata["sanitized_reason"] = reason
        return packet

    def verify_no_execution_payload(self, packet: ActionReviewPacket) -> tuple[bool, str]:
        # Check risk assessment payload
        risk = packet.risk_assessment
        if risk.get("contains_real_execution_credentials", False):
            return True, "credentials_in_risk_assessment"
        if risk.get("blocked_reason", "") and "external" in risk.get("blocked_reason", ""):
            return True, "external_action_in_risk_assessment"
        # Check impact summary
        impact = packet.impact_summary
        if impact.get("api_endpoint") or impact.get("iot_device_id") or impact.get("hardware_channel"):
            return True, "execution_references_in_impact_summary"
        if packet.contains_real_execution_credentials:
            return True, "packet_flagged_with_credentials"
        return False, ""

    def export_packet_dict(self, packet: ActionReviewPacket) -> Dict[str, Any]:
        return packet.model_dump()

    def _build_summary(
        self,
        proposal: ExternalActionProposal,
        risk: ActionRiskAssessment,
        decision: ActionGovernanceDecision,
    ) -> str:
        return (
            f"Action {proposal.proposal_id} ({proposal.action_type.value}) "
            f"classified as {risk.risk_class.value} risk. "
            f"Governance decision: {decision.governance_mode.value}."
        )
