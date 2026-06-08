# T44 — Associative Learning Between Assemblies

## Overview

T44 implements associative links between cell assemblies created by T43. This transforms SPEACE from isolated semantic memory to relational / associative memory:

- Assembly A → Assembly B
- Pattern A → associative recall of B
- Co-activation A+B → association strengthening
- Absence/negative correction → association weakening

## Design Principles

- **Non-destructive**: Does not alter original assemblies; associations are separate links.
- **Conservative**: Disabled by default (`associative_learning_enabled=False`).
- **Observable**: All lifecycle events logged to MorphologicalMemory.
- **Bounded**: Strength clamped to [0, 1]; prune removes only very weak links.

## Architecture

### Models

- `AssemblyAssociation` — Link between two assemblies with type, strength, confidence, coactivation count, recall success/failure counts.
- `AssociativeLearningResult` — Aggregate metrics from a learning cycle.
- `AssociativeRecallResult` — Result of an associative recall query.

### Engines

- `AssociativeLearningEngine`
  - `observe_assemblies(active_assemblies, tick)` — detects co-activation within window and creates/reinforces associations
  - `create_or_get_association`, `reinforce_association`, `weaken_association`
  - `decay_associations()`, `prune_weak_associations()`
  - `list_associations()`, `get_associations_for_source()`

- `AssociativeRecallEngine`
  - `recall_from_assembly(cue_assembly_id)` — returns linked assemblies scored by strength/confidence/recall history
  - `recall_from_pattern(pattern, semantic_recall_engine)` — semantic recall first, then associative recall
  - `score_association(association)` — formula: 0.50*strength + 0.25*confidence + 0.15*success_rate - 0.10*failure_rate

### Integration

- Orchestrator flags: `associative_learning_enabled`, `associative_recall_enabled`
- Lazy init via `get_associative_learning_engine()` / `get_associative_recall_engine()`
- Tick loop: if both `semantic_memory_enabled` and `associative_learning_enabled`, active assemblies are passed to `observe_assemblies()` after the semantic memory cycle.

### Event Types

- `ASSEMBLY_ASSOCIATION_CREATED`
- `ASSEMBLY_ASSOCIATION_REINFORCED`
- `ASSEMBLY_ASSOCIATION_WEAKENED`
- `ASSEMBLY_ASSOCIATION_PRUNED`
- `ASSOCIATIVE_RECALL_ATTEMPTED`
- `ASSOCIATIVE_RECALL_SUCCEEDED`
- `ASSOCIATIVE_RECALL_FAILED`

### Benchmark Metrics

- `assembly_association_count`
- `assembly_associations_created`
- `assembly_associations_reinforced`
- `assembly_associations_weakened`
- `assembly_associations_pruned`
- `mean_association_strength`
- `max_association_strength`
- `association_density`
- `associative_recall_success_rate`
- `associative_recall_partial_success_rate`
- `associative_memory_effect_score`

## Acceptance Criteria

- T44 creates associations between distinct assemblies.
- T44 reinforces associations via repeated co-activation.
- T44 allows associative recall A → B.
- T44 logs events in MorphologicalMemory.
- T44 adds benchmark metrics without breaking existing reports.
- T44 is disableable via `associative_learning_enabled=False`.
- All existing 856 tests pass; coverage >= 85%.

## Version

v0.3.34-t44-associative-learning-between-assemblies
