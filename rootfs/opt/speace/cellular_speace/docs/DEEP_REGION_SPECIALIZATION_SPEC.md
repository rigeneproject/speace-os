# T31 — Deep Region Specialization v0.3 — Specification

## Overview

T30 completed reward-modulated plasticity with utility learning. The system now evaluates pathway usefulness but operates on a minimal 4-region pipeline:

sensory → hippocampus → prefrontal → motor

T31 extends this to an 8-region deep architecture:

sensory → limbic → hippocampus → default_mode → prefrontal → cerebellar → motor

with brainstem_homeostatic connected bidirectionally to all regions.

The timing is right because T30's utility learning ensures new regions are not just added complexity — each new pathway will be evaluated for reward, cost, and functional impact.

## New regions

### limbic
- **Role**: salience_valence_regulation
- **Function**: threat_level, novelty_score, urgency, reward_valence
- **Decides**: what deserves attention, memory, energy, or inhibition

### cerebellar
- **Role**: error_correction_prediction
- **Function**: reduce error between predicted and actual output, stabilize repetitive patterns, optimize micro-corrections

### default_mode
- **Role**: internal_simulation_consolidation
- **Function**: reflection, consolidation, offline simulation, self-modeling from morphological memory

### brainstem_homeostatic
- **Role**: metabolic_arousal_survival_control
- **Function**: energy regulation, tick/burst frequency, neurogenesis/apoptosis gating, collapse protection

## Architecture

### New module

- `speace_core/cellular_brain/regions/deep_region_specialization.py`

### Modified modules

- `speace_core/dna/genome/default_genome.yaml` — 4 new regions + cell differentiation rules
- `speace_core/cellular_brain/regions/region_factory.py` — `DEEP_REGION_PIPELINE`, fallback assignments
- `speace_core/cellular_brain/benchmark/neurofunctional_benchmark.py` — 9 new metrics
- `speace_core/cellular_brain/memory/morphology_events.py` — 3 new event types
- `tests/regions/test_deep_region_specialization.py` — 14 tests

## Genome changes

### brain_regions (8 regions)

| Region | neuron_fraction | plasticity_bias | role_description |
|--------|----------------|-----------------|------------------|
| sensory | 0.15 | 0.5 | Input encoding |
| limbic | 0.08 | 0.9 | Salience, valence, urgency |
| hippocampus | 0.18 | 0.9 | Pattern memory |
| default_mode | 0.08 | 0.8 | Internal simulation |
| prefrontal | 0.25 | 0.7 | Planning, control |
| cerebellar | 0.08 | 0.6 | Error correction |
| motor | 0.15 | 0.4 | Output execution |
| brainstem_homeostatic | 0.03 | 0.3 | Metabolic, arousal |

### cell_differentiation_rules (4 new neuron types)

- `limbic_neuron` — salience role, plasticity 1.2
- `cerebellar_neuron` — error_correction role, plasticity 0.9
- `default_mode_neuron` — consolidation role, plasticity 1.1
- `brainstem_neuron` — homeostasis role, plasticity 0.8

## DeepRegionSpecialization

### DEEP_REGION_PIPELINE

```
["sensory", "limbic", "hippocampus", "default_mode", "prefrontal", "cerebellar", "motor"]
```

### DEEP_PATHWAYS (13 connections)

| Source | Target | Type |
|--------|--------|------|
| sensory | limbic | salience |
| limbic | prefrontal | valence |
| hippocampus | default_mode | consolidation |
| default_mode | prefrontal | reflection |
| prefrontal | cerebellar | prediction |
| cerebellar | motor | correction |
| brainstem_homeostatic | sensory | arousal |
| brainstem_homeostatic | limbic | arousal |
| brainstem_homeostatic | hippocampus | arousal |
| brainstem_homeostatic | default_mode | arousal |
| brainstem_homeostatic | prefrontal | arousal |
| brainstem_homeostatic | cerebellar | arousal |
| brainstem_homeostatic | motor | arousal |

Plus backward feedback from all regions to brainstem_homeostatic.

### Methods

- `extend_region_connectome(registry) -> int` — adds deep pathways, returns count added
- `apply_deep_region_specialization(registry, memory) -> Dict[str, Any]` — full application + events
- `validate_deep_region_architecture(registry) -> (bool, List[str])` — checks all regions/pathways present
- `compute_region_role_alignment(registry) -> float` — 0-1 score based on description + neuron count
- `compute_region_specialization_diversity(registry) -> float` — unique dominant cell types / max possible
- `compute_deep_region_signal_flow(registry) -> float` — mean_strength * active_fraction * density
- `compute_deep_region_metrics(registry) -> Dict[str, float]` — all 8 metrics in one dict

## RegionFactory changes

- `DEEP_REGION_PIPELINE` added
- `build_from_genome(..., deep_regions_enabled: bool = True)`
- `_assign_fallback_regions(..., deep_regions_enabled: bool = True)`
- When `deep_regions_enabled=True`: uses 8-region pipeline and fallback assignments

## Benchmark metrics (T31)

| Metric | Source |
|--------|--------|
| `deep_region_count` | `len(registry.regions)` |
| `limbic_salience_score` | neuron_count * connectivity / 10 |
| `cerebellar_error_correction_score` | neuron_count * connectivity / 10 |
| `default_mode_consolidation_score` | neuron_count * connectivity / 10 |
| `brainstem_homeostatic_stability_score` | neuron_count * connectivity / 10 |
| `deep_region_signal_flow` | `compute_deep_region_signal_flow` |
| `region_specialization_diversity` | `compute_region_specialization_diversity` |
| `region_role_alignment_score` | `compute_region_role_alignment` |

## Acceptance criteria

- [x] `DeepRegionSpecialization` exists and is importable
- [x] `extend_region_connectome` adds expected deep pathways
- [x] `apply_deep_region_specialization` records `DEEP_REGION_SPECIALIZATION_APPLIED` events
- [x] `validate_deep_region_architecture` returns True when all regions/pathways present
- [x] `validate_deep_region_architecture` reports missing items when incomplete
- [x] `compute_region_role_alignment` returns 1.0 for complete architecture
- [x] `compute_region_specialization_diversity` > 0 for distinct regions
- [x] `compute_deep_region_signal_flow` > 0 when pathways exist
- [x] `compute_deep_region_metrics` returns all 8 metrics
- [x] `RegionFactory` supports `deep_regions_enabled` parameter
- [x] `default_genome.yaml` contains 8 brain_regions and 4 new neuron types
- [x] Benchmark extracts and reports T31 metrics
- [x] 395+ tests pass; coverage ≥ 85%
- [x] `docs/DEEP_REGION_SPECIALIZATION_SPEC.md` created

## Post-T31 next step

- Run full calibration suite to verify deep regions do not regress cognitive score
- If deep regions improve or stabilize → T32 Deep Region Functional Audit
- If energy regression → T32 Brainstem Energy Arbitration
- If Φ regression → T32 Region-Level Stability Controller
