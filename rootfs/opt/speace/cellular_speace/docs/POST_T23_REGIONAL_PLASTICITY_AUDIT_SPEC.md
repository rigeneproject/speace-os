# PostT23RegionalPlasticityAudit v0.3 — Specification

## Overview

T24 validates and calibrates the inter-region plasticity introduced in T23 before SPEACE expands to new brain regions. Rather than adding functional organs, T24 measures whether pathway-specific STDP improves, destabilizes, or leaves unchanged the organism’s cognitive score, coherence Φ, energy efficiency, and regional signal flow.

Biologically: plastic long-range pathways must be validated against behavior. If a pathway strengthens but the brain becomes epileptic, the plasticity is pathological, not functional. T24 finds the sweet spot.

## Architecture

### New module

- `speace_core/cellular_brain/calibration/pathway_calibrator.py`

### Modified modules

- `speace_core/cellular_brain/regions/inter_region_plasticity.py` — `confidence_modulation_strength` and `energy_modulation_strength` added
- `speace_core/cellular_brain/benchmark/neurofunctional_benchmark.py` — `regional_signal_flow_score`

### No behavioral regressions

All existing orchestrator, benchmark, audit, and calibration behavior is preserved. T24 is purely observational and parameter-sweeping.

## Models

### PathwayCalibrationProfile

| Field | Type | Description |
|-------|------|-------------|
| `profile_id` | str | Unique ID |
| `name` | str | Human-readable label |
| `inter_region_plasticity_enabled` | bool | Toggle T23 engine |
| `ltp_rate` | float | LTP increment |
| `ltd_rate` | float | LTD decrement |
| `min_strength` | float | Minimum pathway strength |
| `max_strength` | float | Maximum pathway strength |
| `stdp_window` | int | Tick window for temporal STDP |
| `energy_cost_per_update` | float | Energy cost per pathway update |
| `confidence_modulation_strength` | float | Scaling factor for confidence modulation |
| `energy_modulation_strength` | float | Scaling factor for energy modulation |
| `description` | str | Rationale |

### PathwayCalibrationResult

| Field | Type | Description |
|-------|------|-------------|
| `profile` | PathwayCalibrationProfile | Tested profile |
| `benchmark_metrics` | dict | Raw benchmark dict |
| `speace_cognitive_score` | float | Cognitive score |
| `coherence_phi` | float | Final Φ |
| `energy_efficiency` | float | Final energy efficiency |
| `mean_pathway_strength` | float | Average pathway strength |
| `reinforced_pathways` | int | Count of LTP events |
| `weakened_pathways` | int | Count of LTD events |
| `pathway_energy_cost` | float | Total energy cost |
| `regional_signal_flow_score` | float | Composite flow metric |
| `regression_score` | float | Improvement-over-baseline |
| `distance_from_baseline` | float | Absolute deviation |
| `passed` | bool | Success flag |

### PathwayAuditReport

| Field | Type | Description |
|-------|------|-------------|
| `audit_id` | str | Unique ID |
| `baseline_metrics` | dict | Baseline benchmark dict |
| `profile_results` | list | Results per profile |
| `best_profile` | PathwayCalibrationProfile \| None | Selected best |
| `verdict` | str | Audit verdict |

## PathwayCalibrator

### Constructor

- `genome: dict \| None = None`
- `report_dir: str = "reports/pathway"`
- `seed: int = 42`
- `n_adaptive_cycles: int = 5`
- `benchmark_case: str = "morphological_memory_trace"`

### Methods

- `default_profiles() -> list[PathwayCalibrationProfile]`
  Returns 8 profiles:
  1. `inter_region_off` — disable T23
  2. `current_t23_default` — T23 defaults
  3. `low_plasticity` — reduced LTP/LTD
  4. `medium_plasticity` — moderate rates
  5. `high_plasticity` — aggressive rates
  6. `energy_conservative_pathways` — lower energy cost, stronger energy modulation
  7. `confidence_guided_pathways` — confidence-driven emphasis
  8. `balanced_pathway_profile` — compromise across dimensions

