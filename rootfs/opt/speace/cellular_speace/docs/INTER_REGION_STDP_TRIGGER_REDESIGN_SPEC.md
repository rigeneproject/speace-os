# T27 — Inter-Region STDP Trigger Redesign v0.3 — Specification

## Overview

T26 verified that T25 routing works but T23 plasticity remains dormant:
- `verdict: routing_active_but_no_plasticity`
- `delivered_signals = 3`
- `regional_signal_flow_score = 1.0`
- `inter_region_plasticity_events = 0`

Root cause: `InterRegionPlasticityEngine.compute_region_activation` requires `activation > 0.5`, but `RegionSignalRouter` distributes `signal_strength / n_target_neurons ≈ 0.02` per neuron. The STDP engine never "sees" the weak but causally significant signals.

T27 does **not** patch the threshold to 0.02. It introduces a multi-modal trigger system that detects:
1. **Soft activation** — weak but persistent regional activity
2. **Routing awareness** — signals delivered by T25 router
3. **Temporal correlation** — source activation followed by target activation within a window
4. **Hybrid** — any of the above (default for T27)

Biologically: long-range plasticity does not require all-or-nothing spikes; it responds to graded potentials, temporal pairing, and axonal signal delivery.

## Architecture

### New module

- `speace_core/cellular_brain/regions/region_plasticity_trigger.py`

### Modified modules

- `speace_core/cellular_brain/regions/inter_region_plasticity.py` — `trigger_mode`, `_trigger`, `update_pathways` integration
- `speace_core/cellular_brain/memory/morphology_events.py` — 4 new event types
- `speace_core/orchestrator.py` — pass `last_routing_result` to `update_pathways`
- `speace_core/cellular_brain/calibration/pathway_calibrator.py` — `trigger_mode` in profile, T28 verdict logic

### No behavioral regressions

`hard_spike` mode preserves original T23 behavior exactly.

## Models

### RegionActivationTrace

| Field | Type | Description |
|-------|------|-------------|
| `region_id` | str | Region identifier |
| `tick_id` | int | Tick when captured |
| `soft_activation` | float | Composite soft score |
| `mean_activation` | float | Mean |activation| |
| `max_activation` | float | Max |activation| |
| `active_fraction` | float | Fraction with |a| > 0.05 |
| `routed_input_strength` | float | Sum of routed signals |
| `delta_activation` | float | Change from previous tick |

### RegionPlasticityTriggerResult

| Field | Type | Description |
|-------|------|-------------|
| `source_region_id` | str | Source |
| `target_region_id` | str | Target |
| `triggered` | bool | Whether any trigger fired |
| `trigger_type` | str | Which mode(s) fired |
| `delta_tick` | int \| None | Temporal offset |
| `source_trace` | RegionActivationTrace \| None | Source snapshot |
| `target_trace` | RegionActivationTrace \| None | Target snapshot |
| `causal_score` | float | Confidence in causality |
| `recommended_update` | str \| None | "ltp", "ltd", or "none" |
| `confidence` | float | Trigger confidence |

## RegionPlasticityTrigger

### Constructor

- `trigger_mode: str = "hybrid"`
- `min_soft_activation: float = 0.03`
- `min_routed_signal: float = 0.001`
- `temporal_window: int = 2`
- `history_depth: int = 5`

### Methods

- `compute_soft_region_activation(region_id, circuit) -> float`

  ```
  soft = mean(|a|) + 0.5 * max(|a|) + 0.25 * active_fraction
  ```

- `capture_region_trace(region_id, circuit, tick_id, routed_input_strength) -> RegionActivationTrace`

  Captures activation and computes delta from previous tick. Maintains rolling history per region.

- `detect_temporal_correlation(source, target) -> (bool, delta_tick)`

  Scans history for source delta > 0 followed by target delta > 0 within `temporal_window`.
  Returns negative delta for reverse causality (LTD candidate).

- `detect_routing_causality(source, target, routing_result) -> bool`

  True if `routing_result.signals` contains a delivered signal between source and target with strength > `min_routed_signal`.

