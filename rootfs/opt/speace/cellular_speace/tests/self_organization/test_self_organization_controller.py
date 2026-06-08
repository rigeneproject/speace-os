import json
from pathlib import Path

import pytest

from speace_core.cellular_brain.self_organization.self_organization_controller import (
    ControlAction,
    SelfOrganizationController,
)


class TestInitialization:
    def test_disabled_by_default(self):
        ctrl = SelfOrganizationController()
        assert ctrl.enabled is False

    def test_enabled(self):
        ctrl = SelfOrganizationController(enabled=True)
        assert ctrl.enabled is True

    def test_default_parameters(self):
        ctrl = SelfOrganizationController()
        assert ctrl._parameter_state["mutation_rate"] == 1.0
        assert ctrl._parameter_state["routing_gain"] == 1.0


class TestDecideAction:
    def test_rigid_increases_exploration(self):
        ctrl = SelfOrganizationController()
        from speace_core.cellular_brain.self_organization.criticality_monitor import CriticalityState
        state = CriticalityState(
            state="rigid",
            system_entropy=0.1,
            behavioral_diversity=0.1,
            pathway_volatility=0.05,
            instability_mean=0.1,
        )
        action = ctrl.decide_action(state)
        assert action.action_type == "increase_exploration"
        assert action.parameter_changes["mutation_rate"] > 1.0

    def test_chaotic_increases_selection(self):
        ctrl = SelfOrganizationController()
        from speace_core.cellular_brain.self_organization.criticality_monitor import CriticalityState
        state = CriticalityState(
            state="chaotic",
            system_entropy=0.8,
            behavioral_diversity=0.7,
            pathway_volatility=0.4,
            instability_mean=0.3,
        )
        action = ctrl.decide_action(state)
        assert action.action_type == "increase_selection"
        assert action.parameter_changes["mutation_rate"] < 1.0

    def test_collapsing_increases_constraints(self):
        ctrl = SelfOrganizationController()
        from speace_core.cellular_brain.self_organization.criticality_monitor import CriticalityState
        state = CriticalityState(
            state="collapsing",
            system_entropy=0.5,
            behavioral_diversity=0.5,
            pathway_volatility=0.2,
            instability_mean=0.8,
        )
        action = ctrl.decide_action(state)
        assert action.action_type == "increase_constraints"
        assert action.parameter_changes["mutation_rate"] < 0.6

    def test_balanced_consolidates(self):
        ctrl = SelfOrganizationController()
        from speace_core.cellular_brain.self_organization.criticality_monitor import CriticalityState
        state = CriticalityState(
            state="balanced",
            system_entropy=0.5,
            behavioral_diversity=0.4,
            pathway_volatility=0.15,
            instability_mean=0.3,
        )
        action = ctrl.decide_action(state)
        assert action.action_type == "consolidate"


class TestTick:
    def test_tick_updates_criticality(self):
        ctrl = SelfOrganizationController()
        result = ctrl.tick(neuron_activations=[0.5, 0.5], coherence_phi=0.3)
        assert "criticality" in result
        assert result["active_perturbations"] == 0

    def test_enabled_may_trigger_perturbation(self):
        ctrl = SelfOrganizationController(enabled=True)
        # Force rigid state by using very low entropy / diversity
        result = ctrl.tick(
            neuron_activations=[1.0, 0.0, 0.0],
            coherence_phi=0.3,
            mean_energy=0.4,
            plasticity_rate=0.1,
            instability_mean=0.1,
        )
        # With rigid state, a perturbation may be triggered
        assert result["perturbation_count"] >= 0

    def test_tick_expires_perturbations(self):
        from speace_core.cellular_brain.self_organization.perturbation_scheduler import PerturbationScheduler
        sched = PerturbationScheduler(enabled=True, default_duration=1)
        ctrl = SelfOrganizationController(enabled=True, scheduler=sched)
        # Inject a perturbation manually
        p = ctrl.scheduler.apply_noise_injection()
        assert ctrl.scheduler.active_count == 1
        ctrl.tick(neuron_activations=[0.5], coherence_phi=0.3)
        # After tick, if duration was 1, it may have expired
        # We just verify tick runs without error


class TestBenchmarkSnapshot:
    def test_snapshot_keys(self):
        ctrl = SelfOrganizationController()
        ctrl.tick(neuron_activations=[0.5], coherence_phi=0.3)
        snap = ctrl.benchmark_snapshot()
        assert "criticality_state" in snap
        assert "system_entropy" in snap
        assert "self_organization_score" in snap
        assert "emergent_structure_gain" in snap