- `build_orchestrator() -> CellularBrainOrchestrator`
  Builds MVP orchestrator.

- `apply_homeostatic_baseline(orch)`
  Applies `energy_medium` (T22 best profile) via `HomeostaticCalibrator.apply_profile_to_orchestrator`.

- `apply_pathway_profile(profile, orch)`
  Sets `inter_region_plasticity_enabled` and all `InterRegionPlasticityEngine` parameters.

- `run_profile(profile) -> PathwayCalibrationResult`
  Builds orchestrator, applies baseline + pathway, runs benchmark, extracts metrics.

- `run_pathway_calibration_suite(profiles=None) -> PathwayAuditReport`
  1. Runs `inter_region_off` baseline.
  2. Runs all requested profiles.
  3. Computes `regression_score` and `distance_from_baseline`.
  4. Selects `best_profile`.
  5. Determines verdict.
  6. Generates JSON + Markdown reports.

- `compute_regression_score(result, baseline_metrics) -> float`
  Weighted deltas across cognitive, phi, energy, flow, functional improvement, meta-cognitive.

- `compute_distance_from_baseline(result, baseline_metrics) -> float`
  L1 distance across the same dimensions.

- `select_best_profile(results, baseline_metrics) -> PathwayCalibrationResult \| None`
  Highest regression_score if improvers exist; otherwise smallest distance.

- `_compute_verdict(results, baseline_metrics) -> str`
  Six possible outcomes (see below).

### Verdict

- `pathway_plasticity_validated` — improver exists, energy stable, events > 0, flow_score > 0
- `pathway_plasticity_partially_validated` — improvement on at least 1 metric without collapse
- `pathway_overplasticity_detected` — high_plasticity profile worsens Φ or causes instability
- `pathway_energy_regression` — pathway_energy_cost high and energy_efficiency drops significantly
- `pathway_no_effect` — events present but no functional delta
- `insufficient_evidence` — no passed results

### Report format

#### JSON
Machine-readable `PathwayAuditReport.model_dump_json()`.

#### Markdown
Sections:
1. Header (audit ID, date, verdict)
2. Baseline Metrics
3. Comparative Results table
4. Best Profile (if any)

## Regional signal flow score

```
regional_signal_flow_score =
  mean_pathway_strength
  * (active_inter_region_connections / total_inter_region_connections)
  * mean_region_phi
```

This measures whether regions not only exist but communicate functionally.

## Energy baseline

T24 uses `energy_medium` (T22 best profile) as the fixed metabolic baseline. This ensures that pathway calibration results are not confounded by metabolic variance.

## Test coverage

1. PathwayCalibrator importable
2. default_profiles contains ≥ 8 profiles
3. inter_region_off disables plasticity
4. current_t23_default enables it
5. low/medium/high modify LTP/LTD
6. energy_conservative_pathways reduces energy cost
7. confidence_guided_pathways uses confidence modulation
8. run_profile produces PathwayCalibrationResult
9. regional_signal_flow_score in [0,1]
10. JSON report generated
11. Markdown report generated
12. verdict produced
13. compute_regression_score positive when metrics improve
14. apply_pathway_profile mutates orchestrator correctly

## Acceptance criteria

- [x] PathwayCalibrator exists and is importable.
- [x] At least 8 pathway profiles defined.
- [x] energy_medium used as fixed homeostatic baseline.
- [x] Report JSON generated.
- [x] Report Markdown generated with comparative table.
- [x] `best_profile` selected by regression score or distance.
- [x] Verdict is non-binary (6 possible outcomes).
- [x] `regional_signal_flow_score` computed and included.
- [x] All tests pass; coverage stays ≥ 85%.
- [x] `docs/POST_T23_REGIONAL_PLASTICITY_AUDIT_SPEC.md` created.

## Post-T24 next step

- `pathway_plasticity_validated` → T25 Deep Region Specialization
- `pathway_overplasticity_detected` → T25 Region-Level Stability Controller
- `pathway_energy_regression` → T25 Energy-Aware Regional Routing
- `pathway_no_effect` → T25 Regional Signal Routing Redesign
