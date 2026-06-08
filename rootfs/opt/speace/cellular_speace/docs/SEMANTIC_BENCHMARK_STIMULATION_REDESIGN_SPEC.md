# T43C — Semantic Benchmark Stimulation Redesign

**Version:** v0.3.32-t43c-semantic-benchmark-stimulation-redesign  
**Date:** 2026-05-17  
**Status:** Implemented  
**Depends on:** T43 (Semantic Cell Assembly Memory), T43B (Functional Audit)

## 1. Objective

Redesign semantic benchmark stimulation so that repeated patterns can form, stabilize, consolidate, and be recalled — addressing the T43B finding that assemblies form but recall and consolidation remain unobservable.

## 2. Problem Statement (from T43B)

T43B real-run findings:
- `assembly_count` > 0 (assemblies form)
- `recall_success_rate` = 0.0 everywhere (recall never succeeds)
- `consolidated_assembly_count` = 0 everywhere (no consolidation)
- `cognitive_score`, `coherence_phi`, `energy_efficiency` identical across profiles

Root cause: stimulation was generic and insufficient for:
1. Pattern distinctness → assemblies overlap
2. Repetition pressure → recurrence_count stays low
3. Consolidation window → no dedicated stabilization time
4. Recall query mismatch → query was input pattern, not full circuit activation vector

## 3. Architecture

### 3.1 Package

`speace_core/cellular_brain/analysis/`

### 3.2 Files

| File | Role |
|---|---|
| `semantic_stimulation_designer.py` | Designer class, profiles, metrics, verdict logic |
| `test_semantic_stimulation_designer.py` | 24+ tests |
| `docs/SEMANTIC_BENCHMARK_STIMULATION_REDESIGN_SPEC.md` | This document |
| `reports/semantic_stimulation/` | Generated JSON/Markdown reports |

## 4. Models

### 4.1 SemanticStimulus

| Field | Type | Description |
|---|---|---|
| stimulus_id | str | Unique identifier |
| pattern | list[float] | Input activation pattern |
| label | str | Human-readable label |
| target_region | str | "hippocampus" or "prefrontal" |
| repetitions | int | How many times to present |
| interval_ticks | int | Ticks between presentations |
| amplitude | float | Input amplitude multiplier |
| noise_level | float | Noise added during presentation |
| expected_assembly_signature | str \| None | Expected matching assembly |

### 4.2 SemanticRecallProbe

| Field | Type | Description |
|---|---|---|
| probe_id | str | Unique identifier |
| cue_pattern | list[float] | Degraded/noisy cue |
| expected_label | str | Expected matching stimulus label |
| partial_cue_ratio | float | Fraction of pattern retained |
| noise_level | float | Noise added to cue |
| recall_threshold | float | Similarity threshold for success |

### 4.3 SemanticStimulationProfile

| Field | Type | Default |
|---|---|---|
| profile_name | str | — |
| repeated_stimuli_count | int | 3 |
| novel_stimuli_count | int | 2 |
| repetitions_per_stimulus | int | 6 |
| consolidation_ticks | int | 3 |
| recall_trials | int | 5 |
| cue_degradation_ratio | float | 0.5 |
| stimulation_amplitude | float | 1.0 |
| semantic_memory_enabled | bool | True |
| consolidation_enabled | bool | True |
| recall_enabled | bool | True |
| reactivation_enabled | bool | False |
| pattern_size | int | 10 |
| pattern_separation | float | 0.5 |
| seed | int | 42 |

## 5. SemanticStimulationDesigner

### 5.1 Pattern Generation

`generate_distinct_patterns(count, size, separation=0.5, seed=42)`
- Generates structured binary-ish patterns with controlled randomness
- Ensures minimum Euclidean distance between any pair
- Fallback for insufficient separation

### 5.2 Protocol Phases

**Encoding Phase:**
1. For each stimulus, inject pattern × `repetitions`
2. Run 1 tick after each injection
3. Run manual semantic cycle (observe → match/create → reinforce)

**Consolidation Phase:**
1. Run `consolidation_ticks` with no new input
2. Each tick: observe → match → reinforce → decay → consolidate

**Recall Phase:**
1. Build partial/noisy cues from repeated stimuli
2. Inject cue, run 1 tick
3. Extract full activation vector via `recall_from_current_activation`
4. Record success/failure
5. Also test noisy variant with extra noise

### 5.3 Key Fixes over T43B

1. **Full-vector recall:** Uses circuit activation vector after cue presentation, not raw input pattern
2. **Higher repetition:** Default 6 repetitions vs T43B's 2
3. **Lower thresholds:** `similarity_threshold=0.65`, `min_neurons=2`, `min_mean_activation=0.05`
4. **Consolidation window:** Dedicated ticks after encoding
5. **Partial cues:** Recall uses degraded patterns, testing robustness
6. **Region targeting:** Hippocampus/prefrontal neuron tagging for targeted profiles

## 6. Profiles

