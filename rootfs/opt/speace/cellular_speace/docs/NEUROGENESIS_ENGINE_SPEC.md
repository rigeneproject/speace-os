# T8 — NeurogenesisEngine v0.2 Specification

## Vision

T8 transforms SPEACE from a system with fixed topology into one that grows new neurons in response to learning stress. With T7 (MorphologicalMemory) in place, neurogenesis is no longer an opaque structural mutation: it is a recorded evolutionary event, complete with pre-conditions, post-conditions, and historical trace.

> SPEACE non aggiunge solo neuroni: aggiunge storia strutturale.

---

## Goals

1. **Conditional Generation**: Create `DigitalNeuron` cells only when the system exhibits sustained negative feedback, low coherence (Φ), and sufficient metabolic energy.
2. **Circuit Integration**: Seamlessly wire new neurons into `NeuralCircuit.hidden_neurons` with bidirectional synaptic connectivity.
3. **Morphological Memory**: Record every `NEURON_CREATED` event in `MorphologicalMemory` with full metadata (reason, Φ_before, synapse count).
4. **Safety Limits**: Enforce a hard cap on total neuron count to prevent unbounded growth.
5. **Orchestrator Integration**: Expose `run_neurogenesis()` in `CellularBrainOrchestrator`, tied to the existing feedback loop.
6. **Test Coverage**: Unit tests for decision logic and generation; integration tests for orchestrator-triggered neurogenesis.

---

## Data Model

### NeurogenesisResult

```python
class NeurogenesisResult(BaseModel):
    created: bool
    neuron_id: Optional[str] = None
    neuron_type: Optional[str] = None
    reason: str = ""
    phi_before: Optional[float] = None
    metadata: dict = Field(default_factory=dict)
```

### NeurogenesisEngine

```python
class NeurogenesisEngine:
    def __init__(
        self,
        error_threshold: int = 3,
        phi_threshold: float = 0.55,
        min_energy: float = 0.25,
        max_new_neurons_per_cycle: int = 3,
    )
```

| Parameter | Default | Description |
|---|---|---|
| `error_threshold` | 3 | Minimum consecutive negative feedback scores to trigger generation |
| `phi_threshold` | 0.55 | Maximum coherence Φ allowed for generation (low coherence = high disorder) |
| `min_energy` | 0.25 | Minimum mean system energy required |
| `max_new_neurons_per_cycle` | 3 | Not yet enforced per-cycle; total cap is 1000 neurons |

---

## Decision Logic

```python
def should_generate(self, error_count: int, phi: float, energy: float) -> bool:
    return (
        error_count >= self.error_threshold
        and phi <= self.phi_threshold
        and energy >= self.min_energy
    )
```

All three conditions must be met simultaneously. This prevents growth during:
- High coherence (system already ordered)
- Low energy (metabolic exhaustion)
- Isolated errors (noise, not trend)

---

## Generation Protocol

### Step 1: Validate Limit

If `total_neurons >= 1000`, return `NeurogenesisResult(created=False, reason="max_neuron_limit_reached")`.

### Step 2: Create DigitalNeuron

```python
neuron_id = f"ng_{uuid4()[:8]}"
new_neuron = DigitalNeuron(
    cell_id=neuron_id,
    role="digital_neuron",
    threshold=0.5,
    plasticity_rate=0.05,
)
```

### Step 3: Integrate into Circuit

Append to `circuit.hidden_neurons`.

Create **2 incoming synapses** from random existing neurons:
- `weight=0.3`, `trust=0.3`

Create **2 outgoing synapses** to random existing neurons:
- `weight=0.3`, `trust=0.3`

### Step 4: Record Event

If `circuit.memory` is present:
```python
circuit.memory.create_event(
    event_type=MorphologyEventType.NEURON_CREATED,
    source_id="neurogenesis_engine",
    target_id=neuron_id,
    phi_before=phi_before,
    metadata={
        "reason": reason,
        "neuron_type": "digital_neuron",
        "initial_synapses": 4,
    },
)
```

### Step 5: Return Result

Return `NeurogenesisResult(created=True, ...)` with all fields populated.

---

## Orchestrator Integration

`CellularBrainOrchestrator` gains:

- `negative_feedback_count: int = 0`
- `_neurogenesis: NeurogenesisEngine` initialized in `model_post_init()`
- `feedback(score: float)` increments `negative_feedback_count` on `score < 0`
- `run_neurogenesis()` queries `latest_metrics`, evaluates `should_generate()`, and calls `generate_neuron()` if conditions are met; resets `negative_feedback_count` to 0 after generation

---

## Test Requirements

### Unit Tests (`tests/regulation/test_neurogenesis_engine.py`)

- `test_should_generate_false_low_error` — error < threshold → False
- `test_should_generate_false_low_energy` — energy < min → False
- `test_should_generate_false_high_phi` — phi > threshold → False
- `test_should_generate_true` — all conditions met → True
- `test_generate_neuron_increases_count` — total neurons +1
- `test_generate_neuron_creates_synapses` — synapse count increases
- `test_generate_neuron_records_event` — `MorphologicalMemory` receives `NEURON_CREATED`
- `test_generate_neuron_respects_max_limit` — at 1000 neurons, creation is blocked

### Integration Tests (`tests/memory/test_neurogenesis_integration.py`)

- `test_orchestrator_triggers_neurogenesis` — 10 negative feedback ticks + `run_neurogenesis()` → at least one `NEURON_CREATED` event
- `test_orchestrator_neurogenesis_increases_neurons` — total neuron count strictly increases after generation

---

## Files Created / Modified

| File | Action | Description |
|---|---|---|
| `speace_core/cellular_brain/regulation/neurogenesis_engine.py` | Created | Engine implementation |
| `speace_core/orchestrator.py` | Modified | Adds `_neurogenesis`, `negative_feedback_count`, `run_neurogenesis()` |
| `tests/regulation/test_neurogenesis_engine.py` | Created | Unit tests |
| `tests/memory/test_neurogenesis_integration.py` | Created | Integration tests |
| `docs/NEUROGENESIS_ENGINE_SPEC.md` | Created | This document |

---

## Validation Results

- **Tests**: 49/49 passed
- **Coverage**: 86.39% (target: ≥85%)
- **New module coverage**: `neurogenesis_engine.py` 100%

---

## Closure Criteria

- [x] `NeurogenesisEngine` exists and decides when to generate neurons based on error, Φ, and energy
- [x] Creates valid `DigitalNeuron` instances
- [x] Integrates new neurons into `NeuralCircuit`
- [x] Creates initial synapses for new neurons (2 in, 2 out)
- [x] Records `NEURON_CREATED` in `MorphologicalMemory`
- [x] Unit tests and integration tests present and passing
- [x] Documentation updated
- [x] pytest passes (49/49)
- [x] Coverage ≥ 85% (86.39%)

---

## Next Task

**T9 — ApoptosisEngine v0.2**: The structural counterpart to neurogenesis. Removes under-utilized neurons when the system is over-provisioned or metabolically stressed, maintaining homeostatic balance.
