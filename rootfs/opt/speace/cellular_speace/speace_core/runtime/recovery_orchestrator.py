"""RecoveryOrchestrator — warm restart from checkpoint (T109).

At boot, checks for a recent checkpoint, validates it, and restores
orchestrator context. Falls back to cold start if none found.
"""

import time
from typing import Any, Dict, Optional


class RecoveryOrchestrator:
    """Restores runtime state from the latest checkpoint."""

    def __init__(
        self,
        checkpoint_manager: Any,
        narrative_engine: Any = None,
        session_continuity: Any = None,
    ) -> None:
        self.checkpoint_manager = checkpoint_manager
        self.narrative_engine = narrative_engine
        self.session_continuity = session_continuity
        self._recovery_status: str = "not_attempted"
        self._restored_from: Optional[str] = None

    def boot(self, orchestrator: Any) -> Dict[str, Any]:
        """Attempt recovery. Returns status dict."""
        checkpoint = self.checkpoint_manager.latest()
        if checkpoint is None:
            self._recovery_status = "cold_start"
            self._log_event("cold_start", "No checkpoint found. Starting from tick 0.")
            return {"status": "cold_start", "tick": 0}

        # Validate checkpoint
        orch_state = checkpoint.get("orchestrator", {})
        tick = orch_state.get("current_tick", 0)
        if tick <= 0:
            self._recovery_status = "cold_start"
            self._log_event("cold_start", "Checkpoint invalid (tick <= 0).")
            return {"status": "cold_start", "tick": 0}

        # Restore lightweight orchestrator state
        orchestrator.current_tick = tick
        orchestrator.tick_interval = orch_state.get("tick_interval", 1.0)
        orchestrator.execution_mode = orch_state.get("execution_mode", "global_tick")

        # Restore lifecycle state if possible
        lifecycle = getattr(orchestrator, "_lifecycle_manager", None)
        if lifecycle is not None:
            target = orch_state.get("lifecycle_state", "active")
            if target and lifecycle.validate_transition(target):
                lifecycle.transition_to(target, reason="recovery_from_checkpoint")

        self._recovery_status = "recovered"
        self._restored_from = checkpoint.get("timestamp")
        self._log_event(
            "recovered",
            f"Recovered from checkpoint at tick {tick}.",
            metadata={"tick": tick, "checkpoint_timestamp": self._restored_from},
        )

        return {
            "status": "recovered",
            "tick": tick,
            "checkpoint_timestamp": self._restored_from,
            "lifecycle_state": orch_state.get("lifecycle_state"),
            "brainstem_state": orch_state.get("brainstem_state"),
        }

    def _log_event(self, status: str, description: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        if self.narrative_engine is not None:
            try:
                self.narrative_engine.record(
                    event_type="runtime_recovery",
                    description=description,
                    importance=6 if status == "recovered" else 3,
                    metadata=metadata or {"status": status},
                )
            except Exception:
                pass

    def resume_narrative(self) -> str:
        if self.session_continuity is not None:
            try:
                return self.session_continuity.build_resume_narrative()
            except Exception:
                pass
        if self._recovery_status == "recovered":
            return "Sono tornato online dopo un recupero da checkpoint. Pronto a riprendere."
        return "Sono online. Pronto per iniziare."

    def snapshot(self) -> Dict[str, Any]:
        return {
            "recovery_status": self._recovery_status,
            "restored_from": self._restored_from,
            "resume_narrative": self.resume_narrative(),
        }
