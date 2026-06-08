"""EmergencyHaltGate — controlled shutdown on critical conditions (T109).

The only autonomous action permitted: save checkpoint and stop the tick loop.
Does NOT kill the process; leaves dashboard/API active in read-only mode.
Requires human command to resume.
"""

import logging
import time
from typing import Any, Dict, Optional


class EmergencyHaltGate:
    """Evaluates emergency conditions and triggers controlled halt."""

    def __init__(
        self,
        brainstem_emergency_ticks: int = 5,
        health_score_threshold: float = 0.1,
        memory_rss_critical_mb: float = 4096.0,
        checkpoint_manager: Any = None,
        narrative_engine: Any = None,
    ) -> None:
        self.brainstem_emergency_ticks = brainstem_emergency_ticks
        self.health_score_threshold = health_score_threshold
        self.memory_rss_critical_mb = memory_rss_critical_mb
        self.checkpoint_manager = checkpoint_manager
        self.narrative_engine = narrative_engine
        self._consecutive_brainstem_emergency: int = 0
        self._halt_reason: Optional[str] = None
        self._halted_at: Optional[float] = None

    def evaluate(
        self,
        runtime_health: Dict[str, Any],
        brainstem_state: str,
        memory_rss_mb: float,
        orchestrator: Any,
        runtime_state: str,
        circadian_phase: str,
    ) -> Optional[str]:
        """Returns halt reason if emergency triggered, else None."""
        if runtime_state == "halted":
            return None

        # Count consecutive brainstem emergency
        if brainstem_state == "emergency":
            self._consecutive_brainstem_emergency += 1
        else:
            self._consecutive_brainstem_emergency = 0

        if self._consecutive_brainstem_emergency >= self.brainstem_emergency_ticks:
            return self._trigger_halt(
                "brainstem_emergency_sustained",
                orchestrator,
                runtime_state,
                circadian_phase,
            )

        health_score = runtime_health.get("health_score", 1.0)
        if health_score <= self.health_score_threshold:
            return self._trigger_halt(
                "runtime_health_critical",
                orchestrator,
                runtime_state,
                circadian_phase,
            )

        if memory_rss_mb >= self.memory_rss_critical_mb:
            return self._trigger_halt(
                "memory_rss_critical",
                orchestrator,
                runtime_state,
                circadian_phase,
            )

        return None

    def _trigger_halt(
        self,
        reason: str,
        orchestrator: Any,
        runtime_state: str,
        circadian_phase: str,
    ) -> str:
        self._halt_reason = reason
        self._halted_at = time.time()

        # Save emergency checkpoint
        if self.checkpoint_manager is not None:
            try:
                self.checkpoint_manager.save(
                    orchestrator=orchestrator,
                    runtime_state="halting",
                    circadian_phase=circadian_phase,
                    emergency=True,
                )
            except Exception:
                logging.getLogger(__name__).warning("Emergency checkpoint save failed", exc_info=True)

        # Log narrative event
        if self.narrative_engine is not None:
            try:
                self.narrative_engine.record(
                    event_type="emergency_halt",
                    description=f"Emergency halt triggered: {reason}. Checkpoint saved. Runtime paused.",
                    importance=10,
                    metadata={
                        "reason": reason,
                        "halted_at": self._halted_at,
                        "tick": getattr(orchestrator, "current_tick", 0),
                    },
                )
            except Exception:
                logging.getLogger(__name__).warning("Narrative record failed during emergency halt", exc_info=True)

        return reason

    @property
    def is_halted(self) -> bool:
        return self._halt_reason is not None

    def reset(self) -> None:
        """Human-initiated reset after halt."""
        self._halt_reason = None
        self._halted_at = None
        self._consecutive_brainstem_emergency = 0

    def snapshot(self) -> Dict[str, Any]:
        return {
            "is_halted": self.is_halted,
            "halt_reason": self._halt_reason,
            "halted_at": self._halted_at,
            "consecutive_brainstem_emergency": self._consecutive_brainstem_emergency,
        }
