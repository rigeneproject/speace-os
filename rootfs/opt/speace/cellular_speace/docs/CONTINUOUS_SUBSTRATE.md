# Continuous Substrate Architecture (SPEACE)

> **Status:** experimental (introduced with the T-CDS family of tasks)
> **Layer:** cognitive / neurodynamic
> **Replaces:** pure event-driven / discrete-step orchestration of
> the previous architecture.

This document describes SPEACE's transition from a *symbolic pipeline*
to a *continuous neurodynamic substrate*. It is the architectural
companion to the `Istruzioni_periodiche_di_aggiornamento.md` notes and
captures both the goal (a persistent cognitive process rather than a
chat orchestrator) and the concrete modules that implement it.

---

## 1. Motivation

The classical SPEACE architecture was an *event-driven*, *discrete-step*
orchestrator: every cognitive pass was a function call, every
"memory" a snapshot, every "drive" a scalar recomputed per request.
That model has two structural limits:

1. **It is not biological.** Real brains operate as continuous
   dynamical fields: oscillations, phase coupling, energy diffusion,
   criticality, predictive coding. Discrete steps lose the temporal
   structure that gives cognition its *texture*.
2. **It cannot produce persistent cognitive process.** Without a
   continuous time base, the system is forced to start from cold at
   every prompt. There is no inertia, no momentum, no slow drift —
   no substrate for emergence.

The continuous-substrate architecture addresses both by making the
*neural substrate itself* the primary loop and reducing the symbolic
modules to *observers* and *modulators* of that loop.

---

## 2. Module map

| Concern | Module | Path | Role |
|---|---|---|---|
| Continuous time | `TemporalDynamicsEngine` | `dynamics/` | ODE activations, weights, energy |
| Oscillations | `NeuralOscillatorBank` | `dynamics/` | theta/alpha/beta/gamma rhythms |
| Synchrony | `PhaseCouplingEngine` | `dynamics/` | Kuramoto coupling between bands |
| Energy | `EnergyFieldEngine` | `dynamics/` | metabolic diffusion field |
| Prediction | `PredictiveCodingEngine` | `dynamics/` | hierarchical prediction errors |
| Inference | `ActiveInferenceEngine` | `dynamics/` | beliefs, EFE, action selection |
| Drives | `GlobalHomeostaticDrive` | `dynamics/` | exploration/stability/survival/efficiency |
| Criticality | `CriticalityMonitor` | `dynamics/` | avalanche / branching ratio |
| **Wiring** | `ContinuousSubstrateCoordinator` | `runtime/coordinators/substrate_coordinator.py` | owns all the above |
| **Substepping** | `SubstepRuntimeLoop` | `runtime/substep_runtime_loop.py` | advances at sub-second dt |
| **Safety** | `SubstrateStabilityGuard` | `regulation/substrate_stability_guard.py` | runaway / chaos / energy collapse |
| **Criticality feedback** | `CriticalityFeedbackController` | `regulation/criticality_feedback_controller.py` | monitor → circuit |
| **Energy–plasticity** | `EnergyDrivenPlasticity` | `regulation/energy_driven_plasticity.py` | metabolic gating of LTP/LTD |
| **Drive–action** | `ActionBias` | `drives/action_bias.py` | homeostatic drives → action selection |
| **Interoception** | `InteroceptiveSignalBus` | `interoception/interoceptive_signal_bus.py` | internal state → workspace |
| **Embodied loop** | `ActiveInferenceEmbodiedLoop` | `embodiment/active_inference_embodied_loop.py` | AI ↔ actuator |
| **Audit trail** | `EmbodiedActionAuditTrail` | `embodiment/embodied_action_audit_trail.py` | per-step causal record |
| **Audit** | `ContinuousSubstrateAuditor` | `audit/continuous_substrate_audit.py` | verifies runtime wiring |
| **Baseline** | `PersistentProcessBaseline` | `analysis/persistent_process_baseline.py` | end-to-end smoke test |

---

## 3. Runtime integration

The `ContinuousRuntimeEngine` exposes three new methods:

```python
runtime.attach_continuous_substrate(
    substrate_coordinator=coordinator,
    stability_guard=guard,
)
runtime.tick_substrate(
    tick_interval=1.0,
    activations=...,
    prediction_error=...,
    last_drive_metrics=...,
)
```

`tick_substrate` advances the substrate at sub-second resolution
(`tick_interval / substep_dt` substeps per outer tick), evaluates
the safety guard, and stores the latest state in
`runtime._last_substrate_state` for downstream observers.

The orchestrator must enable the corresponding feature flags for the
substrate modules to do anything:

