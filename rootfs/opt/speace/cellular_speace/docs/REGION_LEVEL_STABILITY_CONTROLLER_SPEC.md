# T33 — Region-Level Stability Controller v0.3 — Specification

## Overview

T32B revealed that deep regions are structurally neutral but cause Φ regression when routing is activated. T33 introduces a stability controller that monitors each region and applies reversible modulations to prevent coherence loss.

## Diagnosis from T32B

| Configuration | Φ | Net Gain |
|---|---|---|
| four_region_baseline | 0.2482 | 0.0000 |
| deep_regions_static | 0.2507 | +0.0011 |
| deep_regions_routing_only | 0.1740 | -0.0214 |
| deep_regions_full_utility | 0.1963 | -0.0155 |

Conclusion: anatomy is fine, dynamics need stabilization.

## Models

### RegionStabilityState
- `region_id`, `phi`, `energy`, `activation`, `signal_inflow`, `signal_outflow`
- `instability_score` ∈ [0.0, 1.0]
- `cooldown_remaining`, `damping_factor`, `routing_allowed`

### RegionStabilityAction
- `region_id`, `action_type`, `reason`
- `damping_factor`, `cooldown_ticks`
- `plasticity_multiplier`, `routing_multiplier`

### RegionStabilityResult
- `regions_checked`, `unstable_regions`, `actions_applied`
- `mean_instability_score`, `mean_damping_factor`
- `phi_guard_triggered`, `brainstem_override_triggered`

## Instability formula

```
instability_score =
  0.35 * max(0, phi_baseline - region_phi)
+ 0.25 * activation_volatility
+ 0.20 * signal_overflow
+ 0.10 * energy_stress
+ 0.10 * negative_utility_pressure
```

Clamped to [0.0, 1.0].

## Thresholds

| Range | Label | Action |
|---|---|---|
| 0.00–0.25 | stable | none |
| 0.25–0.50 | watch | soft damping |
| 0.50–0.75 | damp | hard damping + cooldown |
| 0.75–1.00 | critical | routing block + cooldown |

## Actions

### Soft damping
- routing_multiplier = 0.75
- plasticity_multiplier = 0.75
- damping_factor = 0.85

### Hard damping
- routing_multiplier = 0.40
- plasticity_multiplier = 0.40
- damping_factor = 0.60
- cooldown_ticks = 2

### Routing block
- routing_multiplier = 0.0
- plasticity_multiplier = 0.20
- damping_factor = 0.30
- cooldown_ticks = 3

### Brainstem override
Triggered when ≥ 1/3 of regions are unstable:
- global_routing_multiplier = 0.5
- global_plasticity_multiplier = 0.5

## Orchestrator integration

```
1. Pre-routing stability check → compute multipliers
2. Routing with routing_multiplier_map
3. Plasticity with plasticity_multiplier_map
4. Post-routing stability check → detect new instability
5. Energy control
6. Snapshot
```

## Benchmark metrics

| Metric | Source |
|---|---|
| region_instability_mean | mean of all region instability scores |
| unstable_region_count | regions with score ≥ 0.25 |
| stability_actions_applied | total damping + block + cooldown events |
| routing_blocks_applied | REGION_ROUTING_BLOCKED events |
| cooldowns_started | REGION_COOLDOWN_STARTED events |
| mean_region_damping_factor | mean damping_factor across regions |
| brainstem_override_count | BRAINSTEM_STABILITY_OVERRIDE events |
| phi_recovery_score | max(0, final_phi - baseline_phi) |
| stability_controller_active | bool |

## Acceptance criteria

- [x] RegionLevelStabilityController exists and is importable
- [x] instability_score formula clamps to [0, 1]
- [x] soft/hard damping and routing block actions are generated
- [x] brainstem override triggers when ≥ 1/3 regions are unstable
- [x] pre/post routing stability checks run and record events
- [x] cooldowns decrement and recover correctly
- [x] routing/plasticity multipliers are exposed for orchestrator use
- [x] benchmark includes T33 stability metrics
- [x] orchestrator supports region_stability_controller_enabled flag
- [x] no regression on existing tests
- [x] coverage ≥ 85%
- [x] docs created
- [x] commit and tag

## Post-T33 next step

Re-run T32B with `region_stability_controller_enabled=True` and verify that at least one deep routing profile recovers Φ relative to `deep_regions_routing_only`.
