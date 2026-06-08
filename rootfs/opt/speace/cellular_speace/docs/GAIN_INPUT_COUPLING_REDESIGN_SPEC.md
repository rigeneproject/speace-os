# T39 — Gain Input Coupling Redesign

**Version:** v0.3.23-t39-gain-input-coupling-redesign  
**Date:** 2026-05-16  
**Status:** Implemented  
**Depends on:** T38 (Gain Sensitivity Tuning)

## 1. Objective

Rendere il gain controller causalmente efficace accoppiando il vettore di gain direttamente nel flusso decisionale del brainstem: input scoring, soglie dinamiche, protective escape e traccia di output coupling.

## 2. Problem Statement

T38B Audit Results:
- reward_v2 positivo
- cross-profile divergence 0.0905
- net_gain stagnante (~0)
- brainstem rimane in protective indipendentemente dal gain profile

Diagnosi: il gain controller e intelligente ma disaccoppiato. Il brainstem non riceve il vettore di gain *prima* di selezionare lo stato, quindi i gain non influenzano causalmente le decisioni.

## 3. Architecture

### 3.1 Components

| File | Role |
|---|---|
| `speace_core/cellular_brain/regions/brainstem_controller.py` | Brainstem con T39 coupling |
| `speace_core/cellular_brain/regions/brainstem_gain_controller.py` | Gain controller invariato (T38) |
| `speace_core/orchestrator.py` | Ordine di valutazione: gain -> brainstem |

### 3.2 Classes

| Class | Role |
|---|---|
| `BrainstemCouplingTrace` | Traccia T39 del coupling input->output |
| `BrainstemFunctionalController` | Accetta `gain_vector` in `apply()` |

## 4. Four Main Changes

### 4.1 Gain-Coupled Input Scoring

```python
adjusted_vitality = min(1.0, vitality * cognitive_preservation_gain)
adjusted_risk = min(1.0, risk * emergency_gain)
```

### 4.2 Dynamic State Thresholds

```python
protective = base + 0.10 * (cog_pres - 1.0)
emergency = base + 0.10 * (1.0 - emg)
corrective = base + 0.05 * (cog_pres - emg)
```

### 4.3 Protective Escape

Dopo 3+ tick consecutivi in protective, se:
- adjusted_vitality > 0.45
- adjusted_risk < 0.65
- energy >= 0.15

→ forza stato CORRECTIVE.

### 4.4 Output Coupling Trace

`BrainstemCouplingTrace` registra:
- raw vs adjusted vitality/risk/pressure
- gain_vector applicato
- raw vs final modulations
- coupling_delta
- protective_escape_applied

## 5. Orchestrator Order

```
Tick:
1. Gain controller evaluates -> gain_vector
2. Brainstem controller.apply(metrics, memory, gain_vector)
3. Brainstem decide() usa gain_vector per input scoring e soglie
4. Modulazioni finali composte con gain
```

## 6. Metrics

| Metric | Source |
|---|---|
| `gain_input_coupling_strength` | BenchmarkMetrics T39 |
| `adjusted_cognitive_vitality_score` | BenchmarkMetrics T39 |
| `adjusted_autonomic_risk_score` | BenchmarkMetrics T39 |
| `adjusted_balance_pressure` | BenchmarkMetrics T39 |
| `protective_escape_count` | BenchmarkMetrics T39 |
| `coupling_delta_mean` | BenchmarkMetrics T39 |
| `suppression_cost_after_coupling` | BenchmarkMetrics T39 |
| `brainstem_state_transition_count` | BenchmarkMetrics T39 |

## 7. Events

- `BRAINSTEM_GAIN_INPUT_COUPLED`
- `BRAINSTEM_STATE_THRESHOLD_ADJUSTED`
- `BRAINSTEM_PROTECTIVE_ESCAPE`
- `BRAINSTEM_OUTPUT_COUPLED`
- `BRAINSTEM_COUPLING_TRACE_RECORDED`
- `BRAINSTEM_SUPPRESSION_RELEASED`

## 8. Acceptance Criteria

| Criterion | Threshold |
|---|---|
| coupling_strength > 0 | verificato |
| adjusted_vitality != raw_vitality | verificato |
| adjusted_risk != raw_risk | verificato |
| state transitions > 0 | verificato |
| tests pass | >= 85% coverage |

## 9. Audit Verdicts

| Verdict | Condition | Next Step |
|---|---|---|
| COUPLING_EFFECTIVE | net_gain >= 0.02, coupling_strength > 0, escape_count > 0 | T40 |
| COUPLING_NEUTRAL | abs(net_gain) <= 0.005, coupling_strength > 0 | T39B v2 |
| COUPLING_REGRESSION | cog_delta < -0.05 or phi_delta < -0.05 | T39 Fix |

## 10. Commit Tag

`v0.3.23-t39-gain-input-coupling-redesign`
