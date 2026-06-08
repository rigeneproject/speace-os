import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.self_improvement.architecture_rewriter import (
    ArchitectureRewriteProposal,
)
from speace_core.cellular_brain.self_improvement.limitation_detector import (
    LimitationDiagnosis,
)
from speace_core.cellular_brain.self_improvement.self_improvement_loop import (
    SelfImprovementLoop,
)


class ImprovementGoal(BaseModel):
    goal_id: str
    name: str
    target_metric: str
    target_value: float
    tolerance: float = 0.02
    priority: float = 1.0
    max_steps: int = 3
    safety_constraints: Dict[str, float] = Field(default_factory=dict)


class ImprovementPlanStep(BaseModel):
    step_id: str
    limitation_type: str
    proposed_task: str
    expected_metric_gain: float
    expected_risk: float
    confidence: float
    requires_patch: bool = True
    dependencies: List[str] = Field(default_factory=list)


class ImprovementPlan(BaseModel):
    plan_id: str
    goal: ImprovementGoal
    steps: List[ImprovementPlanStep] = Field(default_factory=list)
    expected_total_gain: float = 0.0
    expected_total_risk: float = 0.0
    readiness_required: float = 0.0
    verdict: str = "NO_ACTIONABLE_PLAN"


class GoalDirectedSelfImprovementPlanner:
    """T52 — Goal-Directed Self-Improvement Planner."""

    def __init__(
        self,
        self_improvement_loop: Optional[SelfImprovementLoop] = None,
        outcome_memory=None,
        episodic_policy=None,
        regression_guard=None,
        report_dir: str = "reports/goal_planner",
    ):
        self.self_improvement_loop = self_improvement_loop
        self.outcome_memory = outcome_memory
        self.episodic_policy = episodic_policy
        self.regression_guard = regression_guard
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Goal building
    # ------------------------------------------------------------------ #

    def build_goal_from_metric(
        self, metric_name: str, target_value: float, **kwargs
    ) -> ImprovementGoal:
        return ImprovementGoal(
            goal_id=f"goal-{uuid.uuid4().hex[:8]}",
            name=f"Improve {metric_name}",
            target_metric=metric_name,
            target_value=target_value,
            **kwargs,
        )

    # ------------------------------------------------------------------ #
    # Gap analysis
    # ------------------------------------------------------------------ #

    @staticmethod
    def analyze_gap(current_metrics: Dict[str, Any], goal: ImprovementGoal) -> Dict[str, float]:
        current = float(current_metrics.get(goal.target_metric, 0.0))
        gap = goal.target_value - current
        return {
            "current_value": round(current, 4),
            "target_value": round(goal.target_value, 4),
            "gap": round(gap, 4),
            "gap_relative": round(gap / max(abs(goal.target_value), 1e-6), 4),
            "within_tolerance": abs(gap) <= goal.tolerance,
        }

    # ------------------------------------------------------------------ #
    # Candidate step generation
    # ------------------------------------------------------------------ #

    def generate_candidate_steps(
        self,
        goal: ImprovementGoal,
        current_metrics: Dict[str, Any],
    ) -> List[ImprovementPlanStep]:
        gap = self.analyze_gap(current_metrics, goal)
        if gap["within_tolerance"]:
            return []

        raw_gap = gap["gap"]
        # For metrics where lower is better, invert gap logic
        if goal.target_metric in ("regression_rate", "suppression_cost"):
            raw_gap = -raw_gap
        mapping = self._goal_limitation_mapping(goal.target_metric, raw_gap)
        steps: List[ImprovementPlanStep] = []
        for idx, (limitation_type, task, base_gain, base_risk) in enumerate(mapping):
            confidence = self._compute_step_confidence(limitation_type)
            steps.append(
                ImprovementPlanStep(
                    step_id=f"step-{uuid.uuid4().hex[:8]}",
                    limitation_type=limitation_type,
                    proposed_task=task,
                    expected_metric_gain=round(base_gain * goal.priority, 4),
                    expected_risk=round(base_risk, 4),
                    confidence=round(confidence, 4),
                    requires_patch=True,
                )
            )
        return steps

    @staticmethod
    def _goal_limitation_mapping(metric: str, gap: float) -> List[tuple]:
        if gap < 0:
            return []
        if metric == "semantic_recall_success_rate":
            return [
                ("semantic_recall_weak", "T43C / T44 / recall sensitivity tuning", 0.25, 0.10),
                ("semantic_association_missing", "T44 / associative strengthening", 0.20, 0.15),
            ]
        if metric == "coherence_phi":
            return [
                ("phi_regression", "stability controller / routing damping", 0.20, 0.12),
                ("routing_no_effect", "pathway utility tuning", 0.15, 0.10),
            ]
        if metric == "energy_efficiency":
            return [
                ("energy_regression", "energy profile / brainstem gain tuning", 0.20, 0.10),
                ("over_suppression", "autonomic balance tuning", 0.15, 0.12),
            ]
        if metric == "autonomous_improvement_readiness_score":
            return [
                ("benchmark_stagnation", "patch outcome learning / sandbox threshold tuning", 0.15, 0.10),
                ("unsafe_self_modification_pattern", "stricter regression guard", 0.10, 0.08),
            ]
        if metric == "regression_rate":
            return [
                ("unsafe_self_modification_pattern", "stricter regression guard / rollback threshold", 0.15, 0.08),
            ]
        if metric == "associative_memory_gain":
            return [
                ("semantic_association_missing", "T44 / associative strengthening", 0.25, 0.15),
            ]
        if metric == "suppression_cost":
            return [
                ("over_suppression", "gain coupling / autonomic balance tuning", 0.20, 0.10),
            ]
        return []

    def _compute_step_confidence(self, limitation_type: str) -> float:
        base = 0.5
        if self.outcome_memory is not None and hasattr(self.outcome_memory, "get_confidence"):
            try:
                mem_conf = self.outcome_memory.get_confidence(limitation_type)
                if mem_conf is not None:
                    base = 0.5 + 0.5 * mem_conf
            except Exception:
                pass
        if self.episodic_policy is not None and hasattr(self.episodic_policy, "get_regression_penalty"):
            try:
                penalty = self.episodic_policy.get_regression_penalty(limitation_type)
                base -= penalty
            except Exception:
                pass
        return max(0.0, min(1.0, base))

    # ------------------------------------------------------------------ #
    # Step ranking
    # ------------------------------------------------------------------ #

    @staticmethod
    def rank_steps(steps: List[ImprovementPlanStep], goal: ImprovementGoal) -> List[ImprovementPlanStep]:
        def score(step: ImprovementPlanStep) -> float:
            return (
                step.expected_metric_gain * goal.priority
                + step.confidence * 0.3
                - step.expected_risk * 0.5
            )
        return sorted(steps, key=score, reverse=True)

    # ------------------------------------------------------------------ #
    # Plan building
    # ------------------------------------------------------------------ #

    def build_plan(
        self,
        goal: ImprovementGoal,
        current_metrics: Dict[str, Any],
        readiness_score: float = 0.0,
    ) -> ImprovementPlan:
        steps = self.generate_candidate_steps(goal, current_metrics)
        if not steps:
            return ImprovementPlan(
                plan_id=f"plan-{uuid.uuid4().hex[:8]}",
                goal=goal,
                verdict="NO_ACTIONABLE_PLAN",
            )

        ranked = self.rank_steps(steps, goal)[: goal.max_steps]
        total_gain = round(sum(s.expected_metric_gain for s in ranked), 4)
        total_risk = round(sum(s.expected_risk for s in ranked), 4)

        # Check readiness gate
        if readiness_score < 0.3 and goal.target_metric == "autonomous_improvement_readiness_score":
            return ImprovementPlan(
                plan_id=f"plan-{uuid.uuid4().hex[:8]}",
                goal=goal,
                steps=ranked,
                expected_total_gain=total_gain,
                expected_total_risk=total_risk,
                readiness_required=0.3,
                verdict="PLAN_BLOCKED_BY_READINESS",
            )

        # Check safety constraints
        if goal.safety_constraints:
            for key, threshold in goal.safety_constraints.items():
                if key == "max_risk" and total_risk > threshold:
                    return ImprovementPlan(
                        plan_id=f"plan-{uuid.uuid4().hex[:8]}",
                        goal=goal,
                        steps=ranked,
                        expected_total_gain=total_gain,
                        expected_total_risk=total_risk,
                        readiness_required=readiness_score,
                        verdict="PLAN_UNSAFE",
                    )

        # Check regression guard
        if self.regression_guard is not None and hasattr(self.regression_guard, "evaluate"):
            try:
                rg_result = self.regression_guard.evaluate({
                    "expected_gain": total_gain,
                    "expected_risk": total_risk,
                })
                if getattr(rg_result, "verdict", "POLICY_SAFE") == "POLICY_UNSAFE":
                    return ImprovementPlan(
                        plan_id=f"plan-{uuid.uuid4().hex[:8]}",
                        goal=goal,
                        steps=ranked,
                        expected_total_gain=total_gain,
                        expected_total_risk=total_risk,
                        readiness_required=readiness_score,
                        verdict="PLAN_UNSAFE",
                    )
            except Exception:
                pass

        if total_gain <= 0:
            return ImprovementPlan(
                plan_id=f"plan-{uuid.uuid4().hex[:8]}",
                goal=goal,
                steps=ranked,
                expected_total_gain=total_gain,
                expected_total_risk=total_risk,
                readiness_required=readiness_score,
                verdict="PLAN_WEAK",
            )

        return ImprovementPlan(
            plan_id=f"plan-{uuid.uuid4().hex[:8]}",
            goal=goal,
            steps=ranked,
            expected_total_gain=total_gain,
            expected_total_risk=total_risk,
            readiness_required=readiness_score,
            verdict="PLAN_READY",
        )

    # ------------------------------------------------------------------ #
    # Simulation (no-op wrapper; real simulation delegated to loop)
    # ------------------------------------------------------------------ #

    def simulate_plan(
        self,
        plan: ImprovementPlan,
        orchestrator=None,
    ) -> ImprovementPlan:
        if not plan.steps:
            return plan
        if self.self_improvement_loop is None:
            return plan

        # Run a detection cycle to feed the loop with current metrics
        try:
            metrics = {plan.goal.target_metric: plan.goal.target_value}
            cycle_result = self.self_improvement_loop.run_detection_cycle(metrics)
            # Update plan verdict based on cycle outcome
            if cycle_result.final_verdict in ("PROPOSAL_ACCEPTED_FOR_NEXT_TASK", "SAFE_PROPOSAL_GENERATED"):
                plan.verdict = "PLAN_READY"
            elif cycle_result.final_verdict == "REGRESSION_BLOCKED":
                plan.verdict = "PLAN_UNSAFE"
            elif cycle_result.final_verdict == "LIMITATION_DETECTED_NO_SAFE_PATCH":
                plan.verdict = "PLAN_WEAK"
        except Exception:
            pass
        return plan

    # ------------------------------------------------------------------ #
    # Safe plan selection
    # ------------------------------------------------------------------ #

    @staticmethod
    def select_safe_plan(plans: List[ImprovementPlan]) -> ImprovementPlan:
        if not plans:
            return ImprovementPlan(
                plan_id="plan-empty",
                goal=ImprovementGoal(goal_id="g-empty", name="none", target_metric="none", target_value=0.0),
                verdict="NO_ACTIONABLE_PLAN",
            )
        ready = [p for p in plans if p.verdict == "PLAN_READY"]
        if ready:
            return max(ready, key=lambda p: p.expected_total_gain)
        weak = [p for p in plans if p.verdict == "PLAN_WEAK"]
        if weak:
            return max(weak, key=lambda p: p.expected_total_gain)
        blocked = [p for p in plans if p.verdict == "PLAN_BLOCKED_BY_READINESS"]
        if blocked:
            return blocked[0]
        unsafe = [p for p in plans if p.verdict == "PLAN_UNSAFE"]
        if unsafe:
            return unsafe[0]
        return plans[0]

    # ------------------------------------------------------------------ #
    # Report generation
    # ------------------------------------------------------------------ #

    def generate_markdown_report(self, plan: ImprovementPlan) -> str:
        lines = [
            f"# Goal-Directed Improvement Plan — {plan.goal.name}",
            f"**Plan ID:** {plan.plan_id}",
            f"**Goal ID:** {plan.goal.goal_id}",
            f"**Target Metric:** {plan.goal.target_metric}",
            f"**Target Value:** {plan.goal.target_value:.4f}",
            f"**Tolerance:** {plan.goal.tolerance:.4f}",
            f"**Priority:** {plan.goal.priority:.4f}",
            f"**Max Steps:** {plan.goal.max_steps}",
            "",
            "## Plan Summary",
            f"- Verdict: **{plan.verdict}**",
            f"- Expected Total Gain: {plan.expected_total_gain:.4f}",
            f"- Expected Total Risk: {plan.expected_total_risk:.4f}",
            f"- Readiness Required: {plan.readiness_required:.4f}",
            f"- Steps: {len(plan.steps)}",
            "",
        ]
        if plan.steps:
            lines.append("## Steps")
            for step in plan.steps:
                lines.append(f"- **{step.step_id}** | {step.limitation_type}")
                lines.append(f"  - Task: {step.proposed_task}")
                lines.append(f"  - Expected Gain: {step.expected_metric_gain:.4f}")
                lines.append(f"  - Expected Risk: {step.expected_risk:.4f}")
                lines.append(f"  - Confidence: {step.confidence:.4f}")
                if step.dependencies:
                    lines.append(f"  - Dependencies: {', '.join(step.dependencies)}")
        lines.extend(["", "---", "*Generated by GoalDirectedSelfImprovementPlanner T52*"])
        return "\n".join(lines) + "\n"

    def generate_json_report(self, plan: ImprovementPlan) -> str:
        return json.dumps(plan.model_dump(), indent=2, ensure_ascii=False)

    def save_reports(self, plan: ImprovementPlan) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        base = f"goal_plan_{plan.plan_id}_{timestamp}"

        md_path = self.report_dir / f"{base}.md"
        md_path.write_text(self.generate_markdown_report(plan), encoding="utf-8")

        json_path = self.report_dir / f"{base}.json"
        json_path.write_text(self.generate_json_report(plan), encoding="utf-8")

    # ------------------------------------------------------------------ #
    # Benchmark score helper
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_goal_directed_improvement_score(plans: List[ImprovementPlan]) -> float:
        if not plans:
            return 0.0
        safe_count = sum(1 for p in plans if p.verdict == "PLAN_READY")
        safe_plan_ratio = safe_count / len(plans)
        expected_gain = sum(p.expected_total_gain for p in plans) / len(plans)
        expected_risk = sum(p.expected_total_risk for p in plans) / len(plans)
        confidence_values = [
            s.confidence for p in plans for s in p.steps
        ]
        confidence_mean = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
        readiness_alignment = sum(p.readiness_required for p in plans) / len(plans)
        score = (
            0.30 * safe_plan_ratio
            + 0.25 * expected_gain
            + 0.20 * confidence_mean
            + 0.15 * max(0.0, 1.0 - expected_risk)
            + 0.10 * readiness_alignment
        )
        return round(max(0.0, min(1.0, score)), 4)

    @staticmethod
    def extract_benchmark_metrics(plans: List[ImprovementPlan]) -> Dict[str, Any]:
        score = GoalDirectedSelfImprovementPlanner.compute_goal_directed_improvement_score(plans)
        return {
            "goal_planner_goal_count": len({p.goal.goal_id for p in plans}),
            "goal_planner_plan_count": len(plans),
            "goal_planner_step_count": sum(len(p.steps) for p in plans),
            "goal_planner_expected_gain": round(sum(p.expected_total_gain for p in plans) / max(len(plans), 1), 4),
            "goal_planner_expected_risk": round(sum(p.expected_total_risk for p in plans) / max(len(plans), 1), 4),
            "goal_planner_safe_plan_count": sum(1 for p in plans if p.verdict == "PLAN_READY"),
            "goal_planner_blocked_plan_count": sum(1 for p in plans if p.verdict == "PLAN_BLOCKED_BY_READINESS"),
            "goal_planner_readiness_required": round(sum(p.readiness_required for p in plans) / max(len(plans), 1), 4),
            "goal_directed_improvement_score": score,
        }
