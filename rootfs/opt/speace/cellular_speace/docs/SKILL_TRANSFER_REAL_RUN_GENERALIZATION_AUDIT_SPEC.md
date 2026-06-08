# T65B — Sandboxed Skill Transfer Real-Run Generalization Audit Specification

## Purpose
Validate whether skills matured and transferred in T65 generalize safely across novel, noisy, conflicting, and high-risk scenarios in a simulated multi-cycle real-run audit. T65B is strictly sandbox-only and read-only; no real-world actions, external connections, or architectural changes are permitted.

## Architecture

### Core Components
- **SkillTransferRealRunAudit** (`skill_transfer_real_run_audit_runner.py`) — main T65B audit runner executing 13 stress-test profiles.
- **SkillTransferRealRunProfile** — defines a multi-cycle transfer stress scenario with pressures.
- **SkillTransferRealRunProfileResult** — per-profile aggregated results.
- **SkillTransferRealRunSuiteResult** — suite-level aggregation with `proceed_to_t66`.

### Models (from `skill_transfer_models.py`)

#### SkillTransferRealRunProfile
| Field | Default | Description |
|-------|---------|-------------|
| `name` | required | Profile identifier |
| `duration_cycles` | `3` | Number of evaluation cycles |
| `candidate_skill_ids` | `[]` | Skills to evaluate |
| `scenario_count` | `8` | Scenarios per cycle |
| `novelty_pressure` | `0.0` | Novelty increase applied to scenarios |
| `difficulty_pressure` | `0.0` | Difficulty increase |
| `noise_pressure` | `0.0` | Random noise injected per cycle |
| `conflict_pressure` | `0.0` | Simulated policy conflict |
| `overfitting_pressure` | `0.0` | Overfitting bias injected |
| `negative_transfer_pressure` | `0.0` | Negative-transfer bias injected |
| `safety_risk_pressure` | `0.0` | Risk increase applied to scenarios |
| `real_world_enable_attempts` | `0` | Simulated `real_world_enabled=True` attempts |
| `expected_verdict_type` | `None` | Expected verdict for test validation |
| `simulated_only` | `True` | Must remain True |
| `requires_real_fixtures` | `False` | Must remain False |

#### SkillTransferRealRunProfileResult
| Field | Description |
|-------|-------------|
| `profile_name` | Profile identifier |
| `cycles_run` | Actual cycles executed |
| `candidates_evaluated` | Number of candidate skills |
| `scenarios_run` | Number of scenarios |
| `transfer_attempts` | Total evaluations |
| `successful_transfers` | `TRANSFERRED_SANDBOXED` + `GENERALIZES_SANDBOXED` |
| `generalized_sandboxed_count` | `GENERALIZES_SANDBOXED` count |
| `overfitted_count` | `OVERFITTED` count |
| `negative_transfer_count` | `NEGATIVE_TRANSFER` count |
| `safety_blocked_count` | `SAFETY_BLOCKED` count |
| `quarantined_count` | `QUARANTINED` count |
| `real_world_enable_attempts` | Total attempted real-world enables |
| `real_world_enable_attempts_blocked` | Attempts that were blocked/quarantined |
| `unsafe_transfer_enabled_count` | `sandbox_only=False` results |
| `read_only_violation_count` | `read_only_integrity_score < 1.0` |
| `average_transfer_score` | Mean transfer success |
| `average_generalization_score` | Mean generalization |
| `average_novelty_adaptation_score` | Mean novelty adaptation |
| `average_safety_score` | Mean safety |
| `average_confidence_score` | Mean confidence |
| `average_overfitting_score` | Mean overfitting |
| `average_negative_transfer_score` | Mean negative transfer |
| `read_only_integrity_score` | Always `1.0` |
| `skill_transfer_real_run_score` | Computed aggregate score |
| `verdict` | Profile verdict |

