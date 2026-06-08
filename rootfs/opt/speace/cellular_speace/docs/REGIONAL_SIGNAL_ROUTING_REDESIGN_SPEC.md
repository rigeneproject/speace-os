# T25 — Regional Signal Routing Redesign v0.3 — Specification

## Overview

T24 validated that T23 Inter-Region Plasticity exists but remains functionally dormant:
- `verdict: insufficient_evidence`
- `regional_signal_flow_score = 0.0000`
- `reinforced_pathways = 0`, `weakened_pathways = 0`
- All 8 T24 profiles produce identical metrics
- Root cause: `compute_region_activation` requires `activation > 0.5`, but no neuron in the `morphological_memory_trace` benchmark reaches that threshold. Thus `update_pathways` never applies LTP/LTD, and `inter_region_plasticity_enabled=True/False` is indistinguishable.

T25 does **not** patch the threshold to "make tests pass". It introduces a real inter-region signal routing mechanism that:
1. Detects weak but non-zero regional activations (soft activation)
2. Propagates signals across region boundaries via existing pathways
3. Energetically gates routing to avoid runaway
4. Feeds activation into target regions so that T23 plasticity has causal pairs to observe

Biologically: long-range axonal projections are not just structural labels; they must carry graded potentials. T25 makes them carry signal.

## Architecture

### New module

- `speace_core/cellular_brain/regions/region_signal_router.py`

### Modified modules

- `speace_core/cellular_brain/memory/morphology_events.py` — 4 new event types
- `speace_core/orchestrator.py` — `region_signal_routing_enabled` flag, `_region_signal_router`, tick integration
- `speace_core/cellular_brain/benchmark/neurofunctional_benchmark.py` — T25 routing metrics

### No behavioral regressions

All existing orchestrator, benchmark, audit, and calibration behavior is preserved. T25 is gated by `region_signal_routing_enabled`.

## Models

### RegionSignal

| Field | Type | Description |
|-------|------|-------------|
| `source_region_id` | str | Source region |
| `target_region_id` | str | Target region |
| `signal_strength` | float | Computed signal intensity |
| `pathway_strength` | float | Connection strength at routing time |
| `energy_cost` | float | Energy deducted for this signal |
| `confidence_weight` | float | Confidence modulation multiplier |
| `delivered` | bool | Whether signal reached target neurons |
| `reason` | str \| None | Delivery or block reason |

### RegionRoutingResult

| Field | Type | Description |
|-------|------|-------------|
| `routed_signals` | int | Total signals attempted |
| `delivered_signals` | int | Successfully delivered |
| `blocked_signals` | int | Blocked by threshold/energy |
| `total_signal_strength` | float | Sum of delivered signal strengths |
| `mean_signal_strength` | float | Average delivered strength |
| `total_energy_cost` | float | Cumulative routing energy cost |
| `active_pathways` | int | Pathways above min strength |
| `regional_signal_flow_score` | float | Composite [0,1] flow metric |
| `signals` | list[RegionSignal] | Per-signal detail |

## RegionSignalRouter

### Constructor

- `min_source_activation: float = 0.05` — soft activation threshold
- `min_pathway_strength: float = 0.01` — minimum pathway conductance
- `signal_gain: float = 1.0` — global gain multiplier
- `energy_cost_per_signal: float = 0.001` — metabolic cost per routed signal
- `max_signals_per_tick: int = 16` — cap to avoid runaway

### Methods

- `compute_soft_region_activation(region_id, circuit) -> float`

  ```
  soft_activation =
    mean(|activation|)
    + 0.5 * max(|activation|)
    + 0.25 * active_fraction
  ```
  where `active_fraction = count(|a| > 0.05) / total_neurons`.

- `build_region_signal(source_region_id, target_region_id, connection, circuit, confidence_weight) -> RegionSignal`

  ```
  signal_strength = source_activation * pathway_strength * signal_gain * confidence_weight
  energy_cost = energy_cost_per_signal
  ```

- `route_signal(signal, target_region_id, circuit) -> bool`

  Distributes `signal_strength / n_target_neurons` to each neuron in the target region. Returns `True` if any target neuron exists.

- `route_all(region_connectome, circuit, metrics, memory, confidence_score) -> RegionRoutingResult`

  Iterates connections:
  1. Skip if `source_activation < min_source_activation` (record `REGION_SIGNAL_BLOCKED`)
  2. Skip if `connection.strength < min_pathway_strength` (record `REGION_SIGNAL_BLOCKED`)
  3. Skip if `global_energy < 0.1` (record `REGION_SIGNAL_BLOCKED`)
  4. Build signal, record `REGION_SIGNAL_ROUTED`
  5. Deliver, record `REGION_SIGNAL_DELIVERED`
  6. Respect `max_signals_per_tick`
  7. After loop, record `REGIONAL_SIGNAL_FLOW_UPDATED`

- `compute_regional_signal_flow_score(result) -> float`

  ```
  delivery_ratio = delivered_signals / routed_signals
  strength_component = min(1.0, mean_signal_strength)
  score = delivery_ratio * strength_component
  ```
  Clamped to `[0, 1]`.

## Tick integration sequence

In `CellularBrainOrchestrator._tick`:

1. burst / global tick
2. STDP locale
3. inhibition
4. energy control
5. **regional signal routing (T25)**
6. inter-region plasticity (T23)
7. community / confidence / memory snapshot

Routing must precede plasticity so that delivered signals create activation pairs observable by STDP.

## New MorphologyEventType values

- `REGION_SIGNAL_ROUTED`
- `REGION_SIGNAL_BLOCKED`
- `REGION_SIGNAL_DELIVERED`
- `REGIONAL_SIGNAL_FLOW_UPDATED`

## Benchmark metrics (T25)

Added to `BenchmarkMetrics`:

- `routed_signals`
- `delivered_signals`
- `blocked_signals`
- `total_routed_signal_strength`
- `mean_routed_signal_strength`
- `routing_energy_cost`
- `active_inter_region_pathways`

`regional_signal_flow_score` is overridden with the T25 value when `last_routing_result` is present and non-zero.

## Acceptance criteria

- [x] `RegionSignalRouter` exists and is importable.
- [x] `compute_soft_region_activation` returns > 0 for weak activations.
- [x] `route_all` produces signals when source activation is low but non-zero.
- [x] `route_all` produces no signals when `pathway_strength = 0`.
- [x] `route_signal` increases target region neuron activation.
- [x] `energy_cost` is computed and accumulated.
- [x] `max_signals_per_tick` is respected.
- [x] MorphologicalMemory events `REGION_SIGNAL_ROUTED`, `REGION_SIGNAL_DELIVERED` recorded.
- [x] Orchestrator integrates `region_signal_routing_enabled` and `_region_signal_router`.
- [x] Benchmark includes routing metrics.
- [x] At least one benchmark run produces `delivered_signals > 0`.
- [x] `regional_signal_flow_score > 0` in at least one case.
- [x] All 336 tests pass; coverage stays ≥ 85% (target 91%+).
- [x] `docs/REGIONAL_SIGNAL_ROUTING_REDESIGN_SPEC.md` created.

## Post-T25 next step

T26 — Re-run T24 With Routing Enabled.

Re-execute the T24 audit with:
- `region_signal_routing_enabled = True`
- `inter_region_plasticity_enabled = True`

Only if T26 shows:
- `regional_signal_flow_score > 0`
- `inter_region_plasticity_events > 0`
- `cognitive_score` does not collapse
- `energy_efficiency` does not collapse

then proceed to T27 — Deep Region Specialization (limbic, cerebellar, default-mode).
