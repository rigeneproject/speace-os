# T40 — Long-Horizon Neurocellular Adaptation Audit

**Version:** v0.3.24-t40-long-horizon-adaptation-audit  
**Date:** 2026-05-16  
**Status:** Implemented  
**Depends on:** T39 (Gain Input Coupling Redesign)

## 1. Objective

Misurare gli effetti cumulativi del coupling T39 su orizzonti temporali piu lunghi per verificare se il canale causale aperto da T39 produce risultati funzionali nel tempo.

## 2. Problem Statement

T39B Audit Results (5 tick):
- coupling mechanics active
- coupling_strength 0.61-0.73
- adjusted scores divergenti
- net_gain non differenziato
- verdict: COUPLING_NEUTRAL

Diagnosi: il coupling e attivo ma la finestra e troppo breve. Serve un audit longitudinale.

## 3. Architecture

### 3.1 Component

```
speace_core/cellular_brain/analysis/long_horizon_adaptation_audit.py
```

### 3.2 Classes

| Class | Role |
|---|---|
| `LongHorizonAdaptationAuditor` | Esegue audit multi-orizzonte |
| `LongHorizonTrajectoryPoint` | Snapshot a un orizzonte |
| `LongHorizonProfileResult` | Risultati per profilo (slopes, entropy, recovery) |
| `LongHorizonAuditResult` | Risultato top-level con verdict |

### 3.3 Profiles

| ID | Name | Deep | Routing | Stability | Brainstem | Gain |
|---|---|---|---|---|---|---|
| lh0 | baseline_four_region | no | no | no | no | no |
| lh1 | deep_regions_static | yes | no | no | no | no |
| lh2 | deep_regions_routing_stability | yes | yes | yes | no | no |
| lh3 | brainstem_no_gain | yes | yes | yes | yes | no |
| lh4 | brainstem_gain_t38 | yes | yes | yes | yes | balanced |
| lh5 | brainstem_gain_coupling_t39 | yes | yes | yes | yes | cognitive_preserving |
| lh6 | full_organism_gain_coupled | yes | yes | yes | yes | cognitive_preserving + T34 |

### 3.4 Horizons

- 5 ticks
- 25 ticks
- 50 ticks
- 100 ticks
- 250 ticks

## 4. Methodology

### Phase A: Benchmark per orizzonte

Per ogni profilo e orizzonte:
- costruisce orchestrator deterministico (stesso seed)
- applica profilo
- esegue `NeuroFunctionalBenchmark.run_case(n_ticks=horizon)`
- salva trajectory point

### Phase B: Tick-by-tick brainstem tracking

- 250 tick con `orch.run_ticks(1)`
- traccia stato brainstem per tick
- calcola recovery_latency, stabilization_tick, state_entropy

## 5. Metrics

### 5.1 Slopes (regressione lineare)

| Slope | Calcolo |
|---|---|
| net_gain_slope | su trajectory points vs baseline |
| cognitive_score_slope | regressione lineare cognitive_score / tick |
| phi_slope | regressione lineare phi / tick |
| energy_slope | regressione lineare energy_efficiency / tick |
| suppression_cost_slope | regressione lineare suppression_cost / tick |

### 5.2 Temporal Recovery

| Metric | Definizione |
|---|---|
| recovery_latency_ticks | primo tick di uscita da emergency/protective |
| stabilization_tick | primo tick da cui non si torna mai in emergency/protective |
| protective_state_ratio_over_time | % protective su 250 tick |
| corrective_state_ratio_over_time | % corrective su 250 tick |
| emergency_state_ratio_over_time | % emergency su 250 tick |
| state_entropy | entropia di Shannon sulla distribuzione stati |

### 5.3 Composite Score

```
long_horizon_recovery_score =
  0.25 * cognitive_score_slope
+ 0.25 * phi_slope
+ 0.20 * energy_slope
+ 0.15 * max(0, -suppression_cost_slope)
+ 0.15 * state_entropy
```

## 6. Verdicts

| Verdict | Condition |
|---|---|
| LONG_HORIZON_RECOVERY_VALIDATED | recovery_score > 0.01 e T39 attivo |
| PARTIAL_TEMPORAL_RECOVERY | recovery_score > 0.01 ma T39 non dominante |
| SHORT_RUN_ONLY_EFFECT | slope positivo o latency/recovery ma score <= 0 |
| PERSISTENT_NEUTRALITY | entropy > 0.3 ma score <= 0 |
| LONG_HORIZON_REGRESSION | cognitive regression vs baseline |
| INSTABILITY_ACCUMULATION | default |

## 7. Acceptance Criteria

- tutti i test passano
- coverage >= 85%
- docs/LONG_HORIZON_ADAPTATION_AUDIT_SPEC.md creato
- reports/long_horizon/.gitkeep creato
- commit + tag v0.3.24-t40

## 8. Commit Tag

`v0.3.24-t40-long-horizon-adaptation-audit`
