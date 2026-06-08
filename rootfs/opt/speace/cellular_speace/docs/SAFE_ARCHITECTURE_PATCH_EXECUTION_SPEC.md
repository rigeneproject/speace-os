# T50 — Safe Architecture Patch Execution

## Overview

T50 transforms SPEACE from a system that only proposes and simulates architectural changes into one that can safely apply real architecture patches with automatic snapshot, validation, and rollback.

## Pipeline

After T50, the self-improvement pipeline becomes:

```
detect limitation
  → generate proposals
  → episodic ranking (T48)
  → counterfactual sandbox (T49)
  → best safe proposal
  → architecture patch generation
  → pre-patch snapshot
  → real patch execution
  → post-patch benchmark
  → confirm or rollback
  → outcome learning (T46)
```

## Components

### ArchitecturePatch (Pydantic model)
- `patch_id`: unique identifier
- `proposal_id`: links to originating proposal
- `patch_type`: inferred from proposal type (`flag`, `numeric`, `profile_select`)
- `target_path`: allowlisted orchestrator attribute to modify
- `operation`: one of `set`, `scale`, `enable`, `disable`, `profile_select`
- `old_value` / `new_value`: before/after values
- `safety_class`: `low` or `medium`
- `requires_guard`: always `True` for real patches

### PatchExecutionResult (Pydantic model)
- `applied`: whether the patch was applied
- `confirmed`: whether the patch was confirmed after validation
- `rolled_back`: whether the patch was rolled back
- `verdict`: one of
  - `PATCH_CONFIRMED`
  - `PATCH_ROLLED_BACK`
  - `PATCH_REJECTED_UNSAFE`
  - `PATCH_FAILED`
  - `PATCH_NEEDS_MORE_EVIDENCE`
- `pre_score` / `post_score`: benchmark accuracy before/after
- `delta_score` / `delta_phi` / `delta_energy`: measured deltas
- `regression_flags`: list of detected regressions

### PatchSnapshot (Pydantic model)
- `snapshot_id`: unique identifier
- `patch_id`: links to originating patch
- `timestamp`: ISO-8601 UTC timestamp
- `genome_snapshot`: genome state at snapshot time
- `orchestrator_flags`: captured allowlisted flags
- `region_state`: captured region state
- `energy_state`: captured energy state
- `benchmark_baseline`: pre-patch benchmark metrics

### PatchSnapshotStore
- Persists snapshots as JSON in `data/architecture_patches/`
- Methods: `save_snapshot`, `load_snapshot`, `list_snapshots`, `delete_snapshot`, `load_latest`

### ArchitecturePatchExecutor
- `build_patch_from_proposal()`: infers patch details from an `ArchitectureRewriteProposal`
- `validate_patch_safety()`: allowlist-based safety gate
- `create_pre_patch_snapshot()`: captures orchestrator flags and benchmark baseline
- `apply_patch()`: performs the actual mutation on the orchestrator
- `run_post_patch_validation()`: computes deltas, runs RegressionGuard, computes verdict
- `rollback_patch()`: restores orchestrator flags from snapshot
- `execute_patch()`: full pipeline (proposed → validated → snapshot → apply → validate → log → report)

## Allowed Patch Targets

### Flags (boolean)
- `semantic_memory_enabled`
- `associative_memory_enabled`
- `episodic_policy_enabled`
- `counterfactual_sandbox_enabled`
- `brainstem_controller_enabled`
- `region_stability_controller_enabled`
- `architecture_patch_execution_enabled`

### Numeric parameters
- `learning_rate`
- `plasticity_rate`
- `decay_rate`
- `routing_gain`
- `inhibition_decay`
- `semantic_similarity_threshold`
- `assembly_consolidation_threshold`

### Profiles
- `recovery_policy_profile`
- `energy_control_profile`
- `brainstem_gain_profile`
- `routing_profile`
- `plasticity_tuning_profile`

## Verdict Logic

| Condition | Verdict |
|-----------|---------|
| `POLICY_UNSAFE` from RegressionGuard | `PATCH_ROLLED_BACK` |
| `SCORE_REGRESSION` (delta_score < -0.05) | `PATCH_ROLLED_BACK` |
| `PHI_REGRESSION` (delta_phi < -0.05) | `PATCH_ROLLED_BACK` |
| `ENERGY_REGRESSION` (delta_energy < -0.1) | `PATCH_ROLLED_BACK` |
| Any positive delta >= 0.01 | `PATCH_CONFIRMED` |
| Small non-negative deltas | `PATCH_NEEDS_MORE_EVIDENCE` |
| Otherwise | `PATCH_ROLLED_BACK` |

## Safety Constraints

1. **Allowlist only**: only explicitly allowed flags, numeric parameters, and profiles can be patched
2. **Snapshot required**: every patch requires a pre-patch snapshot before application
3. **Automatic rollback**: if post-patch validation detects regression, the patch is automatically rolled back
4. **Disabled by default**: `architecture_patch_execution_enabled` defaults to `False`
5. **MorphologicalMemory logging**: every stage emits a `MorphologyEvent` for full auditability
6. **No file writes**: ArchitecturePatchExecutor never writes `.py` files; it only mutates runtime orchestrator attributes
7. **No module deletion**: deletion or removal of modules is forbidden
8. **No unvalidated genome mutation**: genome mutation proposals are blocked at safety validation

## Integration Points

- **MorphologyEvents**: 8 new event types for T50 patch lifecycle
- **BenchmarkMetrics**: 9 new metrics tracking patch outcomes
- **SelfImprovementLoop**: T50 integrated after T49 counterfactual sandbox; executes best safe proposal when enabled
- **Orchestrator**: `architecture_patch_execution_enabled` flag added
- **ArchitectureRewriter**: `patch_execution_result` and `patch_verdict` fields added to `SelfImprovementCycleResult`

## Files

- `speace_core/cellular_brain/memory/morphology_events.py` — T50 event types
- `speace_core/cellular_brain/self_improvement/architecture_patch_executor.py` — executor implementation
- `speace_core/cellular_brain/self_improvement/patch_snapshot_store.py` — snapshot persistence
- `speace_core/cellular_brain/self_improvement/architecture_rewriter.py` — result model extensions
- `speace_core/cellular_brain/self_improvement/self_improvement_loop.py` — T50 integration
- `speace_core/cellular_brain/benchmark/neurofunctional_benchmark.py` — T50 benchmark metrics and report
- `speace_core/orchestrator.py` — `architecture_patch_execution_enabled` flag
- `tests/self_improvement/test_architecture_patch_executor.py` — >=28 tests
- `tests/self_improvement/test_patch_snapshot_store.py` — snapshot store tests
- `docs/SAFE_ARCHITECTURE_PATCH_EXECUTION_SPEC.md` — this document
