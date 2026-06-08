"""Tests for T168 — Simulated Cognitive Nursery."""

import pytest

from speace_core.cellular_brain.embodiment.cognitive_nursery_scenario_builder import (
    CognitiveNurseryScenarioBuilder,
    NurseryScenario,
)
from speace_core.cellular_brain.embodiment.virtual_agent_population import VirtualAgent, VirtualAgentPopulation
from speace_core.cellular_brain.postnatal_learning.nursery_session_orchestrator import (
    NurserySessionOrchestrator,
)


class TestNurseryScenarioBuilder:
    def test_default_scenarios_loaded(self) -> None:
        builder = CognitiveNurseryScenarioBuilder()
        scenarios = builder.list_scenarios()
        assert len(scenarios) >= 4
        ids = {s["scenario_id"] for s in scenarios}
        assert ids >= {"falling_objects", "agent_approach", "tool_use", "hidden_object"}

    def test_instantiate_scenario(self) -> None:
        builder = CognitiveNurseryScenarioBuilder()
        run = builder.get("falling_objects").instantiate()
        assert run["status"] == "ready"
        assert "run_id" in run
        assert "expected_chain" in run

    def test_custom_override(self) -> None:
        builder = CognitiveNurseryScenarioBuilder()
        run = builder.get("falling_objects").instantiate({"gravity": 5.0})
        assert run["variables"]["gravity"] == 5.0


class TestVirtualAgentPopulation:
    def test_spawn(self) -> None:
        pop = VirtualAgentPopulation()
        agent = pop.spawn("curious")
        assert agent.agent_id.startswith("agent_")
        assert agent.behavior_profile == "curious"

    def test_tick_all(self) -> None:
        pop = VirtualAgentPopulation()
        pop.spawn("curious")
        states = pop.tick_all({"food_nearby": True})
        assert len(states) == 1
        assert states[0]["state"] == "approaching"

    def test_distinct_profiles(self) -> None:
        pop = VirtualAgentPopulation()
        curious = pop.spawn("curious")
        cautious = pop.spawn("cautious")
        pop.tick_all({"food_nearby": True})
        assert curious.state == "approaching"
        pop.tick_all({"food_nearby": True})
        assert cautious.state == "approaching" or cautious.state == "idle"


class TestNurserySessionOrchestrator:
    def test_start_session(self) -> None:
        orch = NurserySessionOrchestrator()
        result = orch.start_session("falling_objects", duration_ticks=5)
        assert result["status"] == "started"
        assert "session" in result

    def test_start_unknown_scenario(self) -> None:
        orch = NurserySessionOrchestrator()
        result = orch.start_session("nonexistent")
        assert "error" in result

    def test_tick_generates_prediction_and_outcome(self) -> None:
        orch = NurserySessionOrchestrator()
        orch.start_session("falling_objects", duration_ticks=3)
        tick = orch.tick()
        assert "predicted" in tick
        assert "outcome" in tick
        assert "error" in tick

    def test_session_completes(self) -> None:
        orch = NurserySessionOrchestrator()
        orch.start_session("falling_objects", duration_ticks=2)
        orch.tick()
        orch.tick()
        orch.tick()
        assert orch._active_session["status"] == "completed"

    def test_close_session(self) -> None:
        orch = NurserySessionOrchestrator()
        orch.start_session("falling_objects", duration_ticks=2)
        orch.tick()
        result = orch.close_session()
        assert result["status"] == "closed"
        assert "summary" in result

    def test_mean_error(self) -> None:
        orch = NurserySessionOrchestrator()
        orch.start_session("falling_objects", duration_ticks=3)
        for _ in range(3):
            orch.tick()
        assert orch._mean_error() >= 0.0

    def test_snapshot(self) -> None:
        orch = NurserySessionOrchestrator()
        snap = orch.snapshot()
        assert "builder" in snap
        assert "agents" in snap
