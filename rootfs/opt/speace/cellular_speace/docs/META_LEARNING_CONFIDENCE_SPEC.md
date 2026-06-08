# MetaLearningConfidence v0.3 — Specification

## Overview

T19 introduces metacognition to SPEACE Digital Cellular Brain. After T15 closed the external evolutionary loop, T19 adds an internal self-evaluation layer that estimates confidence, uncertainty, decision stability, and produces adaptive recommendations. This transforms SPEACE from a reactive system into a self-aware neurocellular organism.

Biologically: a brain that cannot assess its own uncertainty is brittle. A brain with metacognition can choose when to learn, when to stabilize, and when to grow.

## Architecture

### New module

- `speace_core/cellular_brain/metacognition/__init__.py`
- `speace_core/cellular_brain/metacognition/confidence_engine.py`

### Modified modules

- `speace_core/orchestrator.py` — `confidence_enabled`, `_confidence`, `last_confidence_state`, soft recommendation flags
- `speace_core/cellular_brain/benchmark/neurofunctional_benchmark.py` — meta-cognitive metrics
- `speace_core/cellular_brain/memory/morphology_events.py` — `CONFIDENCE_EVALUATED`

## Models

### ConfidenceState

| Field | Type | Description |
|-------|------|-------------|
| `confidence_score` | float | Overall confidence [0, 1] |
| `uncertainty_score` | float | `1.0 - confidence_score` |
| `output_entropy` | float | Normalized output entropy |
| `activation_margin` | float | Top - second-top output |
| `decision_stability` | float | Cosine similarity with recent history |
| `error_risk` | float | Estimated risk of wrong output |
| `recommended_action` | str | Adaptive recommendation |
| `adaptation_pressure` | float | Combined urgency signal |
| `neurogenesis_recommended` | bool | Flag for T8 |
| `plasticity_reduction_recommended` | bool | Flag for T13 |
| `stabilization_recommended` | bool | Flag for T14 |

### ConfidenceTrace

| Field | Type | Description |
|-------|------|-------------|
| `trace_id` | str | Unique trace ID |
| `tick_id` | Optional[int] | Orchestrator tick |
| `burst_id` | Optional[int] | Burst counter |
| `confidence_state` | ConfidenceState | Full state snapshot |
| `output_activations` | List[float] | Raw output activations |
| `phi` | float | Coherence at trace time |
| `mean_energy` | float | Mean energy at trace time |
| `community_count` | Optional[int] | T17 community count |
| `modularity_proxy` | Optional[float] | T17 modularity |
| `timestamp` | str | ISO timestamp |

## ConfidenceEngine

### Constructor

- `low_confidence_threshold: float = 0.35`
- `high_confidence_threshold: float = 0.75`
- `instability_threshold: float = 0.50`
- `entropy_weight: float = 0.30`
- `margin_weight: float = 0.30`
- `phi_weight: float = 0.20`
- `stability_weight: float = 0.20`
- `history_window: int = 3`

### Methods

- `evaluate(circuit, metrics=None, community_result=None, memory=None) -> ConfidenceState`
  1. Compute output entropy
  2. Compute activation margin
  3. Compute decision stability (via output history)
  4. Compute confidence score
  5. Compute error risk
  6. Determine recommendation
  7. Set boolean flags
  8. Record `CONFIDENCE_EVALUATED` event in memory

- `compute_output_entropy(output_activations) -> float`
  - Normalized Shannon entropy of output activations
  - High entropy = flat output = low confidence

- `compute_activation_margin(output_activations) -> float`
  - `top_output - second_output`, clamped to [0, 1]

- `compute_decision_stability(output_activations) -> float`
  - Cosine similarity with most recent history entry
  - Maintains rolling window of `history_window` outputs

- `compute_error_risk(confidence, phi, mean_energy) -> float`
  - `risk = (1 - confidence) * 0.4 + (1 - phi) * 0.3 + |energy - 0.5| * 0.3`
  - Clamped to [0, 1]

- `recommend_action(confidence, phi, mean_energy, error_risk, community_result=None) -> str`
  - Deterministic rule-based recommendation:
    - `confidence >= 0.75` and `phi >= 0.5`:
      - `error_risk > 0.5` → `reduce_plasticity`
      - else → `maintain`
    - `confidence < 0.35` and `phi < 0.4` → `stabilize`
    - `confidence < 0.50` and `error_risk > 0.4` → `increase_inhibition`
    - `confidence < 0.35` and `isolated_neurons > 2` → `community_guided_neurogenesis`
    - `confidence < 0.35` and `mean_energy >= 0.3` → `recommend_neurogenesis`
    - default → `increase_plasticity`

