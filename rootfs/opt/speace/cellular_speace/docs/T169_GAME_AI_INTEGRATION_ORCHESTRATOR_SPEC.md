# T169 — Game AI Integration Orchestrator

## Objective
Provide a unified coordination layer that integrates T163–T166 into the existing runtime, defining a bio-inspired hierarchical control pipeline: FSM → Utility AI → Behavior Trees → GOAP → Metacognition / Governance.

## Background
Individual game-AI modules (T163–T166) are powerful but must be orchestrated so that fast local layers do not conflict with deep strategic layers. T169 defines the integration contract and tick ordering.

## Architecture
Pipeline per stimulus (per tick):
1. **FSM** (`OrganismStateMachine`) — sets global organismic context.
2. **Utility AI** (`UtilityDriveSystem` + `ArbitrationEngine`) — weights module priorities given FSM state.
3. **Behavior Trees** (`ReflexBehaviorLibrary`) — fast local reflexes; executed only if Utility permits.
4. **GOAP** (`GOAPPlanner`) — triggered when BT cannot resolve goal or confidence is low; produces planned sequence.
5. **Metacognition / Governance** — evaluates proposals from BT and GOAP; confidence check; human approval if needed.
6. **Execution / Proposal** — approved actions are executed or queued; all logged.

Lower layers can **suppress** or **escalate**:
- BT can escalate to GOAP if leaf action returns `FAILURE` and goal remains urgent.
- GOAP can abort and fall back to BT if planning confidence < 0.3.
- Utility can globally suppress BTs by zeroing their module weight.
- FSM `overloaded` state can bypass non-safety BTs entirely.

## Components

### `GameAIIntegrationCoordinator`
- **Location:** `speace_core/cellular_brain/runtime/coordinators/game_ai_integration_coordinator.py`
- `tick_pipeline(runtime_context)` executes the 6 steps above.
- Maintains proposal queue from BT and GOAP.
- Feeds final approved actions to orchestrator execution hooks (existing governance).

### Pipeline Contracts
- Each layer exposes `.tick(context) -> ProposalBag`.
- `ProposalBag` contains zero or more proposals with `priority`, `confidence`, `source_layer`, `simulate_only` flag.
- Coordinator merges bags, resolves conflicts (higher layer wins), and forwards to governance.

## Governance & Safety
- No layer can bypass `EmergencyHaltGate`, `CausalLearningAuditor`, or `HumanApprovalGate`.
- Tick latency budget for entire game-AI pipeline: max 50 ms.
- If pipeline exceeds budget, BT and GOAP are skipped; only FSM + Utility run (degraded mode).

## Acceptance Criteria
1. End-to-end test demonstrates a sensor stimulus flowing through FSM → Utility → BT → GOAP → Governance → Audit.
2. Pipeline latency stays under 50 ms in benchmark with 3 BTs and 1 GOAP goal.
3. Degraded mode correctly skips BT/GOAP when simulated load injects 100 ms delay.
4. Dashboard endpoint `/api/game_ai_pipeline` exposes current layer activations, proposal queue, and latency breakdown.
5. All proposals carry `source_layer` tag and appear in unified audit log.
