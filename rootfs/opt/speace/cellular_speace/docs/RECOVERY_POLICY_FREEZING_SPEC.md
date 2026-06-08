# T41 — Long-Horizon Recovery Consolidation & Policy Freezing

**Version:** v0.3.25-t41-recovery-policy-freezing  
**Date:** 2026-05-16  
**Status:** Implemented  
**Depends on:** T40 (Long-Horizon Neurocellular Adaptation Audit)

## 1. Objective

Consolidare il miglior profilo T40 in una RecoveryPolicy canonica e introdurre un RegressionGuard per impedire che task futuri degradino il full organism.

## 2. Problem Statement

T40 Audit Verdict: LONG_HORIZON_RECOVERY_VALIDATED.

Il coupling T39 produce effetti cumulativi positivi. Ora serve:
- selezionare il profilo migliore
- congelarne i parametri
- proteggere contro regressioni future

## 3. Architecture

### 3.1 Components

| File | Role |
|---|---|
| `speace_core/cellular_brain/analysis/recovery_policy_selector.py` | Seleziona e congela policy |
| `speace_core/cellular_brain/analysis/regression_guard.py` | Valuta regressioni |
| `reports/recovery_policy/recovery_policy_v0_3_25.json` | Policy congelata T41 |

### 3.2 Models

| Model | Role |
|---|---|
| `RecoveryPolicy` | Configurazione canonica congelata |
| `RecoveryPolicySelectionResult` | Risultato della selezione |
| `FrozenFlags` | Switch booleani canonici |
| `FrozenGainProfile` | Gain profile canonico |
| `FrozenBrainstemThresholds` | Soglie brainstem canoniche |
| `FrozenEnergyProfile` | Profilo energetico canonico |
| `RegressionGuardThresholds` | Soglie anti-regressione |
| `RegressionGuardResult` | Risultato valutazione regressione |

## 4. Policy Selection Logic

### 4.1 Score Formula

```
policy_score =
  long_horizon_recovery_score
+ max(0, net_gain_slope) * 100
+ max(0, -suppression_cost_slope) * 100
+ state_entropy * 0.02
- emergency_state_ratio_over_time * 0.3
```

Profili con `passed=False` ottengono -999.

### 4.2 Selection Process

1. Calcola policy_score per ogni profilo valido
2. Seleziona il profilo con score massimo
3. Estrae flags, gain, soglie dal profilo
4. Genera regression guard thresholds con 10% margini di sicurezza

## 5. Regression Guard

### 5.1 Thresholds

| Metric | Min | Max |
|---|---|---|
| cognitive_score | min | - |
| coherence_phi | min | - |
| energy_efficiency | min | - |
| suppression_cost | - | max |
| long_horizon_recovery_score | min | - |
| emergency_state_ratio | - | max |
| state_entropy | min | - |

### 5.2 Verdicts

| Verdict | Condition |
|---|---|
| POLICY_STABLE | Nessuna violazione |
| POLICY_MINOR_REGRESSION | Solo recovery_score / entropy / emergency |
| POLICY_MAJOR_REGRESSION | Violazione cognitive / phi / energy / suppression |
| POLICY_UNSAFE | phi < 0.05 o energy < 0.05 |

## 6. Canonical Policy (T40->T41)

| Field | Value |
|---|---|
| selected_profile | brainstem_no_gain |
| selected_profile_id | lh3 |
| long_horizon_recovery_score | 0.2774 |
| cognitive_score | 0.3791 |
| coherence_phi | 0.3422 |
| energy_efficiency | 0.2097 |

## 7. Acceptance Criteria

- RecoveryPolicySelector implementato e testato
- RegressionGuard implementato e testato
- Policy JSON/Markdown generati
- docs/RECOVERY_POLICY_FREEZING_SPEC.md creato
- reports/recovery_policy/.gitkeep creato
- tutti i test passano
- coverage >= 85%
- commit + tag v0.3.25

## 8. Commit Tag

`v0.3.25-t41-recovery-policy-freezing`
