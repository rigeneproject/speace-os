from typing import Any, Dict, List

from speace_core.cellular_brain.skill_transfer.skill_transfer_models import (
    SkillTransferResult,
)


class NegativeTransferDetector:
    """Detects negative transfer (skill makes target performance worse)."""

    def __init__(self):
        self._history: Dict[str, List[float]] = {}

    def record(self, skill_id: str, negative_transfer_score: float) -> None:
        if skill_id not in self._history:
            self._history[skill_id] = []
        self._history[skill_id].append(negative_transfer_score)

    def has_negative_transfer(self, skill_id: str, threshold: float = 0.20) -> bool:
        scores = self._history.get(skill_id, [])
        if not scores:
            return False
        return max(scores) >= threshold

    def get_history(self, skill_id: str) -> List[float]:
        return list(self._history.get(skill_id, []))
