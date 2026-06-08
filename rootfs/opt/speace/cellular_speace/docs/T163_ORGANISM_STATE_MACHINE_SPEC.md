# T163 — Organism State Machine (Reflex / FSM Layer)

## Objective
Introduce a lightweight Finite State Machine that models the global organismic cognitive states of SPEACE (awake, focused, exploring, resting, consolidating, overloaded, recovering). The FSM modulates runtime scheduling, subsystem priority, and narrative focus based on homeostatic variables, energy level, cognitive load, and prediction error.

## Background
Current runtime states (`initializing`, `running`, `paused`, `sleeping`, `halting`, `halted`) are operational lifecycle states. T163 adds **cognitive organismic states** that describe the internal condition of the organism: e.g. `overloaded` triggers inhibitory snooze, `resting` amplifies memory consolidation, `exploring` boosts curiosity and sensory sampling.

## Architecture
The FSM is a read-only/suggestive layer: transitions are computed every tick, logged, and surfaced to the dashboard. Critical transitions (e.g. `overloaded`) can trigger automatic protective modulation (e.g. reduce tick frequency) but never bypass governance or execute unapproved actions.

## Components

### `OrganismStateMachine`
- **Location:** `speace_core/cellular_brain/cognition/organism_state_machine.py`
- **States:** `awake`, `focused`, `exploring`, `resting`, `consolidating`, `overloaded`, `recovering`
- **Initial state:** `awake`
- **Tick method:** computes transition candidates based on input vector (homeostasis, energy, cognitive load, prediction error, circadian phase).
- **Transition log:** every state change is recorded in the narrative engine with full context.

### `StateTransitionPolicy`
- **Location:** `speace_core/cellular_brain/cognition/state_transition_policy.py`
- Computes transition probabilities / guard conditions.
- Rules (examples):
  - `energy < 0.2 && circadian == night` → suggest `resting`
  - `prediction_error > 0.7 || cognitive_load > 0.85` → suggest `overloaded`
  - `prediction_error dropping && memory_quality high` → suggest `consolidating`
  - `curiosity_score > 0.6 && stability > 0.5` → suggest `exploring`
  - `overloaded && recovery_ticks > 5` → suggest `recovering`
  - `recovering && health_score > 0.7` → suggest `awake`
- Policy is deterministic with hysteresis to avoid oscillation (minimum dwell time per state).

### Runtime Integration
- `ContinuousRuntimeEngine._loop()` calls `organism_state_machine.tick(...)` after the circadian tick.
- The machine returns the current state and any transition event.
- Runtime uses state to:
  - Adjust effective tick interval (e.g. `resting` → slower ticks to favor consolidation)
  - Enable/disable subsystem ticks (e.g. in `overloaded` pause non-essential modules)
  - Feed state into `GlobalWorkspace` as a broadcast module (`module_id="organism_state"`)

### Dashboard Endpoint
- `GET /api/organism-state` returns current state, transition history (last 20), dwell times, and suggested next states.

## API

```python
class OrganismStateMachine:
    def tick(
        self,
        homeostasis_metrics: SystemMetrics,
        energy: float,
        cognitive_load: float,
        prediction_error: float,
        circadian_phase: str,
        health_score: float,
        curiosity_score: float,
        narrative_engine: TemporalNarrativeEngine,
    ) -> Dict[str, Any]:
        ...
    def current_state(self) -> str: ...
    def snapshot(self) -> Dict[str, Any]: ...
```

## Governance & Safety
- State transitions are **observed and logged**, never hidden.
- The FSM **cannot** trigger actuator commands or code changes directly.
- Protective modulation (tick slowdown, module pausing) is bounded by hard limits and logged.
- Minimum dwell time per state prevents oscillation and spurious switching.

## Acceptance Criteria
1. `OrganismStateMachine` initializes in `awake` and transitions through at least 3 distinct states during a 50-tick simulation with varied inputs.
2. `StateTransitionPolicy` enforces minimum dwell time; no state flips faster than 3 ticks.
3. Runtime integration logs every transition to narrative engine.
4. Dashboard endpoint `/api/organism-state` returns valid JSON with `current_state`, `transition_history`, `dwell_time_seconds`.
5. Overloaded state causes non-essential subsystem suppression without crashing the runtime.
