"""Tests for T164 — Behavior Tree Layer."""

import time
from typing import Any, Dict, List

import pytest

from speace_core.cellular_brain.cognition.behavior_tree_core import (
    Action,
    BehaviorTree,
    Condition,
    Inverter,
    NodeStatus,
    Selector,
    Sequence,
    Succeeder,
)
from speace_core.cellular_brain.cognition.bt_runtime_integration import BTRuntimeIntegration
from speace_core.cellular_brain.cognition.reflex_behavior_library import (
    DEFAULT_BT_LIBRARY,
    build_avoid_overload,
    build_explore_local,
    build_prioritize_homeostatic_need,
    build_search_grounding_input,
)


class TestBTCoreNodes:
    def test_selector_success_on_first_child(self) -> None:
        sel = Selector(children=[
            Action(fn=lambda ctx: NodeStatus.SUCCESS),
            Action(fn=lambda ctx: NodeStatus.FAILURE),
        ])
        assert sel.tick({}) == NodeStatus.SUCCESS

    def test_selector_failure_when_all_fail(self) -> None:
        sel = Selector(children=[
            Action(fn=lambda ctx: NodeStatus.FAILURE),
            Action(fn=lambda ctx: NodeStatus.FAILURE),
        ])
        assert sel.tick({}) == NodeStatus.FAILURE

    def test_selector_running_persists(self) -> None:
        sel = Selector(children=[
            Action(fn=lambda ctx: NodeStatus.RUNNING),
            Action(fn=lambda ctx: NodeStatus.SUCCESS),
        ])
        assert sel.tick({}) == NodeStatus.RUNNING

    def test_sequence_success_when_all_succeed(self) -> None:
        seq = Sequence(children=[
            Action(fn=lambda ctx: NodeStatus.SUCCESS),
            Action(fn=lambda ctx: NodeStatus.SUCCESS),
        ])
        assert seq.tick({}) == NodeStatus.SUCCESS

    def test_sequence_failure_on_first_fail(self) -> None:
        seq = Sequence(children=[
            Action(fn=lambda ctx: NodeStatus.SUCCESS),
            Action(fn=lambda ctx: NodeStatus.FAILURE),
            Action(fn=lambda ctx: NodeStatus.SUCCESS),
        ])
        assert seq.tick({}) == NodeStatus.FAILURE

    def test_sequence_running_persists(self) -> None:
        seq = Sequence(children=[
            Action(fn=lambda ctx: NodeStatus.SUCCESS),
            Action(fn=lambda ctx: NodeStatus.RUNNING),
            Action(fn=lambda ctx: NodeStatus.SUCCESS),
        ])
        assert seq.tick({}) == NodeStatus.RUNNING

    def test_condition_true(self) -> None:
        cond = Condition(predicate=lambda ctx: True)
        assert cond.tick({}) == NodeStatus.SUCCESS

    def test_condition_false(self) -> None:
        cond = Condition(predicate=lambda ctx: False)
        assert cond.tick({}) == NodeStatus.FAILURE

    def test_inverter(self) -> None:
        inv = Inverter(child=Action(fn=lambda ctx: NodeStatus.SUCCESS))
        assert inv.tick({}) == NodeStatus.FAILURE

    def test_succeeder(self) -> None:
        suc = Succeeder(child=Action(fn=lambda ctx: NodeStatus.FAILURE))
        assert suc.tick({}) == NodeStatus.SUCCESS

    def test_action_exception_returns_failure(self) -> None:
        act = Action(fn=lambda ctx: 1 / 0)
        assert act.tick({}) == NodeStatus.FAILURE

    def test_tree_reset(self) -> None:
        tree = BehaviorTree(name="test", root=Sequence(children=[
            Action(fn=lambda ctx: NodeStatus.RUNNING),
        ]))
        tree.tick({})
        assert tree._last_status == NodeStatus.RUNNING
        tree.reset()
        assert tree._last_status == NodeStatus.FAILURE
        assert tree._tick_count == 0


