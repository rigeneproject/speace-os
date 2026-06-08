import json
import math
import os
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class AttractorEscape:
    tick: int
    from_attractor_id: Optional[int]
    to_attractor_id: Optional[int]
    escape_distance: float


class CognitiveAttractorTracker:
    """Tracks the system's trajectory in state space and identifies attractors.

    An attractor is a region of state space that the system repeatedly visits
    and from which small perturbations do not cause escape.
    """

    def __init__(
        self,
        history_window: int = 500,
        attractor_radius: float = 0.15,
        min_visit_count: int = 5,
        persistence_log_path: Optional[str] = None,
    ):
        self.history_window = history_window
        self.attractor_radius = attractor_radius
        self.min_visit_count = min_visit_count
        self._state_history: deque = deque(maxlen=history_window)
        self._attractor_centers: List[np.ndarray] = []
        self._attractor_visit_counts: List[int] = []
        self._attractor_last_visit_tick: List[int] = []
        self._current_attractor_id: Optional[int] = None
        self._escape_history: List[AttractorEscape] = []
        self._tick: int = 0
        self._persistence_log_path = persistence_log_path or os.path.join(
            "data", "regulation", "attractor_tracker.jsonl"
        )

    # ------------------------------------------------------------------ #
    # State recording
    # ------------------------------------------------------------------ #

    def record_state(self, state_vector: List[float]) -> None:
        """Store a new state snapshot and advance the tick counter."""
        self._tick += 1
        vec = np.array(state_vector, dtype=np.float64)
        self._state_history.append(vec)
        self._update_attractor_membership(vec)

    # ------------------------------------------------------------------ #
    # Attractor detection
    # ------------------------------------------------------------------ #

    def detect_attractor(self) -> Optional[int]:
        """Find if the system is currently orbiting a fixed point.

        Returns the attractor index if the latest state falls within an
        attractor region that has been visited enough times, else None.
        """
        if not self._state_history:
            return None
        latest = self._state_history[-1]
        for idx, center in enumerate(self._attractor_centers):
            if np.linalg.norm(latest - center) <= self.attractor_radius:
                if self._attractor_visit_counts[idx] >= self.min_visit_count:
                    return idx
        return None

    def measure_attractor_stability(self) -> float:
        """Measure how tightly bound the current orbit is.

        Returns a value in [0, 1] where 1.0 means the system is deeply
        trapped (all recent states close to the attractor center) and
        0.0 means it is wandering.
        """
        if len(self._state_history) < 2:
            return 0.0
        attractor_id = self.detect_attractor()
        if attractor_id is None:
            return 0.0

        center = self._attractor_centers[attractor_id]
        # Use last N states for stability estimate
        window = min(50, len(self._state_history))
        recent = list(self._state_history)[-window:]
        distances = [np.linalg.norm(s - center) for s in recent]
        mean_dist = float(np.mean(distances))
        # Stability = 1 - normalized mean distance (clipped)
        stability = max(0.0, 1.0 - (mean_dist / max(self.attractor_radius, 1e-12)))
        return float(np.clip(stability, 0.0, 1.0))

    def get_attractor_count(self) -> int:
        """Return the number of distinct attractors that have been visited
        at least ``min_visit_count`` times."""
        return sum(1 for c in self._attractor_visit_counts if c >= self.min_visit_count)

    def get_escape_history(self) -> List[Dict[str, Any]]:
        """Return history of times the system escaped an attractor."""
        return [
            {
                "tick": e.tick,
                "from_attractor_id": e.from_attractor_id,
                "to_attractor_id": e.to_attractor_id,
                "escape_distance": round(e.escape_distance, 6),
            }
            for e in self._escape_history
        ]

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _update_attractor_membership(self, vec: np.ndarray) -> None:
        matched = False
        for idx, center in enumerate(self._attractor_centers):
            dist = float(np.linalg.norm(vec - center))
            if dist <= self.attractor_radius:
                # Update running average center
                n = self._attractor_visit_counts[idx]
                self._attractor_centers[idx] = (n * center + vec) / (n + 1)
                self._attractor_visit_counts[idx] = n + 1
                self._attractor_last_visit_tick[idx] = self._tick
                if self._current_attractor_id is not None and self._current_attractor_id != idx:
                    self._escape_history.append(
                        AttractorEscape(
                            tick=self._tick,
                            from_attractor_id=self._current_attractor_id,
                            to_attractor_id=idx,
                            escape_distance=dist,
                        )
                    )
                self._current_attractor_id = idx
                matched = True
                break

        if not matched:
            # Create new attractor candidate
            self._attractor_centers.append(vec.copy())
            self._attractor_visit_counts.append(1)
            self._attractor_last_visit_tick.append(self._tick)
            new_id = len(self._attractor_centers) - 1
            if self._current_attractor_id is not None:
                self._escape_history.append(
                    AttractorEscape(
                        tick=self._tick,
                        from_attractor_id=self._current_attractor_id,
                        to_attractor_id=None,
                        escape_distance=float(
                            np.linalg.norm(vec - self._attractor_centers[self._current_attractor_id])
                        ),
                    )
                )
            self._current_attractor_id = new_id

    def get_current_attractor_id(self) -> Optional[int]:
        return self._current_attractor_id

    def get_state_history(self) -> List[np.ndarray]:
        return list(self._state_history)

    def persist(self) -> None:
        """Append current tracker state to JSONL log."""
        os.makedirs(os.path.dirname(self._persistence_log_path), exist_ok=True)
        record = {
            "tick": self._tick,
            "attractor_count": self.get_attractor_count(),
            "current_attractor_id": self._current_attractor_id,
            "stability": round(self.measure_attractor_stability(), 6),
            "escape_count": len(self._escape_history),
        }
        with open(self._persistence_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
