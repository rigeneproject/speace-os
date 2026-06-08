"""NurserySessionOrchestrator — manages guided infant learning sessions in virtual scenarios (T168).

Human selects a scenario and duration. SPEACE observes, generates predictions,
compares with outcomes, and logs surprise. Predictions are NOT auto-consolidated
into memory; they require explicit human approval gate.
"""

import time
import uuid
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.embodiment.cognitive_nursery_scenario_builder import (
    CognitiveNurseryScenarioBuilder,
)
from speace_core.cellular_brain.embodiment.virtual_agent_population import VirtualAgentPopulation
from speace_core.cellular_brain.experience.temporal_narrative_engine import TemporalNarrativeEngine


class NurserySessionOrchestrator:
    """Orchestrates a single nursery session from start to close."""

    def __init__(
        self,
        scenario_builder: Optional[CognitiveNurseryScenarioBuilder] = None,
        agent_population: Optional[VirtualAgentPopulation] = None,
        narrative_engine: Optional[TemporalNarrativeEngine] = None,
    ) -> None:
        self._builder = scenario_builder or CognitiveNurseryScenarioBuilder()
        self._agents = agent_population or VirtualAgentPopulation()
        self._narrative_engine = narrative_engine
        self._session_log: List[Dict[str, Any]] = []
        self._prediction_error_log: List[Dict[str, Any]] = []
        self._active_session: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------ #
    # Session lifecycle
    # ------------------------------------------------------------------ #

    def start_session(
        self,
        scenario_id: str,
        duration_ticks: int = 20,
        human_overrides: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Begin a new nursery session."""
        scenario = self._builder.get(scenario_id)
        if scenario is None:
            return {"error": "scenario_not_found", "available": self._builder.list_scenarios()}

        run = scenario.instantiate(overrides=human_overrides)
        run["duration_ticks"] = duration_ticks
        run["start_time"] = time.time()
        run["tick_count"] = 0
        run["status"] = "running"

        self._active_session = run
        self._session_log.clear()
        self._prediction_error_log.clear()

        # Spawn virtual agents if social scenario
        if scenario_id in ("agent_approach", "tool_use"):
            self._agents.spawn(behavior_profile="curious")
            self._agents.spawn(behavior_profile="cautious")

        if self._narrative_engine is not None:
            try:
                self._narrative_engine.record(
                    event_type="nursery_session_started",
                    description=f"Nursery session {run['run_id']} started with scenario {scenario_id}.",
                    importance=4,
                    metadata={"scenario_id": scenario_id, "duration_ticks": duration_ticks},
                )
            except Exception:
                pass

        return {"status": "started", "session": run}

    def tick(self) -> Dict[str, Any]:
        """Advance the active session by one tick."""
        if self._active_session is None:
            return {"status": "no_active_session"}

        self._active_session["tick_count"] += 1
        tick_ctx = self._build_tick_context()

        # Run agents
        agent_states = self._agents.tick_all(tick_ctx)

        # SPEACE generates a prediction for the next step
        predicted = self._predict_next(tick_ctx)

        # Outcome is determined by scenario physics (simplified)
        outcome = self._simulate_outcome(tick_ctx)

        # Compute prediction error
        error = self._compute_prediction_error(predicted, outcome)
        self._prediction_error_log.append({
            "tick": self._active_session["tick_count"],
            "predicted": predicted,
            "outcome": outcome,
            "error": error,
        })

        # Log event
        self._session_log.append({
            "tick": self._active_session["tick_count"],
            "agent_states": agent_states,
            "predicted": predicted,
            "outcome": outcome,
            "error": error,
        })

        # Check session end
        if self._active_session["tick_count"] >= self._active_session["duration_ticks"]:
            self._active_session["status"] = "completed"
            if self._narrative_engine is not None:
                try:
                    self._narrative_engine.record(
                        event_type="nursery_session_completed",
                        description=f"Nursery session {self._active_session['run_id']} completed.",
                        importance=4,
                        metadata={
                            "total_ticks": self._active_session["tick_count"],
                            "mean_error": self._mean_error(),
                        },
                    )
                except Exception:
                    pass

        return {
            "tick": self._active_session["tick_count"],
            "status": self._active_session["status"],
            "predicted": predicted,
            "outcome": outcome,
            "error": error,
            "agent_states": agent_states,
        }

    def close_session(self) -> Dict[str, Any]:
        """Close the active session and return summary."""
        if self._active_session is None:
            return {"status": "no_active_session"}
        summary = {
            "run_id": self._active_session["run_id"],
            "scenario_id": self._active_session["scenario_id"],
            "total_ticks": self._active_session["tick_count"],
            "mean_prediction_error": self._mean_error(),
            "session_log_count": len(self._session_log),
        }
        self._active_session = None
        return {"status": "closed", "summary": summary}

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _build_tick_context(self) -> Dict[str, Any]:
        tick = self._active_session["tick_count"]
        return {
            "tick": tick,
            "food_nearby": tick % 5 == 0,
            "threat_nearby": tick % 7 == 0,
        }

    def _predict_next(self, ctx: Dict[str, Any]) -> str:
        # Simplified prediction based on scenario expected chain
        chain = self._active_session.get("expected_chain", [])
        idx = ctx["tick"] % max(len(chain), 1)
        return chain[idx] if chain else "unknown"

    def _simulate_outcome(self, ctx: Dict[str, Any]) -> str:
        # Simplified deterministic outcome
        chain = self._active_session.get("expected_chain", [])
        idx = ctx["tick"] % max(len(chain), 1)
        return chain[idx] if chain else "unknown"

    def _compute_prediction_error(self, predicted: str, outcome: str) -> float:
        return 0.0 if predicted == outcome else 1.0

    def _mean_error(self) -> float:
        if not self._prediction_error_log:
            return 0.0
        return sum(e["error"] for e in self._prediction_error_log) / len(self._prediction_error_log)

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def snapshot(self) -> Dict[str, Any]:
        return {
            "active_session": self._active_session,
            "builder": self._builder.snapshot(),
            "agents": self._agents.snapshot(),
            "mean_prediction_error": self._mean_error(),
        }
