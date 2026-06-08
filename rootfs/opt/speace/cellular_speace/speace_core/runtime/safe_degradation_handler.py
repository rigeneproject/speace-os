"""SafeDegradationHandler — conservative degradation under stress (T109).

Triggered by RuntimeHealthMonitor or brainstem state. Only reversible
actions: slow down, disable non-critical subsystems, enter conservation.
Never modifies code, never halts autonomously.
"""

import time
from typing import Any, Dict, List, Optional


class SafeDegradationHandler:
    """Applies graded degradation actions."""

    def __init__(
        self,
        enable_auto_slowdown: bool = True,
        enable_auto_conservation: bool = True,
        narrative_engine: Any = None,
    ) -> None:
        self.enable_auto_slowdown = enable_auto_slowdown
        self.enable_auto_conservation = enable_auto_conservation
        self.narrative_engine = narrative_engine
        self._actions_applied: List[Dict[str, Any]] = []
        self._slowdown_level: int = 0

    def evaluate(
        self,
        runtime_health: Dict[str, Any],
        brainstem_state: str,
        orchestrator: Any,
    ) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []
        health_score = runtime_health.get("health_score", 1.0)

        # Level 1: slowdown
        if self.enable_auto_slowdown and health_score < 0.6 and self._slowdown_level < 3:
            self._slowdown_level += 1
            new_interval = getattr(orchestrator, "tick_interval", 1.0) * 1.5
            orchestrator.tick_interval = new_interval
            actions.append({
                "action": "slowdown",
                "new_tick_interval": new_interval,
                "reason": "runtime_health_degraded",
                "timestamp": time.time(),
            })

        # Level 2: disable non-critical subsystems
        if health_score < 0.4:
            for flag_name in ("community_detection_enabled", "evolution_enabled"):
                if getattr(orchestrator, flag_name, False):
                    setattr(orchestrator, flag_name, False)
                    actions.append({
                        "action": "disable_subsystem",
                        "subsystem": flag_name,
                        "reason": "runtime_health_low",
                        "timestamp": time.time(),
                    })

        # Level 3: conservation via lifecycle
        if self.enable_auto_conservation and health_score < 0.25:
            lifecycle = getattr(orchestrator, "_lifecycle_manager", None)
            if lifecycle is not None and lifecycle.current_state != "conservation":
                transitioned = lifecycle.transition_to("conservation", reason="runtime_health_critical")
                if transitioned:
                    actions.append({
                        "action": "enter_conservation",
                        "reason": "runtime_health_critical",
                        "timestamp": time.time(),
                    })

        # Brainstem-driven degradation
        if brainstem_state in ("protective", "emergency"):
            if getattr(orchestrator, "global_workspace_enabled", False):
                setattr(orchestrator, "global_workspace_enabled", False)
                actions.append({
                    "action": "disable_subsystem",
                    "subsystem": "global_workspace_enabled",
                    "reason": f"brainstem_{brainstem_state}",
                    "timestamp": time.time(),
                })

        if actions:
            self._actions_applied.extend(actions)
            self._log_actions(actions)

        return actions

    def _log_actions(self, actions: List[Dict[str, Any]]) -> None:
        if self.narrative_engine is None:
            return
        for a in actions:
            try:
                self.narrative_engine.record(
                    event_type="safe_degradation",
                    description=f"Degradation action: {a['action']} ({a['reason']})",
                    importance=7 if a.get("action") == "enter_conservation" else 5,
                    metadata=a,
                )
            except Exception:
                pass

    def summary(self) -> Dict[str, Any]:
        return {
            "actions_applied": self._actions_applied,
            "slowdown_level": self._slowdown_level,
        }
