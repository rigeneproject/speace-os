"""OrganismStateMachine — global cognitive organismic states for SPEACE (T163).

Models states: awake, focused, exploring, resting, consolidating, overloaded, recovering.
Transitions are suggested by StateTransitionPolicy and applied with hysteresis.
"""

import time
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.cognition.state_transition_policy import StateTransitionPolicy
from speace_core.cellular_brain.experience.temporal_narrative_engine import TemporalNarrativeEngine


class OrganismStateMachine:
    """Finite state machine for organismic cognitive states."""

    STATES = ("awake", "focused", "exploring", "resting", "consolidating", "overloaded", "recovering")

    def __init__(
        self,
        initial_state: str = "awake",
        policy: Optional[StateTransitionPolicy] = None,
        narrative_engine: Optional[TemporalNarrativeEngine] = None,
    ) -> None:
        if initial_state not in self.STATES:
            raise ValueError(f"Invalid initial state: {initial_state}")
        self._state: str = initial_state
        self._policy = policy or StateTransitionPolicy()
        self._narrative_engine = narrative_engine

        self._ticks_in_state: int = 0
        self._entered_state_at: float = time.time()
        self._transition_history: List[Dict[str, Any]] = []
        self._max_history: int = 100

    # ------------------------------------------------------------------ #
    # Tick
    # ------------------------------------------------------------------ #

    def tick(
        self,
        homeostasis_metrics: Any,
        energy: float,
        cognitive_load: float,
        prediction_error: float,
        circadian_phase: str,
        health_score: float,
        curiosity_score: float,
    ) -> Dict[str, Any]:
        """Evaluate policy and transition if guards are met.

        Returns a dict with `previous_state`, `current_state`, `transitioned`,
        `dwell_time_seconds`, and `ticks_in_state`.
        """
        suggested = self._policy.suggest_transition(
            current_state=self._state,
            ticks_in_state=self._ticks_in_state,
            homeostasis_metrics=homeostasis_metrics,
            energy=energy,
            cognitive_load=cognitive_load,
            prediction_error=prediction_error,
            circadian_phase=circadian_phase,
            health_score=health_score,
            curiosity_score=curiosity_score,
        )

        transitioned = False
        previous_state = self._state
        if suggested is not None and suggested in self.STATES:
            self._transition(suggested, context={
                "previous_state": previous_state,
                "energy": energy,
                "cognitive_load": cognitive_load,
                "prediction_error": prediction_error,
                "circadian_phase": circadian_phase,
                "health_score": health_score,
                "curiosity_score": curiosity_score,
            })
            transitioned = True

        self._ticks_in_state += 1
        dwell = time.time() - self._entered_state_at

        return {
            "previous_state": previous_state,
            "current_state": self._state,
            "transitioned": transitioned,
            "suggested_state": suggested,
            "ticks_in_state": self._ticks_in_state,
            "dwell_time_seconds": round(dwell, 3),
        }

    # ------------------------------------------------------------------ #
    # Transition helpers
    # ------------------------------------------------------------------ #

    def _transition(self, new_state: str, context: Dict[str, Any]) -> None:
        old_state = self._state
        self._state = new_state
        self._ticks_in_state = 0
        self._entered_state_at = time.time()

        record = {
            "from": old_state,
            "to": new_state,
            "at": self._entered_state_at,
            "context": context,
        }
        self._transition_history.append(record)
        if len(self._transition_history) > self._max_history:
            self._transition_history.pop(0)

        if self._narrative_engine is not None:
            try:
                self._narrative_engine.record(
                    event_type="organism_state_transition",
                    description=f"Organism state transitioned from {old_state} to {new_state}.",
                    importance=5,
                    metadata={
                        "from_state": old_state,
                        "to_state": new_state,
                        "energy": round(context.get("energy", 0.0), 3),
                        "cognitive_load": round(context.get("cognitive_load", 0.0), 3),
                        "prediction_error": round(context.get("prediction_error", 0.0), 3),
                        "circadian_phase": context.get("circadian_phase", "unknown"),
                    },
                )
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def current_state(self) -> str:
        return self._state

    def snapshot(self) -> Dict[str, Any]:
        return {
            "current_state": self._state,
            "ticks_in_state": self._ticks_in_state,
            "dwell_time_seconds": round(time.time() - self._entered_state_at, 3) if self._entered_state_at else 0.0,
            "transition_count": len(self._transition_history),
            "transition_history": [
                {
                    "from": r["from"],
                    "to": r["to"],
                    "at": r["at"],
                }
                for r in self._transition_history[-20:]
            ],
            "policy": self._policy.policy_snapshot(),
        }
