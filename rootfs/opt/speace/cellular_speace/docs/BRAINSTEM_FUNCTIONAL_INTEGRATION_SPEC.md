# T35 — Brainstem Functional Integration

**Version:** v0.3.16-t35-brainstem-functional-integration  
**Date:** 2026-05-16  
**Status:** Implemented  
**Depends on:** T34 (Deep Region Routing Calibration v2), T35-ACTCLAMP

## 1. Objective

Transform `brainstem_homeostatic` from a passive deep-region target into an **active systemic homeostatic arbiter** that regulates energy, routing, plasticity, decay, cooldown, and recovery for the entire cellular brain.

## 2. Problem Statement

After T34 and T35-ACTCLAMP:

- Deep-region routing works
- Stability controller works
- Activation clamp works
- Forced decay works

However, the brainstem is still only a **target region** that receives boosted signals. It does not yet act as a **central regulator** that interprets global state and modulates system behavior.

T35 closes this gap:

```
deep regions active
→ instability detected
→ brainstem interprets global state
→ brainstem modulates energy / routing / plasticity / decay
→ Φ recovers or stays stable
```

## 3. Architecture

### 3.1 Component

```
speace_core/cellular_brain/regions/brainstem_controller.py
```

### 3.2 Classes

| Class | Role |
|---|---|
| `BrainstemFunctionalController` | Main regulator engine |
| `BrainstemFunctionalState` | Enum: stable, watchful, corrective, protective, emergency |
| `BrainstemState` | Snapshot of input metrics |
| `BrainstemDecision` | Output modulation plan |
| `BrainstemModulationResult` | Result of applying a decision |

### 3.3 Inputs

The brainstem reads these metrics every tick:

- `mean_region_phi`
- `mean_energy`
- `region_instability_mean`
- `unstable_region_count`
- `mean_deep_region_activation`
- `regional_signal_flow`
- `deep_region_signal_flow`
- `stability_actions_applied`
- `routing_blocks_applied`
- `cooldowns_started`
- `mean_pathway_utility`
- `energy_state`

### 3.4 Outputs

The brainstem produces global/regional multipliers:

| Multiplier | Description |
|---|---|
| `energy_recovery_multiplier` | Boost energy recovery in emergency |
| `routing_suppression_multiplier` | Reduce routing when unstable |
| `plasticity_suppression_multiplier` | Reduce plasticity when unstable |
| `decay_boost_multiplier` | Increase activation decay when unstable |
| `cooldown_boost_multiplier` | Extend cooldown when unstable |
| `neurogenesis_suppression_multiplier` | Suppress neurogenesis in protective/emergency |
| `apoptosis_boost_multiplier` | Increase pruning in protective/emergency |
| `brainstem_priority_boost` | Boost brainstem signal priority |

## 4. State Machine

### 4.1 States

| State | Trigger | Routing | Plasticity | Decay | Cooldown | Neurogenesis | Apoptosis |
|---|---|---|---|---|---|---|---|
| **stable** | Healthy system | normal | normal | normal | none | normal | normal |
| **watchful** | Mild instability | -10% | normal | +10% | normal | normal | normal |
| **corrective** | Moderate instability | -25% | -20% | +25% | +20% | normal | normal |
| **protective** | Strong instability | -45% | -50% | +50% | +40% | -70% | +30% |
| **emergency** | Critical energy or extreme instability | -70% | -80% | +100% | +100% | -90% | +60% |

### 4.2 State Transitions

```
energy < 0.15  or  instability >= 0.70   → emergency
instability >= 0.50  or  unstable_count >= 3  or  deep_activation > 2.0   → protective
instability >= 0.30  or  phi < 0.15   → corrective
instability >= 0.15  or  phi < 0.20   → watchful
otherwise   → stable
```

## 5. Orchestrator Integration

### 5.1 Flag

```python
brainstem_controller_enabled: bool = False
```

### 5.2 Tick Sequence

