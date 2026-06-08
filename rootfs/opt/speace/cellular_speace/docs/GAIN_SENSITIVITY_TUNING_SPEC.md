# T38 — Gain Sensitivity Tuning

**Version:** v0.3.22-t38-gain-sensitivity-tuning  
**Date:** 2026-05-16  
**Status:** Implemented  
**Depends on:** T37 (Adaptive Brainstem Gain Controller)

## 1. Objective

Rendere l'AdaptiveBrainstemGainController piu sensibile, piu differenziato e piu efficace nel ridurre la soppressione cognitiva senza perdere stabilita.

## 2. Problem Statement

T37B Audit Results:
- net_gain: **+0.0008** (vs T36 baseline)
- adjustments: **7** per profile
- reward: **-0.0309**
- all profiles converged to identical state

Diagnosi: il controller reagisce correttamente ma impara troppo lentamente, converge prematuramente e la penalita di soppressione domina il reward.

## 3. Architecture

### 3.1 Component

```
speace_core/cellular_brain/regions/brainstem_gain_controller.py
```

### 3.2 Classes

| Class | Role |
|---|---|
| `AdaptiveBrainstemGainController` | Adatta i gain con sensibilita T38 |
| `BrainstemGainState` | Stato corrente dei gain |
| `BrainstemGainDecision` | Gain applicati in questo tick |
| `BrainstemGainUpdateResult` | Risultato dell'aggiornamento (esteso T38) |

### 3.3 Gain Profile Presets

| Preset | routing | plasticity | decay | emergency | cognitive_preservation |
|---|---|---|---|---|---|
| `conservative` | 0.90 | 0.90 | 0.90 | 0.70 | 1.20 |
| `balanced` | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| `cognitive_preserving` | 1.10 | 1.10 | 0.75 | 0.55 | 1.45 |
| `phi_preserving` | 0.90 | 0.95 | 1.05 | 0.80 | 1.20 |
| `energy_preserving` | 0.85 | 0.85 | 1.10 | 0.75 | 1.10 |
| `exploratory` | 1.20 | 1.20 | 0.80 | 0.60 | 1.30 |
| `low_suppression` | 1.20 | 1.15 | 0.70 | 0.45 | 1.50 |
| `emergency_minimal` | 1.00 | 1.00 | 1.00 | 0.40 | 1.35 |

## 4. Reward v2

```
brainstem_gain_reward_v2 =
  0.30 * cognitive_preservation_delta
+ 0.25 * max(0, coherence_phi_delta)
+ 0.20 * max(0, energy_efficiency_delta)
+ 0.15 * max(0, functional_improvement_delta)
+ 0.10 * max(0, regional_signal_flow_delta)
- 0.15 * suppression_cost
- 0.10 * emergency_tick_ratio
- 0.05 * protective_tick_ratio
```

Differenza chiave: penalita soppressione ridotta da 0.25 a 0.15.

## 5. Adaptive Learning Rate

| Condition | LR |
|---|---|
| Base | 0.05 |
| Over-suppression detected | 0.08 |
| True instability detected | 0.10 |
| Reward negative for 3 cycles | 0.12 |
| Gain oscillation detected | 0.03 |

Range: `[0.02, 0.15]`

## 6. Anti-Convergence / Diversity Pressure

- `gain_profile_divergence`: mean absolute distance tra gain vectors
- Se `divergence < 0.03` e `adjustments_count > 0`:
  - `gain_convergence_detected = True`
  - Applica `diversity_pressure` in base al `profile_type`

## 7. New Benchmark Metrics (T38)

| Metric | Type | Description |
|---|---|---|
| `brainstem_gain_reward_v2` | float | Reward v2 computato |
| `adaptive_gain_learning_rate` | float | LR attuale |
| `gain_profile_divergence` | float | Divergenza tra profili |
| `gain_convergence_detected` | bool | Convergenza rilevata |
| `diversity_pressure_applied` | bool | Pressure applicata |
| `suppression_cost_reduction` | float | Riduzione suppression cost |
| `cognitive_recovery_margin` | float | Margine recupero cognitivo |
| `phi_preservation_margin` | float | Margine preservazione phi |
| `gain_vector_distance` | float | Distanza dal preset balanced |

## 8. New MorphologicalMemory Events (T38)

| Event | Trigger |
|---|---|
| `BRAINSTEM_GAIN_REWARD_V2_COMPUTED` | Ogni tick con gain controller attivo |
| `BRAINSTEM_GAIN_LR_ADAPTED` | Quando LR cambia |
| `BRAINSTEM_GAIN_DIVERSITY_PRESSURE_APPLIED` | Quando diversity pressure attiva |
| `BRAINSTEM_GAIN_CONVERGENCE_DETECTED` | Quando convergence < 0.03 |
| `BRAINSTEM_SUPPRESSION_COST_REDUCED` | Quando suppression cost diminuisce |
| `BRAINSTEM_COGNITIVE_RECOVERY_IMPROVED` | Quando cognitive_recovery_margin > 0 |

