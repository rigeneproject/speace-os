# T29 — Pathway Plasticity Sensitivity Tuning v0.3 — Specification

## Overview

T28 validated that T27 hybrid trigger activates inter-region plasticity (36 events) but with a weak functional outcome:
- Cognitive score regresses slightly (0.4508 → ~0.3932)
- Verdict: `routing_validated_plasticity_weak`

T29 makes plasticity not just active but *useful* by introducing:
1. **Multi-gate guards** — gate updates against causal score, energy, confidence, and uncertainty
2. **Scaled updates** — configurable LTP/LTD scaling per profile
3. **Local rollback** — proxy support for reverting harmful updates
4. **Pathway utility scoring** — track which pathways contribute most
5. **Memory event logging** — accepted, skipped, rolled-back updates recorded

Biologically: real synaptic plasticity is gated by neuromodulators, energy availability, and causal salience. T29 introduces analogous control.

## Architecture

### New module

- `speace_core/cellular_brain/regions/pathway_plasticity_tuner.py`

### Modified modules

- `speace_core/cellular_brain/regions/inter_region_plasticity.py` — `tuner_profile` integration in `update_pathways`
- `speace_core/cellular_brain/calibration/pathway_calibrator.py` — T29 calibration profiles (p8-p10), tuner application
- `speace_core/cellular_brain/benchmark/neurofunctional_benchmark.py` — T29 metrics extraction
- `speace_core/cellular_brain/memory/morphology_events.py` — 5 new event types
- `tests/regions/test_pathway_plasticity_tuner.py` — 14 tests

## Models

### PathwayTuningProfile

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `profile_id` | str | — | Profile identifier |
| `name` | str | — | Human-readable name |
| `min_causal_score` | float | 0.05 | Minimum causal score to proceed |
| `min_routing_strength` | float | 0.01 | Minimum routing signal strength |
| `min_confidence` | float | 0.0 | Minimum confidence score |
| `max_uncertainty` | float | 1.0 | Maximum uncertainty score |
| `ltp_scale` | float | 1.0 | Scale factor for LTP updates |
| `ltd_scale` | float | 1.0 | Scale factor for LTD updates |
| `phi_guard_enabled` | bool | True | Gate on coherence stability |
| `energy_guard_enabled` | bool | True | Gate on energy availability |
| `confidence_guard_enabled` | bool | True | Gate on confidence/uncertainty |
| `rollback_on_phi_drop` | bool | True | Enable rollback proxy |
| `rollback_on_cognitive_drop` | bool | True | Enable rollback proxy |
| `max_pathway_updates_per_tick` | int | 8 | Throttle updates per tick |
| `description` | str | "" | Profile description |

### PathwayTuningResult

| Field | Type | Description |
|-------|------|-------------|
| `profile_id` | str | Profile used |
| `attempted_updates` | int | Triggered pathways evaluated |
| `accepted_updates` | int | Updates applied successfully |
| `skipped_updates` | int | Updates blocked by guards |
| `rolled_back_updates` | int | Updates reverted (MVP proxy) |
| `ltp_updates` | int | Strengthening updates |
| `ltd_updates` | int | Weakening updates |
| `cognitive_score_before/after` | float | Cognitive proxy before/after |
| `phi_before/after` | float | Coherence proxy before/after |
| `energy_before/after` | float | Energy proxy before/after |
| `tuning_gain` | float | Net improvement proxy |
| `pathway_utility_score` | float | Composite utility |
| `verdict` | str | Final assessment |

## PathwayPlasticityTuner

### Default profiles (10)

| ID | Name | Key settings |
|---|---|---|
| t0 | t28_default_hybrid | No guards (baseline) |
| t1 | conservative_phi_guard | phi_guard, 0.5x scale, max 4 updates |
| t2 | energy_guarded_low_rate | energy_guard, 0.3x scale, max 4 updates |
| t3 | confidence_guarded | confidence_guard, min_confidence=0.3 |
| t4 | causal_score_strict | min_causal_score=0.3, phi_guard |
| t5 | ltp_dominant_soft | 1.5x LTP, 0.5x LTD, phi+energy guards |
| t6 | ltd_balanced | 0.8x LTP, 1.2x LTD, phi+energy guards |
| t7 | rollback_enabled | All guards + rollback on drop |
| t8 | minimal_safe_plasticity | 0.2x scale, all guards, max 2 updates |
| t9 | adaptive_best_of_profiles | All guards + rollback, min_causal=0.1 |

