# RegionBasedBrainArchitecture v0.3 — Specification

## Overview

T21 transforms SPEACE from a monolithic neurocellular circuit into a regionalized digital brain. Rather than treating all neurons as a single undifferentiated mass, T21 partitions them into functional regions — each with its own local metrics, regulation, and inter-region connectivity — while preserving all T7–T20 modules.

Biologically: a real brain is not a bag of neurons; it is a hierarchy of specialized regions (sensory cortex, hippocampus, prefrontal cortex, motor cortex) connected by structured pathways. T21 is the first step toward that hierarchy.

## Architecture

### New module

- `speace_core/cellular_brain/regions/__init__.py`
- `speace_core/cellular_brain/regions/brain_region.py`
- `speace_core/cellular_brain/regions/region_connectome.py`
- `speace_core/cellular_brain/regions/region_registry.py`
- `speace_core/cellular_brain/regions/region_factory.py`

### Modified modules

- `speace_core/dna/models.py` — added `brain_regions: Dict[str, Any]` to `SharedGenome`
- `speace_core/dna/genome/default_genome.yaml` — added `brain_regions` section
- `speace_core/orchestrator.py` — `region_architecture_enabled`, `_region_registry`, regional regulation in `_tick()`
- `speace_core/cellular_brain/benchmark/neurofunctional_benchmark.py` — regional metrics in `BenchmarkMetrics` and reports

## Models

### BrainRegionProfile

| Field | Type | Description |
|-------|------|-------------|
| `region_id` | str | Unique region ID |
| `name` | str | Human-readable name |
| `region_type` | str | Functional type |
| `neuron_ids` | list[str] | Neurons assigned |
| `synapse_ids` | list[str] | Intra-region synapses |
| `dominant_cell_types` | list[str] | Preferred cell types |
| `mean_energy` | float | Average neuron energy |
| `local_phi` | float | Internal connectivity ratio |
| `local_confidence` | float \| None | Regional confidence |
| `community_count` | int | Local communities |
| `role_description` | str \| None | Functional description |

### InterRegionConnection

| Field | Type | Description |
|-------|------|-------------|
| `source_region_id` | str | Origin region |
| `target_region_id` | str | Destination region |
| `connection_type` | str | `feedforward`, `feedback`, etc. |
| `strength` | float | Connection weight |
| `plasticity_enabled` | bool | STDP allowed |
| `inhibitory` | bool | Inhibitory projection |

### RegionConnectome

| Field | Type | Description |
|-------|------|-------------|
| `regions` | dict[str, dict] | Serialized region profiles |
| `connections` | list[InterRegionConnection] | Inter-region edges |

## Classes

### BrainRegion

- `__init__(region_id, region_type, neuron_ids, dominant_cell_types, role_description)`
- `compute_local_metrics(circuit) -> BrainRegionProfile`
  - Computes `mean_energy` from assigned neurons
  - Computes `local_phi` as internal_weight / total_weight
- `receive_signal(signal)` — appends to `_input_buffer`
- `emit_signal() -> List[float]` — returns and clears `_output_buffer`
- `flush_buffers()` — clears both buffers
- `regulate_region(circuit)` — energy normalization (drain if > 0.9, boost if < 0.3)

### RegionRegistry

- `register(region)` — stores region and profile in connectome
- `get(region_id) -> BrainRegion | None`
- `list_region_ids() -> List[str]`
- `get_region_profiles() -> List[BrainRegionProfile]`
- `remove_region(region_id)` — cascades to connectome
- `compute_global_metrics() -> Dict[str, float]`
  - `mean_region_energy`, `mean_region_phi`, `total_neurons_in_regions`, `connectome_density`

### RegionFactory

- `build_from_genome(circuit, genome_dict, seed=42) -> RegionRegistry`
  1. Parses `genome_dict["brain_regions"]`
  2. Assigns hidden neurons to regions by `dominant_cell_types` match
  3. Unassigned neurons round-robined to smallest region
  4. Creates default pipeline connections: `sensory → hippocampus → prefrontal → motor`
  5. Tags each neuron with its primary `region` attribute
- `_assign_fallback_regions(circuit, registry)` — heuristic assignment when genome lacks `brain_regions`

## Genome integration

Added to `default_genome.yaml`:

