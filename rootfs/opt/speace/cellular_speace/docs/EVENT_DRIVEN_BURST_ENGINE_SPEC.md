# EventDrivenBurstEngine v0.3 — Specification

## Overview

T12 introduces sparse, event-driven burst execution to SPEACE. Instead of visiting every neuron on every global tick, the burst engine processes only neurons whose activation exceeds their threshold. This is the architectural bridge from "simulated brain" to "scalable neurocellular engine."

The global tick is preserved; an `execution_mode` switch on the orchestrator allows A/B comparison via T11 `NeuroFunctionalBenchmark`.

## Why now

- FEAGI principle: simulate what is active, not the entire network.
- Lower computational cost per cycle.
- Biological plausibility: real brains fire sparsely.
- Foundation for T13 STDP (causal burst-aware plasticity).
- Foundation for T14 inhibition and T18 energy control.

## Architecture

### New package

- `speace_core/cellular_brain/execution/__init__.py`
- `speace_core/cellular_brain/execution/burst_engine.py`

### Models

**FireCandidate**
- `neuron_id: str`
- `activation: float`
- `threshold: float`
- `priority: float = activation - threshold`
- `source: Optional[str]`
- `created_at_burst: int`

**BurstResult**
- `burst_id: int`
- `fired_neurons: List[str]`
- `propagated_synapses: int`
- `skipped_refractory: int`
- `skipped_snoozed: int`
- `mean_activation: float`
- `fire_queue_size: int`

### Engine

**EventDrivenBurstEngine**
- `__init__(activation_threshold=0.5, max_burst_size=128, max_bursts_per_tick=10, min_energy=0.1)`
- `collect_candidates(circuit) -> List[FireCandidate]`
  - Scans all neurons.
  - Candidate conditions:
    - `activation >= activation_threshold`
    - `snooze_counter == 0`
    - `refractory_counter == 0`
    - `energy > min_energy`
  - Sorted by `priority = activation - threshold` descending.
- `process_burst(circuit, burst_id) -> BurstResult`
  - Takes top `max_burst_size` from queue.
  - Double-checks eligibility (state may have changed since collection).
  - For each fired neuron:
    - Deduct 0.05 energy
    - Reset activation to 0
    - Increment `consecutive_fires`
    - Set `last_fired_burst = burst_id`
    - Set `refractory_counter = refractory_period` if > 0
  - Propagate through outgoing active synapses: `target.activation += source_activation * synapse.weight`
- `run_event_cycle(circuit, max_bursts=None) -> List[BurstResult]`
  - Clears queue, collects candidates, processes burst.
  - Repeats until no candidates remain or `max_bursts` reached.
  - Between bursts, new candidates may appear from propagation.
- `propagate_fire(circuit, neuron) -> int`
  - Manual propagation for a single neuron; returns count of propagated synapses.
- `clear_queue()`

## Integration

### Orchestrator

- New field: `execution_mode: str = "global_tick"`
- New field: `_burst_engine: EventDrivenBurstEngine`
- `_tick()` branch:
  - `"global_tick"`: `await self.circuit.tick()` (existing)
  - `"event_driven_burst"`: `self._burst_engine.run_event_cycle(self.circuit)`
- Snapshot builder records `execution_mode` and `burst_id` when in burst mode.

### MorphologySnapshot

New fields:
- `execution_mode: str = "global_tick"`
- `burst_id: int = 0`
- `fired_neurons: int = 0`
- `propagated_synapses: int = 0`
- `fire_queue_size: int = 0`

### NeuroFunctionalBenchmark

- `run_case(..., execution_mode="global_tick")` kwarg added.
- Temporarily switches orchestrator mode, runs case, restores original mode.
- Enables direct comparison: same benchmark case in tick mode vs burst mode.

## Execution rules

1. **Candidate selection**: activation >= threshold, no snooze, no refractory, energy > min.
2. **Priority**: `activation - threshold`. Higher = more urgent.
3. **Burst size cap**: `max_burst_size` per individual burst.
4. **Cascade**: A tick may contain multiple bursts (up to `max_bursts_per_tick`) because propagation creates new candidates.
5. **Refractory**: Firing sets `refractory_counter`, blocking the neuron in subsequent bursts of the same tick.
6. **Energy**: Each firing costs 0.05 energy.

## Test coverage

- Candidate selection above/below threshold
- Snoozed and refractory neurons excluded
- Low-energy neurons excluded
- Max burst size respected
- Propagation updates target activation
- Multiple bursts in a single cycle (cascade)
- Burst counter increments monotonically
- Queue clear
- Consecutive fires incremented
- `last_fired_burst` set
- Refractory period applied after fire
- Pruned synapses skipped
- Missing target neurons skipped
- Empty queue handled
- Orchestrator burst mode integration
- NeuroFunctionalBenchmark burst mode case

## Acceptance criteria

- [x] `EventDrivenBurstEngine` is importable.
- [x] Fire queue selects only valid candidates.
- [x] Snoozed/refractory neurons are excluded.
- [x] Burst propagation updates target activation through active synapses.
- [x] Orchestrator supports `execution_mode="event_driven_burst"`.
- [x] Global tick remains intact and functional.
- [x] At least one benchmark case runs in burst mode.
- [x] MorphologySnapshot records burst metadata.
- [x] All 99 tests pass (81 existing + 18 new).
- [x] Coverage >= 85% (actual: 89.76%).
- [x] `docs/EVENT_DRIVEN_BURST_ENGINE_SPEC.md` created.

## Post-T12 next step

T13 — STDPPlasticityEngine v2 (causal burst-aware spike-timing-dependent plasticity).
