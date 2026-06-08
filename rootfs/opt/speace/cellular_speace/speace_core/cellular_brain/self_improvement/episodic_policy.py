from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.memory.morphology_events import MorphologyEvent, MorphologyEventType
from speace_core.cellular_brain.self_improvement.architecture_rewriter import (
    ArchitectureRewriteProposal,
)


class EpisodicPolicyContext(BaseModel):
    limitation_type: str
    similar_episode_count: int = 0
    recovery_episode_count: int = 0
    regression_episode_count: int = 0
    semantic_learning_episode_count: int = 0
    self_improvement_episode_count: int = 0
    recovery_patterns: List[str] = Field(default_factory=list)
    regression_precursors: List[str] = Field(default_factory=list)
    confidence_modifier: float = 0.0
    risk_modifier: float = 0.0


class EpisodicProposalAdjustment(BaseModel):
    proposal_id: str
    original_confidence: float
    adjusted_confidence: float
    episodic_bonus: float = 0.0
    episodic_penalty: float = 0.0
    reasons: List[str] = Field(default_factory=list)


class EpisodicSelfImprovementPolicy:
    """T48 — Use episodic memory to guide self-improvement proposal selection."""

    def __init__(self, episodic_recall=None, memory=None):
        self.episodic_recall = episodic_recall
        self.memory = memory

    # ------------------------------------------------------------------ #
    # Context building
    # ------------------------------------------------------------------ #

    def build_context(
        self,
        limitation_type: str,
        current_metrics: Optional[Dict[str, float]] = None,
    ) -> EpisodicPolicyContext:
        if self.episodic_recall is None:
            return EpisodicPolicyContext(limitation_type=limitation_type)

        current_metrics = current_metrics or {}

        # Recall similar episodes by metrics
        similar_result = self.episodic_recall.recall_similar_metrics(
            current_metrics, top_k=10
        )
        similar_episodes = similar_result.matched_episodes

        recovery_episodes = self.episodic_recall.recall_by_outcome("recovery")
        regression_episodes = self.episodic_recall.recall_by_outcome("regression")
        self_improvement_episodes = self.episodic_recall.recall_by_outcome("validated")
        semantic_learning_episodes = self.episodic_recall.recall_by_outcome("ok")

        recovery_patterns = self.episodic_recall.find_recovery_patterns()
        regression_precursors = self.episodic_recall.find_regression_precursors()

        # Count episodes whose trigger contains the limitation_type substring
        def _matches_limitation(ep):
            return limitation_type.lower() in ep.trigger.lower()

        recovery_count = sum(1 for ep in recovery_episodes if _matches_limitation(ep))
        regression_count = sum(1 for ep in regression_episodes if _matches_limitation(ep))

        # Net modifiers derived from patterns
        confidence_modifier = 0.0
        risk_modifier = 0.0
        if recovery_patterns:
            confidence_modifier += 0.05
        if regression_precursors:
            risk_modifier -= 0.05

        context = EpisodicPolicyContext(
            limitation_type=limitation_type,
            similar_episode_count=len(similar_episodes),
            recovery_episode_count=recovery_count,
            regression_episode_count=regression_count,
            semantic_learning_episode_count=len(semantic_learning_episodes),
            self_improvement_episode_count=len(self_improvement_episodes),
            recovery_patterns=recovery_patterns,
            regression_precursors=regression_precursors,
            confidence_modifier=round(confidence_modifier, 4),
            risk_modifier=round(risk_modifier, 4),
        )

        self._log_event(
            MorphologyEventType.EPISODIC_POLICY_CONTEXT_BUILT,
            {
                "limitation_type": limitation_type,
                "similar_episode_count": context.similar_episode_count,
                "recovery_episode_count": context.recovery_episode_count,
                "regression_episode_count": context.regression_episode_count,
            },
        )
        return context

    # ------------------------------------------------------------------ #
    # Proposal adjustment
    # ------------------------------------------------------------------ #

    def adjust_proposals(
        self,
        proposals: List[ArchitectureRewriteProposal],
        context: EpisodicPolicyContext,
    ) -> List[EpisodicProposalAdjustment]:
        if self.episodic_recall is None:
            return [
                EpisodicProposalAdjustment(
                    proposal_id=p.id,
                    original_confidence=0.0,
                    adjusted_confidence=0.0,
                )
                for p in proposals
            ]

        # Pre-fetch episodic data for efficiency
        all_episodes = self.episodic_recall.episodic_memory.load_episodes()
        recovery_episodes = [ep for ep in all_episodes if ep.outcome == "recovery"]
        regression_episodes = [ep for ep in all_episodes if ep.outcome == "regression"]
        semantic_episodes = [
            ep for ep in all_episodes
            if ep.outcome in ("ok", "validated") and ep.cognitive_delta > 0
        ]

        adjustments: List[EpisodicProposalAdjustment] = []

        for proposal in proposals:
            original = 0.0  # proposals don't have an intrinsic confidence field
            bonus = 0.0
            penalty = 0.0
            reasons: List[str] = []

            # +0.10 if proposal linked to recovery episode
            if any(proposal.id in ep.linked_proposals for ep in recovery_episodes):
                bonus += 0.10
                reasons.append("linked_to_recovery_episode")

            # +0.05 if limitation_type already resolved in past
            if context.recovery_episode_count > 0:
                bonus += 0.05
                reasons.append("limitation_type_previously_resolved")

            # -0.10 if proposal linked to regression episode
            if any(proposal.id in ep.linked_proposals for ep in regression_episodes):
                penalty += 0.10
                reasons.append("linked_to_regression_episode")

            # -0.05 if regression precursors present and not mitigated
            if context.regression_precursors:
                # Mitigated if proposal targets a module related to the precursor
                mitigated = any(
                    prec in " ".join(proposal.target_modules).lower()
                    for prec in context.regression_precursors
                )
                if not mitigated:
                    penalty += 0.05
                    reasons.append("unmitigated_regression_precursor")

            # +0.05 if semantic/associative episode with positive net gain
            if any(proposal.id in ep.linked_proposals for ep in semantic_episodes):
                bonus += 0.05
                reasons.append("linked_to_semantic_learning_with_gain")

            adjusted = original + bonus - penalty
            adjusted = round(max(0.0, min(1.0, adjusted)), 4)

            adjustments.append(
                EpisodicProposalAdjustment(
                    proposal_id=proposal.id,
                    original_confidence=round(original, 4),
                    adjusted_confidence=adjusted,
                    episodic_bonus=round(bonus, 4),
                    episodic_penalty=round(penalty, 4),
                    reasons=reasons,
                )
            )

            if bonus > 0:
                self._log_event(
                    MorphologyEventType.EPISODIC_POLICY_RECOVERY_BONUS_APPLIED,
                    {
                        "proposal_id": proposal.id,
                        "bonus": bonus,
                        "reasons": reasons,
                    },
                )
            if penalty > 0:
                self._log_event(
                    MorphologyEventType.EPISODIC_POLICY_REGRESSION_PENALTY_APPLIED,
                    {
                        "proposal_id": proposal.id,
                        "penalty": penalty,
                        "reasons": reasons,
                    },
                )

            self._log_event(
                MorphologyEventType.EPISODIC_POLICY_PROPOSAL_ADJUSTED,
                {
                    "proposal_id": proposal.id,
                    "original_confidence": original,
                    "adjusted_confidence": adjusted,
                    "bonus": bonus,
                    "penalty": penalty,
                },
            )

        return adjustments

    # ------------------------------------------------------------------ #
    # Selection
    # ------------------------------------------------------------------ #

    def select_best_proposal(
        self,
        proposals: List[ArchitectureRewriteProposal],
        context: EpisodicPolicyContext,
    ) -> Optional[ArchitectureRewriteProposal]:
        if not proposals:
            return None
        adjustments = self.adjust_proposals(proposals, context)
        if not adjustments:
            return proposals[0]
        # Sort by adjusted_confidence descending
        best_adj = max(adjustments, key=lambda a: a.adjusted_confidence)
        # Find matching proposal
        for p in proposals:
            if p.id == best_adj.proposal_id:
                self._log_event(
                    MorphologyEventType.EPISODIC_POLICY_PROPOSAL_SELECTED,
                    {
                        "proposal_id": p.id,
                        "adjusted_confidence": best_adj.adjusted_confidence,
                        "reasons": best_adj.reasons,
                    },
                )
                return p
        return proposals[0]

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _log_event(
        self,
        event_type: MorphologyEventType,
        metadata: Dict[str, Any],
    ) -> None:
        if self.memory is None or not hasattr(self.memory, "log_event"):
            return
        try:
            import uuid
            from datetime import datetime, timezone
            event = MorphologyEvent(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=event_type,
                timestamp=datetime.now(timezone.utc).timestamp(),
                metadata=metadata,
            )
            self.memory.log_event(event)
        except Exception:
            pass
