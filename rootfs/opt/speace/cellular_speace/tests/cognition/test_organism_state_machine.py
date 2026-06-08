"""Tests for T163 — OrganismStateMachine and StateTransitionPolicy."""

import time
from typing import Any, Dict, List

import pytest

from speace_core.cellular_brain.cognition.organism_state_machine import OrganismStateMachine
from speace_core.cellular_brain.cognition.state_transition_policy import StateTransitionPolicy


class FakeNarrativeEngine:
    """Minimal fake for narrative logging tests."""

    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    def record(self, event_type: str, description: str, importance: int = 0, metadata: Any = None) -> None:
        self.events.append({
            "event_type": event_type,
            "description": description,
            "importance": importance,
            "metadata": metadata,
        })


class TestStateTransitionPolicy:
    def test_min_dwell_enforced(self) -> None:
        policy = StateTransitionPolicy(min_dwell_ticks=3)
        # Even with extreme values, should not transition before 3 ticks
        assert policy.suggest_transition(
            current_state="awake", ticks_in_state=0,
            homeostasis_metrics=None, energy=0.05, cognitive_load=0.9,
            prediction_error=0.9, circadian_phase="night", health_score=0.1,
            curiosity_score=0.0,
        ) is None
        assert policy.suggest_transition(
            current_state="awake", ticks_in_state=2,
            homeostasis_metrics=None, energy=0.05, cognitive_load=0.9,
            prediction_error=0.9, circadian_phase="night", health_score=0.1,
            curiosity_score=0.0,
        ) is None
        # After 3 ticks, transition allowed
        result = policy.suggest_transition(
            current_state="awake", ticks_in_state=3,
            homeostasis_metrics=None, energy=0.05, cognitive_load=0.9,
            prediction_error=0.9, circadian_phase="night", health_score=0.1,
            curiosity_score=0.0,
        )
        assert result is not None

    def test_awake_to_overloaded(self) -> None:
        policy = StateTransitionPolicy(min_dwell_ticks=1)
        assert policy.suggest_transition(
            current_state="awake", ticks_in_state=1,
            homeostasis_metrics=None, energy=0.5, cognitive_load=0.9,
            prediction_error=0.8, circadian_phase="day", health_score=0.5,
            curiosity_score=0.0,
        ) == "overloaded"

    def test_awake_to_exploring(self) -> None:
        policy = StateTransitionPolicy(min_dwell_ticks=1)
        assert policy.suggest_transition(
            current_state="awake", ticks_in_state=1,
            homeostasis_metrics=None, energy=0.6, cognitive_load=0.3,
            prediction_error=0.3, circadian_phase="day", health_score=0.6,
            curiosity_score=0.7,
        ) == "exploring"

    def test_overloaded_to_recovering(self) -> None:
        policy = StateTransitionPolicy(min_dwell_ticks=1)
        assert policy.suggest_transition(
            current_state="overloaded", ticks_in_state=1,
            homeostasis_metrics=None, energy=0.5, cognitive_load=0.4,
            prediction_error=0.4, circadian_phase="day", health_score=0.6,
            curiosity_score=0.0,
        ) == "recovering"

    def test_snapshot(self) -> None:
        policy = StateTransitionPolicy(min_dwell_ticks=5)
        snap = policy.policy_snapshot()
        assert snap["min_dwell_ticks"] == 5
        assert "thresholds" in snap