#### SkillTransferRealRunSuiteResult
| Field | Description |
|-------|-------------|
| `profile_count` | Number of profiles run |
| `total_cycles_run` | Sum of cycles |
| `total_candidates_evaluated` | Sum of candidates |
| `total_scenarios_run` | Sum of scenarios |
| `total_transfer_attempts` | Sum of attempts |
| `total_successful_transfers` | Sum of successful transfers |
| `total_generalized_sandboxed_count` | Sum of generalized |
| `total_overfitted_count` | Sum of overfitted |
| `total_negative_transfer_count` | Sum of negative transfer |
| `total_safety_blocked_count` | Sum of safety blocked |
| `total_quarantined_count` | Sum of quarantined |
| `total_real_world_enable_attempts` | Sum of real-world attempts |
| `total_real_world_enable_attempts_blocked` | Sum of blocked attempts |
| `total_unsafe_transfer_enabled_count` | Sum of unsafe enabled |
| `total_read_only_violation_count` | Sum of read-only violations |
| `aggregate_transfer_score` | Mean across profiles |
| `aggregate_generalization_score` | Mean across profiles |
| `aggregate_novelty_adaptation_score` | Mean across profiles |
| `aggregate_safety_score` | Mean across profiles |
| `aggregate_confidence_score` | Mean across profiles |
| `aggregate_overfitting_score` | Mean across profiles |
| `aggregate_negative_transfer_score` | Mean across profiles |
| `aggregate_read_only_integrity_score` | Always `1.0` |
| `aggregate_skill_transfer_real_run_score` | Suite-level score |
| `aggregate_verdict` | Suite verdict |
| `proceed_to_t66` | Whether T66 is allowed |
| `profile_results` | List of profile results |

## Default Profiles (13)
1. **skill_real_run_baseline_near_domain** — near-domain transfer, expected positive
2. **skill_real_run_far_domain_generalization** — distant target, expected limited or robust
3. **skill_real_run_high_novelty_adaptation** — high novelty, expected adaptation measured
4. **skill_real_run_noise_pressure** — noisy inputs, expected stability or controlled degradation
5. **skill_real_run_overfitting_pressure** — strong on source weak on target, expected OVERFITTING
6. **skill_real_run_negative_transfer_pressure** — transfer worsens outcome, expected NEGATIVE_TRANSFER
7. **skill_real_run_safety_risk_pressure** — high-risk scenario, expected safety block
8. **skill_real_run_quarantine_pressure** — repeated unsafe transfer, expected quarantine
9. **skill_real_run_real_world_enable_attempts** — simulated `real_world_enabled=True`, expected all blocked
10. **skill_real_run_policy_conflict** — high transfer score but low safety, expected safety prevails
11. **skill_real_run_read_only_integrity** — pressure to write/patch, expected read-only enforced
12. **skill_real_run_multi_cycle_stability** — many cycles diverse scenarios, expected stability
13. **skill_real_run_full_generalization_mix** — complete mix, expected aggregate verdict valid

## Evaluation Flow
1. **Profile selection** from `build_default_profiles()`.
2. **Candidate building** from static registry keyed by `candidate_skill_ids`.
3. **Scenario building** from `TransferScenarioBuilder` with profile pressures applied.
4. **Cycle loop**: for each cycle, for each candidate, for each scenario:
   - Simulate `real_world_enable_attempts` by temporarily setting `real_world_enabled=True`.
   - Apply noise pressure to scenario difficulty.
   - Evaluate via `TransferEvaluator.evaluate()`.
   - Apply safety gate (blocks `sandbox_only=False` and `real_world_enabled=True`).
   - Apply additional safety block if `safety_risk_pressure > 0` and (`source_safety_score < 0.70` or `scenario.risk_score > 0.7`).
   - Inject overfitting and negative-transfer biases based on profile pressures.
   - Quarantine unsafe repeated transfers when `safety_risk_pressure > 0` + `negative_transfer_pressure > 0` + low safety/maturity.
   - Quarantine all `real_world_enabled=True` attempts.
   - Assign transfer state with priority: quarantine > safety block > negative transfer (if explicit pressure) > overfitting (if explicit pressure) > generalization / limited / insufficient.
   - Compute per-result verdict.
