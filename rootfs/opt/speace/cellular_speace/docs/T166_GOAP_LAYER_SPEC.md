# T166 — GOAP Layer: Practical Intentional Planning

## Objective
Integrate Goal-Oriented Action Planning (GOAP) as a practical planning layer for intentional problem-solving, aligned with Active Inference, homeostasis, and metacognition.

## Background
SPEACE has deep causal world models and metacognitive reflection but lacks a discrete action planner for chaining known operations toward explicit goals. GOAP provides interpretable, cost-based planning compatible with the existing audit and rollback infrastructure.

## Architecture
GOAP is a **proposer**: it generates plans, simulates them in `WorldModelSandbox`, and submits approved plans for execution through governance gates. It never executes autonomously.

## Components

### `GOAPPlanner`
- **Location:** `speace_core/cellular_brain/cognition/goap_planner.py`
- Implements A* search over action graph.
- Goal representation: `GoalState` with desired world-state predicates.
- Action representation: `GOAPAction` with preconditions, effects, cost, and execution pointer (mapping to existing SPEACE capability).

### `GOAPActionRegistry`
- **Location:** `speace_core/cellular_brain/cognition/goap_action_registry.py`
- Registry of actions mapped to existing modules:
  - `observe_sensor` → `CyberPhysicalSensorArray.capture()`
  - `query_memory` → `EpisodicMemory.recall()`
  - `request_clarification` → `DialogueManager.request_human_clarification()`
  - `run_counterfactual` → `WorldModelSandbox.simulate()`
  - `trigger_metacognitive_review` → `MetacognitiveMonitor.generate_meta_state()`
  - `adjust_attention` → `GlobalWorkspace.broadcast()`
- Actions are tagged `simulate-only` or `proposes-external`. External actions require approval.

### `GOAPMetacognitiveBridge`
- **Location:** `speace_core/cellular_brain/cognition/goap_metacognitive_bridge.py`
- Queries `EpistemicConfidenceEngine` for confidence in plan outcome.
- Queries `CognitiveStrategyEvaluator` to decide if GOAP is appropriate vs. reflex (BT) or drive (Utility).
- If confidence < 0.3, planner aborts and falls back to lower-layer reflex.

## Governance & Safety
- Every plan is simulated in `WorldModelSandbox` / `ImpactSimulator` before approval.
- Plans with external effects are queued in `HumanApprovalGate`.
- Post-execution audit feeds outcome into `SelfImprovementOutcomeLearning` (T52).
- If outcome is negative, triggers rollback via `RegulationProposalBuilder` (T104/T154-B).

## Acceptance Criteria
1. Planner solves a toy goal (`reduce_prediction_error`) in < 50 ms using 3 registered actions.
2. Plan simulation in sandbox correctly predicts at least one side effect.
3. External-action plan is held in `HumanApprovalGate` until approved/rejected.
4. Failed plan outcome triggers a regulation proposal with rollback path.
5. Dashboard endpoint `/api/goap_plans` lists pending, approved, and completed plans with audit trail.
