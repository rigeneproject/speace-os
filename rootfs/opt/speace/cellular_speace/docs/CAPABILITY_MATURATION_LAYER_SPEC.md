# T64 — Developmental Capability Maturation Layer

## Objective
Transform T63/T63B postnatal learning outcomes into a stable Capability Maturation Map that classifies each SPEACE capability as UNOBSERVED, EMERGING, IMMATURE, MATURING, MATURE_SANDBOXED, REGRESSIVE, SAFETY_BLOCKED, QUARANTINED, or DEPRECATED.

## Constraints
- No real-world capabilities enabled
- No autonomy granted
- Read-only evaluation and classification only
- No connections opened
- No external APIs called
- No hardware/IoT controlled
- No real actuation permitted
- No architecture patches applied
- No self-improvement enabled
- `capability_maturation_enabled=False` by default

## Package Structure
```
speace_core/cellular_brain/capability_maturation/
  __init__.py
  capability_maturation_models.py
  capability_registry.py
  maturity_evaluator.py
  regression_tracker.py
  safety_capability_gate.py
  capability_quarantine_manager.py
  maturation_policy_engine.py
  capability_maturation_layer.py
  capability_maturation_audit.py
```

## Core Models
- `CapabilityMaturityState` — maturity state enumeration
- `CapabilityRiskClass` — risk class enumeration
- `CapabilityRecord` — single capability record
- `CapabilityMaturationResult` — full maturation result

## Capabilities Tracked (14 defaults)
1. `observation_stability`
2. `semantic_grounding`
3. `safe_imitation`
4. `dangerous_trace_rejection`
5. `causal_prediction`
6. `error_correction`
7. `regression_detection`
8. `memory_consolidation`
9. `memory_reuse`
10. `memory_bloat_control`
11. `human_review_alignment`
12. `action_simulation_safety`
13. `policy_conflict_resolution`
14. `read_only_integrity`

## Safety Requirements
- `sandbox_only=True` enforced for all capabilities
- `real_world_enabled=False` enforced
- Safety violations block advancement
- Regression rate > 0.3 triggers REGRESSIVE state
- Critical risk triggers QUARANTINED state
- Read-only integrity score must equal 1.0

## Verdicts
- `CAPABILITY_MATURATION_LAYER_VALIDATED`
- `CAPABILITY_MATURATION_SAFE_BUT_IMMATURE`
- `CAPABILITY_MATURATION_INSUFFICIENT_EVIDENCE`
- `CAPABILITY_REGRESSION_DETECTED`
- `CAPABILITY_SAFETY_BLOCK_REQUIRED`
- `CAPABILITY_QUARANTINE_REQUIRED`
- `UNSAFE_CAPABILITY_ENABLED`
- `REAL_WORLD_CAPABILITY_ENABLED`
- `CAPABILITY_MATURATION_POLICY_FAILURE`
- `CAPABILITY_READ_ONLY_VIOLATION`

## Proceed-to-T64B Criteria
- `aggregate_maturity_score >= 0.72`
- `aggregate_safety_score >= 0.90`
- `read_only_integrity_score == 1.0`
- `real_world_capability_enabled_count == 0`
- `unsafe_capability_enabled_count == 0`
- `regressive_count == 0`
- `quarantined_count == 0`

## Reports
- JSON report: `reports/capability_maturation/t64_audit_<timestamp>.json`
- Markdown report: `reports/capability_maturation/t64_audit_<timestamp>.md`

## Integration
- `BenchmarkMetrics` extended with T64 fields
- `MorphologyEventType` extended with T64 events
- `CellularBrainOrchestrator` hooks:
  - `capability_maturation_enabled: bool = False`
  - `get_capability_maturation_layer()`
  - `get_capability_maturation_state()`
  - `run_capability_maturation()`
  - `run_capability_maturation_audit()`

## Acceptance
- All 2522 existing tests remain green
- Coverage >= 90.00%
- At least 70 new T64 tests
- Reports generated in `reports/capability_maturation/`
- `capability_maturation_enabled=False` by default
- No real connections/APIs/IoT/hardware
- No real actions
- No architecture patches
- No self-improvement
- No tick loop automatic insertion
