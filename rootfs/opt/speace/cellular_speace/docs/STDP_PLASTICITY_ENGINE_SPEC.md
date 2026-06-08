# STDPPlasticityEngine v2 — Specification

## Overview

T13 introduces burst-aware Spike-Timing-Dependent Plasticity (STDP) to SPEACE. With T12's `EventDrivenBurstEngine`, neurons now carry `last_fired_burst`. STDP uses this timestamp to strengthen or weaken synapses based on causal firing order:

- **pre fires before post** (`delta = +1`) → LTP (Long-Term Potentiation), synapse reinforced
- **post fires before pre** (`delta = -1`) → LTD (Long-Term Depression), synapse weakened
- **same burst or outside window** → no change

This replaces generic feedback-only plasticity with a temporally local, biologically inspired learning rule.

## Why now

T12 gave SPEACE sparse burst execution and `last_fired_burst`. Without STDP, those timestamps have no learning purpose. T13 makes the burst engine educationally meaningful: the network can now learn from temporal causality, not just scalar feedback.

## Architecture

### Module

- `speace_core/cellular_brain/regulation/stdp_plasticity_engine.py`

### Class: `STDPPlasticityEngine`

**Constructor parameters:**
- `ltp_rate: float = 0.05` — weight increase for LTP
- `ltd_rate: float = 0.03` — weight decrease for LTD
- `stdp_window: int = 1` — max burst distance for plasticity
- `min_weight: float = 0.0` — lower weight bound
- `max_weight: float = 1.0` — upper weight bound

**Core methods:**

- `compute_delta_burst(pre_neuron, post_neuron) -> int | None`
  - Returns `post.last_fired_burst - pre.last_fired_burst`
  - Returns `None` if either neuron never fired (`last_fired_burst == 0`)

- `compute_weight_delta(delta_burst) -> float`
  - `+1` → `+ltp_rate`
  - `-1` → `-ltd_rate`
  - anything else → `0.0`

- `apply_stdp_to_synapse(synapse, pre_neuron, post_neuron, memory=None) -> float | None`
  - Computes delta, applies weight change, clamps to `[min_weight, max_weight]`
  - Records `SYNAPSE_REINFORCED` or `SYNAPSE_WEAKENED` in `MorphologicalMemory`
  - Metadata includes:
    - `mechanism`: `"stdp"`
    - `pre_neuron_id`, `post_neuron_id`
    - `pre_last_fired_burst`, `post_last_fired_burst`
    - `delta_burst`
    - `old_weight`, `new_weight`

- `apply_stdp(circuit, memory=None) -> dict`
  - Iterates all active synapses in the circuit
  - Returns counts: `{"reinforced": int, "weakened": int, "unchanged": int}`

## Integration

### Orchestrator

- New field: `_stdp: STDPPlasticityEngine`
- New field: `stdp_enabled: bool = True`
- Initialized in `model_post_init`
- In `_tick()`, when `execution_mode == "event_driven_burst"`:
  1. `self._burst_engine.run_event_cycle(self.circuit)`
  2. If `self.stdp_enabled`: `self._stdp.apply_stdp(self.circuit, self._memory)`

In global tick mode, STDP is not called because `last_fired_burst` is not updated by the tick loop.

### NeuroFunctionalBenchmark

- `run_case(...)` gains `stdp_enabled: bool = True` parameter
- Temporarily sets `orchestrator.stdp_enabled` before running, restores after
- Enables A/B comparison: same benchmark with/without STDP

## STDP rules

| `delta_burst` | Direction | Weight change | Event type |
|---|---|---|---|
| `+1` | pre before post | `+ltp_rate` | `SYNAPSE_REINFORCED` |
| `-1` | post before pre | `-ltd_rate` | `SYNAPSE_WEAKENED` |
| `0` | same burst | `0` | none |
| `abs(delta) > 1` | outside window | `0` | none |
| `last_fired_burst == 0` | never fired | `0` | none |

## Test coverage

1. LTP when pre fires before post
2. LTD when post fires before pre
3. No change when `delta_burst == 0`
4. No change when `abs(delta) > stdp_window`
5. No change when neuron never fired
6. Weight clamped at `max_weight`
7. Weight clamped at `min_weight`
8. Pruned synapses skipped
9. Missing target neurons skipped
10. Memory records reinforced event with STDP metadata
11. Memory records weakened event with STDP metadata
12. `apply_stdp` counts reinforced/weakened/unchanged correctly
13. Orchestrator burst mode applies STDP without error
14. Benchmark runs in burst mode with STDP enabled

## Acceptance criteria

- [x] `STDPPlasticityEngine` exists and is importable.
- [x] Reinforces synapses when pre fires before post (`delta = +1`).
- [x] Weakens synapses when post fires before pre (`delta = -1`).
- [x] Ignores synapses outside the temporal window.
- [x] Clamps weights within `[min_weight, max_weight]`.
- [x] Records `SYNAPSE_REINFORCED` / `SYNAPSE_WEAKENED` in `MorphologicalMemory`.
- [x] Integrates with `EventDrivenBurstEngine` via Orchestrator.
- [x] `stdp_enabled` flag allows A/B comparison.
- [x] At least one benchmark case runs with burst mode + STDP.
- [x] All existing tests pass; coverage stays ≥ 85%.
- [x] `docs/STDP_PLASTICITY_ENGINE_SPEC.md` created.

## Post-T13 next step

T14 — InhibitoryNeuron & Snooze advanced (stabilization against runaway activation).