### Methods

- `gate_update(trigger_result, profile, metrics, confidence_state) -> (bool, str)`
  - Returns `(should_proceed, reason)`
  - Checks causal_score ≥ min_causal_score
  - If energy_guard_enabled: mean_energy ≥ 0.2
  - If confidence_guard_enabled: confidence ≥ min_confidence AND uncertainty ≤ max_uncertainty

- `apply_scaled_update(pathway, update_type, profile)`
  - LTP: `strength += 0.05 * ltp_scale * plasticity_rate`
  - LTD: `strength -= 0.03 * ltd_scale * plasticity_rate`
  - Clamps to [min_strength, max_strength]

- `rollback_update(pathway, old_strength)`
  - Restores previous strength

- `compute_pathway_utility_score(pathway, trigger_result) -> float`
  - `(strength + causal_score + confidence) / 3.0` clamped to [0, 1]

- `tune_pathway_update(pathway, trigger_result, profile, metrics, confidence_state, memory) -> (bool, bool, str)`
  - Returns `(accepted, rolled_back, reason)`
  - Records memory events for accepted/skipped/rolled-back

- `tune_all_pathways(engine, registry, circuit, profile, metrics, memory, confidence_state, routing_result, tick) -> PathwayTuningResult`
  - Iterates all connections, evaluates triggers, gates, applies scaled updates
  - Respects `max_pathway_updates_per_tick`
  - Records `PATHWAY_TUNING_PROFILE_APPLIED` event

## InterRegionPlasticityEngine integration

- Added `tuner_profile` parameter to `__init__`
- In `update_pathways`, if `tuner_profile is not None`:
  - Lazy-imports `PathwayPlasticityTuner`
  - Delegates to `tune_all_pathways`
  - Converts `PathwayTuningResult` → `InterRegionPlasticityResult`
  - Records `INTER_REGION_PLASTICITY_APPLIED` event with tuning metadata

## Calibration profiles (T29 extensions)

Added to `PathwayCalibrator.default_profiles()`:

| ID | Name | Tuner profile | Description |
|---|---|---|---|
| p8 | routing_plus_tuning_default | t0 | Baseline tuning, no guards |
| p9 | routing_plus_tuning_conservative_phi | t1 | Phi-guarded conservative |
| p10 | routing_plus_tuning_full_guard | t9 | All guards + rollback |

## New MorphologyEventType values

- `REGION_PLASTICITY_UPDATE_ACCEPTED`
- `REGION_PLASTICITY_UPDATE_SKIPPED`
- `REGION_PLASTICITY_UPDATE_ROLLED_BACK`
- `REGION_PATHWAY_UTILITY_UPDATED`
- `PATHWAY_TUNING_PROFILE_APPLIED`

## Benchmark metrics (T29)

Added to `BenchmarkMetrics`:

- `pathway_tuning_accepted_updates`
- `pathway_tuning_skipped_updates`
- `pathway_tuning_rolled_back_updates`
- `pathway_tuning_profile_id`

Extracted from `PATHWAY_TUNING_PROFILE_APPLIED` memory events.

## Acceptance criteria

- [x] `PathwayPlasticityTuner` exists and is importable
- [x] `PathwayTuningProfile` with 10 default profiles
- [x] `gate_update` correctly gates on causal score, energy, confidence
- [x] `apply_scaled_update` respects LTP/LTD scales
- [x] `rollback_update` restores previous strength
- [x] `tune_pathway_update` records accepted/skipped events in memory
- [x] `tune_all_pathways` produces `PathwayTuningResult`
- [x] `InterRegionPlasticityEngine` delegates to tuner when `tuner_profile` set
- [x] `PathwayCalibrator` supports T29 profiles (p8-p10)
- [x] Benchmark extracts T29 metrics from memory events
- [x] Markdown/JSON reports include T29 columns
- [x] 350+ tests pass; coverage stays ≥ 85%
- [x] `docs/PATHWAY_PLASTICITY_SENSITIVITY_TUNING_SPEC.md` created

## Post-T29 next step

- Run full calibration suite to validate that at least one T29 profile produces:
  - `accepted_updates > 0`
  - `skipped_updates > 0` or `rolled_back_updates > 0`
  - Cognitive score and Φ do not collapse
  - `delivered_signals > 0`
  - `inter_region_plasticity_events > 0`
- If functional improvement remains weak, consider T30 — Deep Region Specialization or Homeostatic Stabilization
