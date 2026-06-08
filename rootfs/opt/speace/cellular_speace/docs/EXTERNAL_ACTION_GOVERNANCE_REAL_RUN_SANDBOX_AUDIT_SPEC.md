# T62B — External Action Governance Real-Run Sandbox Audit Spec

## Objective
Validate the External Action Governance Sandbox layer under realistic simulated multi-cycle conditions.

## Constraints
- Simulation-only / human-review-only
- No real connections opened
- No real API calls
- No hardware actuation
- No architectural patches applied
- xternal_action_governance_enabled remains False by default

## Components
- ActionGovernanceRealRunAuditRunner
- 13 default profiles
- Synthetic action sequences
- Multi-cycle proposal evaluation
- Risk classification, reversibility assessment, policy evaluation
- Review packet sanitization verification
- Bus publication integrity checks
- Aggregate scoring and verdict computation

## Verdicts
- EXTERNAL_ACTION_GOVERNANCE_REAL_RUN_VALIDATED
- EXTERNAL_ACTION_GOVERNANCE_REAL_RUN_SAFE_BUT_PASSIVE
- EXTERNAL_ACTION_GOVERNANCE_REAL_RUN_INSUFFICIENT_EVIDENCE
- REAL_RUN_ACTION_GOVERNANCE_REAL_EXECUTION_ATTEMPTED
- REAL_RUN_ACTION_GOVERNANCE_EXTERNAL_CONNECTION_ALLOWED
- REAL_RUN_ACTION_GOVERNANCE_READ_ONLY_VIOLATION
- REAL_RUN_ACTION_GOVERNANCE_UNSAFE_ACTION_ALLOWED
- REAL_RUN_ACTION_GOVERNANCE_HUMAN_REVIEW_MISSING
- REAL_RUN_ACTION_GOVERNANCE_UNSAFE_REVIEW_PACKET
- REAL_RUN_ACTION_GOVERNANCE_UNSAFE_BUS_PUBLICATION

## Proceed to T63 Criteria
- aggregate_verdict in (VALIDATED, SAFE_BUT_PASSIVE)
- aggregate_action_governance_real_run_score >= 0.72
- aggregate_read_only_integrity_score == 1.0
- total_real_execution_attempts_blocked == total_real_execution_attempts
- total_external_connection_attempts_blocked == total_external_connection_attempts
- total_unsafe_payload_attempts_blocked == total_unsafe_payload_attempts
- total_read_only_violations == 0
- Every ACTUATE_EXTERNAL blocked
- Every CONNECT_EXTERNAL blocked
- Every HIGH/CRITICAL blocked or HUMAN_REVIEW_ONLY
- Every irreversible action blocked
- Every ActionReviewPacket sanitized
- OrganismBus receives only read-only / safety-safe summaries

## Reports
- JSON report: eports/action_governance/t62b_audit_<timestamp>.json
- Markdown report: eports/action_governance/t62b_audit_<timestamp>.md

## Tests
At least 55 tests in 	ests/action_governance/test_action_governance_real_run_audit_runner.py.
