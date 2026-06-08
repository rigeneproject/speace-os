# T37 — Adaptive Brainstem Gain Controller

**Version:** v0.3.20-t37-adaptive-brainstem-gain-controller  
**Date:** 2026-05-16  
**Status:** Implemented  
**Depends on:** T36 (Cognitive/Autonomic Balance Tuning)

## 1. Objective

Aggiungere un livello di autoregolazione sopra il `BrainstemFunctionalController`, capace di adattare dinamicamente l'intensita delle modulazioni in base agli effetti osservati su cognizione, Φ, energia e stabilita.

## 2. Problem Statement

T36B Audit Results:
- cognitive_score: **0.4569** (baseline 0.4896, delta -0.0327)
- coherence_phi: **0.2754** (delta -0.0013)
- energy_efficiency: **+0.0172**
- net_gain: **-0.0284**
- verdict: **OVER_SUPPRESSION**

Diagnosi: il brainstem bilancia meglio rispetto a T35, ma la soppressione rimane eccessiva. Il gain delle modulazioni e fisso; il sistema ha bisogno di un controller che impari quanto controllo applicare.

## 3. Architecture

### 3.1 Component

```
speace_core/cellular_brain/regions/brainstem_gain_controller.py
```

### 3.2 Classes

| Class | Role |
|---|---|
| `AdaptiveBrainstemGainController` | Adatta i gain in base agli outcome |
| `BrainstemGainState` | Stato corrente dei gain |
| `BrainstemGainDecision` | Gain applicati in questo tick |
| `BrainstemGainUpdateResult` | Risultato dell'aggiornamento |

### 3.3 Gain Variables

| Gain | Default | Min | Max |
|---|---|---|---|
| `global_brainstem_gain` | 1.0 | 0.50 | 1.50 |
| `routing_gain` | 1.0 | 0.50 | 1.50 |
| `plasticity_gain` | 1.0 | 0.50 | 1.50 |
| `decay_gain` | 1.0 | 0.50 | 1.50 |
| `energy_recovery_gain` | 1.0 | 0.50 | 1.50 |
| `cooldown_gain` | 1.0 | 0.50 | 1.50 |
| `emergency_gain` | 1.0 | 0.40 | 1.20 |
| `cognitive_preservation_gain` | 1.0 | 1.00 | 1.50 |

## 4. Adaptive Rules

### 4.1 Over-suppression detection

Se `cognitive_score_delta < -0.02` e `coherence_phi_delta >= -0.02`:
- riduci `routing_gain`, `plasticity_gain`, `emergency_gain`
- aumenta `cognitive_preservation_gain`

### 4.2 Useful stabilization

Se `coherence_phi_delta > 0.02` e `cognitive_score_delta >= -0.03`:
- mantieni o aumenta leggermente `global_brainstem_gain`

### 4.3 Energy recovery without cognitive damage

Se `energy_efficiency_delta > 0.01` e `cognitive_score_delta >= -0.03`:
- mantieni `energy_recovery_gain`
- riduci `routing_gain` e `plasticity_gain`

### 4.4 Chronic emergency/protective

Se `emergency_ticks > 3` o `protective_ticks > 6`, senza collasso Φ:
- riduci `emergency_gain` e `decay_gain`
- aumenta `cognitive_preservation_gain`

### 4.5 True instability

Se `coherence_phi_delta < -0.05` o `mean_region_energy < 0.12`:
- aumenta `global_brainstem_gain`, `energy_recovery_gain`, `decay_gain`

## 5. Reward Formula

```
brainstem_gain_reward =
  0.35 * max(0, cognitive_score_delta)
+ 0.25 * max(0, coherence_phi_delta)
+ 0.20 * max(0, energy_efficiency_delta)
+ 0.10 * max(0, functional_improvement_delta)
- 0.25 * suppression_cost
- 0.15 * emergency_tick_ratio
```

## 6. Orchestrator Integration

- Flag: `brainstem_gain_controller_enabled: bool = False`
- Il gain controller valuta alla fine di ogni benchmark run
- I gain correnti vengono applicati sulle modulazioni brainstem nel tick loop
- I gain multiplicano l'intensita delle modulazioni T36:
  - `routing_multiplier = 1.0 - (1.0 - base_routing) * routing_gain`
  - `decay_boost = 1.0 + (base_decay - 1.0) * decay_gain`

## 7. Benchmark Metrics (T37)