## 9. Test Plan

| Test | Description |
|---|---|
| reward_v2 penalizza meno soppressione | r2 > r1 per stessi metric |
| adaptive lr aumenta con over_suppression | lr == 0.08 |
| adaptive lr aumenta con true_instability | lr == 0.10 |
| adaptive lr diminuisce con oscillazione | lr == 0.03 |
| gain divergence calcolata correttamente | divergenza > 0 per vettori diversi |
| convergence detection funziona | detection attiva quando appropriato |
| diversity pressure modifica profili diversi | profili divergono |
| low_suppression profile resta meno soppressivo | routing > 1.0 |
| phi_preserving profile mantiene piu decay | decay > 1.0 |
| benchmark espone metriche T38 | campi presenti |
| eventi registrati | nuovi eventi in memory |
| preset factory | apply_preset funziona |
| oscillation detection | rileva oscillazione in history |

## 10. T38B Audit Results

**Audit ID:** t38b_42  
**Verdict:** `GAIN_NEUTRAL`  
**Cross-Profile Divergence:** 0.0905  
**Best Profile:** `gain_balanced` (net_gain +0.0008)  
**Worst Profile:** `gain_energy_preserving` (net_gain -0.028)  
**T39 Recommendation:** T39 Gain Input Coupling Redesign

### Results by profile

| Profile | Reward v2 | Net Gain | Divergence | LR |
|---|---|---|---|---|
| baseline | 0.0 | 0.0000 | — | — |
| balanced | +0.002 | +0.0008 | 0.2575 | 0.12 |
| cognitive_preserving | +0.002 | +0.0006 | 0.0750 | 0.12 |
| phi_preserving | +0.0337 | -0.0151 | 0.1950 | 0.12 |
| low_suppression | +0.002 | +0.0006 | 0.0817 | 0.12 |
| exploratory | +0.002 | +0.0007 | 0.1167 | 0.12 |
| energy_preserving | +0.0279 | -0.0280 | 0.1992 | 0.12 |
| emergency_minimal | +0.002 | +0.0008 | 0.0992 | 0.12 |

### Interpretation
- **Reward v2 funziona**: passa da negativo (-0.0309) a positivo per tutti i profili gain.
- **Profili differenziati**: cross-profile divergence 0.0905 (> 0.03), i preset producono traiettorie diverse.
- **Adaptive LR attivo**: tutti i profili convergono a LR 0.12 (reward negativo per 3 cicli → boost).
- **Net gain stagnante**: il miglioramento resta marginale (+0.0008). Il brainstem sottostante e in stato `protective` per tutti i profili, e il suppression cost rimane 0.12.
- **Conclusione**: il problema non e piu la sensibilita del gain controller, ma il coupling tra gain e le modulazioni effettive del brainstem. T39 deve intervenire sul modo in cui i gain influenzano il routing/plasticity modulations.

## 11. Acceptance Criteria

- [x] `brainstem_gain_reward_v2` calcolato e registrato
- [x] `adaptive_gain_learning_rate` modifica realmente l'intensita
- [x] Profili non convergono tutti allo stesso stato
- [x] `gain_profile_divergence` > 0.03 in almeno una suite (0.0905)
- [ ] `suppression_cost` diminuisce rispetto a T37B (rimane 0.12)
- [ ] `net_gain` migliora rispetto a +0.0008 (rimane +0.0008)
- [ ] Criterio minimo: `net_gain >= +0.005` (non raggiunto)
- [ ] Criterio buono: `net_gain >= +0.01` (non raggiunto)
- [ ] Criterio forte: `net_gain >= +0.02` (non raggiunto)
- [x] Tutti i test passano (574)
- [x] Coverage >= 85% (88.99%)
- [x] Commit e tag creati

## 12. Next Step

**T39 — Gain Input Coupling Redesign**

Il gain controller e sensibile, ma il segnale non arriva efficacemente alle modulazioni brainstem. T39 deve ridisegnare il coupling tra gain e modulazioni (routing/plasticity/decay) per rendere il gain effettivamente influente.

## 12. References

- T37B audit report: `reports/brainstem_gain/t37b_brainstem_gain_audit_20260516_213738.md`
- `speace_core/cellular_brain/regions/brainstem_gain_controller.py`
- `tests/regions/test_brainstem_gain_controller.py`

---
*Generated by T38 Gain Sensitivity Tuning*