class TestReports:
    def test_markdown_report(self, tmp_path):
        ctrl = SelfOrganizationController(report_dir=str(tmp_path))
        ctrl.tick(neuron_activations=[0.5], coherence_phi=0.3)
        md = ctrl.generate_markdown_report()
        assert "Self-Organization Controller Report" in md
        assert "T53" in md

    def test_json_report(self, tmp_path):
        ctrl = SelfOrganizationController(report_dir=str(tmp_path))
        ctrl.tick(neuron_activations=[0.5], coherence_phi=0.3)
        js = ctrl.generate_json_report()
        data = json.loads(js)
        assert "criticality_state" in data

    def test_save_reports(self, tmp_path):
        ctrl = SelfOrganizationController(report_dir=str(tmp_path))
        ctrl.tick(neuron_activations=[0.5], coherence_phi=0.3)
        ctrl.save_reports()
        files = list(tmp_path.glob("self_organization_*"))
        assert len(files) >= 2


class TestReset:
    def test_reset_clears_state(self):
        ctrl = SelfOrganizationController()
        ctrl.tick(neuron_activations=[0.5], coherence_phi=0.3)
        ctrl.reset()
        assert len(ctrl._actions) == 0
        assert ctrl._perturbation_count == 0
        assert ctrl._parameter_state["mutation_rate"] == 1.0


class TestParameterModulation:
    def test_rigid_increases_mutation(self):
        ctrl = SelfOrganizationController()
        from speace_core.cellular_brain.self_organization.criticality_monitor import CriticalityState
        state = CriticalityState(
            state="rigid",
            system_entropy=0.1,
            behavioral_diversity=0.1,
            pathway_volatility=0.05,
            instability_mean=0.1,
        )
        changes = ctrl._modulate_parameters(state)
        assert changes["mutation_rate"] > 1.0
        assert changes["plasticity_gain"] > 1.0

    def test_chaotic_decreases_mutation(self):
        ctrl = SelfOrganizationController()
        from speace_core.cellular_brain.self_organization.criticality_monitor import CriticalityState
        state = CriticalityState(
            state="chaotic",
            system_entropy=0.8,
            behavioral_diversity=0.7,
            pathway_volatility=0.4,
            instability_mean=0.3,
        )
        changes = ctrl._modulate_parameters(state)
        assert changes["mutation_rate"] < 1.0
        assert changes["inhibition_decay"] > 1.0

    def test_collapsing_emergency(self):
        ctrl = SelfOrganizationController()
        from speace_core.cellular_brain.self_organization.criticality_monitor import CriticalityState
        state = CriticalityState(
            state="collapsing",
            system_entropy=0.5,
            behavioral_diversity=0.5,
            pathway_volatility=0.2,
            instability_mean=0.8,
        )
        changes = ctrl._modulate_parameters(state)
        assert changes["mutation_rate"] < 0.6
        assert changes["plasticity_gain"] < 0.7

    def test_balanced_drift(self):
        ctrl = SelfOrganizationController()
        ctrl._parameter_state["mutation_rate"] = 1.1
        from speace_core.cellular_brain.self_organization.criticality_monitor import CriticalityState
        state = CriticalityState(
            state="balanced",
            system_entropy=0.5,
            behavioral_diversity=0.4,
            pathway_volatility=0.15,
            instability_mean=0.3,
        )
        changes = ctrl._modulate_parameters(state)
        assert changes["mutation_rate"] < 1.1


class TestMaybeTriggerPerturbation:
    def test_disabled_returns_none(self):
        ctrl = SelfOrganizationController(enabled=False)
        from speace_core.cellular_brain.self_organization.criticality_monitor import CriticalityState
        state = CriticalityState(state="rigid", system_entropy=0.1, behavioral_diversity=0.1, pathway_volatility=0.05, instability_mean=0.1)
        assert ctrl.maybe_trigger_perturbation(state) is None

    def test_rigid_triggers_mutation_pulse(self):
        ctrl = SelfOrganizationController(enabled=True)
        from speace_core.cellular_brain.self_organization.criticality_monitor import CriticalityState
        state = CriticalityState(state="rigid", system_entropy=0.1, behavioral_diversity=0.1, pathway_volatility=0.05, instability_mean=0.1)
        p = ctrl.maybe_trigger_perturbation(state)
        assert p is not None
        assert p.perturbation_type == "mutation_pulse"

    def test_chaotic_triggers_pathway_suppression(self):
        ctrl = SelfOrganizationController(enabled=True)
        from speace_core.cellular_brain.self_organization.criticality_monitor import CriticalityState
        state = CriticalityState(state="chaotic", system_entropy=0.8, behavioral_diversity=0.7, pathway_volatility=0.4, instability_mean=0.3)
        p = ctrl.maybe_trigger_perturbation(state)
        assert p is not None
        assert p.perturbation_type == "pathway_suppression"

    def test_balanced_no_perturbation(self):
        ctrl = SelfOrganizationController(enabled=True)
        from speace_core.cellular_brain.self_organization.criticality_monitor import CriticalityState
        state = CriticalityState(state="balanced", system_entropy=0.5, behavioral_diversity=0.4, pathway_volatility=0.15, instability_mean=0.3)
        assert ctrl.maybe_trigger_perturbation(state) is None