| # | Profile | Key Parameters |
|---|---|---|
| 1 | semantic_off_control | Disabled baseline |
| 2 | weak_repetition | 2 repetitions |
| 3 | strong_repetition | 8 repetitions, 5 consolidation ticks |
| 4 | high_separation_patterns | separation=0.8 |
| 5 | partial_cue_recall | cue_degradation=0.3 |
| 6 | noisy_recall | cue_degradation=0.5 + noise |
| 7 | consolidation_heavy | 8 repetitions, 8 consolidation ticks |
| 8 | hippocampus_targeted | region="hippocampus" |
| 9 | hippocampus_prefrontal_reactivation | region tags + reactivation |
| 10 | full_semantic_stimulation | 8 reps, 5 consolidation, partial cues, reactivation |

## 7. Metrics

- stimulus_count, repeated_stimulus_count, novel_stimulus_count
- pattern_separation_mean, pattern_separation_min
- encoding_events, assembly_created_events, assembly_reinforced_events, assembly_consolidated_events
- recall_attempts, recall_successes, recall_failures, recall_success_rate
- partial_cue_success_rate, noisy_cue_success_rate
- mean_assembly_strength, mean_assembly_stability, mean_recurrence_count
- semantic_discrimination_score (inter-assembly signature distance)
- semantic_consolidation_score (fraction consolidated)
- semantic_stimulation_effectiveness (clamped [0, 1])
- cognitive_delta, phi_delta, energy_delta

## 8. Effectiveness Formula

```
semantic_stimulation_effectiveness =
  0.25 * recall_success_rate
  + 0.20 * semantic_discrimination_score
  + 0.20 * semantic_consolidation_score
  + 0.15 * mean_assembly_stability
  + 0.10 * max(0, phi_delta)
  + 0.10 * max(0, cognitive_delta)
```

Clamped to [0.0, 1.0].

## 9. Verdict Logic

- **SEMANTIC_STIMULATION_VALIDATED:** recall > 0.2 and effectiveness > 0.25 without regression
- **SEMANTIC_ENCODING_ONLY:** assemblies form but recall = 0
- **SEMANTIC_CONSOLIDATION_WEAK:** recall attempts exist but no consolidation
- **SEMANTIC_RECALL_WEAK:** 0 < recall < 0.2
- **SEMANTIC_DISCRIMINATION_FAILURE:** distinct stimuli collapse into overlapping assemblies
- **SEMANTIC_OVERACTIVATION:** energy regression > 0.3
- **SEMANTIC_GLOBAL_NO_EFFECT:** assemblies exist but global metrics unchanged
- **INSUFFICIENT_EVIDENCE:** no clear signal

## 10. Tests

24 tests covering:
1. SemanticStimulus model
2. SemanticRecallProbe model
3. SemanticStimulationProfile model
4. SemanticStimulationDesigner initialization
5. generate_distinct_patterns returns correct count
6. generated patterns meet minimum separation
7. build_stimulus_sequence creates repeated and novel stimuli
8. inject_semantic_stimulus affects orchestrator state
9. encoding phase creates assemblies
10. repetition increases recurrence_count
11. consolidation phase runs without collapse
12. recall probes are partial cues
13. recall phase records attempts
14. noisy recall remains bounded
15. hippocampus_targeted profile tags regions
16. full_semantic_stimulation produces metrics
17. semantic_stimulation_effectiveness clamped to [0,1]
18. verdict belongs to allowed set
19. JSON report generated
20. Markdown report contains required fields
21. deterministic seed gives reproducible results
22. semantic_off_control has no false positives
23. no unbounded activation
24. T43B audit still works

## 11. Acceptance Criteria

- All existing 774 tests still pass
- New tests pass
- Coverage remains >= 85%
- At least one profile creates assemblies
- At least one profile reinforces assemblies
- At least one profile attempts recall
- Reports saved in reports/semantic_stimulation/
- Commit and tag as v0.3.32-t43c-semantic-benchmark-stimulation-redesign

## 12. Evolutionary Branch Logic

After T43C, the branch depends on verdict:

| Verdict | Next Task |
|---|---|
| VALIDATED | T44 — Associative Learning Between Assemblies |
| ENCODING_ONLY | T43D — Semantic Consolidation Trigger Redesign |
| CONSOLIDATION_WEAK | T43D — Assembly Consolidation Threshold Tuning |
| RECALL_WEAK | T43D — Semantic Recall Sensitivity Tuning |
| DISCRIMINATION_FAILURE | T43D — Pattern Separation / Assembly Orthogonalization |
| OVERACTIVATION | T43D — Semantic Reactivation Safety Controller |
| GLOBAL_NO_EFFECT | T43D — Semantic-Cognitive Coupling Integration |
| INSUFFICIENT_EVIDENCE | T43D — Semantic Audit Instrumentation Patch |

## 13. Commit Tag

`v0.3.32-t43c-semantic-benchmark-stimulation-redesign`