```yaml
brain_regions:
  sensory:
    region_type: "sensory"
    neuron_fraction: 0.20
    dominant_cell_types: [sensory_neuron, input]
    plasticity_bias: 0.5
    role_description: "Input encoding and signal preprocessing"
  hippocampus:
    region_type: "hippocampus"
    neuron_fraction: 0.25
    dominant_cell_types: [hippocampal_neuron, memory_neuron]
    plasticity_bias: 0.9
    role_description: "Pattern memory and consolidation"
  prefrontal:
    region_type: "prefrontal"
    neuron_fraction: 0.35
    dominant_cell_types: [prefrontal_neuron, inhibitory_neuron, control]
    plasticity_bias: 0.7
    role_description: "Planning, control, and decision"
  motor:
    region_type: "motor"
    neuron_fraction: 0.20
    dominant_cell_types: [motor_neuron, output]
    plasticity_bias: 0.4
    role_description: "Output execution and action"
```

## Orchestrator integration

- New field: `region_architecture_enabled: bool = True`
- New field: `_region_registry: RegionRegistry | None = None`
- In `model_post_init`:
  ```python
  if self.region_architecture_enabled:
      self._region_registry = RegionFactory.build_from_genome(
          self.circuit, self.genome.model_dump(), seed=42
      )
  ```
- In `_tick()`, after confidence evaluation:
  ```python
  if self.region_architecture_enabled and self._region_registry is not None:
      for region in self._region_registry.regions.values():
          region.regulate_region(self.circuit)
  ```
- New property: `region_registry -> RegionRegistry | None`

## Benchmark integration

`BenchmarkMetrics` gains four T21 fields:

| Metric | Source |
|--------|--------|
| `region_count` | `len(registry.regions)` |
| `connectome_density` | `registry.connectome.compute_connectome_density()` |
| `mean_region_energy` | `registry.compute_global_metrics()` |
| `mean_region_phi` | `registry.compute_global_metrics()` |

Markdown reports include:
- Region count
- Connectome density
- Mean region energy
- Mean region phi

## Pipeline

T21 defines a canonical information-flow pipeline:

```
input → sensory → hippocampus → prefrontal → motor → output
```

This is implemented as `RegionFactory.DEFAULT_PIPELINE` and instantiated as `InterRegionConnection` edges in the connectome.

## Test coverage

1. `BrainRegion` is importable and initializable
2. `to_profile()` returns valid `BrainRegionProfile`
3. Signal I/O (`receive_signal`, `emit_signal`, `flush_buffers`)
4. `compute_local_metrics` computes energy and phi correctly
5. `regulate_region` drains high energy and boosts low energy
6. `RegionConnectome` add/get/remove connections
7. `RegionConnectome` density computation
8. `RegionRegistry` register/get/list/remove
9. `RegionRegistry` global metrics
10. `RegionFactory` builds from genome with `brain_regions`
11. `RegionFactory` fallback when genome lacks `brain_regions`
12. All neurons assigned to exactly one region
13. Neuron `region` attribute set correctly
14. Pipeline connections created
15. Orchestrator builds regions by default
16. Orchestrator `region_registry` is None when disabled
17. Tick runs regional regulation
18. Benchmark includes regional metrics
19. Local phi computed correctly with internal/external synapses
20. No regression on 244 existing tests

## Acceptance criteria

- [x] Regional architecture exists and is importable.
- [x] At least 4 brain regions implemented (sensory, hippocampus, prefrontal, motor).
- [x] Neurons assigned to regions via genome or fallback heuristics.
- [x] Inter-region connections defined (feedforward pipeline).
- [x] Regional metrics computed (energy, phi).
- [x] Orchestrator integrates `region_architecture_enabled` and `_region_registry`.
- [x] Benchmark compatible with regional metrics.
- [x] Audit T20 compatible (regional metrics collected).
- [x] Documentazione creata.
- [x] All tests pass; coverage stays ≥ 85%.
- [x] `docs/REGION_BASED_BRAIN_ARCHITECTURE_SPEC.md` created.

## Post-T21 next step

T22 — Deep Region Specialization (limbic, cerebellar, default-mode regions) or T22 — Inter-Region Plasticity (pathway-specific STDP between regions).