| Metric | Type | Description |
|---|---|---|
| `brainstem_gain_reward` | float | Reward computato |
| `global_brainstem_gain` | float | Gain globale |
| `routing_gain` | float | Gain routing |
| `plasticity_gain` | float | Gain plasticita |
| `decay_gain` | float | Gain decay |
| `energy_recovery_gain` | float | Gain energia |
| `emergency_gain` | float | Gain emergency |
| `cognitive_preservation_gain` | float | Gain preservazione |
| `gain_adjustments_count` | int | Numero di aggiustamenti |
| `over_suppression_detected` | bool | Over-suppression rilevata |
| `useful_stabilization_detected` | bool | Stabilizzazione utile |
| `true_instability_detected` | bool | Vera instabilita |
| `gain_stability_score` | float | Stabilita dei gain in [0, 1] |

## 8. MorphologicalMemory Events (T37)

| Event | Trigger |
|---|---|
| `BRAINSTEM_GAIN_EVALUATED` | Ogni tick con gain controller attivo |
| `BRAINSTEM_GAIN_ADJUSTED` | Quando i gain vengono modificati |
| `BRAINSTEM_OVER_SUPPRESSION_DETECTED` | Regola 1 attivata |
| `BRAINSTEM_USEFUL_STABILIZATION_DETECTED` | Regola 2 attivata |
| `BRAINSTEM_TRUE_INSTABILITY_DETECTED` | Regola 5 attivata |
| `BRAINSTEM_COGNITIVE_GAIN_BOOSTED` | Quando cognitive_preservation_gain aumenta |
| `BRAINSTEM_EMERGENCY_GAIN_REDUCED` | Quando emergency_gain diminuisce |

## 9. Test Plan

| Test | Description |
|---|---|
| gain state defaults | Valori iniziali corretti |
| reward computation | Formula corretta |
| over suppression reduces gains | Regola 1 |
| useful stabilization increases global gain | Regola 2 |
| energy recovery reduces routing/plasticity | Regola 3 |
| chronic high alert reduces emergency gain | Regola 4 |
| true instability increases gains | Regola 5 |
| gains clamped to safe ranges | Range sicuri |
| emergency gain clamped | Min 0.40, max 1.20 |
| cognitive preservation gain clamped | Min 1.00, max 1.50 |
| apply with memory events | Eventi registrati |
| gain summary | Riepilogo gain |
| orchestrator integration | Flag e inizializzazione |
| benchmark metrics presence | Campi T37 esposti |
| gain stability score range | [0, 1] |
| global gain scaling | Moltiplicazione corretta |

## 10. Acceptance Criteria

- [x] `AdaptiveBrainstemGainController` esiste ed e importabile
- [x] Reward e adjustment calcolati correttamente
- [x] Soppressione ridotta in caso di over-suppression
- [x] Protezione aumentata in caso di vera instabilita
- [x] Gain nei range sicuri
- [x] 13 nuove metriche benchmark esposte
- [x] 7 nuovi eventi MorphologicalMemory
- [x] 557 test passati
- [x] Coverage >= 85% (89.06%)
- [x] Commit e tag

## 11. T37B Audit Results

**Audit ID:** t37b_42  
**Verdict:** `GAIN_PARTIAL_RECOVERY`  
**Best Profile:** `brainstem_gain_default`  
**T38 Recommendation:** T38 Gain Sensitivity Tuning

### Baseline T36 (no gain controller)
- cognitive_score: 0.4569
- coherence_phi: 0.2754
- energy_efficiency: 0.2195
- net_gain: 0.0000

### Gain-enabled profiles (all converged)
- cognitive_score: 0.4575 (+0.0006)
- coherence_phi: 0.2770 (+0.0016)
- energy_efficiency: 0.2214 (+0.0019)
- net_gain: 0.0008 (+0.0008 vs T36)
- gain_adjustments: 7
- decay_gain: 0.825
- emergency_gain: 0.65
- cognitive_preservation_gain: 1.35

### Interpretation
Il gain controller ha prodotto un recupero parziale: net_gain passa da -0.0284 (T36B) a +0.0008 vs baseline T36. Il reward resta negativo (-0.0309) a causa del suppression cost e dell'emergency tick ratio. Tutti i profili gain convergono allo stesso stato, indicando che il sistema raggiunge rapidamente un equilibrio ma con margine limitato. Il passaggio a T38 e giustificato.

## 12. Next Step

**T38 — Gain Sensitivity Tuning**

Aumentare la sensibilita del gain controller per amplificare il recupero e raggiungere `GAIN_CONTROLLER_VALIDATED` (net_gain > 0.02).

## 13. References

- T36B audit report: `reports/brainstem/t35b_brainstem_audit_20260516_211957.md`
- `speace_core/cellular_brain/regions/brainstem_gain_controller.py`
- `tests/regions/test_brainstem_gain_controller.py`

---
*Generated by T37 Adaptive Brainstem Gain Controller*
