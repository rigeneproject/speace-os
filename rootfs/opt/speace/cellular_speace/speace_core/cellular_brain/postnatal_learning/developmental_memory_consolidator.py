from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.postnatal_learning.postnatal_learning_models import (
    CurriculumStageType,
    DevelopmentalMemoryRecord,
    LearningEpisode,
)


class DevelopmentalMemoryConsolidator:
    """Consolidates developmental learning episodes into memory records."""

    def consolidate(self, episode: LearningEpisode) -> Optional[DevelopmentalMemoryRecord]:
        if not episode.correction_applied and episode.error_detected:
            return None
        strength = episode.correction_confidence if episode.correction_applied else 0.5
        return DevelopmentalMemoryRecord(
            record_id=f"mem_{episode.episode_id}",
            episode_id=episode.episode_id,
            stage_id=episode.stage_id,
            consolidation_strength=strength,
            semantic_grounding_score=0.5 if episode.stage_type == CurriculumStageType.GROUNDING_SEMANTIC else 0.2,
            transferability_score=0.3 if episode.stage_type == CurriculumStageType.TRANSFER else 0.1,
            safety_preservation_score=1.0 if episode.simulated_only else 0.0,
            metadata=episode.metadata,
        )

    def evaluate_safety(self, record: DevelopmentalMemoryRecord) -> bool:
        return record.safety_preservation_score >= 0.9 and record.consolidation_strength >= 0.3
