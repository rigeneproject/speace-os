# GenomeDatabase & EvolutionEngine v0.3 — Specification

## Overview

T15 closes the evolutionary loop for SPEACE Digital Cellular Brain. After T17 introduced mesoscopic community detection, T15 adds a persistent genome database and an evolutionary engine that drives the cycle:

```
genome → fenotipo → esperienza → benchmark → fitness → mutazione/crossover → nuovo genoma
```

This is the first fully evolutionary capability: SPEACE can now evaluate its own genomes, score them, breed better ones, and persist the lineage.

## Architecture

### New modules

- `speace_core/cellular_brain/evolution/__init__.py`
- `speace_core/cellular_brain/evolution/genome_database.py`
- `speace_core/cellular_brain/evolution/evolution_engine.py`

### Data directory

- `data/evolution/.gitkeep`
- `data/evolution/genomes.jsonl`
- `data/evolution/evolution_runs.jsonl`
- `data/evolution/lineages.jsonl`

### Modified modules

- `speace_core/cellular_brain/memory/morphology_events.py` — `GENOME_SAVED`, `GENOME_MUTATED`, `GENOME_CROSSED`, `GENOME_SELECTED`, `EVOLUTION_STEP_COMPLETED`

## Models

### GenomeRecord

| Field | Type | Description |
|-------|------|-------------|
| `genome_id` | str | Unique identifier |
| `parent_ids` | List[str] | Parent lineage |
| `generation` | int | Evolution generation |
| `genome` | dict | Full genome dict |
| `created_at` | str | ISO timestamp |
| `mutation_operator` | Optional[str] | Mutation type used |
| `crossover_operator` | Optional[str] | Crossover type used |
| `fitness_score` | Optional[float] | Computed fitness |
| `benchmark_case` | Optional[str] | Evaluation scenario |
| `metrics` | dict | Raw benchmark metrics |
| `lineage_notes` | Optional[str] | Human-readable trace |

### EvolutionRunRecord

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | str | Unique run identifier |
| `generation` | int | Generation number |
| `candidate_genome_ids` | List[str] | IDs of candidates produced |
| `selected_genome_ids` | List[str] | IDs of selected survivors |
| `best_genome_id` | Optional[str] | Top performer |
| `best_fitness` | Optional[float] | Best fitness score |
| `created_at` | str | ISO timestamp |
| `notes` | Optional[str] | Run summary |

### FitnessResult

| Field | Type | Description |
|-------|------|-------------|
| `genome_id` | str | Evaluated genome |
| `fitness_score` | float | Final fitness [0, 1] |
| `accuracy_score` | float | Benchmark accuracy |
| `coherence_phi` | float | Φ coherence |
| `cognitive_score` | float | SPEACE cognitive score |
| `energy_efficiency` | float | Energy metric |
| `modularity_proxy` | float | Community modularity |
| `morphological_stability` | float | Structural stability |
| `functional_improvement` | float | Accuracy/Φ gain |
| `safety_score` | float | Survival check |
| `raw_metrics` | dict | Full benchmark dump |

## GenomeDatabase

### Constructor

- `base_path: str = "data/evolution"`

### Methods

- `save_genome(record) -> str`
- `load_genome(genome_id) -> GenomeRecord | None`
- `list_genomes() -> List[GenomeRecord]`
- `list_by_generation(generation) -> List[GenomeRecord]`
- `get_best_genomes(limit=5) -> List[GenomeRecord]` — sorted by fitness descending
- `save_evolution_run(record) -> str`
- `list_evolution_runs() -> List[EvolutionRunRecord]`
- `record_lineage(child_id, parent_ids, generation) -> None`

### Persistence format

All records are stored as JSONL (one JSON object per line), consistent with `MorphologicalMemory`.

## EvolutionEngine

### Constructor

- `genome_database: GenomeDatabase`
- `mutation_rate: float = 0.10`
- `mutation_strength: float = 0.10`
- `crossover_rate: float = 0.30`
- `elite_fraction: float = 0.20`

### Mutable gene paths

Only numeric structural parameters are mutated:

- `homeostasis.default_threshold`
- `homeostasis.default_plasticity_rate`
- `homeostasis.overload_threshold`
- `homeostasis.noise_suppression_rate`
- `homeostasis.energy_recovery_rate`
- `immune.prune_threshold`
- `immune.quarantine_error_limit`
- `immune.myelination_success_threshold`
- `immune.latency_reduction`

### Protected keys (never mutated)

- `identity`
- `purpose`
- `safety`
- `version`
- `protected_genes`

### Methods

