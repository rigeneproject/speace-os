# EnergyControlAgent v0.3 — Specification

## Overview

T18 introduces metabolic regulation to SPEACE Digital Cellular Brain. After T14 stabilized the network with inhibition, T18 adds an energy-aware control layer that dynamically adapts engine parameters based on the circuit's mean energy state. This prevents energy depletion during learning and avoids runaway energy accumulation.

Biologically: a brain without metabolic regulation wastes glucose during idle periods and crashes during overactivation. A brain with metabolic regulation sustains operation across varying cognitive loads.

## Architecture

### New module

- `speace_core/cellular_brain/regulation/energy_control_agent.py`

### Modified modules

- `speace_core/orchestrator.py` — `_energy_control` field, `energy_control_enabled` flag, tick integration
- `speace_core/cellular_brain/benchmark/neurofunctional_benchmark.py` — `energy_control_enabled` parameter

## EnergyControlDecision

Pydantic model capturing the agent's decision each tick:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `metabolic_state` | str | "optimal" | One of 5 states |
| `mean_energy` | float | 0.0 | Circuit mean energy at decision time |
| `coherence_phi` | float | 0.0 | Circuit coherence at decision time |
| `burst_size_multiplier` | float | 1.0 | Scaling factor for burst engine max size |
| `stdp_rate_multiplier` | float | 1.0 | Scaling factor for STDP learning rates |
| `plasticity_rate_multiplier` | float | 1.0 | Scaling factor for neuron plasticity |
| `neurogenesis_allowance_multiplier` | float | 1.0 | Scaling factor for neurogenesis budget |
| `inhibition_decay_multiplier` | float | 1.0 | Scaling factor for inhibition decay speed |
| `apoptosis_pressure_multiplier` | float | 1.0 | Scaling factor for apoptosis aggressiveness |
| `energy_replenish_rate` | float | 0.0 | Per-tick energy change applied to all neurons |
| `reason` | str | "" | Human-readable rationale |

## Metabolic state machine

| State | Energy range | Burst | STDP | Plasticity | Neurogenesis | Inhibition | Apoptosis | Replenish |
|-------|-------------|-------|------|------------|--------------|------------|-----------|-----------|
| `critical_low` | ≤ 0.20 | 0.25× | 0.0× | 0.0× | 0.0× | 2.0× faster | 0.0× | +0.05 |
| `low` | ≤ 0.40 | 0.50× | 0.50× | 0.50× | 0.0× | 1.5× faster | 0.5× | +0.01 |
| `optimal` | 0.40–0.70 | 1.0× | 1.0× | 1.0× | 1.0× | 1.0× | 1.0× | +0.01 |
| `high` | ≥ 0.70 | 1.50× | 1.25× | 1.25× | 1.50× | 0.5× slower | 1.0× | +0.01 |
| `critical_high` | ≥ 0.85 | 2.0× | 1.50× | 1.50× | 2.0× | 0.25× slower | 2.0× | −0.03 (drain) |

Rationale:
- **critical_low**: Emergency conservation. Suppress firing and plasticity to save energy. Accelerate decay to silence noise. Replenish aggressively.
- **low**: Cautious operation. Reduce burst size and learning rates. No new neurons.
- **optimal**: Full performance. All engines run at baseline.
- **high**: Accelerated learning. Expand burst and plasticity. Reduce inhibition to allow exploration.
- **critical_high**: Overflow prevention. Drain excess energy. Increase apoptosis pressure to trim the circuit.

## EnergyControlAgent

### Constructor

- `critical_low_replenish: float = 0.05`
- `normal_replenish: float = 0.01`
- `overflow_drain: float = 0.03`

### Methods

- `regulate(circuit, metrics=None, burst_engine=None, memory=None) -> EnergyControlDecision`
  1. Classify metabolic state from `metrics.mean_energy`
  2. Build `EnergyControlDecision`
  3. Apply burst size multiplier to `burst_engine.max_burst_size`
  4. Replenish or drain energy across all neurons
  5. Record `ENERGY_CHANGED` event in `MorphologicalMemory`

- `get_last_decision() -> EnergyControlDecision | None`

### Thresholds

- `CRITICAL_LOW_THRESHOLD = 0.20`
- `LOW_THRESHOLD = 0.40`
- `HIGH_THRESHOLD = 0.70`
- `CRITICAL_HIGH_THRESHOLD = 0.85`

## Orchestrator integration

- New field: `_energy_control: EnergyControlAgent`
- New field: `energy_control_enabled: bool = True`
- Initialized in `model_post_init`
- In `_tick()`, after burst cycle, STDP, and inhibition:
  ```python
  if self.energy_control_enabled:
      self._energy_control.regulate(
          self.circuit,
          metrics=self.latest_metrics,
          burst_engine=self._burst_engine,
          memory=self._memory,
      )
  ```
- Not applied in global tick mode (energy dynamics are simpler there).

## Benchmark integration

- `NeuroFunctionalBenchmark.run_case(...)` gains `energy_control_enabled: bool = True`
- Enables A/B comparison:
  - burst without STDP
  - burst with STDP
  - burst with STDP + inhibition
  - burst with STDP + inhibition + energy control

## Test coverage

1. State classification for all 5 metabolic states
2. Decision field correctness per state
3. Energy replenishment in critical_low
4. Energy drainage in critical_high
5. Replenish caps at 1.0
6. Drain floors at 0.0
7. Burst size reduced in low energy
8. Burst size increased in high energy
9. Burst size minimum is 1
10. Multipliers restore to original on optimal
11. `regulate()` returns a valid decision
12. `ENERGY_CHANGED` event registered in memory
13. `get_last_decision()` tracks state
14. Orchestrator has `energy_control_enabled` and `_energy_control`
15. Orchestrator tick applies energy control in burst mode
16. Orchestrator tick skips energy control when disabled
17. Benchmark runs with burst + STDP + inhibition + energy control

## Acceptance criteria

- [x] `EnergyControlAgent` exists and is importable.
- [x] 5-state metabolic classifier functions correctly.
- [x] Energy replenishment and drainage apply to all neurons.
- [x] Burst size multiplier adjusts `EventDrivenBurstEngine.max_burst_size`.
- [x] `ENERGY_CHANGED` events recorded in `MorphologicalMemory`.
- [x] Orchestrator supports `energy_control_enabled=True/False`.
- [x] `NeuroFunctionalBenchmark` can run with energy control enabled.
- [x] All tests pass; coverage stays ≥ 85%.
- [x] `docs/ENERGY_CONTROL_AGENT_SPEC.md` created.

## Post-T18 next step

T17 — CommunityDetectionEngine (structural clustering after metabolic stabilization).
