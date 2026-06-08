# T9 — ApoptosisEngine v0.2 Specification

## Vision

After T7 (MorphologicalMemory) and T8 (NeurogenesisEngine), SPEACE can remember its own shape and grow new neurons. Without a complementary removal mechanism, the circuit would grow cumulatively and unboundedly. T9 introduces **controlled cellular selection**: a multi-level system that silences, prunes, or eliminates cells based on metabolic cost, functional utility, and network stability.

> SPEACE non cresce all'infinito: seleziona, stabilizza, elimina ciò che non serve.

The biological cycle becomes:
**growth → verification → stabilization → pruning → structural selection**

---

## Goals

1. **Snooze**: Temporarily deactivate hyperactive or unstable neurons to prevent runaway firing loops.
2. **Synaptic Pruning**: Remove weak, unused, or energetically inefficient synapses below a threshold.
3. **Apoptosis**: Controlled removal of hidden neurons that are isolated, low-utility, high-energy, or negatively impacting coherence Φ.
4. **Critical Cell Protection**: Never remove input neurons, output neurons, regulatory neurons, or neurons explicitly marked `is_critical`.
5. **Morphological Memory**: Record every `NEURON_SNOOZED`, `SYNAPSE_PRUNED`, and `NEURON_APOPTOSIS` event.
6. **Orchestrator Integration**: Expose `run_apoptosis()` in `CellularBrainOrchestrator`, triggered on demand or tied to homeostatic cycles.

---

## Three Distinct Levels

### Level 1 — Snooze

**Trigger**: `consecutive_fires >= snooze_fire_threshold` (default: 5)

**Action**: Set `snooze_counter = snooze_duration` (default: 3 ticks). During snooze, the neuron decays its activation but does not fire or propagate signals.

**Purpose**: Prevents runaway oscillations and local instability without destroying structure.

### Level 2 — Synaptic Pruning

**Trigger**: Synapse with `weight < synapse_prune_threshold` or `trust < synapse_prune_threshold` (default: 0.05).

**Action**: Mark synapse state as `"pruned"` and record event.

**Purpose**: Reduces metabolic load by eliminating informationally irrelevant connections.

### Level 3 — Apoptosis

**Trigger**: `apoptosis_risk >= apoptosis_risk_threshold` (default: 0.75)

**Risk Formula**:
```
if utility_score < low_utility_threshold:    risk += 0.30
if energy > high_energy_threshold:            risk += 0.25
if connectivity <= low_connectivity_threshold: risk += 0.25
if phi < phi_threshold:                       risk += 0.20
```

**Action**: Remove neuron from `hidden_neurons`, remove all attached incoming/outgoing synapses, clean up `targets` lists on source neurons, record event.

**Guard**: Protected roles (`input`, `output`, `regulatory`) and `is_critical=True` are always skipped.

---

## Data Model

### ApoptosisResult

```python
class ApoptosisResult(BaseModel):
    snoozed: List[str] = []           # cell_ids snoozed
    pruned_synapses: List[str] = []   # cell_ids of synapses pruned
    apoptosed: List[str] = []         # cell_ids removed
    reason: str = ""
```

### ApoptosisEngine

```python
class ApoptosisEngine:
    def __init__(
        self,
        low_utility_threshold: float = 0.15,
        high_energy_threshold: float = 0.85,
        low_connectivity_threshold: int = 1,
        apoptosis_risk_threshold: float = 0.75,
        max_apoptosis_per_cycle: int = 3,
        snooze_fire_threshold: int = 5,
        snooze_duration: int = 3,
        phi_threshold: float = 0.55,
        synapse_prune_threshold: float = 0.05,
    )
```

| Parameter | Default | Description |
|---|---|---|
| `low_utility_threshold` | 0.15 | Minimum utility score to avoid apoptosis risk component |
| `high_energy_threshold` | 0.85 | Energy level above which risk increases |
| `low_connectivity_threshold` | 1 | Max connections considered "isolated" |
| `apoptosis_risk_threshold` | 0.75 | Minimum risk to trigger removal |
| `max_apoptosis_per_cycle` | 3 | Max neurons removed per evaluation cycle |
| `snooze_fire_threshold` | 5 | Consecutive fires triggering snooze |
| `snooze_duration` | 3 | Ticks a snoozed neuron stays silent |
| `phi_threshold` | 0.55 | Coherence threshold below which risk increases |
| `synapse_prune_threshold` | 0.05 | Weight/trust floor for synaptic pruning |

---

## DigitalNeuron Extensions

New fields added to `DigitalNeuron` for T9:

| Field | Default | Description |
|---|---|---|
| `neuron_role` | `"excitatory"` | Functional role: excitatory, inhibitory, memory, input, output, regulatory |
| `is_critical` | `False` | If `True`, protected from apoptosis |
| `snooze_counter` | `0` | Remaining snooze ticks |
| `refractory_counter` | `0` | Remaining refractory ticks |
| `refractory_period` | `0` | Post-firing cooldown (default 0 preserves v0.1 behavior) |
| `consecutive_fires` | `0` | Counter incremented when firing, reset otherwise |
| `last_fired_tick` | `None` | Last tick the neuron fired |
| `utility_score` | `0.0` | Cached utility computed by the engine |
| `apoptosis_risk` | `0.0` | Last computed risk |

### Tick Behavior Update

