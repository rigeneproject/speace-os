# T30 — Pathway Utility Learning / Reward-Modulated Plasticity v0.3 — Specification

## Overview

T29 made plasticity *safety-gated* (causal score, energy, confidence) but not yet *value-gated*. T29 verdict remains `routing_validated_plasticity_weak` because the system lacks memory of which pathways historically improve or degrade system function.

T30 introduces reward-modulated plasticity:
1. **Reward signal** — computed from before/after metrics deltas
2. **Pathway utility records** — per-pathway EMA tracking of reward, cost, and utility
3. **Utility gate** — blocks LTP on pathways with negative utility, allows LTD
4. **Memory event logging** — reward computed, utility positive/negative, gate applied

Biologically: real synapses learn via reinforcement — useful connections strengthen, harmful ones weaken. T30 implements the same principle at the inter-region pathway level.

## Architecture

### New module

- `speace_core/cellular_brain/regions/pathway_utility_learner.py`

### Modified modules

- `speace_core/cellular_brain/regions/pathway_plasticity_tuner.py` — `utility_guard_enabled`, `min_utility_for_ltp`, `utility_learner` parameter
- `speace_core/cellular_brain/benchmark/neurofunctional_benchmark.py` — T30 metrics extraction from events
- `speace_core/cellular_brain/calibration/pathway_calibrator.py` — T30 profiles (p11-p12), utility columns in report
- `speace_core/cellular_brain/memory/morphology_events.py` — 5 new event types
- `tests/regions/test_pathway_utility_learner.py` — 17 tests

## Models

### PathwayUtilityRecord

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `source_region_id` | str | — | Source region |
| `target_region_id` | str | — | Target region |
| `pathway_id` | str | — | Composite ID |
| `utility_score` | float | 0.0 | Computed utility |
| `reward_ema` | float | 0.0 | Exponential moving average of rewards |
| `cost_ema` | float | 0.0 | EMA of costs |
| `stability_ema` | float | 0.0 | EMA of stability |
| `update_count` | int | 0 | Number of updates |
| `positive_updates` | int | 0 | Reward > 0 count |
| `negative_updates` | int | 0 | Reward < 0 count |
| `last_reward` | float | 0.0 | Last computed reward |
| `last_cost` | float | 0.0 | Last cost |
| `last_delta_phi` | float | 0.0 | Last phi delta |
| `last_delta_cognitive_score` | float | 0.0 | Last cognitive delta |
| `last_delta_energy` | float | 0.0 | Last energy delta |

### PathwayRewardSignal

| Field | Type | Description |
|-------|------|-------------|
| `delta_cognitive_score` | float | Cognitive score change |
| `delta_phi` | float | Coherence phi change |
| `delta_energy_efficiency` | float | Energy efficiency change |
| `delta_functional_improvement` | float | Functional improvement change |
| `routing_cost` | float | Energy cost of routing |
| `plasticity_cost` | float | Energy cost of plasticity |
| `composite_reward` | float | Combined reward, clamped to [-1, 1] |

### PathwayUtilityLearningResult

| Field | Type | Description |
|-------|------|-------------|
| `updated_pathways` | int | Total pathways evaluated |
| `rewarded_pathways` | int | Positive reward count |
| `penalized_pathways` | int | Negative reward count |
| `mean_utility_score` | float | Average utility across pathways |
| `best_pathway_id` | str \| None | Highest utility pathway |
| `worst_pathway_id` | str \| None | Lowest utility pathway |

## PathwayUtilityLearner

### Constructor

- `alpha: float = 0.2` — EMA smoothing factor
- `cost_penalty: float = 0.5` — Weight of cost in utility score

### Methods

- `compute_reward_signal(before_metrics, after_metrics, routing_cost, plasticity_cost) -> PathwayRewardSignal`

  Formula:
  ```
  composite_reward =
    0.35 * delta_cognitive_score
  + 0.30 * delta_phi
  + 0.15 * delta_functional_improvement
  + 0.10 * delta_energy_efficiency
  - 0.10 * routing_cost
  - 0.10 * plasticity_cost
  ```
  Clamped to `[-1.0, 1.0]`.