```python
orchestrator.temporal_dynamics_enabled = True
orchestrator.neural_oscillator_enabled  = True
orchestrator.phase_coupling_enabled     = True
orchestrator.energy_field_enabled       = True
orchestrator.predictive_coding_enabled  = True
orchestrator.active_inference_enabled   = True
orchestrator.homeostatic_drive_enabled  = True
orchestrator.criticality_monitor_enabled = True
orchestrator.embodiment_enabled         = True
```

The audit runner (`ContinuousSubstrateAuditor`) verifies that all of
the above are true at runtime and emits a list of human-readable
recommendations when something is missing.

---

## 4. Substepping and the gamma-band problem

`NeuralOscillatorBank` runs a 40 Hz gamma band by default. At a
1 s outer tick the gamma band can change phase 40 times, but most
of that information is lost if the rest of the substrate is only
queried once per tick. The `SubstepRuntimeLoop` therefore runs
``n_substeps = tick_interval / substep_dt`` substeps per outer tick
(100 by default for 1 s × 0.01 s), advancing *all* continuous
modules inside each substep. This gives the system a usable
sub-second resolution without changing the outer wall-clock
schedule.

---

## 5. Stability: why the guard exists

Continuous dynamics can diverge. The `SubstrateStabilityGuard`
monitors:

* **Kuramoto order parameter** sustained above 0.92 → hyper-synchrony
  (rigidity, loss of representational flexibility).
* **Kuramoto order parameter** sustained below 0.05 → hypo-synchrony
  (chaos).
* **Branching ratio** outside [0.5, 1.5] → criticality drift.
* **Free energy** grows > 3× in a 30-tick window → unbounded
  surprise.
* **Activation explosion** in the host circuit.
* **Fatigue fraction** above 70 % → metabolic collapse.
* **Mean energy** below 0.05 → emergency.

Each violation produces a `GuardVerdict` and a dictionary of
*recommendations* (e.g. `{"coupling_strength_reduction": 0.1,
"excitability_delta": -0.3}`) that the orchestrator can apply.
An emergency verdict also sets a cooldown so the system can
recover before being re-evaluated.

---

## 6. Embodiment closure

The classical embodiment loop (T72) used active inference as a
*symbolic* decision-maker: the selected action translated into an
internal `signal_type` rather than a real actuator proposal. The
`ActiveInferenceEmbodiedLoop` closes that gap:

1. The world model predicts the next state.
2. The real `post_state` is read from the sensor array.
3. The prediction error is computed and passed back to the active
   inference engine as Bayesian surprise.
4. The engine selects the lowest-EFE action.
5. The action is mapped (via `ActionBias` or the default table) to
   a concrete `EmbodiedActionActuator.propose_action` call.
6. The proposal is recorded in the audit trail along with the
   pre-state, prediction, post-state, surprise and belief.
7. The prediction error is fed into the predictive coding engine
   as a teaching signal for the next sensory layer.

This produces a verifiable causal loop: every audit entry has
the five elements required to confirm that the system *learned*
from the action's outcome.

---

## 7. Verification

Run the smoke test and the full audit:

```bash
pytest tests/test_continuous_substrate.py -v
python tests/test_persistent_process_smoke.py
python -c "
from speace_core.cellular_brain.audit.continuous_substrate_audit import ContinuousSubstrateAuditor
from speace_core.runtime.continuous_runtime_engine import ContinuousRuntimeEngine
auditor = ContinuousSubstrateAuditor()
report = auditor.audit(runtime)
print(report.summary())
"
```

The baseline runner produces a JSONL trace at
`data/persistent_process/baseline.jsonl` and a summary at
`data/persistent_process/summary.json`. The trace includes
per-tick `sim_time`, `kuramoto_order_parameter`,
`mean_energy_field`, `free_energy`, `branching_ratio`, drives,
modulations, criticality recommendation, selected action and
guard verdict.

---

## 8. What this does *not* solve

The continuous substrate is a *necessary* but not *sufficient*
condition for "true" persistent cognition. It is still bounded by:

* The absence of real sensors in production: SPEACE only "feels" the
  host machine through the cyber-physical sensor array.
* The symbolic layer's limited expressivity: the global workspace
  can broadcast and recall but does not yet have a compositional
  semantics.
* The lack of meta-cognitive reflection on the substrate itself:
  SPEACE can *observe* its dynamics but does not yet narrate them
  to itself in continuous prose.

The next architectural leap is therefore not *more* substrate, but
*meta-cognition over* the substrate. The `InteroceptiveSignalBus`
is the first step in that direction: it makes the substrate
*legible* to the cognitive layer, so the workspace, the self-model
and the active inference engine can all reason about it.
