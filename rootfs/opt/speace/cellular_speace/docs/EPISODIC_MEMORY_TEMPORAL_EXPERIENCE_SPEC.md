# T47 — Episodic Memory & Temporal Experience Layer

## Overview

T47 introduces temporal narrative memory into SPEACE. While T43 (Semantic Cell Assembly Memory) stores static concepts and T44 (Associative Learning) stores relationships, T47 stores *sequences* — episodes of experience composed of events, metrics, and outcomes over time.

This enables the system to:
- Remember what happened, when, and in what order
- Detect patterns across episodes (recovery vs regression signatures)
- Recall similar past experiences given current metric states
- Summarize episodes for reporting and metacognitive reflection

## Design Principles

- **Non-destructive**: Episodes are append-only; no events are mutated after recording.
- **Observable**: All episode lifecycle events logged to MorphologicalMemory.
- **Persistent**: Episodes stored in JSONL (`data/episodic_memory/episodes.jsonl`).
- **Conservative**: Lazy initialization in orchestrator; disabled by default unless `episodic_memory_enabled=True`.
- **Isolated**: Tests use temp directories to avoid cross-test state leakage.

## Architecture

### Models

- `EpisodeEvent` — A single event within an episode (event_type, source_module, timestamp, metrics, metadata).
- `Episode` — A complete episode (episode_id, trigger, start/end times, events, initial/final metrics, cognitive/phi/energy deltas, linked assemblies/proposals, semantic tags).

### Engines

- `EpisodicMemory`
  - `start_episode(trigger, initial_metrics)` — begins a new episode
  - `record_event(episode_id, event_type, source_module, ...)` — appends an event
  - `close_episode(episode_id, final_metrics, outcome)` — computes deltas and seals the episode
  - `link_assembly(episode_id, assembly_id)` — links a semantic assembly
  - `link_proposal(episode_id, proposal_id)` — links a self-improvement proposal
  - `get_recent_episodes(limit)` — returns most recent episodes by start_time
  - `load_episodes()` — returns all episodes
  - JSONL persistence via `_persist()` and `_load()`

- `EpisodicRecall`
  - `recall_by_outcome(outcome)` — filter episodes by outcome string
  - `recall_similar_metrics(query_metrics, top_k)` — cosine-similarity ranking over metric vectors
  - `find_regression_precursors()` — event types that precede regression episodes
  - `find_recovery_patterns()` — event types that precede recovery episodes

- `EpisodeSummarizer`
  - `classify(episode)` — maps an episode to one of six categories:
    - `RECOVERY_EPISODE` (positive cognitive/phi deltas)
    - `REGRESSION_EPISODE` (negative cognitive/phi deltas)
    - `SELF_IMPROVEMENT_EPISODE` (contains architecture_proposal_created)
    - `SEMANTIC_LEARNING_EPISODE` (contains cell_assembly_created)
    - `STABILITY_EPISODE` (contains region_stability_checked)
    - `NEUTRAL_EPISODE` (default)
  - `generate_markdown_report(episode)` — human-readable single-episode report
  - `generate_batch_markdown_report(episodes)` — batch summary report

### Integration with Orchestrator

New orchestrator properties/methods:

- `episodic_memory_enabled: bool = True`
- `get_episodic_memory()` — lazy init
- `get_episodic_recall()` — lazy init
- `start_episode(trigger, initial_metrics, tick_id)`
- `record_episode_event(episode_id, event_type, source_module, tick_id, ...)`
- `close_episode(episode_id, final_metrics, outcome)`

### Event Types

- `EPISODE_STARTED`
- `EPISODE_EVENT_RECORDED`
- `EPISODE_CLOSED`
- `EPISODE_RECALLED`
- `EPISODE_PATTERN_DETECTED`
- `EPISODE_RECOVERY_PATTERN_FOUND`
- `EPISODE_REGRESSION_PRECURSOR_FOUND`

### Benchmark Metrics

- `episode_count`
- `episode_event_count`
- `recovery_episode_count`
- `regression_episode_count`
- `self_improvement_episode_count`
- `semantic_learning_episode_count`
- `episodic_recall_success_rate`
- `recovery_pattern_count`
- `regression_precursor_count`

## Acceptance Criteria

- T47 creates, records, and closes episodes with correct delta computation.
- T47 persists and reloads episodes from JSONL.
- T47 classifies episodes into the six defined categories.
- T47 recalls episodes by outcome and by cosine similarity.
- T47 detects regression precursors and recovery patterns.
- T47 generates Markdown reports containing episode fields.
- T47 logs all lifecycle events to MorphologicalMemory.
- T47 benchmark metrics are populated when episodic memory is enabled.
- All existing tests pass; coverage >= 85%.
- Reports generated in `reports/episodic_memory/`.

## Version

v0.3.36-t47-episodic-memory-temporal-experience
