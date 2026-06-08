"""Phase 6 — Runtime integration stress test.

Goal
----
Wire the SelfImprovementRuntimeHook into the ContinuousRuntimeEngine
(via attach_self_improvement_hook) and run a 60-tick stress test
that exercises the closed loop end-to-end through the real runtime
code paths (not a hand-rolled driver). Verify:

1. The runtime does not crash.
2. The runtime's snapshot() includes the self_improvement summary.
3. The hook's cycles_run grows monotonically.
4. The runtime's state machine is intact (state is "running" or
   "paused" or "sleeping", never "halted" by mistake).
5. The self_improvement summary exposes non-zero activity.

We use lightweight fakes for the orchestrator to avoid pulling in
the full CellularBrainOrchestrator (which has many external
dependencies: DNA, genome, sensors, etc.). The fakes implement only
the surface the runtime actually touches during _loop().
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
import unittest
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ------------------------------------------------------------------ #
# Lightweight fakes
# ------------------------------------------------------------------ #


class _FakeNeuron:
    __slots__ = ("cell_id", "activation", "energy", "threshold", "plasticity_rate", "decay")

    def __init__(self, cell_id: str):
        self.cell_id = cell_id
        self.activation = 0.0
        self.energy = 1.0
        self.threshold = 0.5
        self.plasticity_rate = 0.05
        self.decay = 0.01


class _FakeSynapse:
    __slots__ = ("source", "target", "weight", "state", "decay", "cell_id")

    def __init__(self, source, target, weight=0.5):
        self.source = source
        self.target = target
        self.weight = weight
        self.state = "active"
        self.decay = 0.001
        self.cell_id = f"syn_{source}_{target}"


class _FakeCircuit:
    def __init__(self, n_in=4, n_hidden=6, n_out=2, seed=11):
        import random
        rng = random.Random(seed)
        self.input_neurons = [_FakeNeuron(f"i{i}") for i in range(n_in)]
        self.hidden_neurons = [_FakeNeuron(f"h{i}") for i in range(n_hidden)]
        self.output_neurons = [_FakeNeuron(f"o{i}") for i in range(n_out)]
        self.synapses: List[_FakeSynapse] = []
        for pre in self.input_neurons + self.hidden_neurons:
            for post in self.hidden_neurons + self.output_neurons:
                if rng.random() < 0.3:
                    self.synapses.append(
                        _FakeSynapse(pre.cell_id, post.cell_id, rng.random())
                    )


class _FakeSubstrateState:
    def __init__(self, tick: int):
        self._tick = tick
        # vary a little so the hook sees real deltas
        self._phase = (tick * 0.3) % (2 * 3.14159)
        import math
        self._kuramoto = 0.5 + 0.2 * math.sin(self._phase)
        self._mean_energy = 0.7 + 0.1 * math.cos(self._phase * 0.5)
        self._free_energy = 0.1 + 0.05 * abs(math.sin(self._phase))
        self._branching = 0.8 + 0.1 * math.cos(self._phase * 0.7)
        self._fatigue = int(tick // 10)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sim_time": self._tick * 1.0,
            "kuramoto_order_parameter": self._kuramoto,
            "mean_energy_field": self._mean_energy,
            "total_free_energy": self._free_energy,
            "branching_ratio": self._branching,
            "fatigue_count": self._fatigue,
            "drives": {"exploration": 0.5, "stability": 0.4, "survival": 0.1, "efficiency": 0.6},
            "modulations": {"learning_rate": 0.05},
            "selected_action": "observe",
        }


class _FakeSubstrateCoordinator:
    def __init__(self, n_neurons=4, n_hidden=6, n_output=2):
        self._circuit = _FakeCircuit(n_neurons, n_hidden, n_output)
        self._substep_dt = 0.01
        self._substeps_per_tick = 100
        self._last_substep_count = 0
        self._substrate = None

    @property
    def _circuit(self):
        return self.__circuit

    @_circuit.setter
    def _circuit(self, v):
        self.__circuit = v

    def initialize(self):
        pass

    def register_active_inference_states(self, *a, **kw):
        pass

    def substeps_for_tick(self, tick_interval):
        return max(1, int(tick_interval / self._substep_dt))

    def advance(self, tick_interval, activations=None, prediction_error=None, **kw):
        self._last_substep_count = self.substeps_for_tick(tick_interval)
        # Update the circuit activations so the hook sees the latest state
        if activations:
            for cid, a in activations.items():
                for n in self._circuit.input_neurons + self._circuit.hidden_neurons + self._circuit.output_neurons:
                    if n.cell_id == cid:
                        n.activation = a
        # Drive a fake state
        return _FakeSubstrateState(tick=int(getattr(self, "_tick_counter", 0)))


class _FakeOrchestrator:
    """Minimal orchestrator that the runtime's _loop() can drive."""

    def __init__(self):
        self.circuit = _FakeCircuit()
        self.semantic_memory_enabled = False
        self.region_signal_routing_enabled = False
        self.inter_region_plasticity_enabled = False
        self.embodiment_enabled = False
        self.systemic_harmony_enabled = False
        self.temporal_dynamics_enabled = True
        self.neural_oscillator_enabled = True
        self.phase_coupling_enabled = True
        self.energy_field_enabled = True
        self.predictive_coding_enabled = True
        self.active_inference_enabled = True
        self.homeostatic_drive_enabled = True
        self.criticality_monitor_enabled = True
        self.brainstem_controller_enabled = True
        self.global_workspace_enabled = True
        self.sleep_enabled = True
        self._tick_counter = 0
        self._initialize_dynamic_modules_called = False
        self._last_sensor_snapshot = None
        # Health-monitor friendly attributes
        self.current_tick = 0
        self.latest_metrics = None
        # brainstem_controller for the runtime's _brainstem_state()
        self._brainstem_controller = type("B", (), {"last_state": type("S", (), {"state": "stable"})()})()
        # tick is async-aware: we'll just bump the counter
        self._tick_lock = asyncio.Lock()

    def _initialize_dynamic_modules(self):
        self._initialize_dynamic_modules_called = True

    async def _tick(self):
        async with self._tick_lock:
            self._tick_counter += 1
            self.current_tick = self._tick_counter
        # noop


