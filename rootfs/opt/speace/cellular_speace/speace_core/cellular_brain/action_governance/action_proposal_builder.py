import random
import uuid
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.action_governance.action_governance_models import (
    ExternalActionProposal,
    ExternalActionType,
)
from speace_core.cellular_brain.world_model.world_model_models import (
    CausalSimulationResult,
    ImpactAssessment,
    WorldModelSnapshot,
)


class ActionProposalBuilder:
    """Generates simulated action proposals from world model outputs. Never invokes real adapters."""

    def __init__(self, seed: int = 42):
        self._seed = seed
        self._rng = random.Random(seed)

    def build_observe_only_proposal(
        self,
        snapshot: WorldModelSnapshot,
        assessment: Optional[ImpactAssessment] = None,
    ) -> ExternalActionProposal:
        return ExternalActionProposal(
            proposal_id=f"prop_observe_{uuid.uuid4().hex[:8]}",
            action_type=ExternalActionType.OBSERVE_ONLY,
            title="Observe external state",
            description="Read-only observation of world model snapshot.",
            source_snapshot_id=snapshot.snapshot_id,
            simulated_only=True,
            estimated_urgency=0.1,
            estimated_benefit=0.1,
            estimated_risk=0.0,
            uncertainty_score=0.0,
        )

    def build_recommendation_proposal(
        self,
        snapshot: WorldModelSnapshot,
        assessment: Optional[ImpactAssessment] = None,
    ) -> ExternalActionProposal:
        risk = 0.1 if assessment is None else min(1.0, assessment.impact_score * 0.3)
        return ExternalActionProposal(
            proposal_id=f"prop_rec_{uuid.uuid4().hex[:8]}",
            action_type=ExternalActionType.RECOMMEND,
            title="Recommend human review",
            description="Non-operational recommendation based on world model assessment.",
            source_snapshot_id=snapshot.snapshot_id,
            source_assessment_id=assessment.assessment_id if assessment else None,
            simulated_only=True,
            estimated_urgency=0.2,
            estimated_benefit=0.3,
            estimated_risk=risk,
            uncertainty_score=0.1,
        )

    def build_resource_shift_simulated_proposal(
        self,
        snapshot: WorldModelSnapshot,
        assessment: Optional[ImpactAssessment] = None,
    ) -> ExternalActionProposal:
        risk = 0.3 if assessment is None else min(1.0, assessment.energy_impact_score + 0.1)
        return ExternalActionProposal(
            proposal_id=f"prop_shift_{uuid.uuid4().hex[:8]}",
            action_type=ExternalActionType.RESOURCE_SHIFT_SIMULATED,
            title="Simulated resource shift",
            description="Simulated redistribution of resources. No real control issued.",
            source_snapshot_id=snapshot.snapshot_id,
            source_assessment_id=assessment.assessment_id if assessment else None,
            target_zone_id=snapshot.zones[0].zone_id if snapshot.zones else None,
            simulated_only=True,
            estimated_urgency=0.4,
            estimated_benefit=0.4,
            estimated_risk=risk,
            uncertainty_score=0.2,
        )

    def build_isolation_simulated_proposal(
        self,
        snapshot: WorldModelSnapshot,
        assessment: Optional[ImpactAssessment] = None,
    ) -> ExternalActionProposal:
        risk = 0.4 if assessment is None else min(1.0, assessment.infrastructure_impact_score + 0.15)
        return ExternalActionProposal(
            proposal_id=f"prop_iso_{uuid.uuid4().hex[:8]}",
            action_type=ExternalActionType.ISOLATE_SIMULATED,
            title="Simulated infrastructure isolation",
            description="Simulated isolation of affected zone. No real infrastructure change.",
            source_snapshot_id=snapshot.snapshot_id,
            source_assessment_id=assessment.assessment_id if assessment else None,
            target_zone_id=snapshot.zones[0].zone_id if snapshot.zones else None,
            simulated_only=True,
            estimated_urgency=0.5,
            estimated_benefit=0.3,
            estimated_risk=risk,
            uncertainty_score=0.25,
        )

    def build_from_impact_assessment(
        self,
        snapshot: WorldModelSnapshot,
        assessment: ImpactAssessment,
    ) -> ExternalActionProposal:
        action_type = ExternalActionType.RECOMMEND
        if assessment.impact_score > 0.5:
            action_type = ExternalActionType.RESOURCE_SHIFT_SIMULATED
        if assessment.safety_impact_score > 0.5:
            action_type = ExternalActionType.ISOLATE_SIMULATED
        return ExternalActionProposal(
            proposal_id=f"prop_ia_{uuid.uuid4().hex[:8]}",
            action_type=action_type,
            title=f"Proposal from impact assessment {assessment.assessment_id}",
            description="Generated from impact assessment. Simulated only.",
            source_snapshot_id=snapshot.snapshot_id,
            source_assessment_id=assessment.assessment_id,
            simulated_only=True,
            estimated_urgency=min(1.0, assessment.impact_score),
            estimated_benefit=max(0.0, 1.0 - assessment.impact_score),
            estimated_risk=min(1.0, assessment.safety_impact_score + assessment.impact_score),
            uncertainty_score=assessment.uncertainty_impact_score,
        )

    def validate_proposal_is_sandboxed(self, proposal: ExternalActionProposal) -> bool:
        if not proposal.simulated_only:
            return False
        if proposal.requested_real_execution:
            return False
        if proposal.action_type in (ExternalActionType.ACTUATE_EXTERNAL, ExternalActionType.CONNECT_EXTERNAL):
            return False
        return True
