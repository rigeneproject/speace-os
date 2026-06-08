from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.postnatal_learning.postnatal_learning_models import (
    CurriculumStageType,
    DevelopmentalMemoryRecord,
    ImitationTrace,
    LearningEpisode,
    LearningRiskClass,
)


class PostnatalLearningPolicyEngine:
    """Policy engine for postnatal learning. Enforces simulation-only and human review."""

    def classify_risk(self, episode: LearningEpisode) -> LearningRiskClass:
        if episode.stage_type in (CurriculumStageType.TRANSFER, CurriculumStageType.ACTION_SIMULATION):
            return LearningRiskClass.HIGH
        if episode.error_detected and episode.error_magnitude > 0.8:
            return LearningRiskClass.CRITICAL
        if episode.error_detected and episode.error_magnitude > 0.5:
            return LearningRiskClass.HIGH
        if episode.stage_type == CurriculumStageType.OBSERVATION:
            return LearningRiskClass.LOW
        return LearningRiskClass.MODERATE

    def evaluate_policy(self, episode: LearningEpisode, trace: ImitationTrace) -> Dict[str, Any]:
        risk = self.classify_risk(episode)
        requires_review = risk in (LearningRiskClass.HIGH, LearningRiskClass.CRITICAL)
        blocked = trace.blocked or not episode.simulated_only
        return {
            "risk_class": risk,
            "blocked": blocked,
            "requires_human_review": requires_review,
            "allowed": not blocked and not requires_review,
            "simulation_only": episode.simulated_only,
        }
