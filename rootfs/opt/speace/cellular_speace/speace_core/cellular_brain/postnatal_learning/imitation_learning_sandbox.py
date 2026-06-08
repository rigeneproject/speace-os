from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.postnatal_learning.postnatal_learning_models import (
    CurriculumStageType,
    ImitationTrace,
    LearningEpisode,
    LearningRiskClass,
)


class ImitationLearningSandbox:
    """Sandbox for imitation learning. Blocks dangerous traces."""

    DANGEROUS_KEYWORDS = [
        "actuate", "execute", "run", "call", "connect", "external",
        "hardware", "iot", "api", "network", "socket", "shell",
        "system", "os.", "subprocess", "eval(", "exec(", "import os",
    ]

    def evaluate_trace(self, episode: LearningEpisode) -> ImitationTrace:
        trace = ImitationTrace(
            trace_id=f"trace_{episode.episode_id}",
            episode_id=episode.episode_id,
            source_pattern=episode.target_output or "",
            target_pattern=episode.predicted_output or "",
            metadata=episode.metadata,
        )
        combined = (trace.source_pattern + " " + trace.target_pattern).lower()
        trace.contains_dangerous_action = any(kw in combined for kw in self.DANGEROUS_KEYWORDS)
        trace.trace_confidence = self._compute_confidence(episode)
        trace.blocked = trace.contains_dangerous_action or episode.stage_type in (
            CurriculumStageType.TRANSFER,
            CurriculumStageType.ACTION_SIMULATION,
        )
        return trace

    def _compute_confidence(self, episode: LearningEpisode) -> float:
        if episode.error_detected:
            return max(0.0, 1.0 - episode.error_magnitude)
        return 0.8
