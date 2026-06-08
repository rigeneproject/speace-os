from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.postnatal_learning.postnatal_learning_models import (
    CurriculumStageType,
    DevelopmentalMemoryRecord,
    LearningEpisode,
)


class ErrorCorrectionEngine:
    """Detects and corrects errors in learning episodes."""

    def detect_error(self, episode: LearningEpisode) -> bool:
        if episode.target_output is None or episode.predicted_output is None:
            return False
        return episode.target_output != episode.predicted_output

    def compute_error_magnitude(self, episode: LearningEpisode) -> float:
        if not self.detect_error(episode):
            return 0.0
        target = episode.target_output or ""
        predicted = episode.predicted_output or ""
        max_len = max(len(target), len(predicted), 1)
        diff = sum(a != b for a, b in zip(target, predicted))
        diff += abs(len(target) - len(predicted))
        return min(1.0, diff / max_len)

    def apply_correction(self, episode: LearningEpisode) -> LearningEpisode:
        if not self.detect_error(episode):
            episode.error_detected = False
            episode.error_magnitude = 0.0
            episode.correction_applied = False
            episode.correction_confidence = 1.0
            return episode
        episode.error_detected = True
        episode.error_magnitude = self.compute_error_magnitude(episode)
        episode.correction_applied = True
        episode.correction_confidence = max(0.0, 1.0 - episode.error_magnitude)
        episode.predicted_output = episode.target_output
        return episode
