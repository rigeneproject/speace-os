import random
import uuid
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.postnatal_learning.curriculum_stage_builder import (
    CurriculumStageBuilder,
)
from speace_core.cellular_brain.postnatal_learning.developmental_memory_consolidator import (
    DevelopmentalMemoryConsolidator,
)
from speace_core.cellular_brain.postnatal_learning.error_correction_engine import (
    ErrorCorrectionEngine,
)
from speace_core.cellular_brain.postnatal_learning.imitation_learning_sandbox import (
    ImitationLearningSandbox,
)
from speace_core.cellular_brain.postnatal_learning.learning_episode_runner import (
    LearningEpisodeRunner,
)
from speace_core.cellular_brain.postnatal_learning.postnatal_learning_models import (
    CurriculumStage,
    CurriculumStageType,
    DevelopmentalMemoryRecord,
    LearningEpisode,
    LearningRiskClass,
)
from speace_core.cellular_brain.postnatal_learning.postnatal_learning_policy_engine import (
    PostnatalLearningPolicyEngine,
)


class PostnatalCurriculumEngine:
    """T63 — Postnatal Learning Curriculum Engine."""

    def __init__(self, seed: int = 42):
        self._seed = seed
        self._rng = random.Random(seed)
        self._stage_builder = CurriculumStageBuilder()
        self._episode_runner = LearningEpisodeRunner(seed=seed)
        self._sandbox = ImitationLearningSandbox()
        self._error_engine = ErrorCorrectionEngine()
        self._consolidator = DevelopmentalMemoryConsolidator()
        self._policy = PostnatalLearningPolicyEngine()
        self._stages: List[CurriculumStage] = self._stage_builder.build_default_stages()

    def get_stages(self) -> List[CurriculumStage]:
        return self._stages

    def run_episode(self, episode: LearningEpisode) -> Dict[str, Any]:
        episode = self._error_engine.apply_correction(episode)
        trace = self._sandbox.evaluate_trace(episode)
        policy = self._policy.evaluate_policy(episode, trace)
        record = None
        if policy["allowed"] and not policy["blocked"]:
            record = self._consolidator.consolidate(episode)
        return {
            "episode": episode,
            "trace": trace,
            "policy": policy,
            "record": record,
        }
