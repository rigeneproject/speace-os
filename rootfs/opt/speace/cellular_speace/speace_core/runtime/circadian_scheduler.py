"""CircadianScheduler — awake/sleep/consolidation phases (T109).

Orchestrates circadian rhythm for SPEACE. Transitions are logged to the
narrative engine if available.
"""

import time
from typing import Any, Dict, Optional


class CircadianScheduler:
    """Manages circadian phases for the organism runtime."""

    PHASES = ("awake", "pre_sleep", "sleep", "consolidation", "post_sleep")

    def __init__(
        self,
        awake_duration: float = 300.0,
        sleep_duration: float = 60.0,
        narrative_engine: Any = None,
    ) -> None:
        self.awake_duration = awake_duration
        self.sleep_duration = sleep_duration
        self.narrative_engine = narrative_engine
        self._phase: str = "awake"
        self._phase_entered_at: float = time.time()
        self._sleep_ticks_remaining: int = 0

    @property
    def phase(self) -> str:
        return self._phase

    def tick(self) -> str:
        """Evaluate phase transitions. Returns current phase."""
        now = time.time()
        elapsed = now - self._phase_entered_at

        if self._phase == "awake":
            if elapsed >= self.awake_duration:
                self._transition_to("pre_sleep")
        elif self._phase == "pre_sleep":
            # brief transition window (5s)
            if elapsed >= 5.0:
                self._transition_to("sleep")
                self._sleep_ticks_remaining = int(self.sleep_duration)
        elif self._phase == "sleep":
            if elapsed >= self.sleep_duration:
                self._transition_to("consolidation")
        elif self._phase == "consolidation":
            # brief consolidation window (10s)
            if elapsed >= 10.0:
                self._transition_to("post_sleep")
        elif self._phase == "post_sleep":
            if elapsed >= 5.0:
                self._transition_to("awake")

        return self._phase

    def _transition_to(self, new_phase: str) -> None:
        old = self._phase
        self._phase = new_phase
        self._phase_entered_at = time.time()
        if self.narrative_engine is not None:
            try:
                self.narrative_engine.record(
                    event_type="circadian_transition",
                    description=f"Circadian phase: {old} → {new_phase}",
                    importance=4,
                    metadata={"from": old, "to": new_phase},
                )
            except Exception:
                pass

    def is_sleeping(self) -> bool:
        return self._phase in ("sleep", "consolidation")

    def phase_context(self) -> Dict[str, Any]:
        return {
            "phase": self._phase,
            "phase_elapsed_seconds": time.time() - self._phase_entered_at,
            "awake_duration": self.awake_duration,
            "sleep_duration": self.sleep_duration,
            "is_sleeping": self.is_sleeping(),
        }
