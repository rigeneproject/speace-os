# IntegratedNeurocellularEvolutionAudit v0.3 — Specification

## Overview

T20 introduces an integrated audit layer that validates SPEACE Digital Cellular Brain as a unified organism. Rather than adding a new functional organ, T20 measures whether the progressive assembly of T7–T19 modules produces measurable functional improvement, stability, efficiency, coherence, modularity, metacognition, and evolutionary fitness.

Biologically: an organism is not the sum of its organs, but an integrated system. T20 is the electroencephalogram + metabolic panel + evolutionary fitness test of SPEACE.

## Architecture

### New module

- `speace_core/cellular_brain/audit/__init__.py`
- `speace_core/cellular_brain/audit/integrated_neurocellular_audit.py`

### New reports

- `reports/audit/integrated_audit_<timestamp>.json`
- `reports/audit/integrated_audit_<timestamp>.md`

### No existing modules modified

T20 is observational — it reads orchestrator state and benchmark results without altering engine behavior.

## Models

### AuditConfiguration

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Configuration label |
| `execution_mode` | str | `global_tick` or `event_driven_burst` |
| `stdp_enabled` | bool | T13 STDP |
| `inhibition_enabled` | bool | T14 inhibition |
| `energy_control_enabled` | bool | T18 energy control |
| `community_detection_enabled` | bool | T17 community detection |
| `confidence_enabled` | bool | T19 metacognition |
| `evolution_enabled` | bool | T15 evolution micro-run |
| `n_adaptive_cycles` | int | Benchmark ticks per config |
| `benchmark_case` | str | Benchmark scenario name |

### AuditCaseResult

| Field | Type | Description |
|-------|------|-------------|
| `configuration` | AuditConfiguration | Tested config |
| `benchmark_metrics` | dict[str, Any] | Collected metrics dict |
| `fitness_score` | float \| None | Best fitness if evolution ran |
| `best_genome_id` | str \| None | Best genome if evolution ran |
| `test_passed` | bool | Success flag |
| `failure_reason` | str \| None | Exception message if failed |

### IntegratedAuditSummary

| Field | Type | Description |
|-------|------|-------------|
| `baseline_name` | str | Baseline configuration name |
| `best_configuration` | str \| None | Highest cognitive score config |
| `best_cognitive_score` | float \| None | Best cognitive score |
| `best_fitness_score` | float \| None | Best fitness score |
| `cognitive_score_delta` | float | Full vs baseline cognitive |
| `phi_delta` | float | Full vs baseline Φ |
| `energy_efficiency_delta` | float | Full vs baseline energy |
| `modularity_delta` | float | Full vs baseline modularity |
| `confidence_delta` | float | Full vs baseline confidence |
| `stability_delta` | float | Full vs baseline stability |
| `verdict` | str | Audit verdict |

### IntegratedAuditReport

| Field | Type | Description |
|-------|------|-------------|
| `audit_id` | str | Unique audit ID |
| `created_at` | str | ISO timestamp |
| `configurations` | list[AuditConfiguration] | All tested configs |
| `results` | list[AuditCaseResult] | Results per config |
| `summary` | IntegratedAuditSummary | Computed summary |
| `json_report_path` | str \| None | Path to JSON report |
| `markdown_report_path` | str \| None | Path to Markdown report |

## IntegratedNeurocellularAudit

### Constructor

- `genome: dict \| None = None` — initial genome dict; loads default if None
- `report_dir: str = "reports/audit"` — output directory
- `seed: int = 42` — random seed for reproducibility
- `evolution_db_path: str = "data/evolution"` — GenomeDatabase path

### Methods

- `default_configurations() -> list[AuditConfiguration]`
  Returns 7 progressive configurations:
  1. `baseline_global_tick`
  2. `burst_only`
  3. `burst_stdp`
  4. `burst_stdp_inhibition`
  5. `burst_stdp_inhibition_energy`
  6. `burst_stdp_inhibition_energy_community`
  7. `full_organism_with_confidence_and_evolution`

- `build_orchestrator_for_config(config) -> CellularBrainOrchestrator`
  Loads default genome, calls `build_mvp`, applies config flags.

- `run_configuration(config) -> AuditCaseResult`
  1. Build orchestrator
  2. Run `NeuroFunctionalBenchmark.run_case()`
  3. Supplement metrics with event counts (STDP, energy, confidence)
  4. If `evolution_enabled`, run micro-evolution:
     - Save initial genome
     - Compute baseline fitness
     - Create 3 mutated candidates
     - Evaluate candidates
     - Select best via `run_evolution_step`
     - Record `fitness_score` and `best_genome_id`

