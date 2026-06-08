# T43 — Semantic Cell Assembly Memory

**Version:** v0.3.29-t43-semantic-cell-assembly-memory  
**Date:** 2026-05-17  
**Status:** Implemented  
**Depends on:** T42C (Cellular Resilience Audit)

## 1. Objective

Implement a semantic memory layer for SPEACE based on recurrent co-activation patterns across neurons and brain regions. The system detects, stores, consolidates, reactivates, and evaluates cell assemblies as distributed semantic memory traces.

## 2. Biological Concept

In the biological brain, a memory is not a single neuron or a file. It is a distributed pattern of cells that reinforce together.

For SPEACE:

input pattern → regional/neuronal activation → co-activation detection → cell assembly creation → consolidation if recurrent → recall if similar pattern reappears → reinforcement/weakening via utility, STDP, energy, coherence Φ

## 3. Architecture

### 3.1 Package

`speace_core/cellular_brain/memory/semantic/`

### 3.2 Files

| File | Role |
|---|---|
| `__init__.py` | Public exports |
| `cell_assembly.py` | Core models |
| `semantic_memory_store.py` | Persistence and retrieval |
| `cell_assembly_engine.py` | Detection, reinforcement, decay, consolidation |
| `semantic_recall_engine.py` | Recall, reactivation, similarity |

### 3.3 Models

| Model | Role |
|---|---|
| `CellAssembly` | Distributed memory trace |
| `AssemblyActivationTrace` | Per-tick activation snapshot |
| `SemanticRecallResult` | Recall query result |
| `SemanticMemoryMetrics` | Aggregate metrics |

## 4. CellAssemblyEngine

### 4.1 Responsibilities

1. **observe_activation(orchestrator)** → `AssemblyActivationTrace`
   - Reads active neurons from circuit/regions
   - Uses soft activation threshold (configurable)

2. **detect_candidate_assembly(trace)** → `CellAssembly | None`
   - Minimum requirements: min_neurons, min_regions, min_mean_activation, min_confidence or min_phi

3. **match_existing_assembly(trace)** → `CellAssembly | None`
   - Cosine similarity against existing assemblies
   - Threshold: similarity >= 0.70

4. **reinforce_assembly(assembly, trace)**
   - Increases strength, recurrence_count, stability

5. **decay_assemblies()**
   - Slowly reduces strength for unused assemblies
   - Consolidated assemblies decay 3x slower

6. **consolidate_assemblies()**
   - Assemblies with recurrence >= 3 and stability >= 0.30 become consolidated

7. **run_semantic_memory_cycle(orchestrator)** → `SemanticMemoryMetrics`
   - observe → match or create → reinforce/decay/consolidate → log events

## 5. SemanticMemoryStore

- JSONL persistence
- get_by_id, list_active, list_consolidated, count
- get_best_by_strength, get_recent
- persist_metrics

## 6. SemanticRecallEngine

- **recall(query_signature)** → `SemanticRecallResult`
- **recall_from_current_activation(orchestrator)** → `SemanticRecallResult`
- **reactivate_assembly(assembly_id, orchestrator)** → bool
  - Injects bounded weak activation into member neurons
  - Respects energy constraints
- **compute_similarity(a, b)** → cosine similarity

## 7. Orchestrator Integration

- Flag: `semantic_memory_enabled: bool = False`
- Engines instantiated in `model_post_init` if enabled
- Hook in `_tick()` after T42 cellular layer, before morphology snapshot
- Public methods: `run_semantic_memory_cycle()`, `recall_semantic_memory()`, `get_semantic_memory_metrics()`

## 8. MorphologicalMemory Events

- `CELL_ASSEMBLY_CREATED`
- `CELL_ASSEMBLY_REINFORCED`
- `CELL_ASSEMBLY_CONSOLIDATED`
- `CELL_ASSEMBLY_DECAYED`
- `CELL_ASSEMBLY_REACTIVATED`
- `SEMANTIC_RECALL_SUCCEEDED`
- `SEMANTIC_RECALL_FAILED`

## 9. BenchmarkMetrics Integration

New fields:
- semantic_assembly_count
- semantic_active_assembly_count
- semantic_consolidated_assembly_count
- mean_assembly_strength
- mean_assembly_stability
- semantic_recall_success_rate
- semantic_memory_density
- semantic_memory_utility
- semantic_consolidation_rate
- semantic_memory_score

Formula:
```
semantic_memory_score =
  0.25 * semantic_recall_success_rate
  + 0.20 * mean_assembly_stability
  + 0.15 * mean_assembly_strength
  + 0.15 * semantic_consolidation_rate
  + 0.10 * semantic_memory_utility
  + 0.10 * min(1.0, semantic_memory_density)
  + 0.05 * coherence_phi
```

## 10. Acceptance Criteria

- 18+ tests covering models, store, engine, recall, events, benchmark, orchestrator
- All existing 713 tests still pass
- Coverage remains >= 85%
- JSONL persistence works
- Benchmark exposes semantic metrics
- MorphologicalMemory records semantic events
- No unbounded activation injection during recall
- Commit and tag as v0.3.29-t43-semantic-cell-assembly-memory

## 11. Commit Tag

`v0.3.29-t43-semantic-cell-assembly-memory`

## 12. Next Steps

- T43B — Semantic Memory Functional Audit
- T44 — Associative Learning Between Assemblies
- T45 — Episodic Memory Layer
- T46 — Symbolic Grounding / Semantic Pointer Labeling
