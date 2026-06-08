# T46 — Self-Improvement Outcome Learning

## Overview

T46 closes the metacognitive loop started by T45. After T45 detected a limitation, proposed T44, and T44B validated the proposal with `ASSOCIATIVE_MEMORY_VALIDATED` and net gain `+0.2903`, T46 records this outcome and updates the self-improvement system's learned confidence.

The new chain is:

1. Detect limitation
2. Propose architecture
3. Implement
4. Audit
5. **Learn from outcome** (T46)
6. Improve future proposal selection

## Design Principles

- **Non-destructive**: Does not alter existing proposals or cycles.
- **Observable**: All outcome learning events logged to MorphologicalMemory.
- **Persistent**: Outcomes, learning records, and history stored in JSONL.
- **Conservative**: Confidence clamped to `[0, 1]`; regressions penalize mappings.

## Architecture

### Models

- `ProposalOutcome` — Result of an implemented proposal after audit.
- `ProposalLearningRecord` — Aggregated statistics per limitation→task mapping.
- `SelfImprovementHistoryEntry` — Generic history event for the self-improvement memory.

### Engines

- `OutcomeTracker`
  - `record_outcome(...)` — classifies success / partial_success / regression
  - `load_outcomes()`, `get_outcomes_for_limitation(...)`
  - `generate_outcome_report(...)` — Markdown report

- `ProposalLearningEngine`
  - `update_from_outcome(...)` — updates or creates a `ProposalLearningRecord`
  - `get_learning_record(...)`, `load_learning_records()`
  - `rank_candidate_proposals(...)` — orders candidates by learned confidence
  - Confidence formula: `0.35*success_rate + 0.25*partial_success_rate + 0.25*normalized_mean_net_gain - 0.15*regression_rate`

- `SelfImprovementMemory`
  - `write_history_event(...)`, `load_history()`, `get_history_by_type(...)`
  - Convenience wrappers: `record_limitation_detected`, `record_proposal_accepted`, `record_audit_outcome`, etc.

### Integration with SelfImprovementLoop

New methods on `SelfImprovementLoop`:

- `record_proposal_outcome(...)` — delegates to `OutcomeTracker`
- `learn_from_outcome(...)` — delegates to `ProposalLearningEngine`
- `get_best_known_proposal_for_limitation(...)` — uses learned confidence to rank candidates

### Event Types

- `SELF_IMPROVEMENT_OUTCOME_RECORDED`
- `SELF_IMPROVEMENT_PROPOSAL_VALIDATED`
- `SELF_IMPROVEMENT_PROPOSAL_FAILED`
- `SELF_IMPROVEMENT_MAPPING_REINFORCED`
- `SELF_IMPROVEMENT_MAPPING_WEAKENED`
- `SELF_IMPROVEMENT_CONFIDENCE_UPDATED`

### Benchmark Metrics

- `self_improvement_outcome_count`
- `self_improvement_success_rate`
- `self_improvement_regression_rate`
- `self_improvement_mean_net_gain`
- `self_improvement_learning_confidence`
- `validated_proposal_count`
- `failed_proposal_count`

## Acceptance Criteria

- T46 records outcomes with correct success / partial_success / regression classification.
- T46 updates learning records incrementally.
- T46 confidence formula produces values in `[0, 1]`.
- T46 ranks candidates penalizing regression mappings.
- T44B outcome yields confidence > 0.70 for `semantic_association_missing → T44`.
- All existing tests pass; coverage >= 85%.
- Reports generated in `reports/self_improvement_outcomes/`.

## Version

v0.3.35-t46-self-improvement-outcome-learning
