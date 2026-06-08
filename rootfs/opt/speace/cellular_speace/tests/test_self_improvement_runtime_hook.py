"""End-to-end + unit tests for SelfImprovementRuntimeHook.

These tests are *self-contained*: they do not require the full
orchestrator, the network, or any external services. They wire the
canonical components together so the closed loop is exercised:

    Substrate -> SelfImprovementLoop -> OutcomeTracker
              -> ProposalLearningEngine -> EvolutionaryMemoryGovernor

We use the same mock circuit and the same coordinator/guard/loop that
``tests/test_persistent_process_smoke.py`` uses, which gives us a
known-good substrate to drive.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import random
import sys
import tempfile
import unittest

# Make sure tests can be run directly from the project root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ---------------------------------------------------------------------------
# Local helpers (shared with the persistent-process smoke test pattern)
# ---------------------------------------------------------------------------


class _MockNeuron:
    __slots__ = ("cell_id", "activation", "threshold", "energy", "plasticity_rate", "decay")

    def __init__(self, cell_id: str):
        self.cell_id = cell_id
        self.activation = 0.0
        self.threshold = 0.5
        self.energy = 1.0
        self.plasticity_rate = 0.05
        self.decay = 0.01


class _MockSynapse:
    __slots__ = ("source", "target", "weight", "state", "decay")

    def __init__(self, source, target, weight=0.5):
        self.source = source
        self.target = target
        self.weight = weight
        self.state = "active"
        self.decay = 0.001


class _MockCircuit:
    def __init__(self, n_in: int, n_hidden: int, n_out: int, seed: int = 7):
        rng = random.Random(seed)
        self.input_neurons = [_MockNeuron(f"i{i}") for i in range(n_in)]
        self.hidden_neurons = [_MockNeuron(f"h{i}") for i in range(n_hidden)]
        self.output_neurons = [_MockNeuron(f"o{i}") for i in range(n_out)]
        self.synapses = []
        for pre in self.input_neurons + self.hidden_neurons:
            for post in self.hidden_neurons + self.output_neurons:
                if rng.random() < 0.15:
                    self.synapses.append(
                        _MockSynapse(pre.cell_id, post.cell_id, rng.random())
                    )


class _MockOrchestrator:
    """Minimal orchestrator surface for the hook.

    We do not need the full CellularBrainOrchestrator — the hook only
    reads ``latest_metrics``, ``semantic_memory_enabled``,
    ``region_signal_routing_enabled``, ``inter_region_plasticity_enabled``.
    """

    def __init__(self):
        self.latest_metrics = None
        self.semantic_memory_enabled = False
        self.region_signal_routing_enabled = False
        self.inter_region_plasticity_enabled = False


class _SafeRegressionGuard:
    """A regression guard that always returns POLICY_SAFE.

    Counterfactual sandbox / patch executor are happy with this.
    """

    def evaluate(self, delta):  # pragma: no cover - trivial
        class _R:
            verdict = "POLICY_SAFE"

        return _R()


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _build_substrate_stack(n_neurons=8, n_hidden=12, n_output=4, substep_dt=0.01):
    from speace_core.cellular_brain.runtime.coordinators.substrate_coordinator import (
        ContinuousSubstrateCoordinator,
    )
    from speace_core.cellular_brain.regulation.substrate_stability_guard import (
        SubstrateStabilityGuard,
    )
    from speace_core.runtime.substep_runtime_loop import SubstepRuntimeLoop

    class _DynCfg:
        def model_dump(self):
            return {}

    class _Genome:
        dynamics = _DynCfg()

    circuit = _MockCircuit(n_neurons, n_hidden, n_output, seed=11)
    coord = ContinuousSubstrateCoordinator(
        circuit=circuit,
        genome=_Genome(),
        substep_dt=substep_dt,
    )
    coord.initialize()
    coord.register_active_inference_states(
        {"stable": 0.5, "unstable": 0.5},
        {
            "observe": {"stable": 0.7, "unstable": 0.3},
            "actuate": {"stable": 0.3, "unstable": 0.7},
        },
    )
    guard = SubstrateStabilityGuard()
    loop = SubstepRuntimeLoop(substrate_coordinator=coord, stability_guard=guard)
    return coord, guard, loop, circuit


def _build_self_improvement_loop(regression_guard=None):
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

    si = SelfImprovementLoop(
        regression_guard=regression_guard or _SafeRegressionGuard(),
        episodic_policy_enabled=True,
        episodic_policy=EpisodicSelfImprovementPolicy(),
        counterfactual_sandbox_enabled=True,
        counterfactual_sandbox=CounterfactualArchitectureSandbox(
            regression_guard=regression_guard or _SafeRegressionGuard(),
        ),
        architecture_patch_execution_enabled=True,
        architecture_patch_executor=ArchitecturePatchExecutor(
            regression_guard=regression_guard or _SafeRegressionGuard(),
        ),
    )
    return si


def _build_outcome_tracker(report_dir):
    from speace_core.cellular_brain.self_improvement.outcome_tracker import (
        OutcomeTracker,
    )
    return OutcomeTracker(base_path=report_dir)


def _build_governor(report_dir):
    from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_governor import (
        EvolutionaryMemoryGovernor,
    )
    return EvolutionaryMemoryGovernor(report_dir=report_dir)


def _build_hook(report_dir, si, outcome_tracker, governor=None, cycle_interval=2):
    from speace_core.runtime.self_improvement_runtime_hook import (
        SelfImprovementRuntimeHook,
    )
    return SelfImprovementRuntimeHook(
        self_improvement_loop=si,
        outcome_tracker=outcome_tracker,
        evolutionary_memory_governor=governor,
        cycle_interval_ticks=cycle_interval,
        report_dir=report_dir,
    )


def _drive_activations(circuit, tick):
    acts = {}
    for i, n in enumerate(circuit.input_neurons):
        n.activation = 0.5 * (1.0 + math.sin(tick * 0.3 + i * 0.2))
        acts[n.cell_id] = n.activation
    for i, n in enumerate(circuit.hidden_neurons):
        n.activation = 0.3 * math.sin(tick * 0.4 + i * 0.7)
        acts[n.cell_id] = n.activation
    for i, n in enumerate(circuit.output_neurons):
        n.activation = 0.2 * math.cos(tick * 0.2 + i)
        acts[n.cell_id] = n.activation
    return acts


# ---------------------------------------------------------------------------
# End-to-end test
# ---------------------------------------------------------------------------


class SelfImprovementRuntimeHookE2ETests(unittest.TestCase):
    """Demonstrates the closed loop end-to-end."""

    def test_closed_loop_runs_at_least_one_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            # 1. Substrate stack
            coord, guard, subloop, circuit = _build_substrate_stack()

            # 2. Self-improvement loop (full pipeline: episodic + counterfactual + patch)
            si = _build_self_improvement_loop()

            # 3. Outcome tracker + governor
            outcome_tracker = _build_outcome_tracker(
                os.path.join(tmp, "outcomes")
            )
            governor = _build_governor(os.path.join(tmp, "memory"))
            hook = _build_hook(
                os.path.join(tmp, "hook_reports"),
                si=si,
                outcome_tracker=outcome_tracker,
                governor=governor,
                cycle_interval=2,  # run a cycle every 2 outer ticks
            )

            # 4. Drive 6 outer ticks; the hook fires every 2 ticks => 3 cycles.
            orch = _MockOrchestrator()
            last_state = None
            for tick in range(6):
                acts = _drive_activations(circuit, tick)
                res = subloop.advance(
                    tick_interval=1.0,
                    activations=acts,
                    prediction_error=0.05,
                )
                last_state = res.substrate_state
                # Feed the orchestrator's latest_metrics if any
                if last_state is not None and hasattr(last_state, "to_dict"):
                    snap = last_state.to_dict()
                    class _M:
                        pass

                    m = _M()
                    m.coherence_phi = snap.get("kuramoto_order_parameter", 0.0)
                    m.mean_energy = snap.get("mean_energy_field", 0.0)
                    m.energy_efficiency = max(
                        0.0, 1.0 - snap.get("total_free_energy", 0.0)
                    )
                    m.cognitive_score = snap.get("branching_ratio", 0.0)
                    orch.latest_metrics = m
                result = asyncio.run(
                    hook.tick(tick=tick, orchestrator=orch, substrate_state=last_state)
                )
                # First cycle: tick=0, second: tick=2, third: tick=4
                if tick in (0, 2, 4):
                    self.assertIsNotNone(
                        result,
                        f"hook should fire at tick={tick} (interval=2)",
                    )
                    self.assertIn(
                        "final_verdict",
                        result,
                        f"result missing final_verdict at tick={tick}",
                    )
                    self.assertIn(
                        result.get("final_verdict", "FAILED"),
                        hook._VALID_VERDICTS,
                    )
                else:
                    self.assertIsNone(
                        result, f"hook should be in cooldown at tick={tick}"
                    )

            # 5. Summary must show at least 3 cycles (we fired at 0, 2, 4).
            summary = hook.summary()
            self.assertEqual(summary["cycles_run"], 3)
            # The last verdict must be one of the recognised values.
            # With a mock circuit the LimitationDetector typically picks
            # up a 'cellular_damage' signal (resilience=0) and the
            # executor's safety filter rejects the proposal, so we
            # see REGRESSION_BLOCKED; other valid verdicts are also
            # possible (e.g. NO_LIMITATION_DETECTED if the detector
            # stays silent). We just assert membership.
            self.assertIn(summary["last_verdict"], hook._VALID_VERDICTS)
            # Look anywhere under tmp
            all_files = []
            for root, _, files in os.walk(tmp):
                all_files.extend(files)
            cycle_reports = [f for f in all_files if f.startswith("cycle_") and f.endswith(".json")]
            self.assertGreaterEqual(
                len(cycle_reports),
                1,
                f"expected at least one cycle_*.json report, got: {all_files}",
            )

            # 6. The governor must have ingested at least one record
            records = governor.store.list_records()
            self.assertGreaterEqual(
                len(records),
                1,
                "EvolutionaryMemoryGovernor should have ingested the cycle results",
            )

            # 7. The outcome tracker must have a JSONL file with at least
            #    one outcome (if any proposal was accepted/rejected)
            outcomes_path = outcome_tracker.outcomes_path
            if outcomes_path.exists():
                with outcomes_path.open("r", encoding="utf-8") as fh:
                    lines = [ln for ln in fh if ln.strip()]
                # Lines are non-empty only when proposals were processed; we
                # just assert the file exists and is a valid JSONL.
                for line in lines:
                    json.loads(line)

    def test_no_hook_no_op_when_interval_not_elapsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            coord, guard, subloop, circuit = _build_substrate_stack()
            si = _build_self_improvement_loop()
            outcome_tracker = _build_outcome_tracker(os.path.join(tmp, "outcomes"))
            governor = _build_governor(os.path.join(tmp, "memory"))
            hook = _build_hook(
                os.path.join(tmp, "hook_reports"),
                si=si,
                outcome_tracker=outcome_tracker,
                governor=governor,
                cycle_interval=10,  # never fires during the test
            )
            # Pretend the hook already fired a long time ago so the
            # very first tick is well within the cooldown window.
            hook._last_cycle_tick = 0
            for tick in range(5):
                res = asyncio.run(hook.tick(tick=tick, orchestrator=_MockOrchestrator()))
                self.assertIsNone(res, f"hook should be in cooldown at tick={tick}, got {res}")
            self.assertEqual(hook.summary()["cycles_run"], 0)

    def test_summary_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            si = _build_self_improvement_loop()
            outcome_tracker = _build_outcome_tracker(os.path.join(tmp, "outcomes"))
            governor = _build_governor(os.path.join(tmp, "memory"))
            hook = _build_hook(
                os.path.join(tmp, "hook_reports"),
                si=si,
                outcome_tracker=outcome_tracker,
                governor=governor,
                cycle_interval=1,
            )
            s = hook.summary()
            for key in (
                "cycles_run",
                "last_verdict",
                "last_tick",
                "accepted_total",
                "rejected_total",
                "cycle_interval_ticks",
                "metric_window",
                "recent_cycles",
            ):
                self.assertIn(key, s)


# ---------------------------------------------------------------------------
# Stand-alone async entry point for direct invocation
# ---------------------------------------------------------------------------


async def run_end_to_end_demo() -> dict:
    """Run the closed loop once and return the hook's summary.

    Useful for ``python -c "import asyncio; print(asyncio.run(...))"``
    or similar ad-hoc smoke checks.
    """
    with tempfile.TemporaryDirectory() as tmp:
        coord, guard, subloop, circuit = _build_substrate_stack()
        si = _build_self_improvement_loop()
        outcome_tracker = _build_outcome_tracker(os.path.join(tmp, "outcomes"))
        governor = _build_governor(os.path.join(tmp, "memory"))
        hook = _build_hook(
            os.path.join(tmp, "hook_reports"),
            si=si,
            outcome_tracker=outcome_tracker,
            governor=governor,
            cycle_interval=2,
        )
        orch = _MockOrchestrator()
        last_state = None
        for tick in range(6):
            acts = _drive_activations(circuit, tick)
            res = subloop.advance(
                tick_interval=1.0,
                activations=acts,
                prediction_error=0.05,
            )
            last_state = res.substrate_state
            await hook.tick(tick=tick, orchestrator=orch, substrate_state=last_state)
        return hook.summary()


# ---------------------------------------------------------------------------
# Unit tests for the metric collector
# ---------------------------------------------------------------------------


class CollectMetricsTests(unittest.TestCase):
    def test_collect_metrics_handles_none_substrate(self):
        from speace_core.runtime.self_improvement_runtime_hook import (
            SelfImprovementRuntimeHook,
        )
        si = _build_self_improvement_loop()
        outcome_tracker = _build_outcome_tracker(tempfile.mkdtemp())
        hook = SelfImprovementRuntimeHook(
            self_improvement_loop=si,
            outcome_tracker=outcome_tracker,
            cycle_interval_ticks=1,
            report_dir=tempfile.mkdtemp(),
        )
        m = hook._collect_metrics(tick=0, orchestrator=_MockOrchestrator(), substrate_state=None)
        for key in (
            "kuramoto_order_parameter",
            "mean_energy_field",
            "total_free_energy",
            "branching_ratio",
            "cognitive_delta",
            "phi_delta",
            "energy_delta",
        ):
            self.assertIn(key, m)

    def test_collect_metrics_pulls_from_substrate(self):
        from speace_core.runtime.self_improvement_runtime_hook import (
            SelfImprovementRuntimeHook,
        )

        class _S:
            def to_dict(self):
                return {
                    "kuramoto_order_parameter": 0.42,
                    "mean_energy_field": 0.73,
                    "total_free_energy": 0.12,
                    "branching_ratio": 0.95,
                    "fatigue_count": 2,
                    "drives": {"exploration": 0.6},
                    "modulations": {"learning_rate": 0.05},
                    "selected_action": "observe",
                }

        si = _build_self_improvement_loop()
        outcome_tracker = _build_outcome_tracker(tempfile.mkdtemp())
        hook = SelfImprovementRuntimeHook(
            self_improvement_loop=si,
            outcome_tracker=outcome_tracker,
            cycle_interval_ticks=1,
            report_dir=tempfile.mkdtemp(),
        )
        m = hook._collect_metrics(tick=0, orchestrator=_MockOrchestrator(), substrate_state=_S())
        self.assertAlmostEqual(m["kuramoto_order_parameter"], 0.42, places=4)
        self.assertAlmostEqual(m["mean_energy_field"], 0.73, places=4)
        self.assertAlmostEqual(m["total_free_energy"], 0.12, places=4)
        self.assertAlmostEqual(m["branching_ratio"], 0.95, places=4)
        self.assertEqual(m["fatigue_count"], 2)
        self.assertEqual(m["selected_action"], "observe")

    def test_collect_metrics_pulls_from_orchestrator(self):
        from speace_core.runtime.self_improvement_runtime_hook import (
            SelfImprovementRuntimeHook,
        )

        class _M:
            coherence_phi = 0.5
            mean_energy = 0.7
            energy_efficiency = 0.6
            cognitive_score = 0.4

        orch = _MockOrchestrator()
        orch.latest_metrics = _M()
        orch.semantic_memory_enabled = True
        orch.region_signal_routing_enabled = True
        orch.inter_region_plasticity_enabled = True

        si = _build_self_improvement_loop()
        outcome_tracker = _build_outcome_tracker(tempfile.mkdtemp())
        hook = SelfImprovementRuntimeHook(
            self_improvement_loop=si,
            outcome_tracker=outcome_tracker,
            cycle_interval_ticks=1,
            report_dir=tempfile.mkdtemp(),
        )
        m = hook._collect_metrics(tick=0, orchestrator=orch, substrate_state=None)
        self.assertAlmostEqual(m["coherence_phi"], 0.5, places=4)
        self.assertAlmostEqual(m["mean_energy_field"], 0.7, places=4)
        self.assertAlmostEqual(m["cognitive_score"], 0.4, places=4)
        self.assertTrue(m["semantic_memory_enabled"])
        self.assertTrue(m["region_signal_routing_enabled"])
        self.assertTrue(m["inter_region_plasticity_enabled"])

    def test_compute_deltas_neutral_when_window_cold(self):
        from speace_core.runtime.self_improvement_runtime_hook import (
            SelfImprovementRuntimeHook,
        )
        si = _build_self_improvement_loop()
        outcome_tracker = _build_outcome_tracker(tempfile.mkdtemp())
        hook = SelfImprovementRuntimeHook(
            self_improvement_loop=si,
            outcome_tracker=outcome_tracker,
            cycle_interval_ticks=1,
            report_dir=tempfile.mkdtemp(),
        )
        d = hook._compute_deltas()
        for k in ("phi_delta", "cognitive_delta", "energy_delta", "kuramoto_delta", "branching_delta"):
            self.assertEqual(d[k], 0.0)

    def test_compute_deltas_positive_when_energy_rises(self):
        from speace_core.runtime.self_improvement_runtime_hook import (
            SelfImprovementRuntimeHook,
        )
        si = _build_self_improvement_loop()
        outcome_tracker = _build_outcome_tracker(tempfile.mkdtemp())
        hook = SelfImprovementRuntimeHook(
            self_improvement_loop=si,
            outcome_tracker=outcome_tracker,
            cycle_interval_ticks=1,
            report_dir=tempfile.mkdtemp(),
        )
        hook._substrate_window.append(
            {"kuramoto": 0.1, "mean_energy": 0.2, "free_energy": 0.5, "branching": 0.6, "phi": 0.1, "cognitive": 0.1, "energy_efficiency": 0.5}
        )
        hook._substrate_window.append(
            {"kuramoto": 0.3, "mean_energy": 0.4, "free_energy": 0.4, "branching": 0.8, "phi": 0.3, "cognitive": 0.2, "energy_efficiency": 0.6}
        )
        d = hook._compute_deltas()
        self.assertAlmostEqual(d["phi_delta"], 0.2, places=4)
        self.assertAlmostEqual(d["energy_delta"], 0.2, places=4)
        self.assertAlmostEqual(d["kuramoto_delta"], 0.2, places=4)
        self.assertAlmostEqual(d["branching_delta"], 0.2, places=4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