class TestOrganismStateMachine:
    def test_initial_state(self) -> None:
        fsm = OrganismStateMachine()
        assert fsm.current_state() == "awake"
        assert fsm.snapshot()["transition_count"] == 0

    def test_invalid_initial_state_raises(self) -> None:
        with pytest.raises(ValueError):
            OrganismStateMachine(initial_state="invalid")

    def test_tick_no_transition_when_not_allowed(self) -> None:
        fsm = OrganismStateMachine()
        result = fsm.tick(
            homeostasis_metrics=None, energy=0.5, cognitive_load=0.5,
            prediction_error=0.5, circadian_phase="day", health_score=0.5,
            curiosity_score=0.0,
        )
        assert result["current_state"] == "awake"
        assert result["transitioned"] is False
        assert result["ticks_in_state"] == 1

    def test_tick_transitions_after_dwell(self) -> None:
        fsm = OrganismStateMachine(policy=StateTransitionPolicy(min_dwell_ticks=1))
        # First tick: stay awake (no extreme values)
        fsm.tick(
            homeostasis_metrics=None, energy=0.5, cognitive_load=0.5,
            prediction_error=0.5, circadian_phase="day", health_score=0.5,
            curiosity_score=0.0,
        )
        # Second tick with overload conditions
        result = fsm.tick(
            homeostasis_metrics=None, energy=0.5, cognitive_load=0.9,
            prediction_error=0.8, circadian_phase="day", health_score=0.5,
            curiosity_score=0.0,
        )
        assert result["transitioned"] is True
        assert result["current_state"] == "overloaded"
        assert result["previous_state"] == "awake"

    def test_narrative_logging(self) -> None:
        fake = FakeNarrativeEngine()
        fsm = OrganismStateMachine(
            policy=StateTransitionPolicy(min_dwell_ticks=1),
            narrative_engine=fake,
        )
        fsm.tick(
            homeostasis_metrics=None, energy=0.5, cognitive_load=0.9,
            prediction_error=0.8, circadian_phase="day", health_score=0.5,
            curiosity_score=0.0,
        )
        fsm.tick(
            homeostasis_metrics=None, energy=0.5, cognitive_load=0.9,
            prediction_error=0.8, circadian_phase="day", health_score=0.5,
            curiosity_score=0.0,
        )
        transitions = [e for e in fake.events if e["event_type"] == "organism_state_transition"]
        assert len(transitions) == 1
        assert transitions[0]["metadata"]["from_state"] == "awake"
        assert transitions[0]["metadata"]["to_state"] == "overloaded"

    def test_snapshot_after_transition(self) -> None:
        fake = FakeNarrativeEngine()
        fsm = OrganismStateMachine(
            policy=StateTransitionPolicy(min_dwell_ticks=1),
            narrative_engine=fake,
        )
        fsm.tick(
            homeostasis_metrics=None, energy=0.5, cognitive_load=0.9,
            prediction_error=0.8, circadian_phase="day", health_score=0.5,
            curiosity_score=0.0,
        )
        fsm.tick(
            homeostasis_metrics=None, energy=0.5, cognitive_load=0.9,
            prediction_error=0.8, circadian_phase="day", health_score=0.5,
            curiosity_score=0.0,
        )
        snap = fsm.snapshot()
        assert snap["current_state"] == "overloaded"
        assert snap["transition_count"] == 1
        assert len(snap["transition_history"]) == 1
        assert snap["policy"]["min_dwell_ticks"] == 1

    def test_multi_state_simulation(self) -> None:
        """Simulate 50 ticks with varying inputs and verify at least 3 distinct states are visited."""
        fsm = OrganismStateMachine(policy=StateTransitionPolicy(min_dwell_ticks=3))
        visited = {fsm.current_state()}

        for i in range(50):
            # Vary inputs to force different states
            if i < 5:
                energy, load, pred_err, circadian, curiosity = 0.5, 0.5, 0.5, "day", 0.0
            elif i < 15:
                energy, load, pred_err, circadian, curiosity = 0.1, 0.9, 0.8, "night", 0.0
            elif i < 25:
                energy, load, pred_err, circadian, curiosity = 0.6, 0.3, 0.2, "day", 0.7
            elif i < 35:
                energy, load, pred_err, circadian, curiosity = 0.4, 0.5, 0.1, "day", 0.2
            else:
                energy, load, pred_err, circadian, curiosity = 0.8, 0.2, 0.1, "day", 0.1

            result = fsm.tick(
                homeostasis_metrics=None, energy=energy, cognitive_load=load,
                prediction_error=pred_err, circadian_phase=circadian,
                health_score=energy, curiosity_score=curiosity,
            )
            visited.add(result["current_state"])

        assert len(visited) >= 3, f"Expected at least 3 states, got {visited}"

    def test_dwell_time_tracking(self) -> None:
        fsm = OrganismStateMachine()
        time.sleep(0.01)
        snap = fsm.snapshot()
        assert snap["dwell_time_seconds"] >= 0.0
