"""Unit tests for the continuous-substrate stack."""
from __future__ import annotations

import math
import os
import sys
import tempfile
import unittest

# Make sure tests can be run directly from the project root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


from speace_core.cellular_brain.regulation.substrate_stability_guard import (
    GuardVerdict,
    SubstrateStabilityGuard,
)
from speace_core.cellular_brain.regulation.energy_driven_plasticity import (
    EnergyDrivenPlasticity,
)
from speace_core.cellular_brain.regulation.criticality_feedback_controller import (
    CriticalityFeedbackController,
)
from speace_core.cellular_brain.drives.action_bias import ActionBias
from speace_core.cellular_brain.interoception.interoceptive_signal_bus import (
    InteroceptiveSignalBus,
)
from speace_core.cellular_brain.dynamics.criticality_monitor import (
    Avalanche,
    CriticalityMonitor,
    Spike,
)
from speace_core.cellular_brain.dynamics.active_inference_engine import (
    ActiveInferenceEngine,
)
from speace_core.cellular_brain.dynamics.global_homeostatic_drive import (
    GlobalHomeostaticDrive,
)
from speace_core.cellular_brain.embodiment.embodied_action_audit_trail import (
    EmbodiedActionAuditTrail,
)
from speace_core.cellular_brain.embodiment.active_inference_embodied_loop import (
    ActiveInferenceEmbodiedLoop,
)


class _MockNeuron:
    __slots__ = ("cell_id", "activation", "energy", "threshold", "plasticity_rate", "decay")

    def __init__(self, cid):
        self.cell_id = cid
        self.activation = 0.0
        self.energy = 1.0
        self.threshold = 0.5
        self.plasticity_rate = 0.05
        self.decay = 0.01


class _MockSynapse:
    __slots__ = ("source", "target", "weight", "state", "decay")

    def __init__(self, s, t, w=0.5):
        self.source = s
        self.target = t
        self.weight = w
        self.state = "active"
        self.decay = 0.001


class _MockEnergyField:
    def __init__(self, mapping=None, mean=1.0):
        self._m = mapping or {}
        self._mean = mean

    def get_energy(self, nid):
        return self._m.get(nid, 1.0)

    def get_global_energy(self):
        return self._mean


class SubstrateStabilityGuardTests(unittest.TestCase):
    def test_hyper_synchrony_triggers_adjust(self):
        g = SubstrateStabilityGuard(kuramoto_window=5)
        # Feed a 0.95 kuramoto for 5+ ticks.
        for _ in range(7):
            class _S:
                kuramoto_order_parameter = 0.95
                branching_ratio = 1.0
                mean_energy_field = 0.5
                total_free_energy = 0.0
                fatigue_count = 0
                neuron_count = 0

                def to_dict(self):
                    return {
                        "kuramoto_order_parameter": 0.95,
                        "branching_ratio": 1.0,
                        "mean_energy_field": 0.5,
                        "total_free_energy": 0.0,
                        "fatigue_count": 0,
                    }

            r = g.evaluate(_S())
        self.assertEqual(r.verdict, GuardVerdict.ADJUST)
        self.assertIn("hyper-synchrony", r.reason)

    def test_emergency_on_activation_explosion(self):
        g = SubstrateStabilityGuard(activation_max=1.0)

        class _S:
            kuramoto_order_parameter = 0.5
            branching_ratio = 1.0
            mean_energy_field = 0.5
            total_free_energy = 0.0
            fatigue_count = 0
            neuron_count = 0

            def to_dict(self):
                return {
                    "kuramoto_order_parameter": 0.5,
                    "branching_ratio": 1.0,
                    "mean_energy_field": 0.5,
                    "total_free_energy": 0.0,
                    "fatigue_count": 0,
                }

        n = _MockNeuron("a")
        n.activation = 5.0
        r = g.evaluate(_S(), circuit_neurons=[n])
        self.assertEqual(r.verdict, GuardVerdict.EMERGENCY)
        self.assertIn("explosion", r.reason)


class EnergyDrivenPlasticityTests(unittest.TestCase):
    def test_modulation_lowers_ltp_for_fatigued_post(self):
        ef = _MockEnergyField({"post_a": 0.1, "post_b": 0.9})
        syn_a = _MockSynapse("pre", "post_a")
        syn_b = _MockSynapse("pre", "post_b")
        edp = EnergyDrivenPlasticity(fatigue_threshold=0.2)
        m = edp.compute_modulation_map([syn_a, syn_b], ef)
        self.assertLess(m[("pre", "post_a")].ltp_multiplier, m[("pre", "post_b")].ltp_multiplier)
        self.assertGreater(m[("pre", "post_a")].ltd_multiplier, m[("pre", "post_b")].ltd_multiplier)


