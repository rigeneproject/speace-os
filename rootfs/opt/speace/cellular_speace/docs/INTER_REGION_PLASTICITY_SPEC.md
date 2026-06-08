# InterRegionPlasticity v0.3 — Specification

## Overview

T23 transforms the static T21 regional pipeline into an adaptive inter-region network. Rather than fixed-strength connections between sensory, hippocampus, prefrontal, and motor regions, T23 applies pathway-specific STDP that reinforces or weakens inter-region edges based on temporal activation order, regional energy, and meta-cognitive confidence.

Biologically: long-range cortico-cortical pathways (e.g., fronto-hippocampal) are not hardwired; they strengthen with correlated use and weaken with anti-correlated firing. T23 implements this for SPEACE.

## Architecture

### New module

- `speace_core/cellular_brain/regions/inter_region_plasticity.py`

### Modified modules

- `speace_core/orchestrator.py` — `_inter_region_plasticity`, `inter_region_plasticity_enabled`, hook in `_tick()`
- `speace_core/cellular_brain/benchmark/neurofunctional_benchmark.py` — T23 metrics
- `speace_core/cellular_brain/audit/integrated_neurocellular_audit.py` — `inter_region_plasticity_enabled` config
- `speace_core/cellular_brain/memory/morphology_events.py` — new event types

## Models

### RegionPathwayState

| Field | Type | Description |
|-------|------|-------------|
| `source_region_id` | str | Origin region |
| `target_region_id` | str | Destination region |
| `pathway_strength` | float | Current connection strength [0,1] |
| `plasticity_rate` | float | Modulated plasticity multiplier |
| `last_source_activation_tick` | int \| None | Last source activation |
| `last_target_activation_tick` | int \| None | Last target activation |
| `ltp_events` | int | Count of reinforcements |
| `ltd_events` | int | Count of weakenings |
| `energy_cost` | float | Cumulative energy spent this tick |
| `confidence_modulation` | float | Confidence-derived multiplier |

### InterRegionPlasticityResult

| Field | Type | Description |
|-------|------|-------------|
| `updated_pathways` | int | Pathways touched this tick |
| `reinforced_pathways` | int | Pathways strengthened |
| `weakened_pathways` | int | Pathways weakened |
| `mean_pathway_strength` | float | Average strength across all pathways |
| `total_energy_cost` | float | Sum of energy costs |
| `events` | list[dict] | Recorded event metadata |

### InterRegionPlasticityEngine

- `compute_region_activation(region_id, circuit) -> bool`
  True if any neuron in the region has activation > 0.5.

- `compute_delta_tick(pathway, tick) -> int | None`
  Returns `target_tick - source_tick` if within `stdp_window`.

- `apply_pathway_ltp(pathway)`
  Increases `pathway_strength` by `ltp_rate * plasticity_rate`, clamped to `max_strength`.

- `apply_pathway_ltd(pathway)`
  Decreases `pathway_strength` by `ltd_rate * plasticity_rate`, clamped to `min_strength`.

- `modulate_by_energy(pathway, mean_region_energy)`
  - energy < 0.3 → `plasticity_rate = max(0.1, energy)`
  - energy > 0.8 → `plasticity_rate = 1.2`
  - else → `plasticity_rate = 1.0`

- `modulate_by_confidence(pathway, confidence_score, coherence_phi)`
  - confidence > 0.6 and phi > 0.2 → `confidence_modulation = 0.7`
  - confidence < 0.3 → `confidence_modulation = 1.3`
  - else → `confidence_modulation = 1.0`
  Then `plasticity_rate *= confidence_modulation`.

- `_is_isolated_region(region_id, registry) -> bool`
  True if the region has ≤1 total connections.

- `update_pathways(circuit, registry, metrics, memory, tick, confidence_score) -> InterRegionPlasticityResult`
  1. Iterate all `InterRegionConnection` in `registry.connectome.connections`.
  2. Skip if `plasticity_enabled=False`.
  3. Track activations per region.
  4. Build/recover `RegionPathwayState` stored in `conn._pathway_state`.
  5. Apply energy and confidence modulation.
  6. Compensatory strengthening for isolated regions.
  7. If both regions fired within `stdp_window`, apply LTP (source before target) or LTD (target before source).
  8. Clamp `pathway_strength` to [0,1] and sync back to `conn.strength`.
  9. Record events in `MorphologicalMemory`.

## Integration

### Orchestrator

- New flag: `inter_region_plasticity_enabled: bool = True`
- New engine: `_inter_region_plasticity: InterRegionPlasticityEngine`
- Hook in `_tick()` after regional regulation (T21), before morphological snapshot.

### Benchmark

New fields in `BenchmarkMetrics`:
- `mean_pathway_strength`
- `reinforced_pathways`
- `weakened_pathways`
- `inter_region_plasticity_events`
- `pathway_energy_cost`

### Audit

- `AuditConfiguration.inter_region_plasticity_enabled: bool = False`
- Added to `full_organism_with_confidence_and_evolution` preset.

## Event types

- `REGION_PATHWAY_REINFORCED`
- `REGION_PATHWAY_WEAKENED`
- `REGION_PATHWAY_STABILIZED`
- `INTER_REGION_PLASTICITY_APPLIED`

## Test coverage

1. Engine importable and initializable
2. Compute region activation (true/false)
3. Reinforce pathway when source precedes target
4. Weaken pathway when target precedes source
5. Clamp pathway_strength in [0,1]
6. Low energy reduces plasticity but does not zero it
7. Confidence modulates plasticity
8. Records events in MorphologicalMemory
9. Orchestrator integrates `inter_region_plasticity_enabled`
10. Benchmark includes pathway metrics
11. Audit remains compatible
12. Compute delta tick within/outside window
13. Isolated region compensatory strengthening

## Acceptance criteria

- [x] `InterRegionPlasticityEngine` exists and is importable.
- [x] Pathway STDP works (LTP/LTD based on temporal order).
- [x] Energy and confidence modulation implemented.
- [x] Events recorded in `MorphologicalMemory`.
- [x] Orchestrator integrates the engine behind a toggle.
- [x] Benchmark reports T23 metrics.
- [x] Audit T20 compatible with new flag.
- [x] All tests pass; coverage stays ≥ 85%.
- [x] `docs/INTER_REGION_PLASTICITY_SPEC.md` created.

## Post-T23 next step

T24 — Deep Region Specialization (limbic, cerebellar, default-mode regions) or T24 — Cross-Region Memory Consolidation (hippocampal → cortical replay-driven plasticity).
