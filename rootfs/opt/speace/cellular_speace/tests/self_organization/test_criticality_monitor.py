import math

import pytest

from speace_core.cellular_brain.self_organization.criticality_monitor import (
    CriticalityMonitor,
    CriticalityState,
)


class TestComputeSystemEntropy:
    def test_uniform_activations_high_entropy(self):
        monitor = CriticalityMonitor()
        entropy = monitor.compute_system_entropy([1.0, 1.0, 1.0, 1.0])
        assert pytest.approx(entropy, 0.001) == 1.0

    def test_single_activation_zero_entropy(self):
        monitor = CriticalityMonitor()
        entropy = monitor.compute_system_entropy([1.0, 0.0, 0.0])
        assert pytest.approx(entropy, 0.001) == 0.0

    def test_empty_returns_zero(self):
        monitor = CriticalityMonitor()
        assert monitor.compute_system_entropy([]) == 0.0

    def test_all_zeros_returns_one(self):
        monitor = CriticalityMonitor()
        assert monitor.compute_system_entropy([0.0, 0.0]) == 1.0


class TestComputeBehavioralDiversity:
    def test_identical_activations_zero_diversity(self):
        monitor = CriticalityMonitor()
        assert monitor.compute_behavioral_diversity([0.5, 0.5, 0.5]) == 0.0

    def test_high_diversity(self):
        monitor = CriticalityMonitor()
        div = monitor.compute_behavioral_diversity([0.0, 1.0, 0.0, 1.0])
        assert div > 0.4

    def test_empty_returns_zero(self):
        monitor = CriticalityMonitor()
        assert monitor.compute_behavioral_diversity([]) == 0.0


class TestComputeModularityScore:
    def test_no_regions_zero(self):
        monitor = CriticalityMonitor()
        assert monitor.compute_modularity_score({}, {}) == 0.0

    def test_high_intra_low_inter(self):
        monitor = CriticalityMonitor()
        score = monitor.compute_modularity_score({"a": 1.0, "b": 1.0}, {"a-b": 0.1})
        assert score > 0.9

    def test_equal_intra_inter(self):
        monitor = CriticalityMonitor()
        score = monitor.compute_modularity_score({"a": 1.0}, {"a-b": 1.0})
        assert score == 0.5


class TestComputePathwayVolatility:
    def test_no_previous_zero(self):
        monitor = CriticalityMonitor()
        assert monitor.compute_pathway_volatility([0.5, 0.6], None) == 0.0

    def test_same_strengths_zero(self):
        monitor = CriticalityMonitor()
        assert monitor.compute_pathway_volatility([0.5, 0.6], [0.5, 0.6]) == 0.0

    def test_volatile_pathways(self):
        monitor = CriticalityMonitor()
        vol = monitor.compute_pathway_volatility([0.5, 0.6], [0.1, 0.9])
        assert vol > 0.2


class TestClassifyState:
    def test_rigid_state(self):
        monitor = CriticalityMonitor()
        state = CriticalityState(
            system_entropy=0.1, behavioral_diversity=0.1, pathway_volatility=0.05, instability_mean=0.1
        )
        assert monitor.classify_state(state) == "rigid"

    def test_chaotic_state(self):
        monitor = CriticalityMonitor()
        state = CriticalityState(
            system_entropy=0.8, behavioral_diversity=0.7, pathway_volatility=0.4, instability_mean=0.3
        )
        assert monitor.classify_state(state) == "chaotic"

    def test_collapsing_state(self):
        monitor = CriticalityMonitor()
        state = CriticalityState(
            system_entropy=0.5, behavioral_diversity=0.5, pathway_volatility=0.2, instability_mean=0.8
        )
        assert monitor.classify_state(state) == "collapsing"

    def test_balanced_state(self):
        monitor = CriticalityMonitor()
        state = CriticalityState(
            system_entropy=0.5, behavioral_diversity=0.4, pathway_volatility=0.15, instability_mean=0.3
        )
        assert monitor.classify_state(state) == "balanced"

    def test_collapsing_by_phi_energy(self):
        monitor = CriticalityMonitor()
        state = CriticalityState(
            system_entropy=0.5,
            behavioral_diversity=0.4,
            pathway_volatility=0.15,
            instability_mean=0.3,
            coherence_phi=0.05,
            mean_energy=0.95,
        )
        assert monitor.classify_state(state) == "collapsing"


class TestUpdate:
    def test_updates_history(self):
        monitor = CriticalityMonitor()
        result = monitor.update(neuron_activations=[0.5, 0.5], coherence_phi=0.3)
        assert result is not None
        assert len(monitor._history) == 1

    def test_latest_state(self):
        monitor = CriticalityMonitor()
        monitor.update(neuron_activations=[0.5, 0.5], coherence_phi=0.3)
        latest = monitor.latest_state()
        assert latest is not None
        assert latest.coherence_phi == 0.3

    def test_phi_trend(self):
        monitor = CriticalityMonitor()
        monitor.update(neuron_activations=[0.5], coherence_phi=0.2)
        monitor.update(neuron_activations=[0.5], coherence_phi=0.4)
        assert monitor.phi_trend() == 0.2

    def test_energy_trend(self):
        monitor = CriticalityMonitor()
        monitor.update(neuron_activations=[0.5], mean_energy=0.3)
        monitor.update(neuron_activations=[0.5], mean_energy=0.5)
        assert monitor.energy_trend() == 0.2

    def test_summary(self):
        monitor = CriticalityMonitor()
        monitor.update(neuron_activations=[0.5], coherence_phi=0.3)
        summary = monitor.summary()
        assert summary["history_length"] == 1


class TestOrderChaosBalance:
    def test_perfect_balance(self):
        monitor = CriticalityMonitor()
        state = CriticalityState(system_entropy=0.5, behavioral_diversity=0.5, pathway_volatility=0.15)
        bal = monitor.compute_order_chaos_balance(state)
        assert 0.0 <= bal <= 1.0

    def test_extreme_order(self):
        monitor = CriticalityMonitor()
        state = CriticalityState(system_entropy=0.0, behavioral_diversity=0.0, pathway_volatility=0.0)
        bal = monitor.compute_order_chaos_balance(state)
        assert bal == 0.0