- `compute_fitness(benchmark_result) -> FitnessResult`
  - Formula:
    ```
    fitness =
      0.20 * speace_cognitive_score
      + 0.20 * coherence_phi
      + 0.15 * max(0, functional_improvement)
      + 0.15 * energy_efficiency
      + 0.10 * modularity_proxy
      + 0.10 * morphological_stability
      + 0.10 * safety_score
    ```
  - Clamped to `[0.0, 1.0]`

- `select_parents(records, strategy="top_k", k=3) -> List[GenomeRecord]`
  - `top_k`: highest fitness
  - `elite`: top `elite_fraction` percentile

- `mutate_genome(genome, strength=None) -> dict`
  - `new_value = old_value * random.uniform(1 - strength, 1 + strength)`
  - Clamped by semantic type (rate/threshold → [0,1], count/limit → ≥1, window → [1,10])

- `adaptive_strength(fitness) -> float`
  - `fitness < 0.50` → `0.30`
  - `fitness >= 0.50` → `0.10`
  - `fitness >= 0.80` → `0.05`

- `crossover_genomes(parent_a, parent_b) -> dict`
  - For each mutable path: average if float, pick one if int
  - Preserves protected keys and non-mutable fields from parent_a

- `validate_genome_safety(genome) -> bool`
  - Rejects: `neuron_count <= 0`, `synapse_density < 0`, `threshold <= 0`, `prune_threshold` out of [0,1], `overload > max_energy`, missing protected keys

- `create_candidate_generation(parent_records, n_candidates=5, generation=0, benchmark_case="morphological_memory_trace", memory=None) -> List[GenomeRecord]`
  - Generates candidates via mutation or crossover
  - Records `GENOME_MUTATED` / `GENOME_CROSSED` events in `MorphologicalMemory`

- `evaluate_genome(genome_record, benchmark_case, n_ticks=3) -> BenchmarkResult` (async)
  - Builds a full `CellularBrainOrchestrator` from the genome dict
  - Runs `NeuroFunctionalBenchmark` with all engines enabled
  - Returns the full benchmark result

- `run_evolution_step(parent_records, benchmark_results=None, generation=0, n_candidates=5, candidate_records=None) -> EvolutionRunRecord`
  - Creates (or accepts pre-built) candidates
  - Persists them to the database
  - If `benchmark_results` provided, updates fitness and selects best
  - Saves an `EvolutionRunRecord`

## Integrations

### MorphologicalMemory

Five new event types:
- `GENOME_SAVED`
- `GENOME_MUTATED`
- `GENOME_CROSSED`
- `GENOME_SELECTED`
- `EVOLUTION_STEP_COMPLETED`

### NeuroFunctionalBenchmark

`EvolutionEngine.evaluate_genome()` instantiates a full orchestrator and runs the benchmark with all flags enabled (burst, STDP, inhibition, energy control, community detection).

## Test coverage

1. GenomeDatabase creates directory and files
2. save_genome / load_genome round-trip
3. load_missing_genome returns None
4. list_genomes returns all saved records
5. list_by_generation filters correctly
6. get_best_genomes sorts and limits correctly
7. save/list evolution_runs works
8. record_lineage writes JSONL
9. compute_fitness returns value in [0, 1]
10. compute_fitness populates component fields
11. mutate_genome changes at least one mutable gene
12. mutate_genome preserves protected genes
13. mutate_genome clamps rate genes to [0, 1]
14. mutate_genome clamps count genes to ≥1
15. crossover_genomes combines two parents
16. crossover preserves non-mutable fields
17. adaptive_strength returns correct tiers
18. select_parents top_k picks best
19. select_parents falls back when no fitness
20. validate_genome_safety accepts valid genome
21. validate rejects zero threshold
22. validate rejects negative prune
23. validate rejects overload above max_energy
24. create_candidate_generation produces children with parent_ids
25. create_candidate_generation records memory events
26. run_evolution_step saves run record
27. run_evolution_step with benchmark_results selects best
28. evaluate_genome runs full benchmark (integration)
29. No regression on existing 172 tests
30. Coverage stays ≥ 85%

## Acceptance criteria

- [x] `GenomeDatabase` exists and is importable.
- [x] `EvolutionEngine` exists and is importable.
- [x] Genomes persisted in JSONL.
- [x] Evolution runs persisted in JSONL.
- [x] Fitness computed correctly and clamped to [0, 1].
- [x] Mutation and crossover produce new valid genomes.
- [x] Protected genes remain unchanged.
- [x] Safety validation blocks invalid genomes.
- [x] At least one candidate generation can be created and saved.
- [x] `evaluate_genome` runs a full benchmark end-to-end.
- [x] All tests pass; coverage stays ≥ 85%.
- [x] `docs/GENOME_DATABASE_EVOLUTION_ENGINE_SPEC.md` created.

## Post-T15 next step

T19 — MetaLearningConfidence (internal self-evaluation of learning certainty).
