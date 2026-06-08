# InhibitoryNeuron & Snooze v0.3 — Specification

## Overview

T14 introduces neurocellular stabilization: functional inhibitory neurons, consistent refractory periods, dynamic snooze for hyperactive cells, runaway activation damping, and activation decay. After T13's STDP made the network causally plastic, T14 prevents runaway activation loops and stabilizes learning.

Biologically: plasticity without inhibition = unstable learning. Plasticity + inhibition = stable, useful learning.

## Architecture

### New module

- `speace_core/cellular_brain/regulation/inhibition_engine.py`

### Modified modules

- `speace_core/cellular_brain/cells/digital_neuron.py` — added `inhibitory`, `inhibition_strength`, `max_consecutive_fires`
- `speace_core/cellular_brain/execution/burst_engine.py` — inhibitory propagation logic
- `speace_core/cellular_brain/regulation/cell_differentiation_engine.py` — inhibitory phenotype
- `speace_core/orchestrator.py` — `inhibition_enabled` flag, engine initialization, tick integration
- `speace_core/cellular_brain/benchmark/neurofunctional_benchmark.py` — `inhibition_enabled` parameter

## InhibitionEngine

### Constructor

- `max_consecutive_fires: int = 5`
- `default_snooze_duration: int = 3`
- `activation_decay: float = 0.10`
- `runaway_activation_threshold: float = 1.5`

### Methods

- `stabilize_after_burst(circuit, burst_result=None, memory=None)` — composite pass:
  1. `update_refractory_states(circuit)` — decrement refractory counters
  2. `update_snooze_states(circuit)` — decrement snooze counters
  3. `apply_decay(circuit)` — decay activation of non-firing neurons
  4. `detect_and_handle_runaway(circuit)` — dampen neurons above threshold
  5. `apply_dynamic_snooze(circuit, memory)` — snooze hyperactive neurons

- `apply_dynamic_snooze(circuit, memory) -> List[str]`
  - For each neuron with `consecutive_fires >= max_consecutive_fires`:
    - Reset `snooze_counter = default_snooze_duration`
    - Reset `activation = 0.0`
    - Reset `consecutive_fires = 0`
    - Record `NEURON_SNOOZED` in memory with metadata

- `detect_and_handle_runaway(circuit) -> List[str]`
  - For each neuron with `activation >= runaway_activation_threshold`:
    - Subtract 0.5 from activation

- `apply_decay(circuit)`
  - Multiply activation by `(1.0 - activation_decay)` for all neurons
  - Clamp to 0 if below 1e-6

- `apply_snooze(neuron, reason)` — manual snooze helper

- `is_inhibitory(neuron)` — checks `inhibitory` flag or `neuron_role == "inhibitory"`

- `apply_inhibitory_signal(source, target, strength)` — direct inhibitory signal

## Inhibitory propagation in BurstEngine

When a neuron fires in `process_burst` or `propagate_fire`:

```python
if neuron.inhibitory:
    target.activation -= abs(delta) * neuron.inhibition_strength
else:
    target.activation += delta
target.activation = max(0.0, target.activation)
```

Inhibitory neurons subtract activation from their targets. This prevents runaway excitation.

## Inhibitory phenotype from CellDifferentiationEngine

When `new_type == "inhibitory_neuron"`:
- `neuron.inhibitory = True`
- `neuron.neuron_role = "inhibitory"`
- `neuron.inhibition_strength = 1.0`
- `neuron.refractory_period = 2` (if previously 0)

## Orchestrator integration

- New field: `_inhibition: InhibitionEngine`
- New field: `inhibition_enabled: bool = True`
- Initialized in `model_post_init`
- In `_tick()`, after burst cycle and STDP:
  ```python
  if self.inhibition_enabled:
      self._inhibition.stabilize_after_burst(self.circuit, last_result, self._memory)
  ```
- Not called in global tick mode (neuron.tick() already handles snooze/refractory).

## Benchmark integration

- `NeuroFunctionalBenchmark.run_case(...)` gains `inhibition_enabled: bool = True`
- Enables A/B comparison:
  - burst without STDP
  - burst with STDP
  - burst with STDP + inhibition

## Test coverage

1. Inhibitory neuron decreases target activation
2. Excitatory neuron increases target activation
3. Refractory neuron is skipped by fire queue
4. Refractory counter decays over cycles
5. Neuron with too many consecutive fires enters snooze
6. Snoozed neuron is skipped by fire queue
7. `NEURON_SNOOZED` event registered in memory
8. Activation decay reduces non-firing neuron activation
9. Runaway detection dampens high activation
10. CellDifferentiationEngine produces functional inhibitory phenotype
11. Orchestrator burst mode works with `inhibition_enabled=True`
12. Benchmark runs with burst + STDP + inhibition

## Acceptance criteria

- [x] `InhibitionEngine` exists and is importable.
- [x] Inhibitory neurons reduce target activation during burst propagation.
- [x] Refractory counters are respected and decay correctly.
- [x] Snooze is applied to hyperactive neurons.
- [x] Snoozed neurons do not fire while snoozed.
- [x] `NEURON_SNOOZED` events recorded in `MorphologicalMemory`.
- [x] `CellDifferentiationEngine` produces functional inhibitory neurons.
- [x] Orchestrator supports `inhibition_enabled=True/False`.
- [x] `NeuroFunctionalBenchmark` can run with inhibition enabled.
- [x] All tests pass; coverage stays ≥ 85%.
- [x] `docs/INHIBITORY_NEURON_SNOOZE_SPEC.md` created.

## Post-T14 next step

T18 — EnergyControlAgent (metabolic regulation after stabilization).
