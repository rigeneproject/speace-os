# T36 — Cognitive/Autonomic Balance Tuning

**Version:** v0.3.18-t36-cognitive-autonomic-balance-tuning  
**Date:** 2026-05-16  
**Status:** Implemented  
**Depends on:** T35 (Brainstem Functional Integration), T35B (Brainstem Functional Audit)

## 1. Objective

Ricalibrare il `BrainstemFunctionalController` affinché bilanci stabilità autonomica e vitalità cognitiva, evitando la regressione cognitiva osservata in T35B (`cognitive_score_delta = -0.1136`).

## 2. Problem Statement

T35B Audit Results:
- Baseline T34B cognitive_score: **0.4896**
- T35B cognitive_score: **0.3760**
- Cognitive delta: **-0.1136**
- Φ delta: **+0.0748**
- Energy delta: **+0.0105**
- Net gain: **-0.0607**
- Verdict: **BRAINSTEM_COGNITIVE_REGRESSION**

Diagnosi: il brainstem funziona ma è troppo conservativo. Entra persistentemente in `emergency`/`protective`, comprimendo eccessivamente routing, plasticità e attivazione anche quando l'attività cognitiva è produttiva.

## 3. Architecture

### 3.1 Component

```
speace_core/cellular_brain/regions/brainstem_controller.py
```

### 3.2 New Concepts

| Concept | Description |
|---|---|
| `cognitive_vitality_score` | Punteggio di attività cognitiva produttiva in [0, 1] |
| `autonomic_risk_score` | Punteggio di rischio autonomico sistemico in [0, 1] |
| `balance_pressure` | `autonomic_risk_score - cognitive_vitality_score` |
| `EMERGENCY_CONSECUTIVE_TICKS_REQUIRED` | Isteresi: 2 tick consecutivi per entrare in emergency |
| `EMERGENCY_EXIT_THRESHOLD` | Uscita da emergency se `balance_pressure < 0.55` |
| `COGNITIVE_PRESERVATION_THRESHOLD` | Se `cognitive_vitality > 0.55` e nessun limite fisico violato, stato massimo = `corrective` |

### 3.3 State Machine (T36)

| State | Balance Pressure | Routing | Plasticity | Decay | Neurogenesis | Apoptosis |
|---|---|---|---|---|---|---|
| **stable** | < 0.10 | normal | normal | normal | normal | normal |
| **watchful** | 0.10 – 0.25 | 0.95 | 0.95 | 1.05 | normal | normal |
| **corrective** | 0.25 – 0.45 | 0.85 | 0.90 | 1.10 | normal | normal |
| **protective** | 0.45 – 0.70 | 0.70 | 0.75 | 1.20 | 0.50 | 1.15 |
| **emergency** | >= 0.70 | 0.50 | 0.50 | 1.50 | 0.30 | 1.30 |

### 3.4 Absolute Emergency Overrides

Triggert sempre `emergency` indipendentemente dalla vitalità cognitiva:
- `energy < 0.10`
- `deep_activation > 5.0` (activation explosion)
- `phi < 0.10` **e** `instability >= 0.40`
- `instability >= 0.85` **e** `unstable_count >= 4`

### 3.5 Soft Modulation vs T35

| State | T35 Routing | T36 Routing | T35 Plasticity | T36 Plasticity | T35 Decay | T36 Decay |
|---|---|---|---|---|---|---|
| watchful | 0.90 | **0.95** | 1.00 | **0.95** | 1.10 | **1.05** |
| corrective | 0.75 | **0.85** | 0.80 | **0.90** | 1.25 | **1.10** |
| protective | 0.55 | **0.70** | 0.50 | **0.75** | 1.50 | **1.20** |
| emergency | 0.30 | **0.50** | 0.20 | **0.50** | 2.00 | **1.50** |

## 4. Formule

### 4.1 Cognitive Vitality Score

Con metriche benchmark disponibili:
```
0.35 * cognitive_score
+ 0.25 * functional_improvement
+ 0.15 * regional_signal_flow
+ 0.15 * deep_region_signal_flow
+ 0.10 * max(0, mean_pathway_utility)
```

Con metriche tick-level (proxy):
```
0.45 * min(1.0, mean_region_phi)
+ 0.25 * min(1.0, regional_signal_flow)
+ 0.20 * min(1.0, deep_region_signal_flow)
+ 0.10 * min(1.0, mean_pathway_utility)
```

