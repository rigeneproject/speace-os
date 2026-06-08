from typing import Any, Dict, List

from speace_core.cellular_brain.skill_transfer.skill_transfer_models import (
    SkillTransferResult,
)


class GeneralizationTracker:
    """Tracks whether a skill generalizes across scenarios."""

    def __init__(self):
        self._history: Dict[str, List[float]] = {}

    def record(self, skill_id: str, generalization_score: float) -> None:
        if skill_id not in self._history:
            self._history[skill_id] = []
        self._history[skill_id].append(generalization_score)

    def generalizes(self, skill_id: str, threshold: float = 0.68) -> bool:
        scores = self._history.get(skill_id, [])
        if len(scores) < 2:
            return False
        return sum(scores) / len(scores) >= threshold

    def get_history(self, skill_id: str) -> List[float]:
        return list(self._history.get(skill_id, []))
