# T65 — Sandboxed Skill Transfer & Generalization Layer Specification

## Purpose
Evaluate whether capabilities matured in prior layers transfer safely to novel, unseen scenarios **without** enabling real-world execution. T65 is a read-only, sandbox-only audit layer that generalizes sandboxed skills across domains and detects overfitting, negative transfer, and safety violations before any real-world enablement.

## Architecture

### Core Components
- **SkillTransferLayer** (`skill_transfer_layer.py`) — main T65 layer coordinating evaluation.
- **SkillTransferAudit** (`skill_transfer_audit.py`) — audit runner with default candidates and report generation.
- **SkillCandidateRegistry** (`skill_candidate_registry.py`) — registry of candidate skills eligible for transfer.
- **TransferScenarioBuilder** (`transfer_scenario_builder.py`) — builds default and novel transfer scenarios.
- **TransferEvaluator** (`transfer_evaluator.py`) — evaluates a candidate against a scenario, producing scores.
- **GeneralizationTracker** (`generalization_tracker.py`) — tracks whether a skill generalizes across multiple scenarios.
- **NegativeTransferDetector** (`negative_transfer_detector.py`) — detects degradation in performance due to transfer.
- **SkillSafetyGate** (`skill_safety_gate.py`) — blocks candidates that violate sandbox-only or real-world constraints.
- **TransferPolicyEngine** (`transfer_policy_engine.py`) — policy decisions on whether a candidate can advance.

### Models (`skill_transfer_models.py`)

#### SkillTransferCandidate
| Field | Default | Description |
|-------|---------|-------------|
| `skill_id` | required | Unique skill identifier |
| `source_capability_id` | `""` | Originating capability |
| `source_maturity_score` | `0.0` | Maturity from prior layer |
| `source_confidence_score` | `0.0` | Confidence from prior layer |
| `source_safety_score` | `0.0` | Safety score from prior layer |
| `sandbox_only` | `True` | Must remain sandbox-only |
| `real_world_enabled` | `False` | Must remain False |
| `eligible_for_transfer` | `False` | Whether the skill is eligible |

#### TransferScenario
| Field | Default | Description |
|-------|---------|-------------|
| `scenario_id` | required | Unique scenario identifier |
| `novelty_score` | `0.0` | How novel the scenario is |
| `difficulty_score` | `0.0` | Difficulty rating |
| `risk_score` | `0.0` | Risk rating |
| `requires_external_action` | `False` | Must remain False |
| `simulated_only` | `True` | Must remain True |

#### SkillTransferResult
| Field | Default | Description |
|-------|---------|-------------|
| `transfer_state` | `NOT_OBSERVED` | State after evaluation |
| `transfer_success_score` | `0.0` | Success in scenario |
| `generalization_score` | `0.0` | Generalization metric |
| `overfitting_score` | `0.0` | Overfitting metric |
| `negative_transfer_score` | `0.0` | Negative transfer metric |
| `safety_score` | `0.0` | Safety metric |
| `read_only_integrity_score` | `1.0` | Must remain 1.0 |
| `blocked` | `False` | Safety gate block |
| `quarantined` | `False` | Quarantine flag |
| `verdict` | `SKILL_TRANSFER_INSUFFICIENT_EVIDENCE` | Result verdict |

#### SkillTransferAuditResult
| Field | Default | Description |
|-------|---------|-------------|
| `candidate_count` | `0` | Total candidates |
| `scenario_count` | `0` | Total scenarios |
| `transfer_attempt_count` | `0` | Candidate × scenario evaluations |
| `transferred_sandboxed_count` | `0` | Successful sandboxed transfers |
| `generalized_sandboxed_count` | `0` | Generalized sandboxed transfers |
| `overfitted_count` | `0` | Overfitting detections |
| `negative_transfer_count` | `0` | Negative transfer detections |
| `safety_blocked_count` | `0` | Safety blocks |
| `quarantined_count` | `0` | Quarantined results |
| `unsafe_transfer_enabled_count` | `0` | sandbox_only=False results |
| `real_world_enabled_count` | `0` | real_world_enabled=True results |
| `aggregate_transfer_score` | `0.0` | Mean transfer success |
| `aggregate_generalization_score` | `0.0` | Mean generalization |
| `aggregate_safety_score` | `0.0` | Mean safety |
| `read_only_integrity_score` | `1.0` | Must remain 1.0 |
| `transfer_verdict` | `SKILL_TRANSFER_INSUFFICIENT_EVIDENCE` | Overall verdict |
| `proceed_to_t65b` | `False` | Whether T65B is allowed |