1. Homeostasis metrics computed
2. Community detection / confidence evaluation
3. Regional architecture regulation (T21)
4. **T35 — Brainstem controller reads metrics and produces modulations**
5. T33 — Stability controller pre-routing check
6. T25 — Regional signal routing (with composed brainstem + stability multipliers)
7. T23 — Inter-region plasticity (with composed multipliers)
8. T33 — Stability controller post-routing check

### 5.3 Multiplier Composition

Brainstem modulations are **multiplicative** with stability-controller multipliers:

```python
final_routing_multiplier = stability_multiplier * brainstem_routing_suppression
final_plasticity_multiplier = stability_multiplier * brainstem_plasticity_suppression
```

## 6. Benchmark Metrics

New metrics added to `BenchmarkMetrics`:

| Metric | Type | Description |
|---|---|---|
| `brainstem_state` | str | Current brainstem state |
| `brainstem_decisions_count` | int | Total decisions made |
| `brainstem_energy_modulation` | float | Energy recovery multiplier |
| `brainstem_routing_modulation` | float | Routing suppression multiplier |
| `brainstem_plasticity_modulation` | float | Plasticity suppression multiplier |
| `brainstem_decay_modulation` | float | Decay boost multiplier |
| `brainstem_recovery_actions` | int | Recovery actions in this run |
| `brainstem_emergency_count` | int | Emergency states entered |
| `brainstem_homeostatic_gain` | float | Simple homeostatic score |
| `brainstem_phi_recovery_contribution` | float | Phi delta since last tick |

## 7. MorphologicalMemory Events

New events added to `MorphologyEventType`:

- `BRAINSTEM_STATE_CHANGED`
- `BRAINSTEM_MODULATION_APPLIED`
- `BRAINSTEM_EMERGENCY_TRIGGERED`
- `BRAINSTEM_RECOVERY_APPLIED`
- `BRAINSTEM_ROUTING_SUPPRESSED`
- `BRAINSTEM_PLASTICITY_SUPPRESSED`
- `BRAINSTEM_ENERGY_RECOVERY_BOOSTED`

## 8. Test Plan

| Test | Description |
|---|---|
| stable with healthy metrics | State = stable, no suppression |
| watchful with mild instability | Routing -10%, decay +10% |
| corrective with moderate instability | Routing -25%, plasticity -20% |
| protective with strong instability | Routing -45%, plasticity -50% |
| emergency with simulated collapse | Routing -70%, energy +50% |
| routing suppression in unstable scenario | Multiplier < 1.0 |
| plasticity suppression in unstable scenario | Multiplier < 1.0 |
| energy recovery in low-energy scenario | Multiplier > 1.0 |
| memory events recorded | All relevant events present |
| orchestrator integration | Controller initialized, metrics populated |
| benchmark metrics present | All 10 brainstem metrics exposed |

## 9. Acceptance Criteria

- [x] `BrainstemFunctionalController` exists and is importable
- [x] Brainstem reads real metrics from regional system
- [x] Brainstem produces operative modulations
- [x] At least one scenario induces watchful/corrective/protective state
- [x] At least one emergency scenario is artificially tested
- [x] In unstable scenario, brainstem reduces routing or plasticity
- [x] In low-energy scenario, brainstem increases recovery or reduces consumption
- [x] Benchmark exposes T35 metrics
- [x] All tests pass
- [x] Coverage >= 85%
- [x] JSON/Markdown reports updated
- [x] Final commit
- [x] Tag: `v0.3.16-t35-brainstem-functional-integration`

## 10. Next Step

**T35B — Brainstem Functional Audit**

Verify whether the brainstem improves the best post-T34B profile (`routing_v2_medium_with_stability`) by comparing benchmark results with and without `brainstem_controller_enabled`.

## 11. References

- T34B re-audit results (2026-05-16): `ROUTING_V2_STABILITY_VALIDATED`
- `reports/deep_region_routing/t34b_routing_v2_audit_20260516_194117.md`
- `speace_core/cellular_brain/regions/brainstem_controller.py`
- `tests/regions/test_brainstem_controller.py`

---
*Generated by T35 Brainstem Functional Integration*
