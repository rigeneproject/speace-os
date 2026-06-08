# T49 — Counterfactual Architecture Sandbox

## Overview

The Counterfactual Architecture Sandbox (T49) provides a safe simulation environment for evaluating architecture rewrite proposals without modifying the real SPEACE system. It enables multi-future simulation by cloning orchestrator state, applying proposals counterfactually, and computing verdicts based on expected benefits, risks, and safety constraints.

## Design Goals

- **Safety First**: No real system mutation during evaluation.
- **Conservative Defaults**: Sandbox is disabled by default.
- **Verdict-Driven**: Clear accept/reject/unsafe/needs_more_evidence outcomes.
- **Observability**: Full MorphologicalMemory event logging for auditability.
- **Integration**: Seamlessly plugs into the Self-Improvement Loop after episodic policy ranking.

## Architecture

```
SelfImprovementLoop
  └─ Episodic Policy Ranking
      └─ CounterfactualArchitectureSandbox
          ├─ clone_orchestrator_state()
          ├─ apply_proposal_counterfactually()
          ├─ run_scenario(proposal, limitation_type)
          │   ├─ Capture baseline metrics
          │   ├─ Simulate counterfactual score
          │   ├─ Regression Guard check
          │   ├─ Safety checks (neuron count, energy collapse)
          │   └─ Compute verdict
          └─ run_batch(proposals, limitation_type)
              ├─ Run scenario for each proposal
              ├─ Aggregate counts
              └─ Select best safe result
```

## Models

### CounterfactualScenario

| Field | Type | Description |
|-------|------|-------------|
| scenario_id | str | Unique identifier |
| proposal_id | str | Linked proposal ID |
| limitation_type | str | Category of limitation being addressed |
| sandbox_profile | str | Evaluation profile (default: "default") |
| applied_changes | dict | Simulated changes applied |
| seed | int | Random seed for reproducibility |

### CounterfactualResult

| Field | Type | Description |
|-------|------|-------------|
| scenario_id | str | Unique identifier |
| proposal_id | str | Linked proposal ID |
| baseline_score | float | Pre-proposal cognitive score |
| counterfactual_score | float | Post-proposal simulated score |
| delta_score | float | Score improvement |
| delta_phi | float | Expected phi change |
| delta_energy | float | Expected energy change |
| delta_cognitive | float | Expected cognitive change |
| regression_flags | list[str] | Safety/policy flags |
| verdict | str | accept / reject / unsafe / needs_more_evidence |
| confidence | float | Confidence in the result (0-1) |

### CounterfactualBatchResult

| Field | Type | Description |
|-------|------|-------------|
| limitation_type | str | Category evaluated |
| scenarios_tested | int | Total scenarios run |
| accepted_count | int | Accepted proposals |
| rejected_count | int | Rejected proposals |
| unsafe_count | int | Unsafe proposals |
| best_scenario_id | str | Best safe scenario ID |
| best_proposal_id | str | Best safe proposal ID |
| mean_delta_score | float | Average delta across all scenarios |
| verdict | str | Batch-level aggregate verdict |

## Verdict Rules

| Verdict | Conditions |
|---------|------------|
| **unsafe** | RUNTIME_ERROR, ENERGY_COLLAPSE, NEURON_COUNT_BELOW_THRESHOLD, or POLICY_UNSAFE in regression_flags |
| **reject** | delta_score <= 0 |
| **accept** | delta_score > 0.02 AND delta_phi >= -0.02 AND delta_energy >= -0.05 AND no unsafe flags |
| **needs_more_evidence** | 0.0 < delta_score <= 0.02 AND no unsafe flags |

## Proposal Type Modifiers

| Proposal Type | Modifier | Rationale |
|---------------|----------|-----------|
| module_addition | x0.95 | Slightly penalize complexity |
| genome_mutation | x0.85 | Heavily penalize high-risk mutations |
| parameter_tuning | x1.05 | Slightly favor low-risk tuning |

## Safety Constraints

1. **Neuron Count**: Circuit must have >= 5 neurons after simulated changes.
2. **Energy Collapse**: Reject if delta_energy < -0.5.
3. **Policy Guard**: Integration with RegressionGuard; POLICY_UNSAFE verdicts propagate.
4. **No Core Mutation**: Safety constraints must reference "core" or "test".
5. **Rollback Required**: Every proposal must have a rollback plan.

## Integration Points

### SelfImprovementLoop

After episodic policy ranking, the loop calls:

```python
if self.counterfactual_sandbox_enabled and self.counterfactual_sandbox:
    batch = self.counterfactual_sandbox.run_batch(ranked_proposals, limitation_type)
    best = self.counterfactual_sandbox.select_best_safe_result(batch)
```

Results are stored in `SelfImprovementCycleResult`:
- `counterfactual_results`
- `counterfactual_best_result`
- `counterfactual_verdict`

### Orchestrator

Flag added to `CellularBrainOrchestrator`:
- `counterfactual_sandbox_enabled: bool = False`

### Benchmark Metrics

T49 metrics added to `BenchmarkMetrics`:
- `counterfactual_scenarios_tested`
- `counterfactual_accepted_count`
- `counterfactual_rejected_count`
- `counterfactual_unsafe_count`
- `counterfactual_best_delta_score`
- `counterfactual_mean_delta_score`
- `counterfactual_best_confidence`
- `counterfactual_policy_safe`

## Morphology Events

| Event | Description |
|-------|-------------|
| COUNTERFACTUAL_SCENARIO_STARTED | Sandbox scenario initiated |
| COUNTERFACTUAL_SCENARIO_COMPLETED | Scenario finished with verdict |
| COUNTERFACTUAL_BATCH_COMPLETED | Batch evaluation finished |
| COUNTERFACTUAL_PROPOSAL_ACCEPTED | Proposal passed sandbox |
| COUNTERFACTUAL_PROPOSAL_REJECTED | Proposal failed sandbox |
| COUNTERFACTUAL_PROPOSAL_UNSAFE | Proposal deemed unsafe |

## Test Coverage

Test suite: `tests/self_improvement/test_counterfactual_sandbox.py`
- 36+ tests covering models, state cloning, proposal application, verdict computation, batch execution, event logging, score bounds, and error handling.

## Version

- **Tag**: `v0.3.38-t49-counterfactual-architecture-sandbox`
- **Commit**: `T49 — Counterfactual Architecture Sandbox`
