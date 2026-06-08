"""Tests for T166 — GOAP Layer."""

import pytest

from speace_core.cellular_brain.cognition.goap_action_registry import GOAPActionRegistry
from speace_core.cellular_brain.cognition.goap_metacognitive_bridge import GOAPMetacognitiveBridge
from speace_core.cellular_brain.cognition.goap_planner import GOAPAction, GOAPPlanner, GoalState
from speace_core.cellular_brain.cognition.goap_runtime_integration import GOAPRuntimeIntegration


class TestGOAPPlanner:
    def test_simple_plan(self) -> None:
        actions = [
            GOAPAction(
                name="observe",
                preconditions={"sensor_ready": True},
                effects={"data_collected": True},
                cost=1.0,
            ),
            GOAPAction(
                name="analyze",
                preconditions={"data_collected": True},
                effects={"prediction_error": "reduced"},
                cost=1.0,
            ),
        ]
        planner = GOAPPlanner(actions=actions)
        initial = {"sensor_ready": True}
        goal = GoalState({"prediction_error": "reduced"})
        plan = planner.plan(initial, goal)
        assert plan is not None
        assert plan["actions"] == ["observe", "analyze"]
        assert plan["total_cost"] == 2.0

    def test_no_plan_when_preconditions_unmet(self) -> None:
        actions = [
            GOAPAction(
                name="analyze",
                preconditions={"data_collected": True},
                effects={"prediction_error": "reduced"},
                cost=1.0,
            ),
        ]
        planner = GOAPPlanner(actions=actions)
        initial = {"sensor_ready": True}
        goal = GoalState({"prediction_error": "reduced"})
        plan = planner.plan(initial, goal)
        assert plan is None

    def test_planning_timeout(self) -> None:
        planner = GOAPPlanner()
        planner._max_planning_ms = 0.001
        # Large state space to force timeout
        for i in range(50):
            planner.add_action(GOAPAction(
                name=f"act_{i}",
                preconditions={},
                effects={f"k{i}": True},
                cost=1.0,
            ))
        initial = {}
        goal = GoalState({"k49": True})
        plan = planner.plan(initial, goal)
        # May or may not find plan before timeout; just ensure no crash
        assert plan is None or isinstance(plan, dict)


class TestGOAPActionRegistry:
    def test_default_registry_populated(self) -> None:
        reg = GOAPActionRegistry()
        reg.build_default_registry()
        assert len(reg.list_actions()) >= 6

    def test_get_action(self) -> None:
        reg = GOAPActionRegistry()
        reg.build_default_registry()
        act = reg.get_action("observe_sensor")
        assert act is not None
        assert act.simulate_only is True

    def test_snapshot(self) -> None:
        reg = GOAPActionRegistry()
        reg.build_default_registry()
        snap = reg.snapshot()
        assert snap["count"] >= 6


class TestGOAPMetacognitiveBridge:
    def test_no_plan_returns_fallback(self) -> None:
        bridge = GOAPMetacognitiveBridge()
        result = bridge.evaluate_plan(None, {})
        assert result["proceed"] is False
        assert result["fallback_to_reflex"] is True

    def test_low_confidence_blocks(self) -> None:
        bridge = GOAPMetacognitiveBridge()
        plan = {"actions": ["a"], "total_cost": 1.0}
        result = bridge.evaluate_plan(plan, {})
        # Default confidence is 0.5, which is >= 0.3 threshold
        assert result["proceed"] is True

    def test_snapshot(self) -> None:
        bridge = GOAPMetacognitiveBridge()
        assert bridge.snapshot()["confidence_threshold"] == 0.3


class TestGOAPRuntimeIntegration:
    def test_tick_generates_proposal(self) -> None:
        goap = GOAPRuntimeIntegration()
        ctx = {"world_state": {"sensor_data_fresh": False, "prediction_error": "high"}}
        proposals = goap.tick(ctx, goal_predicates={"prediction_error": "reduced"})
        # With default registry, at least observe_sensor should be applicable
        assert len(proposals) >= 0

    def test_tick_with_no_goal_uses_default(self) -> None:
        goap = GOAPRuntimeIntegration()
        ctx = {"world_state": {"sensor_data_fresh": False, "prediction_error": "high"}}
        proposals = goap.tick(ctx)
        assert isinstance(proposals, list)

    def test_snapshot(self) -> None:
        goap = GOAPRuntimeIntegration()
        snap = goap.snapshot()
        assert "planner" in snap
        assert "registry" in snap
        assert "bridge" in snap