- `update_pathway_utility(pathway_id, source, target, reward_signal, memory) -> PathwayUtilityRecord`

  Updates EMAs:
  ```
  reward_ema = alpha * reward + (1-alpha) * reward_ema
  cost_ema = alpha * (routing_cost + plasticity_cost) + (1-alpha) * cost_ema
  utility_score = reward_ema - cost_penalty * cost_ema
  ```

  Records `PATHWAY_REWARD_COMPUTED` and `PATHWAY_UTILITY_POSITIVE`/`NEGATIVE` events.

- `reward_all_pathways(registry, before_metrics, after_metrics, routing_cost, plasticity_cost, memory) -> PathwayUtilityLearningResult`

  Computes reward for all connections and returns summary.

- `apply_utility_gate(pathway_id, candidate_update_type) -> (bool, str)`

  Rules:
  - No history: proceed (`no_utility_history`)
  - `utility_score < -0.05`: block LTP, allow LTD/skip (`utility_negative_blocks_ltp`)
  - `utility_score > 0.05`: allow LTP (`utility_positive_allows_ltp`)
  - Neutral: proceed (`utility_neutral`)

- `get_utility_score(pathway_id) -> float`
- `summarize_utilities() -> Dict[str, Any]`
- `reset_utilities()`

## Integration with T29 PathwayPlasticityTuner

### PathwayTuningProfile additions

- `utility_guard_enabled: bool = False`
- `min_utility_for_ltp: float = 0.0`

### gate_update

Added optional parameters:
- `utility_learner = None`
- `pathway_id: str = ""`
- `update_type: str = ""`

If `utility_guard_enabled` and learner provided:
- Calls `apply_utility_gate` before other gates
- Records `PATHWAY_UTILITY_GATE_APPLIED` event on skip

### tune_pathway_update

Added optional parameters:
- `utility_learner = None`
- `pathway_id: str = ""`

### tune_all_pathways

Added optional parameter:
- `utility_learner = None`

## New MorphologyEventType values

- `PATHWAY_REWARD_COMPUTED`
- `PATHWAY_UTILITY_UPDATED`
- `PATHWAY_UTILITY_POSITIVE`
- `PATHWAY_UTILITY_NEGATIVE`
- `PATHWAY_UTILITY_GATE_APPLIED`

## Benchmark metrics (T30)

Added to `BenchmarkMetrics`:

- `mean_pathway_utility`
- `best_pathway_utility`
- `worst_pathway_utility`
- `rewarded_pathways`
- `penalized_pathways`
- `pathway_reward_mean`
- `pathway_cost_mean`
- `utility_gated_updates`
- `utility_skipped_updates`

## Calibration profiles (T30)

Added to `PathwayCalibrator.default_profiles()`:

| ID | Name | Description |
|---|---|---|
| p11 | routing_plus_tuning_with_utility_learning | Routing + T29 tuning + T30 utility learning |
| p12 | routing_plus_tuning_utility_negative_penalty | Routing + T29 tuning + T30 aggressive penalty |

## Acceptance criteria

- [x] `PathwayUtilityLearner` exists and is importable
- [x] `compute_reward_signal` correctly applies formula and clamps
- [x] `update_pathway_utility` updates EMAs and tracks positive/negative updates
- [x] Memory events recorded: `PATHWAY_REWARD_COMPUTED`, `PATHWAY_UTILITY_POSITIVE`, `PATHWAY_UTILITY_NEGATIVE`
- [x] `apply_utility_gate` blocks LTP on negative utility, allows LTD
- [x] `summarize_utilities` returns correct statistics
- [x] `reset_utilities` clears state
- [x] `PathwayPlasticityTuner` integrates utility gate
- [x] `BenchmarkMetrics` extracts T30 metrics from events
- [x] Markdown/JSON reports include T30 columns
- [x] 385+ tests pass; coverage stays ≥ 85% (89.01%)
- [x] `docs/PATHWAY_UTILITY_LEARNING_SPEC.md` created

## Post-T30 next step

- Run full calibration suite with T30 profiles
- If utility learning shows functional improvement → T31 Deep Region Specialization
- If still weak → T31 Homeostatic Stabilization before specialization