## Orchestrator integration

- New field: `_confidence: ConfidenceEngine`
- New field: `confidence_enabled: bool = True`
- New field: `last_confidence_state: ConfidenceState | None = None`
- New soft flags:
  - `neurogenesis_recommended: bool = False`
  - `stabilization_recommended: bool = False`
  - `plasticity_reduction_recommended: bool = False`
- Initialized in `model_post_init`
- In `_tick()`, after community detection:
  ```python
  if self.confidence_enabled:
      self.last_confidence_state = self._confidence.evaluate(
          self.circuit,
          metrics=metrics,
          community_result=self.last_community_result,
          memory=self._memory,
      )
      self.neurogenesis_recommended = self.last_confidence_state.neurogenesis_recommended
      self.stabilization_recommended = self.last_confidence_state.stabilization_recommended
      self.plasticity_reduction_recommended = self.last_confidence_state.plasticity_reduction_recommended
  ```

## Benchmark integration

`BenchmarkMetrics` gains eight T19 fields:

| Metric | Source |
|--------|--------|
| `confidence_score` | `last_confidence_state.confidence_score` |
| `uncertainty_score` | `last_confidence_state.uncertainty_score` |
| `output_entropy` | `last_confidence_state.output_entropy` |
| `decision_stability` | `last_confidence_state.decision_stability` |
| `error_risk` | `last_confidence_state.error_risk` |
| `recommended_action` | `last_confidence_state.recommended_action` |
| `meta_cognitive_score` | Computed from confidence components |

`meta_cognitive_score` formula:
```
meta_cognitive_score =
  0.40 * confidence_score
  + 0.30 * decision_stability
  + 0.20 * (1.0 - error_risk)
  + 0.10 * coherence_phi
```
Clamped to [0, 1].

The `speace_cognitive_score` formula is **not modified** in T19 to avoid regressions.

## MorphologicalMemory integration

- New event type: `CONFIDENCE_EVALUATED`
- Fired whenever `evaluate()` runs with `memory` provided
- Metadata contains all confidence fields

## Test coverage

1. Engine is importable
2. Output entropy is high for flat outputs
3. Output entropy is low for peaked outputs
4. Empty output yields zero entropy
5. Activation margin computed correctly for clear winner
6. Activation margin is zero for tie
7. Activation margin is zero for single output
8. Decision stability is 1.0 on first call
9. Decision stability is high for similar consecutive outputs
10. Decision stability is low for different outputs
11. Error risk is high for low confidence/phi/energy
12. Error risk is low for high confidence/phi/optimal energy
13. Error risk is clamped to [0, 1]
14. Recommend maintain for high confidence + high phi
15. Recommend reduce_plasticity for high confidence + high error risk
16. Recommend stabilize for low confidence + low phi
17. Recommend neurogenesis for low confidence + sufficient energy
18. Recommend increase_inhibition for unstable state
19. Recommend community_guided for low confidence + isolated neurons
20. evaluate returns valid ConfidenceState
21. evaluate records CONFIDENCE_EVALUATED event
22. evaluate produces a valid recommendation
23. Orchestrator has confidence_enabled and _confidence
24. Orchestrator tick populates last_confidence_state
25. Orchestrator skips confidence when disabled
26. Benchmark includes all confidence metrics
27. meta_cognitive_score is in [0, 1]
28. No regression on 202 existing tests

## Acceptance criteria

- [x] `ConfidenceEngine` exists and is importable.
- [x] `ConfidenceState` and `ConfidenceTrace` implemented.
- [x] `confidence_score` and `uncertainty_score` computed in [0, 1].
- [x] `output_entropy`, `activation_margin`, `decision_stability` computed.
- [x] `recommended_action` produced deterministically.
- [x] Orchestrator integrates `confidence_enabled` and `last_confidence_state`.
- [x] Soft recommendation flags populated.
- [x] `MorphologicalMemory` records `CONFIDENCE_EVALUATED`.
- [x] `NeuroFunctionalBenchmark` measures meta-cognitive metrics.
- [x] `meta_cognitive_score` computed separately from `speace_cognitive_score`.
- [x] All tests pass; coverage stays ≥ 85%.
- [x] `docs/META_LEARNING_CONFIDENCE_SPEC.md` created.

## Post-T19 next step

T20 — Integrated Neurocellular Evolution Audit (validate T7–T19 as a unified organism).
