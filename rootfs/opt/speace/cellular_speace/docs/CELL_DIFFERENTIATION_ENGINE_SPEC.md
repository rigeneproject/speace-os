# CellDifferentiationEngine v0.2 — Specification

## Overview

The `CellDifferentiationEngine` is the specialization layer of the SPEACE cellular lifecycle. After neurogenesis creates a new neuron, and apoptosis removes the weakest ones, differentiation assigns each cell a precise biological role based on its context (region, connectivity, activity, energy) and the genome rules encoded in the Digital DNA.

This closes the minimal cellular lifecycle: **T7 Memory → T8 Creation → T9 Elimination → T10 Specialization**.

---

## Responsibilities

1. **Context Evaluation**: Inspect a neuron's local environment (region, role, energy, connectivity, firing history, global Φ).
2. **Fate Selection**: Map context to a cell type using hardcoded biological heuristics + genome differentiation rules.
3. **Phenotype Application**: Modify threshold, plasticity rate, refractory period, gene expression, and epigenetic marks.
4. **Morphological Recording**: Emit `CELL_DIFFERENTIATED` events to `MorphologicalMemory`.
5. **Circuit-Wide Scan**: Iterate all neurons and differentiate any that are still `undifferentiated`.

---

## Cell Types

| Cell Type            | Trigger Condition                              | Phenotype Effect                                      |
|----------------------|------------------------------------------------|-------------------------------------------------------|
| `sensory_neuron`     | `neuron_role == "input"` or `region == "sensory"` | Lower threshold, higher plasticity, excitatory          |
| `motor_neuron`       | `neuron_role == "output"` or `region == "motor"`   | Moderate threshold, fast signaling, excitatory        |
| `hippocampal_neuron` | `region == "hippocampus"` or `"memory"`           | Memory affinity, moderate plasticity                  |
| `prefrontal_neuron`  | `region == "prefrontal"`, `"pfc"`, or `"control"` | Control-oriented, moderate threshold                  |
| `inhibitory_neuron`  | `consecutive_fires >= 5`                        | Inhibition affinity, higher threshold, stabilizer role |
| `regulatory_neuron`  | `energy < 0.25` and `connectivity > 3`          | Energy-management role, moderate plasticity           |
| `memory_neuron`      | Defined in genome rules (reserved for T16)     | High memory affinity, low plasticity                  |
| `generic_neuron`     | Default fallback                                | Baseline phenotype                                    |

---

## Genome Integration

The `SharedGenome` carries a `cell_differentiation_rules` dictionary keyed by cell type. Each rule (`CellDifferentiationRule`) contains:

- `regions`: list of brain regions this rule applies to
- `role`: biological role string
- `threshold_modifier`: additive shift to neuron's firing threshold
- `plasticity_modifier`: multiplicative factor for learning rate
- `energy_profile`: metabolic cost profile
- `signal_sign`: `"excitatory"` or `"inhibitory"`
- `refractory_period`: post-fire cooldown ticks
- `memory_affinity`: float [0,1] for memory-related tasks
- `inhibition_affinity`: float [0,1] for stabilization tasks

The engine reads the rule for the selected type and applies it to the neuron's phenotype.

---

## API

### `CellDifferentiationEngine`

#### `__init__(genome: SharedGenome, memory: MorphologicalMemory | None = None)`
Initialize with genome rules and optional memory sink.

#### `evaluate_cell_context(neuron, circuit, metrics=None) -> DifferentiationContext`
Build a context snapshot from neuron state + circuit topology + global metrics.

#### `select_cell_fate(context) -> str`
Return the target cell type string based on context heuristics.

#### `apply_differentiation(neuron, new_type, context)`
Mutate the neuron's phenotype in-place using the genome rule for `new_type`.

#### `differentiate_cell(neuron, circuit, metrics=None) -> str`
Full pipeline: evaluate → select → apply → record memory event. Returns the new type.

#### `differentiate_circuit(circuit, metrics=None) -> List[str]`
Iterate all neurons in the circuit; differentiate any whose `differentiation_state != "differentiated"`. Returns the list of assigned types.

---

## Integration Points

- **NeurogenesisEngine**: After `generate_neuron`, the orchestrator passes `differentiation_engine` so the newborn is immediately specialized.
- **Orchestrator**: `run_differentiation()` calls `differentiate_circuit()` on demand.
- **MorphologicalMemory**: Every differentiation emits a `CELL_DIFFERENTIATED` event with metadata including `from_type`, `to_type`, `gene_expression`, and `differentiation_score`.

---

## Acceptance Criteria

- [x] `CellDifferentiationEngine` exists and is importable.
- [x] Assigns `cell_type` based on region, role, activity, and genome rules.
- [x] Modifies threshold, plasticity rate, refractory period, and gene expression verifiably.
- [x] Reads at least one rule from `SharedGenome.cell_differentiation_rules`.
- [x] Records `CELL_DIFFERENTIATED` events in `MorphologicalMemory`.
- [x] Integrates with `NeurogenesisEngine` (new neurons are differentiated at birth).
- [x] Integrates with `NeuralCircuit` / `Orchestrator`.
- [x] All tests pass; coverage ≥ 87%.
- [x] `docs/CELL_DIFFERENTIATION_ENGINE_SPEC.md` created.