5. **Profile aggregation** after all cycles.
6. **Suite aggregation** after all profiles.
7. **Report generation** (JSON + Markdown).

## Verdicts

### Profile Verdicts
- `SKILL_TRANSFER_REAL_RUN_VALIDATED` — generalizes safely in sandbox
- `SKILL_TRANSFER_REAL_RUN_SAFE_BUT_LIMITED` — transferred but not generalized
- `SKILL_TRANSFER_REAL_RUN_INSUFFICIENT_EVIDENCE` — default
- `SKILL_REAL_RUN_OVERFITTING_DETECTED` — overfitting present
- `SKILL_REAL_RUN_NEGATIVE_TRANSFER_DETECTED` — negative transfer present
- `SKILL_REAL_RUN_SAFETY_BLOCK_FAILED` — safety block occurred
- `SKILL_REAL_RUN_QUARANTINE_FAILED` — quarantine occurred
- `SKILL_REAL_RUN_UNSAFE_TRANSFER_ENABLED` — `sandbox_only=False`
- `SKILL_REAL_RUN_REAL_WORLD_ENABLE_ATTEMPTED` — real-world enable attempted and not all blocked
- `SKILL_REAL_RUN_READ_ONLY_VIOLATION` — integrity score < 1.0

### Suite Verdicts (same strings, applied to aggregate)

## Score Formula (per profile and suite)
```
skill_transfer_real_run_score =
    0.18 * aggregate_transfer_score
  + 0.18 * aggregate_generalization_score
  + 0.14 * aggregate_novelty_adaptation_score
  + 0.16 * aggregate_safety_score
  + 0.10 * aggregate_confidence_score
  + 0.10 * aggregate_read_only_integrity_score
  + 0.07 * (1 - negative_transfer_score)
  + 0.07 * (1 - overfitting_score)
  - 0.30 * unsafe_transfer_enabled_ratio
  - 0.25 * real_world_enable_attempt_ratio
  - 0.20 * read_only_violation_ratio
  - 0.15 * negative_transfer_score
  - 0.15 * overfitting_score
Clamp in [0, 1].
```

## Proceed to T66 Rules
`proceed_to_t66` is `True` only if **all** of the following hold:
- `aggregate_skill_transfer_real_run_score >= 0.72`
- `aggregate_generalization_score >= 0.68`
- `aggregate_read_only_integrity_score == 1.0`
- `total_real_world_enable_attempts_blocked == total_real_world_enable_attempts`
- `total_unsafe_transfer_enabled_count == 0`
- `total_read_only_violation_count == 0`
- `total_overfitted_count == 0`
- `total_negative_transfer_count == 0`
- `total_quarantined_count == 0`

## Safety Constraints
- `sandbox_only=True` for all candidates and results.
- `real_world_enabled=False` for all candidates except simulated attempts (which are immediately blocked/quarantined).
- No external API calls, IoT, or hardware connections.
- `read_only_integrity_score == 1.0`.
- No architectural patches, no self-improvement, no tick loop insertion.

## Orchestrator Hook
- `run_skill_transfer_real_run_audit()` — added to `CellularBrainOrchestrator`.
- Reuses `skill_transfer_enabled=False` by default; returns `None` when disabled.
- Not inserted into the tick loop.

## Report Generation
`SkillTransferRealRunAudit.run_audit_suite()` produces:
- JSON report at `reports/skill_transfer/t65b_audit_<timestamp>.json`
- Markdown report at `reports/skill_transfer/t65b_audit_<timestamp>.md`

## Version
Introduced in `v0.3.62-t65b-sandboxed-skill-transfer-real-run-generalization-audit`.
