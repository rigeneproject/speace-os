import random
import uuid
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.postnatal_learning.postnatal_learning_models import (
    CurriculumStage,
    CurriculumStageType,
    LearningEpisode,
    PostnatalLearningAuditProfile,
)


class LearningEpisodeRunner:
    """Generates and runs synthetic learning episodes for audit profiles."""

    def __init__(self, seed: int = 42):
        self._rng = random.Random(seed)

    def build_episodes_for_profile(
        self,
        profile: PostnatalLearningAuditProfile,
        stages: List[CurriculumStage],
    ) -> List[LearningEpisode]:
        episodes: List[LearningEpisode] = []
        stage_keys = list(profile.stage_mix.keys()) if profile.stage_mix else ["observation"]
        stage_weights = [profile.stage_mix.get(k, 1.0 / len(stage_keys)) for k in stage_keys]
        stage_map = {s.stage_type.value: s for s in stages}

        for cycle in range(profile.duration_cycles):
            for _ in range(profile.episode_count):
                chosen_type = self._rng.choices(stage_keys, weights=stage_weights, k=1)[0]
                stage = stage_map.get(chosen_type, stages[0])
                episode = LearningEpisode(
                    episode_id=f"ep_{profile.name}_c{cycle}_{uuid.uuid4().hex[:8]}",
                    stage_id=stage.stage_id,
                    stage_type=stage.stage_type,
                    simulated_only=True,
                    metadata={"cycle": cycle, "profile": profile.name},
                )
                if profile.error_rate > 0 and self._rng.random() < profile.error_rate:
                    episode.target_output = "correct"
                    episode.predicted_output = "wrong"
                    episode.error_detected = True
                    episode.error_magnitude = self._rng.uniform(0.1, 0.8)
                if profile.dangerous_trace_attempts > 0 and self._rng.random() < 0.2:
                    episode.metadata["dangerous_trace"] = True
                episodes.append(episode)
        return episodes
