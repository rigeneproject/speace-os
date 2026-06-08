# NeuroFunctionalBenchmark v0.2 — Specification

## Overview

The `NeuroFunctionalBenchmark` is the epistemic validator of SPEACE v0.2. It does not add new cognitive capabilities; it measures whether the minimal cellular lifecycle already implemented (T7→T8→T9→T10) produces real functional improvement, stabilization, and useful morphological transformation.

After T7–T10, SPEACE is a self-modifying digital cellular brain. T11 asks: does this self-modification actually help?

## Purpose

T11 must answer these questions:

1. Does SPEACE improve after feedback?
2. Does neurogenesis increase capacity or only complexity?
3. Does apoptosis reduce noise and cost without collapsing function?
4. Does differentiation produce more functional regions/cell types?
5. Does morphological memory record a useful trajectory?
6. Does Φ improve or stabilize over time?
7. Does energy remain stable?
8. Does the network become more efficient?

## Architecture

### Modules

- `speace_core/cellular_brain/benchmark/neurofunctional_benchmark.py` — core engine
- `tests/neurofunctional/test_neurofunctional_benchmark.py` — test suite
- `reports/neurofunctional/` — JSON and Markdown report output directory

### Data models

**BenchmarkState** — snapshot of circuit state at a single point in time:
- `neuron_count`, `synapse_count`, `active_synapse_count`
- `coherence_phi`, `mean_energy`, `accuracy`, `output_activations`

**BenchmarkMetrics** — delta and composite metrics:
- `accuracy_score`, `coherence_phi`, `phi_trend`
- `mean_energy`, `energy_efficiency`
- `neuron_count_delta`, `synapse_count_delta`
- `neurogenesis_events`, `apoptosis_events`, `cell_differentiation_events`
- `adaptation_gain`, `morphological_stability`, `morphological_adaptation`
- `structural_complexity`, `functional_improvement`
- `speace_cognitive_score`

**BenchmarkResult** — container:
- `case_name`, `baseline_state`, `final_state`, `metrics`
- `json_report_path`, `markdown_report_path`

## Metric definitions

| Metric | Formula | Range |
|---|---|---|
| `accuracy` | `max(0.0, 1.0 - MAE(target, output_clamped))` | [0, 1] |
| `energy_efficiency` | `clamp(mean_energy, 0.0, 1.0)` | [0, 1] |
| `structural_complexity` | `active_synapses / neuron_count` | [0, ∞) |
| `adaptation_gain` | `accuracy_final - accuracy_baseline` | [-1, 1] |
| `phi_trend` | `phi_final - phi_baseline` | [-1, 1] |
| `morphological_stability` | `1.0 / (1.0 + 0.1·|Δneurons| + 0.01·|Δsynapses|)` | (0, 1] |
| `functional_improvement` | `max(0, adaptation_gain) + max(0, phi_trend)` | [0, 2] |
| `morphological_adaptation` | `1.0` if `functional_improvement > 0` and structural change > 0, else `0.0` | {0, 1} |
| `safety_score` | `1.0` if `neuron_count >= 5` and `phi > 0.0`, else `0.0` | {0, 1} |
| `speace_cognitive_score` | `0.20·accuracy + 0.20·phi + 0.15·max(0,adaptation_gain) + 0.15·energy_efficiency + 0.10·stability + 0.10·max(0,phi_trend) + 0.10·safety_score`, clamped to [0,1] | [0, 1] |

## Benchmark cases

### 1. adaptation_after_error
- Inject a pattern, apply negative feedback, then positive feedback.
- Verify that Φ, energy, and accuracy stay within valid ranges.
- Demonstrates stabilization after error-correction.

### 2. useful_neurogenesis
- Force neurogenesis conditions (negative feedback count, sufficient energy).
- Verify neuron count increases, at least one `NEURON_CREATED` event exists, and Φ does not collapse.
- Demonstrates structural growth without functional breakdown.

### 3. useful_apoptosis
- Inject a weak, expensive, isolated neuron into the hidden layer.
- Run apoptosis cycle.
- Verify the weak element is removed or synapses are pruned, and the network does not collapse (`accuracy >= 0`, `neuron_count >= 5`).
- Demonstrates selective elimination preserves function.

### 4. differentiation_consistency
- Add undifferentiated neurons with `region="hippocampus"` and `region="prefrontal"`.
- Run differentiation.
- Verify correct `cell_type` assignment and `CELL_DIFFERENTIATED` events in memory.
- Demonstrates genome-driven specialization.

### 5. morphological_memory_trace
- Execute a full adaptive cycle: feedback → neurogenesis → apoptosis → differentiation.
- Verify `MorphologicalMemory` contains snapshots, a computable `phi_trend`, and events for all three engine types.
- Demonstrates that SPEACE not only changes, but records the trajectory of its own transformation.

## Report generation

The benchmark produces both machine-readable and human-readable reports:

- `reports/neurofunctional/benchmark_<timestamp>.json` — full `BenchmarkResult` dump
- `reports/neurofunctional/benchmark_<timestamp>.md` — human-readable table with all metrics
- `reports/neurofunctional/latest_report.json` — symlink-like copy of latest JSON
- `reports/neurofunctional/latest_report.md` — symlink-like copy of latest Markdown

The JSON is intended for future `EvolutionEngine` (T15). The Markdown serves human operators.

## Integration

- `NeuroFunctionalBenchmark` wraps an existing `CellularBrainOrchestrator`.
- It uses `orchestrator.run_ticks()`, `inject()`, `feedback()`, `run_neurogenesis()`, `run_apoptosis()`, `run_differentiation()`.
- It queries `MorphologicalMemory` via `count_events()`, `latest_phi()`, `phi_trend()`, and direct `events` / `snapshots` lists.

## Acceptance criteria

- [x] `NeuroFunctionalBenchmark` is importable.
- [x] At least 5 reproducible benchmark cases exist.
- [x] JSON and Markdown reports are generated and saved to `reports/neurofunctional/`.
- [x] Reports include Φ, energy, event counts, structural deltas, and cognitive score.
- [x] Baseline vs final state comparison is present.
- [x] At least one full adaptive cycle executes: feedback → neurogenesis/apoptosis/differentiation → morphological memory.
- [x] All 81 tests pass (73 existing + 8 new).
- [x] Coverage ≥ 85% (actual: 89.49%).
- [x] `docs/NEUROFUNCTIONAL_BENCHMARK_SPEC.md` created.
