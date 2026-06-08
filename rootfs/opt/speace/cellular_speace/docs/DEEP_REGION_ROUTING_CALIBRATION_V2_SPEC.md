# T34 — Deep Region Routing Calibration v2 — Specification

## Overview

T33B revealed `STABILITY_NO_EFFECT`: the T33 stability controller runs correctly but deep regions are too dormant to trigger it. T34 redesigns signal routing so deep regions receive enough local activation to generate measurable instability (and thus T33 stabilization), without collapsing Φ, cognitive score, or energy.

## Diagnosis from T33B

| Metric | Value | Threshold | Status |
|---|---|---|---|
| region_instability_mean | ~0.075 | ≥ 0.25 | Below threshold |
| stability_actions_applied | 0 | > 0 | No actions triggered |
| phi_recovery_score | ~0.00 | > 0.02 | No recovery |

Root cause: signal routing distributes activation uniformly across all target neurons. Per-neuron activation is too low to generate volatility, overflow, or energy stress.

## Solution: 5 mechanisms

### 1. Top-k target routing
Concentrate signal on the most active neurons instead of broadcasting to all.

```
k = max(top_k_min, int(top_k_ratio * region_neuron_count))
```

Default: `top_k_ratio = 0.15`, `top_k_min = 3`.

### 2. Regional gain multipliers
Boost signal strength for deep regions based on empirical tuning.

| Region | Gain |
|---|---|
| sensory | 1.00 |
| limbic | 1.20 |
| hippocampus | 1.15 |
| default_mode | 1.10 |
| prefrontal | 1.05 |
| cerebellar | 1.10 |
| motor | 1.00 |
| brainstem_homeostatic | 1.25 |

### 3. Deep-region signal boost
Additional multiplier (`deep_region_signal_boost`, default 1.0–1.5) applied specifically to signals targeting deep regions.

### 4. Flow memory per region
Track per-region signal history:
- `last_signal_inflow`
- `last_signal_outflow`
- `last_activation_delta`
- `cumulative_inflow / outflow`
- `last_routed_tick`

### 5. Stability-aware routing
Prevent the T33 stability controller from fully zeroing deep-region signals. Apply a `deep_region_damping_floor` (default 0.30) so deep regions still receive partial routing even when the controller wants to block them.

## Models

### RegionFlowMemory
- `region_id`, `last_signal_inflow`, `last_signal_outflow`, `last_activation_delta`
- `cumulative_inflow`, `cumulative_outflow`, `inflow_count`, `outflow_count`
- `last_routed_tick`

### DeepRegionRoutingProfile
- `profile_id`, `name`
- `top_k_ratio`, `top_k_min`
- `regional_gain_map: Dict[str, float]`
- `deep_region_signal_boost: float`
- `stability_aware_routing: bool`
- `min_deep_region_activation: float`
- `flow_memory_enabled: bool`
- `top_k_routing_active: bool`
- `deep_region_damping_floor: float`

### DeepRegionRoutingResult
- `profile_id`, `routed_signals`, `delivered_signals`, `blocked_signals`
- `deep_region_targeted_signals`, `mean_deep_region_activation`
- `mean_regional_signal_gain`, `routing_efficiency`
- `flow_memory_entries`, `stability_damping_resisted`

## Calibration profiles (6)

| ID | Name | top_k | gain | boost | stability_aware |
|---|---|---|---|---|---|
| p0 | baseline_no_top_k | off | no | 1.0 | no |
| p1 | top_k_only | 0.15 | no | 1.0 | no |
| p2 | top_k_with_regional_gain | 0.15 | yes | 1.0 | no |
| p3 | top_k_gain_and_boost | 0.15 | yes | 1.30 | no |
| p4 | full_stability_aware | 0.15 | yes | 1.30 | yes (floor=0.30) |
| p5 | aggressive_deep_stimulation | 0.20 | +10% | 1.50 | yes (floor=0.40) |

## Router modifications

### `RegionSignalRouter.route_signal`
If `_t34_profile.top_k_routing_active`, select top-k most active target neurons and deliver signal only to them.

### `RegionSignalRouter.build_region_signal`
Apply `_t34_gain_map[target_region_id]` and `deep_region_signal_boost` for deep targets.

### `RegionSignalRouter.route_all`
- Accept `current_tick` parameter
- Apply stability-aware multiplier correction via `DeepRegionRoutingCalibrator.correct_routing_multiplier`
- Track flow memory after delivery
- Record `deep_region_targeted_signals` in metadata

## Orchestrator integration

```
1. Pre-routing stability check → compute multipliers
2. Apply T34 profile to router (if enabled)
3. Routing with multiplier_map + top-k + regional gain + stability correction
4. Plasticity with plasticity_multiplier_map
5. Post-routing stability check
6. Energy control
7. Snapshot
```

New orchestrator flags:
- `deep_region_routing_calibrator_enabled: bool = False`
- `_deep_region_routing_calibrator: DeepRegionRoutingCalibrator | None = None`
- `_deep_region_routing_profile: DeepRegionRoutingProfile | None = None`

## Benchmark metrics (T34)

| Metric | Source |
|---|---|
| top_k_routing_active | router._t34_profile.top_k_routing_active |
| mean_deep_region_activation | mean activation of deep-region neurons |
| deep_region_routing_efficiency | delivered / routed |
| regional_gain_applied | bool(gain_map) |
| flow_memory_enabled | profile.flow_memory_enabled |
| stability_aware_routing_active | profile.stability_aware_routing |
| deep_region_targeted_signals | from routing result metadata |
| mean_regional_signal_gain | mean of gain_map values |
| deep_region_phi_recovery | max(0, final_phi - baseline_phi) |

## Acceptance criteria

- [x] DeepRegionRoutingCalibrator exists and is importable
- [x] Top-k routing concentrates signal on most-active neurons
- [x] Regional gain multipliers boost deep-region signal strength
- [x] Flow memory tracks per-region inflow/outflow/delta
- [x] Stability-aware routing applies damping floor to deep regions
- [x] 6 default calibration profiles defined
- [x] Router supports T34 settings via attribute injection
- [x] Orchestrator supports `deep_region_routing_calibrator_enabled` flag
- [x] T34 benchmark metrics added to `BenchmarkMetrics`
- [x] T34 memory events added to `MorphologyEventType`
- [x] No regression on existing tests
- [x] Coverage ≥ 85%
- [x] Docs created
- [x] Commit and tag

## Post-T34 next step

Run T34 audit suite comparing the 6 profiles against the T33B baseline. Success = at least one profile achieves `region_instability_mean ≥ 0.25` and `phi_recovery_score > 0.02`.