class CriticalityFeedbackTests(unittest.TestCase):
    def test_subcritical_boosts_excitability(self):
        mon = CriticalityMonitor()
        # Build a fake avalanche pattern that gives a low branching ratio.
        mon._avalanches = [
            Avalanche(
                spikes=[Spike("a", 0.0), Spike("b", 0.1)]
            )
        ]
        ctrl = CriticalityFeedbackController()
        fb = ctrl.step(mon)
        self.assertGreater(fb.excitability_delta, 0.0)

    def test_identity_feedback_when_disabled(self):
        ctrl = CriticalityFeedbackController()
        fb = ctrl.step(None)
        self.assertEqual(fb.branching_ratio, 0.0)
        self.assertEqual(fb.plasticity_scale, 1.0)


class ActionBiasTests(unittest.TestCase):
    def test_survival_high_prefers_sleep(self):
        drive = GlobalHomeostaticDrive()
        drive.update_drive("survival", 1.0)
        drive.update_drive("exploration", 0.0)
        drive.update_drive("stability", 0.0)
        drive.update_drive("efficiency", 0.0)
        bias = ActionBias()
        decision = bias.select(
            ["explore", "request_sleep", "observe"],
            drive,
            base_scores={a: 0.0 for a in ["explore", "request_sleep", "observe"]},
        )
        self.assertEqual(decision.chosen, "request_sleep")

    def test_exploration_high_prefers_explore(self):
        drive = GlobalHomeostaticDrive()
        drive.update_drive("exploration", 1.0)
        drive.update_drive("survival", 0.0)
        drive.update_drive("stability", 0.0)
        drive.update_drive("efficiency", 0.0)
        bias = ActionBias()
        decision = bias.select(
            ["explore", "request_sleep", "consolidate"],
            drive,
            base_scores={a: 0.0 for a in ["explore", "request_sleep", "consolidate"]},
        )
        self.assertEqual(decision.chosen, "explore")


class InteroceptiveBusTests(unittest.TestCase):
    def test_low_energy_yields_high_salience(self):
        bus = InteroceptiveSignalBus()
        snap = bus.read(
            energy_field=_MockEnergyField({}, mean=1.0),
        )
        # All healthy when global mean is 1.0.
        self.assertEqual(snap.signals["energy_field"], 0.0)
        # But if we set the energy field to 0.01 (very low):
        snap2 = bus.read(
            energy_field=_MockEnergyField({}, mean=0.01),
        )
        self.assertGreater(snap2.signals["energy_field"], 0.5)

    def test_vector_dim_matches_channels(self):
        bus = InteroceptiveSignalBus()
        snap = bus.read()
        v = bus.vector(snap)
        self.assertEqual(len(v), len(bus.channels))


class EmbodiedAuditTrailTests(unittest.TestCase):
    def test_record_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "trail.jsonl")
            trail = EmbodiedActionAuditTrail(log_path=log_path, auto_flush=True)
            for i in range(5):
                trail.record(
                    tick=i,
                    pre_state={"cpu": 0.5, "mem": 0.3},
                    post_state={"cpu": 0.5 + 0.01 * i, "mem": 0.31 + 0.02 * i},
                    action="observe",
                    prediction={"cpu": 0.5, "mem": 0.3},
                    surprise=0.1,
                    belief_after={"stable": 0.6, "unstable": 0.4},
                )
            trail.close()
            s = trail.summary()
            self.assertEqual(s["count"], 5)
            self.assertIn("observe", s["action_counts"])
            self.assertGreater(s["mean_prediction_error"], 0.0)


class ActiveInferenceLoopTests(unittest.TestCase):
    def test_step_produces_proposal(self):
        ai = ActiveInferenceEngine()
        ai.register_state("stable", 0.5)
        ai.register_state("unstable", 0.5)
        ai.register_action("observe", {"stable": 0.7, "unstable": 0.3})
        ai.register_action("actuate", {"stable": 0.3, "unstable": 0.7})

        actuator_proposals = []

        class _Actuator:
            def propose_action(self, action_type, params):
                pid = f"prop_{len(actuator_proposals)}"
                actuator_proposals.append({"id": pid, "type": action_type, "params": params})
                self._proposals = {pid: {"status": "proposed"}}
                return pid

        actuator = _Actuator()
        trail = EmbodiedActionAuditTrail()
        loop = ActiveInferenceEmbodiedLoop(ai, actuator, trail)
        r = loop.step(
            pre_state={"cpu": 0.3},
            post_state={"cpu": 0.31},
            surprise=0.2,
        )
        self.assertIsNotNone(r.action)
        self.assertIsNotNone(r.proposal_id)
        self.assertEqual(len(actuator_proposals), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