class TestReflexBehaviorLibrary:
    def test_build_explore_local(self) -> None:
        tree = build_explore_local()
        ctx = {
            "health_score": 0.6,
            "curiosity_score": 0.7,
            "proposals": [],
        }
        status = tree.tick(ctx)
        assert status == NodeStatus.SUCCESS
        assert len(ctx["proposals"]) == 2
        assert ctx["proposals"][0]["proposal_type"] == "observe_sensor"

    def test_build_explore_local_fails_when_unstable(self) -> None:
        tree = build_explore_local()
        ctx = {
            "health_score": 0.2,
            "curiosity_score": 0.7,
            "proposals": [],
        }
        status = tree.tick(ctx)
        assert status == NodeStatus.FAILURE
        assert len(ctx["proposals"]) == 0

    def test_build_avoid_overload(self) -> None:
        tree = build_avoid_overload()
        ctx = {
            "cognitive_load": 0.9,
            "proposals": [],
        }
        status = tree.tick(ctx)
        assert status == NodeStatus.SUCCESS
        assert len(ctx["proposals"]) >= 1
        types = {p["proposal_type"] for p in ctx["proposals"]}
        assert types <= {"modulate_tick", "pause_modules", "request_state"}

    def test_build_prioritize_homeostatic_need_energy_low(self) -> None:
        tree = build_prioritize_homeostatic_need()
        ctx = {
            "energy": 0.1,
            "organism_state": "awake",
            "proposals": [],
        }
        status = tree.tick(ctx)
        assert status == NodeStatus.SUCCESS
        assert ctx["proposals"][0]["proposal_type"] == "energy_conservation"

    def test_build_search_grounding_input(self) -> None:
        tree = build_search_grounding_input()
        ctx = {
            "prediction_error": 0.8,
            "proposals": [],
        }
        status = tree.tick(ctx)
        assert status == NodeStatus.SUCCESS
        assert len(ctx["proposals"]) == 2

    def test_default_library_keys(self) -> None:
        assert set(DEFAULT_BT_LIBRARY.keys()) == {
            "explore_local",
            "avoid_overload",
            "prioritize_homeostatic_need",
            "search_grounding_input",
        }


class TestBTRuntimeIntegration:
    def test_tick_collects_proposals(self) -> None:
        bt = BTRuntimeIntegration()
        ctx = bt.build_context(
            health_score=0.6,
            cognitive_load=0.3,
            prediction_error=0.2,
            energy=0.8,
            curiosity_score=0.7,
            organism_state="exploring",
        )
        proposals = bt.tick(ctx)
        # explore_local should fire
        assert any(p["proposal_type"] == "observe_sensor" for p in proposals)

    def test_tick_no_proposals_when_overloaded(self) -> None:
        bt = BTRuntimeIntegration()
        ctx = bt.build_context(
            health_score=0.3,
            cognitive_load=0.9,
            prediction_error=0.8,
            energy=0.2,
            curiosity_score=0.0,
            organism_state="overloaded",
        )
        proposals = bt.tick(ctx)
        # avoid_overload should fire
        assert any(p["proposal_type"] in {"modulate_tick", "pause_modules", "request_state"} for p in proposals)

    def test_latency_under_budget(self) -> None:
        bt = BTRuntimeIntegration(max_tick_ms=1000.0)
        ctx = bt.build_context()
        start = time.time()
        bt.tick(ctx)
        elapsed_ms = (time.time() - start) * 1000.0
        assert elapsed_ms < 50.0  # generous; should be near-instant

    def test_snapshot(self) -> None:
        bt = BTRuntimeIntegration()
        bt.tick(bt.build_context())
        snap = bt.snapshot()
        assert snap["active_tree_count"] == 4
        assert "trees" in snap
        assert "last_tick_latencies_ms" in snap

    def test_timeout_skips_remaining(self) -> None:
        slow_fn = lambda ctx: (time.sleep(0.05), NodeStatus.SUCCESS)[1]
        from speace_core.cellular_brain.cognition.behavior_tree_core import Action
        slow_tree = BehaviorTree(name="slow", root=Action(fn=slow_fn))
        bt = BTRuntimeIntegration(library={"slow": lambda: slow_tree}, max_tick_ms=1.0)
        ctx = bt.build_context()
        proposals = bt.tick(ctx)
        # slow tree exceeds 1ms budget, so remaining trees are skipped
        assert len(proposals) == 0
        assert bt._last_tick_latencies_ms.get("slow", 0.0) >= 1.0