### 4.2 Autonomic Risk Score

```
0.30 * region_instability_mean
+ 0.20 * max(0, 1 - mean_region_phi)
+ 0.20 * max(0, 1 - mean_region_energy)
+ 0.15 * activation_overflow_score
+ 0.15 * unstable_region_ratio
```

Dove `activation_overflow_score = max(0, (mean_deep_activation - 1.0) / 4.0)`.

## 5. Orchestrator Integration

Il brainstem riceve ora anche:
- `region_count` (per calcolare `unstable_region_ratio`)
- `mean_deep_region_activation` (calcolato dal circuito a tick time)
- Placeholder per `cognitive_score` e `functional_improvement`

## 6. Benchmark Metrics (T36)

| Metric | Type | Description |
|---|---|---|
| `cognitive_vitality_score` | float | Produttività cognitiva percepita |
| `autonomic_risk_score` | float | Rischio autonomico computato |
| `balance_pressure` | float | Pressione di bilanciamento |
| `brainstem_state_distribution` | dict | Conteggio tick per stato |
| `emergency_ticks` | int | Tick trascorsi in emergency |
| `protective_ticks` | int | Tick trascorsi in protective |
| `watchful_ticks` | int | Tick trascorsi in watchful |
| `corrective_ticks` | int | Tick trascorsi in corrective |
| `cognitive_preservation_score` | float | 1.0 se preservation attiva |
| `autonomic_balance_score` | float | `max(0, 1 - balance_pressure)` |
| `suppression_cost` | float | Costo computato della soppressione |
| `useful_activity_preserved` | bool | True se attività utile preservata |

## 7. MorphologicalMemory Events (T6)

| Event | Trigger |
|---|---|
| `BRAINSTEM_BALANCE_EVALUATED` | Ogni tick con brainstem attivo |
| `BRAINSTEM_COGNITIVE_ACTIVITY_PRESERVED` | Quando `cognitive_vitality > 0.55` limita lo stato |
| `BRAINSTEM_EMERGENCY_HYSTERESIS_APPLIED` | Quando l'isteresi blocca l'ingresso in emergency |
| `BRAINSTEM_SUPPRESSION_SOFTENED` | Quando l'attività utile viene preservata |
| `BRAINSTEM_STATE_EXITED_EMERGENCY` | Uscita dallo stato emergency |

## 8. Test Plan

| Test | Description |
|---|---|
| compute_cognitive_vitality_score with benchmark metrics | Formula completa |
| compute_cognitive_vitality_score proxy | Fallback con tick-level metrics |
| compute_autonomic_risk_score | Range e sensibilità |
| compute_balance_pressure | Coerenza aritmetica |
| evaluate_state stable / watchful / corrective / protective / emergency | State selection per pressure |
| cognitive preservation caps at corrective | Regola di preservazione |
| absolute emergency overrides preservation | Override fisici |
| emergency hysteresis requires consecutive ticks | Isteresi ingresso |
| emergency exit after pressure drops | Isteresi uscita |
| soft modulation values | Confronto T35 vs T36 |
| cognitive preservation event logged | Evento memory |
| suppression softened event logged | Evento memory |
| benchmark T36 metrics present | Esistenza campi |
| orchestrator integration | Funzionamento end-to-end |

## 9. Acceptance Criteria

- [x] `BrainstemFunctionalController` implementa scoring cognitivo/autonomico
- [x] State selection basata su `balance_pressure`
- [x] Modulazioni soft rispetto a T35
- [x] Emergency hysteresis operativo
- [x] Cognitive preservation rule operativa
- [x] 12 nuovi campi benchmark esposti
- [x] 5 nuovi eventi MorphologicalMemory
- [x] Test suite passa (534 passed)
- [x] Coverage >= 85% (88.72%)
- [x] Commit e tag

## 10. Next Step

**T36B — Brainstem Balance Audit**

Verificare se il brainstem mantiene il guadagno di Φ senza distruggere il cognitive score.
Metrica decisiva: `net_gain_vs_t34b >= 0`

## 11. References

- T35B audit report: `reports/brainstem/t35b_brainstem_audit_20260516_204821.md`
- `speace_core/cellular_brain/regions/brainstem_controller.py`
- `tests/regions/test_brainstem_controller.py`

---
*Generated by T36 Cognitive/Autonomic Balance Tuning*
