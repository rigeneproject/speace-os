# HomeostaticStabilizationEnergyCalibration v0.3 — Specification

## Overview

T22 introduces a systematic calibration layer to diagnose and reduce the regression detected by T20. Rather than adding a new functional organ, T22 measures how different homeostatic parameter profiles affect the integrated organism’s cognitive score, coherence Φ, energy efficiency, and functional improvement — then selects the least regressive (or most improving) profile.

Biologically: a brain whose metabolism is too conservative becomes torpid. A brain whose metabolism is too permissive becomes epileptic. T22 finds the metabolic sweet spot for SPEACE.

## Architecture

### New module

- `speace_core/cellular_brain/calibration/__init__.py`
- `speace_core/cellular_brain/calibration/homeostatic_calibrator.py`

### Modified modules

- `speace_core/cellular_brain/regulation/energy_control_agent.py` — `state_profiles` made configurable per metabolic state

### No behavioral regressions

All existing orchestrator, benchmark, and audit behavior is preserved. Calibration is purely observational and parameter-sweeping.

## Models

### CalibrationProfile

| Field | Type | Description |
|-------|------|-------------|
| `profile_id` | str | Unique profile ID |
| `name` | str | Human-readable label |
| `energy_control_enabled` | bool | Toggle energy control |
| `stdp_enabled` | bool | Toggle STDP |
| `inhibition_enabled` | bool | Toggle inhibition |
| `community_detection_enabled` | bool | Toggle community detection |
| `confidence_enabled` | bool | Toggle confidence |
| `region_architecture_enabled` | bool | Toggle regional architecture |
| `state_profiles` | dict[str, dict[str, float]] | Override multipliers per metabolic state |
| `description` | str | Rationale |

### CalibrationResult

| Field | Type | Description |
|-------|------|-------------|
| `profile` | CalibrationProfile | Tested profile |
| `benchmark_metrics` | dict[str, Any] | Raw benchmark dict |
| `cognitive_score` | float | SPEACE cognitive score |
| `coherence_phi` | float | Final Φ |
| `energy_efficiency` | float | Final energy efficiency |
| `functional_improvement` | float | Functional improvement |
| `meta_cognitive_score` | float \| None | Meta-cognitive score |
| `regression_score` | float | Improvement-over-baseline metric |
| `distance_from_baseline` | float | Absolute deviation from baseline |
| `passed` | bool | Success flag |
| `failure_reason` | str \| None | Exception if failed |

### CalibrationAuditReport

| Field | Type | Description |
|-------|------|-------------|
| `audit_id` | str | Unique audit ID |
| `created_at` | str | ISO timestamp |
| `baseline_metrics` | dict[str, Any] | Baseline benchmark dict |
| `profile_results` | list[CalibrationResult] | Results per profile |
| `best_profile` | CalibrationProfile \| None | Selected best profile |
| `best_regression_score` | float \| None | Best regression score |
| `verdict` | str | Calibration verdict |
| `json_report_path` | str \| None | Path to JSON report |
| `markdown_report_path` | str \| None | Path to Markdown report |

## HomeostaticCalibrator

### Constructor

- `genome: dict \| None = None` — initial genome dict
- `report_dir: str = "reports/calibration"` — output directory
- `seed: int = 42` — reproducibility seed
- `n_adaptive_cycles: int = 5` — benchmark ticks per profile
- `benchmark_case: str = "morphological_memory_trace"` — benchmark scenario

### Methods

- `default_profiles() -> list[CalibrationProfile]`
  Returns 8 calibration profiles:
  1. `current_full_organism` — default energy control
  2. `energy_control_off` — disable energy control
  3. `energy_soft` — reduce aggressive conservation by 50%
  4. `energy_medium` — reduce aggressive conservation by 25%
  5. `energy_strict` — increase aggressive conservation
  6. `stdp_preserved_energy_soft` — preserve STDP even in soft energy
  7. `inhibition_soft_decay_soft` — softer inhibition decay
  8. `neurogenesis_preserved_energy_soft` — preserve neurogenesis in low energy

- `build_orchestrator() -> CellularBrainOrchestrator`
  Builds MVP orchestrator from genome.

- `apply_profile_to_orchestrator(profile, orchestrator)`
  Applies all profile flags and `state_profiles` overrides to the orchestrator's `EnergyControlAgent`.

