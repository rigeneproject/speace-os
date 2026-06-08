from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.capability_maturation.capability_maturation_models import (
    CapabilityRecord,
)


class RegressionTracker:
    """Tracks regression trends for capabilities across cycles."""

    def __init__(self):
        self._history: Dict[str, List[float]] = {}

    def record_score(self, capability_id: str, score: float) -> None:
        if capability_id not in self._history:
            self._history[capability_id] = []
        self._history[capability_id].append(score)

    def has_regression(self, capability_id: str, threshold: float = 0.2) -> bool:
        history = self._history.get(capability_id, [])
        if len(history) < 3:
            return False
        # Detect downward trend over last 3 entries
        return history[-1] < history[-2] - threshold and history[-2] < history[-3] - threshold

    def compute_regression_rate(self, capability_id: str) -> float:
        history = self._history.get(capability_id, [])
        if len(history) < 2:
            return 0.0
        declines = sum(1 for i in range(1, len(history)) if history[i] < history[i - 1])
        return declines / (len(history) - 1)

    def get_history(self, capability_id: str) -> List[float]:
        return list(self._history.get(capability_id, []))
