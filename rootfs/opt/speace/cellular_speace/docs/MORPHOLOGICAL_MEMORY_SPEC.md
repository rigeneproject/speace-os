# MorphologicalMemory Specification
## SPEACE v0.2 — Tessuto neurocellulare con memoria della forma

**Version:** 0.2.0-DRAFT  
**Date:** 2026-05-14  

---

## 1. Objective

MorphologicalMemory is the structural memory layer of SPEACE. It records every change to the network topology, synaptic weights, pruning events, myelination, energy shifts, and coherence variations. Unlike classical memory (embeddings, databases), morphological memory is inscribed in the network's history.

> SPEACE does not only store information; it preserves the history of its own structural transformations.

---

## 2. Core Concepts

### 2.1 MorphologyEvent

An atomic record of a structural change.

| Field | Description |
|---|---|
| `event_id` | UUID |
| `event_type` | `synapse_reinforced`, `synapse_weakened`, `synapse_pruned`, `pathway_myelinated`, `phi_changed`, `energy_changed`, `astrocyte_regulation`, `microglia_pruning`, `neuron_created`, `neuron_apoptosis`, `cell_differentiated` |
| `timestamp` | Monotonic float |
| `source_id` / `target_id` | Cell references |
| `phi_before` / `phi_after` | Coherence delta |
| `energy_before` / `energy_after` | Energy delta |
| `metadata` | Context-specific dict |

### 2.2 MorphologySnapshot

A periodic photograph of the entire network state.

| Field | Description |
|---|---|
| `snapshot_id` | Tick-based ID |
| `tick` | Simulation step |
| `neuron_count` | Total neurons |
| `synapse_count` | Total synapses |
| `active_synapse_count` | Non-pruned synapses |
| `pruned_synapse_count` | Pruned synapses |
| `average_weight` | Mean synaptic weight |
| `average_trust` | Mean synaptic trust |
| `average_energy` | Mean cellular energy |
| `coherence_phi` | Current Φ |
| `myelinated_pathways` | Count |

### 2.3 MorphologicalMemory

The archive engine. Responsibilities:
- Record events atomically
- Record snapshots periodically
- Persist to JSONL
- Reload from disk
- Compute Φ trends
- Count events by type

---

## 3. Persistence Format

```
data/morphological_memory/
├── events.jsonl
└── snapshots.jsonl
```

Each line is a JSON-serialized Pydantic model. Append-only during runtime; full rewrite on `save()`.

---

## 4. Integration Points

### 4.1 NeuralCircuit

- `apply_feedback(score)` records `synapse_reinforced` or `synapse_weakened` for each updated synapse.
- `run_immune()` records `synapse_pruned` for each pruned synapse.

### 4.2 Orchestrator

- Every tick produces a `MorphologySnapshot` via `_build_morphology_snapshot()`.
- Snapshot is stored in `MorphologicalMemory`.

### 4.3 Future v0.2+ Engines

- `NeurogenesisEngine` → `neuron_created` events
- `ApoptosisEngine` → `neuron_apoptosis` events
- `CellDifferentiationEngine` → `cell_differentiated` events
- `MyelinationEngine` → `pathway_myelinated` events (currently wired in unit tests only)

---

## 5. Acceptance Criteria

- [x] `MorphologicalMemory` records events atomically
- [x] Saves and loads events/snapshots from JSONL
- [x] Records network snapshots every tick
- [x] Computes `latest_phi()` and `phi_trend()`
- [x] Integrated with `NeuralCircuit` (feedback + immune)
- [x] Integrated with `CellularBrainOrchestrator` (periodic snapshots)
- [x] Dedicated tests: 6+ unit tests + 3 integration tests
- [x] All existing 30 tests still pass
- [x] Coverage maintained >= 80%

---

## 6. Known Limitations

- Snapshots are stored in-memory and flushed on `save()`. No append-only streaming yet.
- No compression or rotation for long runs (10k+ ticks).
- `MyelinationEngine` events not yet wired into the main loop.

---

## 7. Next Steps

- v0.2+: Streaming append for events
- v0.3+: Query API (events by type, by region, by time window)
- v0.4+: Diff snapshots (delta between snapshots instead of full state)
- v0.5+: Export to neuro-visualization format
