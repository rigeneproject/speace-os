import json
import tempfile
from pathlib import Path

import pytest

from speace_core.cellular_brain.self_improvement.goal_directed_planner import (
    GoalDirectedSelfImprovementPlanner,
    ImprovementGoal,
    ImprovementPlan,
    ImprovementPlanStep,
)


class FakeOutcomeMemory:
    def __init__(self, confidences=None):
        self.confidences = confidences or {}

    def get_confidence(self, limitation_type):
        return self.confidences.get(limitation_type, 0.5)


class FakeEpisodicPolicy:
    def __init__(self, penalties=None):
        self.penalties = penalties or {}

    def get_regression_penalty(self, limitation_type):
        return self.penalties.get(limitation_type, 0.0)


class FakeRegressionGuardSafe:
    def evaluate(self, metrics):
        result = type("RGResult", (), {"verdict": "POLICY_SAFE"})()
        return result


class FakeRegressionGuardUnsafe:
    def evaluate(self, metrics):
        result = type("RGResult", (), {"verdict": "POLICY_UNSAFE"})()
        return result


class TestBuildGoalFromMetric:
    def test_creates_goal(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = planner.build_goal_from_metric("coherence_phi", 0.8)
        assert goal.goal_id.startswith("goal-")
        assert goal.name == "Improve coherence_phi"
        assert goal.target_metric == "coherence_phi"
        assert goal.target_value == 0.8

    def test_uses_kwargs(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = planner.build_goal_from_metric("energy_efficiency", 0.9, tolerance=0.05, priority=2.0)
        assert goal.tolerance == 0.05
        assert goal.priority == 2.0


class TestAnalyzeGap:
    def test_positive_gap(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = ImprovementGoal(goal_id="g1", name="test", target_metric="phi", target_value=0.8)
        gap = planner.analyze_gap({"phi": 0.5}, goal)
        assert gap["gap"] == 0.3
        assert gap["within_tolerance"] is False

    def test_within_tolerance(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = ImprovementGoal(goal_id="g1", name="test", target_metric="phi", target_value=0.8, tolerance=0.05)
        gap = planner.analyze_gap({"phi": 0.78}, goal)
        assert gap["within_tolerance"] is True

    def test_missing_metric_defaults_zero(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = ImprovementGoal(goal_id="g1", name="test", target_metric="missing", target_value=0.8)
        gap = planner.analyze_gap({}, goal)
        assert gap["current_value"] == 0.0


class TestGenerateCandidateSteps:
    def test_semantic_recall_steps(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = planner.build_goal_from_metric("semantic_recall_success_rate", 0.9)
        steps = planner.generate_candidate_steps(goal, {"semantic_recall_success_rate": 0.4})
        assert len(steps) >= 1
        assert any(s.limitation_type == "semantic_recall_weak" for s in steps)

    def test_phi_steps(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = planner.build_goal_from_metric("coherence_phi", 0.8)
        steps = planner.generate_candidate_steps(goal, {"coherence_phi": 0.5})
        assert len(steps) >= 1
        assert any(s.limitation_type == "phi_regression" for s in steps)

    def test_energy_steps(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = planner.build_goal_from_metric("energy_efficiency", 0.9)
        steps = planner.generate_candidate_steps(goal, {"energy_efficiency": 0.4})
        assert len(steps) >= 1
        assert any(s.limitation_type == "energy_regression" for s in steps)

    def test_readiness_steps(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = planner.build_goal_from_metric("autonomous_improvement_readiness_score", 0.7)
        steps = planner.generate_candidate_steps(goal, {"autonomous_improvement_readiness_score": 0.3})
        assert len(steps) >= 1

    def test_regression_rate_steps(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = planner.build_goal_from_metric("regression_rate", 0.1)
        steps = planner.generate_candidate_steps(goal, {"regression_rate": 0.5})
        assert len(steps) >= 1
        assert any(s.limitation_type == "unsafe_self_modification_pattern" for s in steps)

    def test_associative_memory_steps(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = planner.build_goal_from_metric("associative_memory_gain", 0.8)
        steps = planner.generate_candidate_steps(goal, {"associative_memory_gain": 0.3})
        assert len(steps) >= 1

    def test_suppression_cost_steps(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = planner.build_goal_from_metric("suppression_cost", 0.3)
        steps = planner.generate_candidate_steps(goal, {"suppression_cost": 0.8})
        assert len(steps) >= 1
        assert any(s.limitation_type == "over_suppression" for s in steps)

    def test_unknown_metric_returns_empty(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = planner.build_goal_from_metric("unknown_metric", 0.9)
        steps = planner.generate_candidate_steps(goal, {"unknown_metric": 0.1})
        assert steps == []

    def test_within_tolerance_returns_empty(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = planner.build_goal_from_metric("coherence_phi", 0.8, tolerance=0.5)
        steps = planner.generate_candidate_steps(goal, {"coherence_phi": 0.79})
        assert steps == []


class TestComputeStepConfidence:
    def test_outcome_memory_boosts_confidence(self):
        mem = FakeOutcomeMemory(confidences={"semantic_recall_weak": 0.8})
        planner = GoalDirectedSelfImprovementPlanner(outcome_memory=mem)
        conf = planner._compute_step_confidence("semantic_recall_weak")
        assert conf > 0.5

    def test_episodic_penalty_reduces_confidence(self):
        pol = FakeEpisodicPolicy(penalties={"phi_regression": 0.4})
        planner = GoalDirectedSelfImprovementPlanner(episodic_policy=pol)
        conf = planner._compute_step_confidence("phi_regression")
        assert conf < 0.5


class TestRankSteps:
    def test_orders_by_score(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = ImprovementGoal(goal_id="g1", name="test", target_metric="phi", target_value=0.8)
        steps = [
            ImprovementPlanStep(step_id="s1", limitation_type="a", proposed_task="t", expected_metric_gain=0.5, expected_risk=0.1, confidence=0.5),
            ImprovementPlanStep(step_id="s2", limitation_type="b", proposed_task="t", expected_metric_gain=0.1, expected_risk=0.1, confidence=0.5),
        ]
        ranked = planner.rank_steps(steps, goal)
        assert ranked[0].step_id == "s1"


class TestBuildPlan:
    def test_plan_ready(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = planner.build_goal_from_metric("coherence_phi", 0.8)
        plan = planner.build_plan(goal, {"coherence_phi": 0.5})
        assert plan.verdict == "PLAN_READY"
        assert plan.expected_total_gain > 0

    def test_plan_blocked_by_readiness(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = planner.build_goal_from_metric("autonomous_improvement_readiness_score", 0.9)
        plan = planner.build_plan(goal, {"autonomous_improvement_readiness_score": 0.1}, readiness_score=0.1)
        assert plan.verdict == "PLAN_BLOCKED_BY_READINESS"

    def test_plan_unsafe_by_max_risk(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = ImprovementGoal(goal_id="g1", name="test", target_metric="coherence_phi", target_value=0.8, safety_constraints={"max_risk": 0.01})
        plan = planner.build_plan(goal, {"coherence_phi": 0.5})
        assert plan.verdict == "PLAN_UNSAFE"

    def test_plan_unsafe_by_regression_guard(self):
        rg = FakeRegressionGuardUnsafe()
        planner = GoalDirectedSelfImprovementPlanner(regression_guard=rg)
        goal = planner.build_goal_from_metric("coherence_phi", 0.8)
        plan = planner.build_plan(goal, {"coherence_phi": 0.5})
        assert plan.verdict == "PLAN_UNSAFE"

    def test_plan_weak_low_gain(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = ImprovementGoal(goal_id="g1", name="test", target_metric="unknown", target_value=0.8)
        plan = planner.build_plan(goal, {"unknown": 0.8})
        assert plan.verdict == "NO_ACTIONABLE_PLAN"

    def test_no_actionable_plan_when_no_steps(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = ImprovementGoal(goal_id="g1", name="test", target_metric="unknown", target_value=0.8)
        plan = planner.build_plan(goal, {"unknown": 0.8})
        assert plan.verdict == "NO_ACTIONABLE_PLAN"


class TestSelectSafePlan:
    def test_selects_ready(self):
        plans = [
            ImprovementPlan(plan_id="p1", goal=ImprovementGoal(goal_id="g1", name="a", target_metric="m", target_value=0.0), verdict="PLAN_READY", expected_total_gain=0.5),
            ImprovementPlan(plan_id="p2", goal=ImprovementGoal(goal_id="g2", name="b", target_metric="m", target_value=0.0), verdict="PLAN_WEAK", expected_total_gain=0.2),
        ]
        selected = GoalDirectedSelfImprovementPlanner.select_safe_plan(plans)
        assert selected.plan_id == "p1"

    def test_fallback_to_weak(self):
        plans = [
            ImprovementPlan(plan_id="p1", goal=ImprovementGoal(goal_id="g1", name="a", target_metric="m", target_value=0.0), verdict="PLAN_WEAK", expected_total_gain=0.2),
        ]
        selected = GoalDirectedSelfImprovementPlanner.select_safe_plan(plans)
        assert selected.plan_id == "p1"

    def test_fallback_blocked(self):
        plans = [
            ImprovementPlan(plan_id="p1", goal=ImprovementGoal(goal_id="g1", name="a", target_metric="m", target_value=0.0), verdict="PLAN_BLOCKED_BY_READINESS"),
        ]
        selected = GoalDirectedSelfImprovementPlanner.select_safe_plan(plans)
        assert selected.plan_id == "p1"

    def test_empty_plans_returns_no_actionable(self):
        selected = GoalDirectedSelfImprovementPlanner.select_safe_plan([])
        assert selected.verdict == "NO_ACTIONABLE_PLAN"


class TestReportGeneration:
    def test_markdown_contains_plan_id(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = planner.build_goal_from_metric("coherence_phi", 0.8)
        plan = planner.build_plan(goal, {"coherence_phi": 0.5})
        md = planner.generate_markdown_report(plan)
        assert plan.plan_id in md
        assert "PLAN_READY" in md

    def test_json_is_valid(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = planner.build_goal_from_metric("coherence_phi", 0.8)
        plan = planner.build_plan(goal, {"coherence_phi": 0.5})
        js = planner.generate_json_report(plan)
        data = json.loads(js)
        assert data["verdict"] == "PLAN_READY"

    def test_save_reports_creates_files(self, tmp_path):
        planner = GoalDirectedSelfImprovementPlanner(report_dir=str(tmp_path))
        goal = planner.build_goal_from_metric("coherence_phi", 0.8)
        plan = planner.build_plan(goal, {"coherence_phi": 0.5})
        planner.save_reports(plan)
        files = list(tmp_path.glob("goal_plan_*"))
        assert len(files) >= 2


class TestComputeGoalDirectedImprovementScore:
    def test_in_range(self):
        plans = [
            ImprovementPlan(plan_id="p1", goal=ImprovementGoal(goal_id="g1", name="a", target_metric="m", target_value=0.0), verdict="PLAN_READY", expected_total_gain=0.5, expected_total_risk=0.1, steps=[ImprovementPlanStep(step_id="s1", limitation_type="a", proposed_task="t", expected_metric_gain=0.5, expected_risk=0.1, confidence=0.8)]),
        ]
        score = GoalDirectedSelfImprovementPlanner.compute_goal_directed_improvement_score(plans)
        assert 0.0 <= score <= 1.0

    def test_zero_when_empty(self):
        score = GoalDirectedSelfImprovementPlanner.compute_goal_directed_improvement_score([])
        assert score == 0.0


class TestExtractBenchmarkMetrics:
    def test_contains_all_keys(self):
        plans = [
            ImprovementPlan(plan_id="p1", goal=ImprovementGoal(goal_id="g1", name="a", target_metric="m", target_value=0.0), verdict="PLAN_READY", expected_total_gain=0.5, expected_total_risk=0.1, steps=[ImprovementPlanStep(step_id="s1", limitation_type="a", proposed_task="t", expected_metric_gain=0.5, expected_risk=0.1, confidence=0.8)]),
        ]
        metrics = GoalDirectedSelfImprovementPlanner.extract_benchmark_metrics(plans)
        assert "goal_planner_goal_count" in metrics
        assert "goal_directed_improvement_score" in metrics
        assert metrics["goal_directed_improvement_score"] > 0.0


class TestSimulation:
    def test_simulate_plan_with_no_loop_returns_plan(self):
        planner = GoalDirectedSelfImprovementPlanner()
        goal = planner.build_goal_from_metric("coherence_phi", 0.8)
        plan = planner.build_plan(goal, {"coherence_phi": 0.5})
        result = planner.simulate_plan(plan, orchestrator=None)
        assert result is plan


class TestDependencies:
    def test_step_has_dependencies_field(self):
        step = ImprovementPlanStep(
            step_id="s1",
            limitation_type="a",
            proposed_task="t",
            expected_metric_gain=0.1,
            expected_risk=0.05,
            confidence=0.5,
            dependencies=["step-0"],
        )
        assert step.dependencies == ["step-0"]