- `evaluate_pathway_trigger(source, target, connection, circuit, routing_result, tick, memory) -> RegionPlasticityTriggerResult`

  Evaluates all trigger modes according to `trigger_mode`:
  - `hard_spike`: requires `max_activation > 0.5` (T23 original)
  - `soft_activation`: requires `soft_activation >= min_soft_activation`
  - `routing_aware`: requires delivered routed signal
  - `temporal_correlation`: requires temporal pairing in history
  - `hybrid`: any of the above

  When triggered, recommends LTP/LTD based on causal direction and records events.

## Tick integration

In `CellularBrainOrchestrator._tick`:

1. global/burst execution
2. local STDP
3. inhibition
4. energy control
5. region signal routing (T25)
6. **inter-region plasticity with hybrid trigger (T27)**
   - `update_pathways` now receives `routing_result=self.last_routing_result`
7. memory snapshot

## New MorphologyEventType values

- `REGION_PLASTICITY_TRIGGERED`
- `REGION_PLASTICITY_TRIGGER_SKIPPED`
- `REGION_CAUSAL_CORRELATION_DETECTED`
- `REGION_SOFT_ACTIVATION_TRACE`

## InterRegionPlasticityEngine changes

- Added `trigger_mode: str = "hard_spike"` to `__init__`
- Added `_trigger: RegionPlasticityTrigger` instance
- `update_pathways` accepts `routing_result: Any = None`
- When `trigger_mode != "hard_spike"`, replaces rigid `compute_region_activation > 0.5` with `evaluate_pathway_trigger`
- Legacy mode fully preserved for backward compatibility

## T28 — Re-run Audit Results

T28 re-executed the audit with `trigger_mode="hybrid"`:

| Profile | Cog | Phi | Energy | Flow | Routed | Delivered | Plasticity Events |
|---|---|---|---|---|---|---|---|
| inter_region_off | 0.4508 | 0.2482 | 0.2155 | 0.0000 | 0 | 0 | 0 |
| routing_only | 0.4261 | 0.2018 | 0.1942 | 1.0000 | 3 | 3 | 0 |
| plasticity_without_routing | 0.4508 | 0.2482 | 0.2155 | 0.0000 | 0 | 0 | 0 |
| routing_plus_plasticity | 0.3932 | 0.2060 | 0.2027 | 1.0000 | 3 | 3 | **36** |
| routing_plus_low_plasticity | 0.4289 | 0.2154 | 0.1948 | 1.0000 | 3 | 3 | **36** |
| routing_plus_medium_plasticity | 0.4298 | 0.2132 | 0.2040 | 1.0000 | 3 | 3 | **36** |
| routing_plus_high_plasticity | 0.3952 | 0.2072 | 0.2144 | 1.0000 | 3 | 3 | **36** |
| routing_plus_energy_conservative | 0.4288 | 0.2147 | 0.1948 | 1.0000 | 3 | 3 | **36** |

**Verdict: `routing_validated_plasticity_weak`**

- `regional_signal_flow_score > 0` ✓
- `delivered_signals > 0` ✓
- `inter_region_plasticity_events > 0` ✓ (36 events)
- Cognitive score and energy efficiency did not collapse
- Functional improvement remains weak (regression_score = 0.2) because routing slightly shifts baseline metrics

## Acceptance criteria

- [x] `RegionPlasticityTrigger` exists and is importable.
- [x] `compute_soft_region_activation` detects weak activations.
- [x] `routing_aware_trigger` fires with delivered signals.
- [x] `temporal_correlation_trigger` detects source(t) → target(t+1).
- [x] `hybrid_trigger` fires when any criterion is met.
- [x] `hard_spike_original` preserves T23 behavior.
- [x] Trigger produces LTP on source→target and LTD when target precedes source.
- [x] `REGION_PLASTICITY_TRIGGERED` and `REGION_PLASTICITY_TRIGGER_SKIPPED` events recorded.
- [x] Orchestrator passes `routing_result` to `update_pathways`.
- [x] T28 audit shows `inter_region_plasticity_events > 0`.
- [x] `regional_signal_flow_score` remains > 0.
- [x] 350/350 tests pass; coverage stays ≥ 85% (91.07%).
- [x] `docs/INTER_REGION_STDP_TRIGGER_REDESIGN_SPEC.md` created.

## Post-T28 next step

- `routing_validated_plasticity_weak` → T29 Pathway Plasticity Sensitivity Tuning or T29 Deep Region Specialization

The causal chain is now closed: T23 plasticity exists → T25 routing delivers signal → T27 trigger detects signal → T28 validates plasticity activation.