- `run_profile(profile) -> CalibrationResult`
  Builds orchestrator, applies profile, runs benchmark, extracts metrics.

- `run_calibration_suite(profiles=None) -> CalibrationAuditReport`
  1. Runs baseline (`current_full_organism`) first to capture baseline metrics.
  2. Runs all requested profiles.
  3. Computes `regression_score` and `distance_from_baseline` for each.
  4. Selects `best_profile`.
  5. Determines verdict.
  6. Generates JSON + Markdown reports.

- `compute_regression_score(result, baseline_metrics) -> float`
  ```
  score =
    0.30 * max(0, cognitive - baseline_cognitive)
    + 0.25 * max(0, phi - baseline_phi)
    + 0.20 * max(0, energy_efficiency - baseline_energy)
    + 0.15 * max(0, functional_improvement)
    + 0.10 * max(0, meta_cognitive_score)
  ```
  Clamped to [0, 1].

- `compute_distance_from_baseline(result, baseline_metrics) -> float`
  Sum of absolute deviations for cognitive, phi, and energy efficiency.

- `select_best_profile(results, baseline_metrics) -> CalibrationResult \| None`
  - If any profile improves over baseline (regression_score > 0): pick highest regression_score.
  - Otherwise: pick smallest distance_from_baseline (least regressive).

- `_compute_verdict(results, baseline_metrics) -> str`
  - `regression_reduced` — at least one profile improves over baseline.
  - `partially_stabilized` — no improvement, but at least one profile is less regressive than `current_full_organism`.
  - `regression_persists` — all profiles are as regressive or worse.
  - `insufficient_evidence` — no passed results.

### Report format

#### JSON report
Machine-readable `CalibrationAuditReport.model_dump_json()`.

#### Markdown report
Sections:
1. Header (audit ID, date, verdict)
2. Baseline Metrics
3. Comparative Results table
4. Best Profile (if any)

## EnergyControlAgent changes

`_build_decision` now reads multipliers from `self.state_profiles` instead of hardcoded values. `state_profiles` defaults to `DEFAULT_STATE_PROFILES`, preserving backward compatibility.

This allows `HomeostaticCalibrator.apply_profile_to_orchestrator()` to inject custom multipliers without modifying source code.

## Test coverage

1. Calibrator module is importable
2. `default_profiles` contains ≥ 8 profiles
3. `apply_profile_to_orchestrator` correctly toggles flags
4. `apply_profile_to_orchestrator` correctly injects `state_profiles`
5. `run_profile` produces `CalibrationResult`
6. `run_profile` with `energy_control_enabled=False` runs successfully
7. `compute_regression_score` is positive when metrics improve
8. `compute_regression_score` is zero when metrics worsen
9. `compute_distance_from_baseline` computes absolute deviation
10. `select_best_profile` selects highest regression_score when improvers exist
11. `select_best_profile` selects smallest distance when no improvers exist
12. `verdict` returns `regression_reduced` for improvers
13. `verdict` returns `partially_stabilized` for less-regressive profiles
14. `verdict` returns `regression_persists` when all are equally bad
15. `run_calibration_suite` produces `CalibrationAuditReport`
16. JSON and Markdown reports are generated on disk
17. Markdown contains baseline and comparative table
18. Calibration works with `region_architecture_enabled=True`
19. No regression on 267 existing tests

## Acceptance criteria

- [x] `HomeostaticCalibrator` exists and is importable.
- [x] At least 8 calibration profiles defined.
- [x] Each profile runs a comparable benchmark.
- [x] Report JSON generated.
- [x] Report Markdown generated with comparative table.
- [x] `best_profile` selected by regression score or distance.
- [x] Verdict is non-binary (4 possible outcomes).
- [x] `EnergyControlAgent` accepts configurable `state_profiles`.
- [x] All tests pass; coverage stays ≥ 85%.
- [x] `docs/HOMEOSTATIC_STABILIZATION_ENERGY_CALIBRATION_SPEC.md` created.

## Post-T22 next step

Depending on T22 verdict:
- `regression_reduced` → T23 Inter-Region Plasticity
- `partially_stabilized` → T23 Energy-Aware Regional Routing
- `regression_persists` → T23 Region-Level Homeostasis or deeper EnergyControlAgent redesign
