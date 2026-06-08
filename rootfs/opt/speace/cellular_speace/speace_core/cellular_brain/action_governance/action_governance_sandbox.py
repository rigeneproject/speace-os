import random
import uuid
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.action_governance.action_governance_models import (
    ActionGovernanceDecision,
    ActionReviewPacket,
    ActionRiskClass,
    ExternalActionProposal,
    ExternalActionType,
)
from speace_core.cellular_brain.action_governance.action_policy_engine import (
    ActionPolicyEngine,
)
from speace_core.cellular_brain.action_governance.action_proposal_builder import (
    ActionProposalBuilder,
)
from speace_core.cellular_brain.action_governance.action_risk_classifier import (
    ActionRiskClassifier,
)
from speace_core.cellular_brain.action_governance.human_review_packet import (
    HumanReviewPacketBuilder,
)
from speace_core.cellular_brain.action_governance.reversibility_analyzer import (
    ReversibilityAnalyzer,
)
from speace_core.cellular_brain.world_model.world_model_models import (
    CausalSimulationResult,
    ImpactAssessment,
    WorldModelSnapshot,
)


class ExternalActionGovernanceSandbox:
    """Orchestrates proposal builder, risk classifier, reversibility analyzer, policy engine, and review packet builder."""

    def __init__(self, seed: int = 42):
        self._seed = seed
        self._rng = random.Random(seed)
        self._proposal_builder = ActionProposalBuilder(seed=seed)
        self._risk_classifier = ActionRiskClassifier()
        self._reversibility_analyzer = ReversibilityAnalyzer()
        self._policy_engine = ActionPolicyEngine()
        self._packet_builder = HumanReviewPacketBuilder()

    def ingest_world_model_outputs(
        self,
        snapshot: WorldModelSnapshot,
        causal: Optional[CausalSimulationResult] = None,
        impact: Optional[ImpactAssessment] = None,
    ) -> Dict[str, Any]:
        return {
            "snapshot_id": snapshot.snapshot_id,
            "causal_scenario_id": causal.scenario_id if causal else None,
            "impact_assessment_id": impact.assessment_id if impact else None,
            "ingested": True,
        }

    def generate_action_proposals(
        self,
        snapshot: WorldModelSnapshot,
        impact: Optional[ImpactAssessment] = None,
    ) -> List[ExternalActionProposal]:
        proposals: List[ExternalActionProposal] = []
        proposals.append(self._proposal_builder.build_observe_only_proposal(snapshot, impact))
        proposals.append(self._proposal_builder.build_recommendation_proposal(snapshot, impact))
        if snapshot.zones:
            proposals.append(self._proposal_builder.build_resource_shift_simulated_proposal(snapshot, impact))
            proposals.append(self._proposal_builder.build_isolation_simulated_proposal(snapshot, impact))
        if impact is not None:
            proposals.append(self._proposal_builder.build_from_impact_assessment(snapshot, impact))
        return [p for p in proposals if self._proposal_builder.validate_proposal_is_sandboxed(p)]

    def evaluate_action_proposal(
        self,
        proposal: ExternalActionProposal,
        risk_class_override: Optional[ActionRiskClass] = None,
    ) -> ActionGovernanceDecision:
        risk = self._risk_classifier.classify_action_risk(proposal, risk_class_override)
        rev = self._reversibility_analyzer.assess_reversibility(proposal)
        decision = self._policy_engine.evaluate_action_proposal(proposal, risk, rev)
        return decision

    def generate_human_review_packet(
        self,
        proposal: ExternalActionProposal,
        decision: ActionGovernanceDecision,
    ) -> ActionReviewPacket:
        risk = self._risk_classifier.classify_action_risk(proposal)
        rev = self._reversibility_analyzer.assess_reversibility(proposal)
        impact_summary = {
            "proposal_id": proposal.proposal_id,
            "action_type": proposal.action_type.value,
            "simulated_only": proposal.simulated_only,
        }
        return self._packet_builder.build_review_packet(proposal, risk, rev, decision, impact_summary)

    def publish_read_only_action_governance_summary(
        self,
        decisions: List[ActionGovernanceDecision],
    ) -> Dict[str, Any]:
        summary = {
            "summary_id": f"ag_summary_{uuid.uuid4().hex[:8]}",
            "read_only": True,
            "decision_count": len(decisions),
            "blocked_count": sum(1 for d in decisions if d.blocked),
            "human_review_count": sum(1 for d in decisions if d.requires_human_review),
            "simulation_only_count": sum(1 for d in decisions if d.governance_mode.value == "simulation_only"),
            "safe_noop_count": sum(1 for d in decisions if d.governance_mode.value == "safe_noop"),
        }
        safe, reason = self._policy_engine.verify_bus_publication_safety(summary)
        if not safe:
            summary["unsafe"] = True
            summary["unsafe_reason"] = reason
        return summary

    def generate_sandbox_report(self, suite: Dict[str, Any]) -> str:
        lines = [
            "# External Action Governance Sandbox Report",
            f"Profiles: {suite.get('profile_count', 0)}",
            f"Aggregate verdict: {suite.get('aggregate_verdict', 'unknown')}",
            f"Proceed to T62B: {suite.get('proceed_to_t62b', False)}",
        ]
        return "\n".join(lines)
