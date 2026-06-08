# T164 — Behavior Tree Layer: Micro-Cognitive Reflexes

## Objective
Implement lightweight Behavior Trees (BT) as the digital brainstem / basal ganglia of SPEACE: fast, local, reactive decision micro-modules for avoidance, exploration, search, prioritization, and interaction routines.

## Background
SPEACE has deep metacognitive, narrative, and causal layers but lacks fast local decision circuits. BTs fill this gap by providing interpretable, tick-based micro-reflexes that operate below the strategic layer.

## Architecture
BTs are sandboxed: they run inside the runtime tick, read from sensors/homeostasis, and produce **proposed actions** or **attention signals**. They never touch actuators directly. Every proposed action routes through the existing governance pipeline.

## Components

### `BehaviorTreeCore`
- **Location:** `speace_core/cellular_brain/cognition/behavior_tree_core.py`
- Nodes: `Selector`, `Sequence`, `Action`, `Condition`, `Inverter`, `Succeeder`
- Execution: tick-based, returns `SUCCESS`, `FAILURE`, `RUNNING`
- Stateful nodes may persist across ticks.

### `ReflexBehaviorLibrary`
- **Location:** `speace_core/cellular_brain/cognition/reflex_behavior_library.py`
- Predefined BTs:
  - `explore_local`: Sequence[stability_ok, curiosity_high, scan_sensors, propose_observe]
  - `avoid_overload`: Sequence[load_high, Selector[reduce_tick, pause_nonessential, propose_rest]]
  - `prioritize_homeostatic_need`: Selector[energy_low→propose_conservation, social_low→propose_dialogue]
  - `search_grounding_input`: Sequence[uncertainty_high, scan_environment, propose_query_memory]
- Each leaf action returns a `BehaviorProposal` dict, not an execution command.

### `BTRuntimeIntegration`
- **Location:** `speace_core/cellular_brain/cognition/bt_runtime_integration.py`
- Adapter executed once per runtime tick after the FSM state update.
- Feeds BTs with `CyberPhysicalSensorArray` snapshot, `HomeostasisEngine` metrics, `OrganismStateMachine` current state.
- Collects proposals and feeds the winning proposal (if any) to `CausalLearningAuditor` as a `suggested_micro_action`.

## Governance & Safety
- BTs are **read-only proposers**.
- All leaf actions that would affect the external world produce a proposal subject to human approval / audit.
- BT execution timeout per tick: max 10 ms to preserve realtime properties.
- Circular/repetitive BT patterns are detected and reported to `MetacognitiveMonitor`.

## Acceptance Criteria
1. At least 3 predefined BTs execute successfully in a 30-tick sandbox simulation.
2. BT leaf actions produce proposals that pass through `CausalLearningAuditor`.
3. BT tick latency stays under 10 ms per tree in benchmark.
4. `Selector` and `Sequence` correctly implement standard BT semantics.
5. Dashboard endpoint `/api/behavior_trees` lists active trees, current node, and recent proposals.
