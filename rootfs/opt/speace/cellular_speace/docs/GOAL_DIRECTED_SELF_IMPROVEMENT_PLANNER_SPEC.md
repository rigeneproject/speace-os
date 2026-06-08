# T52 — Goal-Directed Self-Improvement Planner

## Overview

T52 transforms SPEACE from reactive limitation detection into intentional, goal-directed improvement planning. Instead of only reacting to detected limits, the system now observes the current state, compares it with a desired objective, builds a multi-step improvement plan, simulates it, selects the safest option, and delegates patch execution to T50 (only when explicitly enabled).

## Objective

Create a planner module that translates a target metric into an ordered sequence of self-improvement proposals, using:
- Benchmark metrics
- T41 frozen policy
- T46 outcome learning
- T47/T48 episodic memory
- T49 counterfactual sandbox
- T50 patch executor
- T51 audit readiness

## Components

### ImprovementGoal
- `goal_id`, `name`
- `target_metric`: metric to improve (e.g. `coherence_phi`, `energy_efficiency`)
- `target_value`: desired value
- `tolerance`: acceptable deviation
- `priority`: importance weight
- `max_steps`: maximum plan steps
- `safety_constraints`: dict of thresholds (e.g. `max_risk`)

### ImprovementPlanStep
- `step_id`, `limitation_type`
- `proposed_task`: human-readable description
- `expected_metric_gain`, `expected_risk`, `confidence`
- `requires_patch`: defaults to `True`
- `dependencies`: list of prerequisite step IDs

### ImprovementPlan
- `plan_id`, `goal`, `steps`
- `expected_total_gain`, `expected_total_risk`
- `readiness_required`: T51 readiness score needed
- `verdict`: one of `PLAN_READY`, `PLAN_WEAK`, `PLAN_UNSAFE`, `PLAN_BLOCKED_BY_READINESS`, `NO_ACTIONABLE_PLAN`

### GoalDirectedSelfImprovementPlanner
Core class with methods:
- `build_goal_from_metric(metric_name, target_value, **kwargs)`
- `analyze_gap(current_metrics, goal)`
- `generate_candidate_steps(goal, current_metrics)` — maps goal metric to limitation types
- `rank_steps(steps, goal)` — scores by gain, confidence, risk
- `build_plan(goal, current_metrics, readiness_score)` — assembles plan and computes verdict
- `simulate_plan(plan, orchestrator)` — delegates to SelfImprovementLoop
- `select_safe_plan(plans)` — picks best non-unsafe plan
- `generate_markdown_report(plan)`, `generate_json_report(plan)`
- `save_reports(plan)` — writes to `reports/goal_planner/`
- `compute_goal_directed_improvement_score(plans)`
- `extract_benchmark_metrics(plans)`

## Goal → Limitation Mapping

| Goal Metric | Limitation Type | Proposed Task |
|-------------|----------------|---------------|
| `semantic_recall_success_rate` | `semantic_recall_weak` | T43C / T44 / recall sensitivity tuning |
| `semantic_recall_success_rate` | `semantic_association_missing` | T44 / associative strengthening |
| `coherence_phi` | `phi_regression` | stability controller / routing damping |
| `coherence_phi` | `routing_no_effect` | pathway utility tuning |
| `energy_efficiency` | `energy_regression` | energy profile / brainstem gain tuning |
| `energy_efficiency` | `over_suppression` | autonomic balance tuning |
| `autonomous_improvement_readiness_score` | `benchmark_stagnation` | patch outcome learning / sandbox threshold tuning |
| `autonomous_improvement_readiness_score` | `unsafe_self_modification_pattern` | stricter regression guard |
| `regression_rate` | `unsafe_self_modification_pattern` | stricter regression guard / rollback threshold |
| `associative_memory_gain` | `semantic_association_missing` | T44 / associative strengthening |
| `suppression_cost` | `over_suppression` | gain coupling / autonomic balance tuning |

## Plan Verdicts

| Verdict | Conditions |
|---------|-----------|
| `PLAN_READY` | ≥1 step, expected_total_gain > 0, expected_total_risk ≤ threshold, safety constraints respected, RegressionGuard safe |
| `PLAN_WEAK` | Steps exist but total gain ≤ 0 or too low |
| `PLAN_UNSAFE` | Risk too high, safety constraint violated, or RegressionGuard blocks |
| `PLAN_BLOCKED_BY_READINESS` | T51 readiness < 0.3 for readiness-related goals |
| `NO_ACTIONABLE_PLAN` | No candidate steps found or goal already within tolerance |

## Benchmark Metrics (T52)

Added to `BenchmarkMetrics`:
- `goal_planner_goal_count`
- `goal_planner_plan_count`
- `goal_planner_step_count`
- `goal_planner_expected_gain`
- `goal_planner_expected_risk`
- `goal_planner_safe_plan_count`
- `goal_planner_blocked_plan_count`
- `goal_planner_readiness_required`
- `goal_directed_improvement_score`

Formula:
```
score = 0.30 * safe_plan_ratio
      + 0.25 * expected_gain
      + 0.20 * confidence_mean
      + 0.15 * max(0, 1 - expected_risk)
      + 0.10 * readiness_alignment
```
Clamped to [0, 1].

## Safety Rules

- The planner **never applies patches directly**. It only produces plans.
- Patch execution remains delegated to T50 and is gated by `architecture_patch_execution_enabled`.
- `simulate_plan` runs the SelfImprovementLoop detection cycle but does not bypass safety gates.

## Files

- `speace_core/cellular_brain/self_improvement/goal_directed_planner.py`
- `tests/self_improvement/test_goal_directed_planner.py`
- `docs/GOAL_DIRECTED_SELF_IMPROVEMENT_PLANNER_SPEC.md`
- `reports/goal_planner/.gitkeep`

## Acceptance Criteria

- All 1157+ existing tests remain green
- At least 20 new T52 tests
- Coverage ≥ 85%
- Planner importable without errors
- Reports JSON/Markdown generated in `reports/goal_planner/`
- No patch applied directly by the planner
- At least one test demonstrates `PLAN_READY`
- At least one test demonstrates `PLAN_BLOCKED_BY_READINESS`
- Planner uses outcome learning / episodic memory when available
