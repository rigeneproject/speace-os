# T45 Autonomous Limitation Detection & Architecture Rewriting Loop

## Overview

T45 introduces a controlled self-improvement meta-layer for SPEACE. It analyzes benchmarks, audits, morphological memory, regression guards, and current metrics to detect recurring limitations and generate safe architectural rewrite proposals.

## Design Principles

- **Conservative**: No direct source-code mutation without validation.
- **Proposal-driven**: Generates structured `ArchitectureRewriteProposal` objects with risk/benefit estimates, rollback plans, and safety constraints.
- **Manual activation**: The self-improvement cycle is never triggered automatically inside the tick loop. It must be invoked manually or via audit-driven workflows.
- **Observable**: All lifecycle events are logged to `MorphologicalMemory`.

## Architecture

### Models

- `LimitationSignal` — A single detected limitation with category, severity, confidence, and evidence.
- `LimitationDiagnosis` — Aggregated signals grouped by category, with urgency/recurrence scores and recommended action types.
- `ArchitectureRewriteProposal` — Structured proposal including title, target modules, rationale, implementation plan, rollback plan, safety constraints, and status.
- `RewriteSimulationResult` — Conservative simulation result with acceptance score, safety verdict, and recommendation.
- `SelfImprovementCycleResult` — Complete result of one detection cycle, including limitations, diagnoses, proposals, simulations, and final verdict.

### Classes

- `LimitationDetector` — Detects limitations from metrics, audit reports, morphological memory, and regression guard verdicts.
- `ArchitectureRewriter` — Maps diagnoses to structured proposals; estimates risk/benefit; validates safety constraints.
- `ProposalStore` — JSONL persistence for proposals and cycle results.
- `SelfImprovementLoop` — Orchestrates the full cycle: detect → diagnose → propose → simulate → accept/reject → report.

### Integration Points

- `CellularBrainOrchestrator` — Lazy-initialized `SelfImprovementLoop` via `get_self_improvement_loop()`; `run_self_improvement_cycle(metrics)` for manual invocation.
- `NeuroFunctionalBenchmark` — Optional self-improvement metrics added to `BenchmarkMetrics` (e.g., `limitations_detected`, `architecture_proposals_created`).
- `MorphologicalMemory` — 7 new event types log the T45 lifecycle.

## Diagnosis → Proposal Mapping

| Diagnosis | Proposal |
|---|---|
| `semantic_association_missing` | T44 — Associative Learning Between Assemblies |
| `semantic_recall_weak` | Semantic Recall Sensitivity Tuning |
| `phi_regression` | Region-Level Stability Controller / Routing Damping |
| `energy_regression` | Energy Control Agent Calibration |
| `routing_no_effect` | Regional Signal Routing Redesign |
| `plasticity_no_effect` | STDP Trigger Redesign |
| `over_suppression` | Cognitive/Autonomic Balance Tuning |
| `cellular_damage` | Cellular Repair/Defense Escalation |
| `genome_fitness_low` | Genome Database Evolution Step |
| `benchmark_stagnation` | Benchmark Stimulation Redesign |

## Acceptance Rules

- **Accept** if `safety_passed == True`, `acceptance_score >= 0.55`, and risk thresholds are not exceeded.
- **Reject** if `safety_passed == False`, `regression_guard_verdict == POLICY_UNSAFE`, or `acceptance_score < 0.35`.
- **Needs more evidence** otherwise.

## Reports

- Markdown report includes sections: Detected Limitations, Diagnoses, Proposals, Simulation Results, Accepted/Rejected, Final Verdict, Recommended Next Task.
- JSON report is a serialized `SelfImprovementCycleResult`.

## File Structure

```
speace_core/cellular_brain/self_improvement/
  __init__.py
  limitation_detector.py
  architecture_rewriter.py
  proposal_store.py
  self_improvement_loop.py
tests/self_improvement/
  __init__.py
  test_limitation_detector.py
  test_architecture_rewriter.py
  test_proposal_store.py
  test_self_improvement_loop.py
data/self_improvement/
  proposals.jsonl
  cycles.jsonl
reports/self_improvement/
  self_improvement_cycle_<timestamp>.json
  self_improvement_cycle_<timestamp>.md
```

## Post-T43C Expected Behavior

When run against T43C-validated metrics (assemblies present, recall high, but no associative links), T45 should:

1. Detect `semantic_association_missing`.
2. Generate a T44 proposal.
3. Simulate it with low risk and high benefit.
4. Accept the proposal.
5. Output verdict `SAFE_PROPOSAL_GENERATED` or `PROPOSAL_ACCEPTED_FOR_NEXT_TASK`.
6. Recommend: **T44 — Associative Learning Between Assemblies**.

## Safety Constraints

- No automatic source-code mutation.
- No tick-loop automatic activation.
- All proposals require rollback plans and safety constraints.
- Genome mutations require sandbox evaluation.

## Version

v0.3.33-t45-autonomous-limitation-architecture-loop
