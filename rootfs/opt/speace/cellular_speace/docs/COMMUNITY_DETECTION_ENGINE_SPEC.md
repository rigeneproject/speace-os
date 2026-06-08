# CommunityDetectionEngine v0.3 — Specification

## Overview

T17 introduces the mesoscopic layer to SPEACE Digital Cellular Brain. After T18 stabilized metabolic regulation, T17 detects functional neuron communities based on synaptic connectivity, co-activation, and cellular similarity. This bridges the gap between individual cells and the whole circuit.

Biologically: a brain is not just neurons or the whole cortex — it is organized into functional networks (visual, motor, default mode). T17 gives SPEACE the ability to recognize its own emergent functional structure.

## Architecture

### New module

- `speace_core/cellular_brain/analysis/community_detection_engine.py`

### Modified modules

- `speace_core/orchestrator.py` — `community_detection_enabled`, `community_engine`, `last_community_result`, tick integration
- `speace_core/cellular_brain/benchmark/neurofunctional_benchmark.py` — community metrics
- `speace_core/cellular_brain/memory/morphology_events.py` — `COMMUNITY_DETECTED` event type

## Models

### CommunityProfile

| Field | Type | Description |
|-------|------|-------------|
| `community_id` | str | Unique identifier |
| `neuron_ids` | List[str] | Members |
| `size` | int | Member count |
| `mean_activation` | float | Average activation |
| `mean_energy` | float | Average energy |
| `mean_phi_proxy` | float | Local coherence proxy |
| `internal_synapse_count` | int | Synapses within community |
| `external_synapse_count` | int | Synapses crossing community boundary |
| `cohesion_score` | float | `internal / (internal + external + 1)` |
| `isolation_score` | float | `1.0 - cohesion_score` |
| `dominant_cell_type` | Optional[str] | Most frequent cell type |
| `dominant_region` | Optional[str] | Most frequent region |

### CommunityDetectionResult

| Field | Type | Description |
|-------|------|-------------|
| `communities` | List[CommunityProfile] | All detected communities |
| `community_count` | int | Number of communities |
| `modularity_proxy` | float | Weighted-average cohesion |
| `isolated_neurons` | List[str] | Neurons with zero active synapses |
| `overloaded_communities` | List[str] | Communities with high activation/energy |
| `weak_communities` | List[str] | Communities with low cohesion |

## CommunityDetectionEngine

### Constructor

- `cohesion_weak_threshold: float = 0.3`
- `overload_activation_threshold: float = 0.8`
- `overload_energy_threshold: float = 0.9`

### Methods

- `analyze(circuit, memory=None) -> CommunityDetectionResult`
  1. Build adjacency map from active synapses
  2. Find connected components via DFS/BFS
  3. Profile each component
  4. Compute modularity proxy
  5. Find isolated, overloaded, and weak communities
  6. Record `COMMUNITY_DETECTED` event in memory

- `build_adjacency_map(circuit) -> Dict[str, Set[str]]`
- `detect_communities(circuit, adjacency=None) -> List[List[str]]`
- `profile_community(circuit, neuron_ids, community_id) -> CommunityProfile`
- `compute_modularity_proxy(result) -> float`
- `find_isolated_neurons(circuit, adjacency=None) -> List[str]`
- `find_overloaded_communities(profiles) -> List[str]`
- `find_weak_communities(profiles) -> List[str]`

### Algorithm

For v0.3, we use a simple connected-components approach:

1. Treat the circuit as an undirected graph via active synapses.
2. Each connected component is an initial community.
3. Compute internal vs external synapse counts.
4. Derive cohesion and isolation from these counts.

Future versions may replace this with Louvain or Leiden for more granular clustering.

### Formulas

```
cohesion_score = internal_synapse_count / (internal_synapse_count + external_synapse_count + 1)
isolation_score = 1.0 - cohesion_score
modularity_proxy = weighted_mean(cohesion_score, weight=community_size)
```

## Orchestrator integration

- New field: `_community: CommunityDetectionEngine`
- New field: `community_detection_enabled: bool = True`
- New field: `last_community_result: CommunityDetectionResult | None = None`
- Initialized in `model_post_init`
- In `_tick()`, after metrics computation:
  ```python
  if self.community_detection_enabled:
      self.last_community_result = self._community.analyze(
          self.circuit, memory=self._memory
      )
  ```
- Observational only in T17: the engine does not yet modify the circuit.

## Benchmark integration

`BenchmarkMetrics` gains five T17 fields:

| Metric | Source |
|--------|--------|
| `community_count` | `result.community_count` |
| `modularity_proxy` | `result.modularity_proxy` |
| `isolated_neuron_count` | `len(result.isolated_neurons)` |
| `weak_community_count` | `len(result.weak_communities)` |
| `overloaded_community_count` | `len(result.overloaded_communities)` |

The benchmark dispatcher gains `community_detection_enabled: bool = True`.

Reports include a new "Community Metrics" section in Markdown.

## MorphologicalMemory integration

- New event type: `COMMUNITY_DETECTED`
- Fired whenever `analyze()` runs and `memory` is provided
- Metadata contains aggregate community statistics

## Test coverage

1. Engine is importable
2. Adjacency map builds correctly from active synapses
3. `detect_communities` finds connected components
4. Isolated neurons are detected
5. No isolated neurons in fully-connected circuit
6. `profile_community` computes all fields
7. `cohesion_score` is in [0, 1]
8. `modularity_proxy` is in [0, 1]
9. Single component yields high modularity
10. Weak communities detected with low cohesion threshold
11. Overloaded communities detected with high activation/energy
12. `COMMUNITY_DETECTED` event recorded in memory
13. Dominant cell type and region computed
14. Orchestrator has `community_detection_enabled` and `_community`
15. Orchestrator tick populates `last_community_result`
16. Orchestrator skips detection when disabled
17. Benchmark includes community metrics after run
18. No regression on existing 154 tests

## Acceptance criteria

- [x] `CommunityDetectionEngine` exists and is importable.
- [x] Detects connected-component communities from active synapses.
- [x] Computes `CommunityProfile` per community.
- [x] Identifies isolated neurons.
- [x] Computes `cohesion_score` and `modularity_proxy`.
- [x] Integrates with Orchestrator via `community_detection_enabled`.
- [x] Integrates with `NeuroFunctionalBenchmark` via community metrics.
- [x] Records `COMMUNITY_DETECTED` events in `MorphologicalMemory`.
- [x] All tests pass; coverage stays ≥ 85%.
- [x] `docs/COMMUNITY_DETECTION_ENGINE_SPEC.md` created.

## Post-T17 next step

T15 — GenomeDatabase & EvolutionEngine (evolutionary loop driven by community-level fitness).