### Transfer States (`SkillTransferState`)
- `NOT_OBSERVED`
- `TRANSFER_CANDIDATE`
- `TRANSFER_TESTED`
- `TRANSFERRED_SANDBOXED`
- `GENERALIZES_SANDBOXED`
- `OVERFITTED`
- `NEGATIVE_TRANSFER`
- `SAFETY_BLOCKED`
- `QUARANTINED`
- `INSUFFICIENT_EVIDENCE`

## Default Scenarios
The `TransferScenarioBuilder` provides 8 default scenarios:
1. Cross-domain motor adaptation
2. Novel sensory context transfer
3. Temporal sequence generalization
4. Abstract rule transfer
5. Safety-critical scenario simulation
6. Edge-case perturbation handling
7. Multi-modal integration transfer
8. Unseen environment navigation

## Evaluation Flow
1. **Candidate registration** via `SkillTransferLayer.register_candidates()`.
2. **Scenario building** via `TransferScenarioBuilder.build_default_scenarios()`.
3. **Evaluation** loop: for each candidate × scenario, `TransferEvaluator.evaluate()` returns scores.
4. **Safety gate** checks `sandbox_only` and `real_world_enabled`; blocks violators.
5. **Tracking** records generalization and negative-transfer metrics per skill.
6. **Policy engine** decides if the candidate can advance based on thresholds:
   - `source_maturity_score >= 0.72`
   - `source_confidence_score >= 0.70`
   - `source_safety_score >= 0.90`
   - `transfer_success_score >= 0.70`
   - `generalization_score >= 0.68`
   - `overfitting_score <= 0.25`
   - `negative_transfer_score <= 0.20`
   - `sandbox_only == True`
   - `real_world_enabled == False`
   - `read_only_integrity_score == 1.0`
7. **State assignment** based on policy and tracking results.
8. **Quarantine check** forces `QUARANTINED` if `real_world_enabled` is True on the candidate.
9. **Verdict computation** per result and aggregate audit verdict.
10. **Proceed to T65B** computed from aggregate metrics.

## Safety Constraints
- `sandbox_only` must be `True` for all candidates and results.
- `real_world_enabled` must be `False` for all candidates and results.
- No external API calls, IoT connections, or hardware interactions are permitted.
- `read_only_integrity_score` must remain `1.0`.
- The layer is read-only with respect to system state; it does not mutate capabilities, enable real-world actions, or self-improve.

## Verdicts

### Per-Result Verdicts
- `SKILL_TRANSFER_READ_ONLY_VIOLATION` — integrity score < 1.0
- `REAL_WORLD_SKILL_ENABLED` — real_world_enabled=True
- `UNSAFE_SKILL_TRANSFER_ENABLED` — sandbox_only=False
- `SKILL_TRANSFER_QUARANTINE_REQUIRED` — quarantined
- `SKILL_TRANSFER_SAFETY_BLOCK_REQUIRED` — safety blocked
- `SKILL_OVERFITTING_DETECTED` — overfitting state
- `NEGATIVE_TRANSFER_DETECTED` — negative transfer state
- `SKILL_TRANSFER_LAYER_VALIDATED` — generalizes safely in sandbox
- `SKILL_TRANSFER_SAFE_BUT_LIMITED` — transferred but not generalized
- `SKILL_TRANSFER_INSUFFICIENT_EVIDENCE` — default

### Aggregate Verdicts (same strings, applied to audit)

## Proceed to T65B Rules
`proceed_to_t65b` is `True` only if **all** of the following hold:
- `aggregate_transfer_score >= 0.70`
- `aggregate_generalization_score >= 0.68`
- `read_only_integrity_score == 1.0`
- `real_world_enabled_count == 0`
- `unsafe_transfer_enabled_count == 0`
- `overfitted_count == 0`
- `negative_transfer_count == 0`
- `quarantined_count == 0`

## Orchestrator Hooks
The orchestrator exposes:
- `skill_transfer_enabled: bool = False`
- `get_skill_transfer_layer()` — returns the `SkillTransferLayer` instance.
- `get_skill_transfer_state()` — returns candidate count and serialized candidates.
- `run_skill_transfer()` — runs the transfer layer and returns an audit result.
- `run_skill_transfer_audit()` — convenience alias for audit runner.

## Determinism
All evaluation uses a seeded `random.Random` instance (default seed `42`) to ensure reproducible scores across runs.

## Report Generation
`SkillTransferAudit.run_audit()` produces:
- A JSON report at `reports/skill_transfer/skill_transfer_audit_<timestamp>.json`
- A Markdown summary at `reports/skill_transfer/skill_transfer_audit_<timestamp>.md`

## Version
Introduced in `v0.3.61-t65-sandboxed-skill-transfer-generalization-layer`.