- `run_all(configurations=None) -> IntegratedAuditReport`
  Runs all configs sequentially, computes summary, generates JSON + Markdown reports.

- `compute_summary(results) -> IntegratedAuditSummary`
  Identifies baseline and full organism results, computes deltas, applies verdict rules.

- `generate_json_report(report) -> Path`
  Writes `IntegratedAuditReport.model_dump_json()` to `reports/audit/`.

- `generate_markdown_report(report) -> Path`
  Writes human-readable Markdown with:
  - Comparative results table
  - Incremental effects section (deltas between consecutive configs)
  - Summary deltas
  - Verdict

### Verdict rules

| Verdict | Condition |
|---------|-----------|
| `validated` | full >= baseline cognitive, Φ >= 0.1, confidence > 0, modularity > 0, fitness available |
| `partially_validated` | no collapse, at least 2 metrics improve |
| `unstable` | Φ < 0.05 or energy < 0.05 or cognitive drops > 50% |
| `regression_detected` | full worse than baseline on both cognitive and Φ |
| `insufficient_evidence` | metrics missing or not comparable |

### Metrics collected

From `BenchmarkMetrics`:
- `speace_cognitive_score`
- `meta_cognitive_score`
- `accuracy_score`
- `coherence_phi`
- `phi_trend`
- `mean_energy`
- `energy_efficiency`
- `functional_improvement`
- `morphological_stability`
- `structural_complexity`
- `community_count`
- `modularity_proxy`
- `isolated_neuron_count`
- `confidence_score`
- `uncertainty_score`
- `error_risk`
- `neurogenesis_events`
- `apoptosis_events`
- `cell_differentiation_events`

From memory event counts:
- `stdp_events` — SYNAPSE_REINFORCED + SYNAPSE_WEAKENED
- `energy_events` — ENERGY_CHANGED
- `confidence_events` — CONFIDENCE_EVALUATED

From evolution micro-run:
- `fitness_score` — best candidate fitness

## Evolution micro-run integration

For `evolution_enabled=True` configs:
1. Create `GenomeDatabase` at `evolution_db_path`
2. Save initial genome as `GenomeRecord` (generation 0)
3. Compute baseline `FitnessResult` from benchmark result
4. Call `EvolutionEngine.create_candidate_generation(parents, n_candidates=3)`
5. Evaluate each candidate via `evaluate_genome()`
6. Call `run_evolution_step(benchmark_results=...)` to select best
7. Return `best_fitness` and `best_genome_id`

This validates the closed loop: genome → benchmark → fitness → mutation → selection.

## Report format

### JSON report

Machine-readable `IntegratedAuditReport.model_dump_json()`.

### Markdown report

Sections:
1. Header (audit ID, date, config count)
2. Comparative Results table
3. Incremental Effects (deltas between consecutive configurations)
4. Summary (baseline, best config, deltas)
5. Verdict

Example table row:

```
| full_organism_with_confidence_and_evolution | 0.4521 | 0.3102 | 0.7800 | 0.1200 | 0.3500 | 0.4100 | ✅ |
```

## Test coverage

1. Audit module is importable
2. `default_configurations` contains ≥ 6 configs
3. `build_orchestrator_for_config` applies flags correctly
4. `run_configuration` produces `AuditCaseResult`
5. `run_all` produces `IntegratedAuditReport`
6. Summary contains `best_configuration`
7. Verdict is one of allowed values
8. JSON report is generated on disk
9. Markdown report contains comparative table and incremental effects
10. Full organism config includes confidence metrics
11. Full organism config includes community metrics
12. Evolution-enabled config produces `fitness_score` and `best_genome_id`
13. Verdict unit tests for all 5 outcomes
14. No regression on 227 existing tests

## Acceptance criteria

- [x] `IntegratedNeurocellularAudit` exists and is importable.
- [x] At least 7 progressive configurations defined.
- [x] Benchmark executed for each configuration.
- [x] Report JSON generated.
- [x] Report Markdown generated with table and incremental effects.
- [x] Summary comparativo generated.
- [x] Verdict is non-binary (5 possible outcomes).
- [x] Full organism configuration includes T7–T19 modules.
- [x] `EvolutionEngine` validated end-to-end in micro-run.
- [x] All tests pass; coverage stays ≥ 85%.
- [x] `docs/INTEGRATED_NEUROCELLULAR_EVOLUTION_AUDIT_SPEC.md` created.

## Post-T20 next step

T21 — Region-Based Brain Architecture (hippocampus, prefrontal cortex, sensory cortex, limbic system, cerebellum, basal ganglia).
