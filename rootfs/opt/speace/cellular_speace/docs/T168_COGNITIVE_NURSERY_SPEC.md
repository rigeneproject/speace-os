# T168 — Simulated Cognitive Nursery

## Objective
Transform simulated environments into structured "cognitive nurseries": safe virtual playgrounds where SPEACE can practice infant learning, causal reasoning, and social interaction without real-world risk.

## Background
SPEACE has `SimulatedEnvironmentEngine`, `WorldModelSandbox`, and `GuidedInfantLearningProtocol`. T168 ties these into a pedagogical scenario system with virtual agents, physics events, and symbolic grounding exercises.

## Architecture
The nursery is fully sandboxed and opt-in. Outcomes from nursery sessions flow into concept formation and causal world model **only after** human validation gate.

## Components

### `CognitiveNurseryScenarioBuilder`
- **Location:** `speace_core/cellular_brain/embodiment/cognitive_nursery_scenario_builder.py`
- Scenario templates:
  - `falling_objects` — gravity, collision, cause/effect
  - `agent_approach` — virtual agent moves toward/away; social proximity
  - `tool_use` — object manipulation to reach goal
  - `hidden_object` — object permanence, memory test
- Each scenario defines controllable variables (gravity, agent speed, reward signal).

### `NurserySessionOrchestrator`
- **Location:** `speace_core/cellular_brain/postnatal_learning/nursery_session_orchestrator.py`
- Human selects scenario and duration.
- SPEACE observes passively, generates predictions, compares with outcomes.
- Predictions are logged; surprise drives curiosity update and concept formation trigger.
- Integration with `GuidedInfantLearningProtocol` for human-guided labeling.

### `VirtualAgentPopulation`
- **Location:** `speace_core/cellular_brain/embodiment/virtual_agent_population.py`
- Lightweight agents inside nursery, driven by simplified BT/FSM.
- Provide social interaction targets: cooperation, competition, communication.
- Agents have simple drives (approach food, avoid threat) so SPEACE can model their minds.

## Governance & Safety
- Nursery is **opt-in per session**; no autonomous activation.
- Raw sensory data from nursery is **not persisted** by default; only symbolic summaries and validated concepts enter memory.
- Virtual agents cannot execute outside the nursery sandbox.
- World model real is kept separate from nursery world model; merge requires explicit gate.

## Acceptance Criteria
1. At least 3 scenario templates load and execute without errors.
2. Nursery session produces a prediction-error log and a curiosity update.
3. Virtual agents exhibit distinct behavioral patterns based on their BT/FSM configuration.
4. Human approval gate intercepts any attempt to export a nursery-derived concept to main memory.
5. Dashboard endpoint `/api/nursery` lists scenarios, active sessions, and session logs.