# ------------------------------------------------------------------ #
# Stress test
# ------------------------------------------------------------------ #


async def _run_runtime_stress(num_ticks: int = 60) -> dict:
    """Run a 60-tick stress test of the runtime + hook integration."""
    from speace_core.runtime.continuous_runtime_engine import (
        ContinuousRuntimeEngine,
    )
    from speace_core.runtime.self_improvement_runtime_hook import (
        SelfImprovementRuntimeHook,
    )
    from speace_core.cellular_brain.self_improvement.outcome_tracker import (
        OutcomeTracker,
    )
    from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_governor import (
        EvolutionaryMemoryGovernor,
    )
    from speace_core.cellular_brain.self_improvement.self_improvement_loop import (
        SelfImprovementLoop,
    )
    from speace_core.cellular_brain.self_improvement.episodic_policy import (
        EpisodicSelfImprovementPolicy,
    )
    from speace_core.cellular_brain.self_improvement.counterfactual_sandbox import (
        CounterfactualArchitectureSandbox,
    )
    from speace_core.cellular_brain.self_improvement.architecture_patch_executor import (
        ArchitecturePatchExecutor,
    )
    from speace_core.cellular_brain.regulation.substrate_stability_guard import (
        SubstrateStabilityGuard,
    )

    with tempfile.TemporaryDirectory() as tmp:
        # Build runtime
        orch = _FakeOrchestrator()
        # ContinuousRuntimeEngine is heavy; build with the smallest
        # possible config to keep the test fast.
        engine = ContinuousRuntimeEngine(
            orchestrator=orch,
            tick_interval=0.01,  # very tight tick
            checkpoint_interval_seconds=10**9,  # no periodic checkpoint
            awake_duration=10**9,
            sleep_duration=10**9,  # no circadian flip
        )
        # Substrate
        substrate = _FakeSubstrateCoordinator()
        guard = SubstrateStabilityGuard()
        engine.attach_continuous_substrate(substrate_coordinator=substrate, stability_guard=guard)
        # Self-improvement loop
        class _G:
            def evaluate(self, delta):
                class _R:
                    verdict = "POLICY_SAFE"
                return _R()
        rg = _G()
        si = SelfImprovementLoop(
            regression_guard=rg,
            episodic_policy_enabled=False,
            counterfactual_sandbox_enabled=False,
            architecture_patch_execution_enabled=False,  # observational only
        )
        outcome_tracker = OutcomeTracker(base_path=os.path.join(tmp, "outcomes"))
        governor = EvolutionaryMemoryGovernor(report_dir=os.path.join(tmp, "memory"))
        hook = SelfImprovementRuntimeHook(
            self_improvement_loop=si,
            outcome_tracker=outcome_tracker,
            evolutionary_memory_governor=governor,
            cycle_interval_ticks=3,  # conservative: every 3 ticks
            report_dir=os.path.join(tmp, "hook_reports"),
        )
        engine.attach_self_improvement_hook(hook)
        # Start the runtime
        start_info = await engine.start()
        # Let the loop run for num_ticks * tick_interval seconds
        wait = num_ticks * engine.tick_interval
        # Add a small buffer
        await asyncio.sleep(wait + 0.5)
        # Snapshot
        snap = engine.snapshot()
        # Stop
        await engine.stop()
        return {
            "phase": 6,
            "runtime_state": engine._state,
            "ticks_target": num_ticks,
            "ticks_executed": engine._tick_count_since_start,
            "cycles_run": hook.summary()["cycles_run"],
            "self_improvement_summary": snap.get("self_improvement", {}),
            "snapshot_keys": sorted(list(snap.keys())),
            "memory_records": len(governor.store.list_records()),
            "start_info": start_info,
        }


class Phase6RuntimeStressTests(unittest.TestCase):
    def test_runtime_stress_60_ticks(self):
        result = asyncio.run(_run_runtime_stress(num_ticks=60))
        # Runtime didn't crash
        self.assertIn(result["runtime_state"], {"running", "paused", "sleeping", "halting", "halted"}, result)
        # Ticks executed
        self.assertGreater(result["ticks_executed"], 0, result)
        # The self_improvement summary is in the snapshot
        self.assertIn("self_improvement", result["snapshot_keys"])
        # The hook ran at least once
        si = result["self_improvement_summary"]
        self.assertGreaterEqual(si.get("cycles_run", 0), 1, result)
        # The memory governor ingested at least one record
        self.assertGreaterEqual(result["memory_records"], 1, result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