```python
async def tick(self) -> List[DigitalSignal]:
    if self.snooze_counter > 0:
        self.snooze_counter -= 1
        self.activation *= 0.5
        return []
    if self.refractory_counter > 0:
        self.refractory_counter -= 1
        self.activation *= 0.5
        return []
    # ... existing firing logic ...
    if fired:
        self.consecutive_fires += 1
        if self.refractory_period > 0:
            self.refractory_counter = self.refractory_period
    else:
        self.consecutive_fires = 0
    return signals
```

---

## Execution Protocol (`ApoptosisEngine.run()`)

### Phase 1 — Utility Evaluation & Snooze

Iterate all non-protected neurons:
- Compute `utility_score` from connectivity, recent firing, and consecutive fires.
- If `consecutive_fires >= snooze_fire_threshold`, apply snooze and record `NEURON_SNOOZED`.

### Phase 2 — Weak Synapse Pruning

Find all non-pruned synapses with `weight < threshold` or `trust < threshold`:
- Mark state `"pruned"`.
- Record `SYNAPSE_PRUNED` with reason `"weak_synapse_pruning"`.

### Phase 3 — Apoptosis Risk Evaluation & Removal

For each non-protected neuron:
- Compute `apoptosis_risk` using the formula above.
- If `risk >= threshold`, add to candidate list.
- Sort candidates by highest risk.
- Remove up to `max_apoptosis_per_cycle` candidates:
  - Remove neuron from `hidden_neurons`.
  - Remove all synapses connected to it.
  - Clean up `targets` lists on remaining source neurons.
  - Record `NEURON_APOPTOSIS` with full metadata.

---

## Orchestrator Integration

`CellularBrainOrchestrator` gains:

- `_apoptosis: ApoptosisEngine` initialized in `model_post_init()`.
- `run_apoptosis()` queries `latest_metrics` and calls `_apoptosis.run(self.circuit, metrics)`.

---

## Test Requirements

### Unit Tests (`tests/regulation/test_apoptosis_engine.py`)

- `test_engine_does_not_remove_critical_neurons` — `is_critical=True` blocks removal.
- `test_engine_does_not_remove_input_or_output_neurons` — input/output roles protected.
- `test_engine_removes_isolated_useless_neuron` — isolated hidden neuron with high risk is removed.
- `test_engine_removes_connected_synapses_on_apoptosis` — synapses attached to removed neuron are cleaned up.
- `test_engine_records_apoptosis_event` — `MorphologicalMemory` receives `NEURON_APOPTOSIS`.
- `test_engine_applies_snooze_to_hyperactive_neuron` — consecutive fires trigger snooze.
- `test_engine_records_snooze_event` — `MorphologicalMemory` receives `NEURON_SNOOZED`.
- `test_engine_prunes_weak_synapses` — low weight/trust synapses are pruned.
- `test_neuron_snooze_blocks_firing` — snoozed neuron returns empty signals.
- `test_neuron_refractory_blocks_firing` — refractory neuron returns empty signals.

### Integration Tests (`tests/memory/test_apoptosis_integration.py`)

- `test_orchestrator_apoptosis_removes_hidden_neuron` — orchestrator-level apoptosis triggers.
- `test_orchestrator_apoptosis_does_not_remove_input_output` — input/output count preserved after `run_apoptosis()`.

---

## Files Created / Modified

| File | Action | Description |
|---|---|---|
| `speace_core/cellular_brain/regulation/apoptosis_engine.py` | Created | Engine implementation |
| `speace_core/cellular_brain/cells/digital_neuron.py` | Modified | Adds snooze, refractory, utility, risk, role, critical fields |
| `speace_core/cellular_brain/memory/morphology_events.py` | Modified | Adds `NEURON_SNOOZED` event type |
| `speace_core/orchestrator.py` | Modified | Adds `_apoptosis`, `run_apoptosis()` |
| `tests/regulation/test_apoptosis_engine.py` | Created | Unit tests (10) |
| `tests/memory/test_apoptosis_integration.py` | Created | Integration tests (2) |
| `docs/APOPTOSIS_ENGINE_SPEC.md` | Created | This document |

---

## Validation Results

- **Tests**: 61/61 passed
- **Coverage**: 87.51% (target: ≥85%)
- **New module coverage**: `apoptosis_engine.py` 92%

---

## Closure Criteria

- [x] `ApoptosisEngine` exists and evaluates neurons based on utility, energy, connectivity, and Φ
- [x] Protects critical / input / output / regulatory neurons
- [x] Applies temporary snooze to hyperactive neurons
- [x] Removes hidden neurons with high apoptosis risk
- [x] Removes attached synapses when a neuron is eliminated
- [x] Prunes weak synapses below threshold
- [x] Records `NEURON_APOPTOSIS`, `NEURON_SNOOZED`, and `SYNAPSE_PRUNED` in `MorphologicalMemory`
- [x] Unit tests and integration tests present and passing
- [x] Documentation updated
- [x] pytest passes (61/61)
- [x] Coverage ≥ 85% (87.51%)

---

## Next Task

**T10 — CellDifferentiationEngine v0.2**: With T7, T8, and T9 complete, SPEACE now has the full minimal cellular lifecycle:

- T7 MorphologicalMemory → remembers shape
- T8 NeurogenesisEngine → creates new cells
- T9 ApoptosisEngine → removes non-functional cells
- T10 CellDifferentiationEngine → specializes cells by role, region, and DNA

This is the first true foundation of an evolving digital cellular brain.
