import numpy as np
import pytest

from speace_core.cellular_brain.dynamics.energy_field_engine import EnergyFieldEngine


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_register_neuron():
    engine = EnergyFieldEngine()
    engine.register_neuron("n1", baseline_supply=0.2, consumption_rate=0.05, diffusion_rate=0.01)
    assert engine.neuron_count() == 1
    assert engine.get_energy("n1") == pytest.approx(1.0)


def test_register_neuron_with_initial_energy():
    engine = EnergyFieldEngine()
    engine.register_neuron("n1", initial_energy=0.5)
    assert engine.get_energy("n1") == pytest.approx(0.5)


def test_register_duplicate_updates_params():
    engine = EnergyFieldEngine()
    engine.register_neuron("n1", baseline_supply=0.1, consumption_rate=0.05, initial_energy=0.8)
    engine.register_neuron("n1", baseline_supply=0.3, consumption_rate=0.1, initial_energy=0.9)
    assert engine.get_energy("n1") == pytest.approx(0.9)
    assert engine.neuron_count() == 1


def test_register_synapse():
    engine = EnergyFieldEngine()
    engine.register_neuron("n1")
    engine.register_neuron("n2")
    engine.register_synapse("n1", "n2")
    assert engine.synapse_count() == 1


def test_register_synapse_missing_neuron():
    engine = EnergyFieldEngine()
    engine.register_neuron("n1")
    with pytest.raises(KeyError):
        engine.register_synapse("n1", "n2")


# ---------------------------------------------------------------------------
# Basic queries
# ---------------------------------------------------------------------------

def test_get_global_energy_empty():
    engine = EnergyFieldEngine()
    assert engine.get_global_energy() == 0.0


def test_get_global_energy_average():
    engine = EnergyFieldEngine()
    engine.register_neuron("n1", initial_energy=0.5)
    engine.register_neuron("n2", initial_energy=1.0)
    assert engine.get_global_energy() == pytest.approx(0.75)


def test_get_fatigued_neurons():
    engine = EnergyFieldEngine()
    engine.register_neuron("n1", initial_energy=0.25)
    engine.register_neuron("n2", initial_energy=0.15)
    engine.register_neuron("n3", initial_energy=0.50)
    fatigued = engine.get_fatigued_neurons(threshold=0.2)
    assert "n2" in fatigued
    assert "n1" not in fatigued
    assert "n3" not in fatigued


def test_get_all_energies():
    engine = EnergyFieldEngine()
    engine.register_neuron("n1", initial_energy=0.3)
    engine.register_neuron("n2", initial_energy=0.7)
    energies = engine.get_all_energies()
    assert energies == {"n1": pytest.approx(0.3), "n2": pytest.approx(0.7)}


# ---------------------------------------------------------------------------
# Step dynamics
# ---------------------------------------------------------------------------

def test_step_no_change_when_idle():
    engine = EnergyFieldEngine(global_supply_rate=0.0, recovery_boost=0.0)
    engine.register_neuron("n1", baseline_supply=0.1, consumption_rate=0.05, initial_energy=0.5)
    engine.step(dt=1.0, activations={})
    assert engine.get_energy("n1") == pytest.approx(0.5)


def test_step_consumption():
    engine = EnergyFieldEngine(global_supply_rate=0.0, recovery_boost=0.0)
    engine.register_neuron("n1", baseline_supply=0.1, consumption_rate=0.1, initial_energy=1.0)
    engine.step(dt=1.0, activations={"n1": 1.0})
    # de = -0.1 * 1^2 = -0.1
    assert engine.get_energy("n1") == pytest.approx(0.9)


def test_step_supply():
    engine = EnergyFieldEngine(global_supply_rate=0.1, recovery_boost=0.0)
    engine.register_neuron("n1", baseline_supply=0.5, consumption_rate=0.0, initial_energy=0.0)
    engine.step(dt=1.0, activations={})
    # de = 0.1 * 0.5 = 0.05
    assert engine.get_energy("n1") == pytest.approx(0.05)


def test_step_recovery_boost():
    engine = EnergyFieldEngine(global_supply_rate=0.0, recovery_boost=0.1)
    engine.register_neuron("n1", baseline_supply=0.1, consumption_rate=0.0, initial_energy=0.0)
    engine.step(dt=1.0, activations={"n1": 0.0})
    assert engine.get_energy("n1") == pytest.approx(0.1)


def test_step_no_recovery_when_active():
    engine = EnergyFieldEngine(global_supply_rate=0.0, recovery_boost=0.1)
    engine.register_neuron("n1", baseline_supply=0.1, consumption_rate=0.0, initial_energy=0.5)
    engine.step(dt=1.0, activations={"n1": 0.5})
    # resting is False, so no recovery boost
    assert engine.get_energy("n1") == pytest.approx(0.5)


def test_energy_clipped_to_max():
    engine = EnergyFieldEngine(global_supply_rate=1.0, recovery_boost=0.5)
    engine.register_neuron("n1", baseline_supply=1.0, consumption_rate=0.0, initial_energy=0.95)
    engine.step(dt=1.0, activations={})
    assert engine.get_energy("n1") == pytest.approx(1.0)


def test_energy_clipped_to_min():
    engine = EnergyFieldEngine(global_supply_rate=0.0, recovery_boost=0.0)
    engine.register_neuron("n1", baseline_supply=0.1, consumption_rate=1.0, initial_energy=0.05)
    engine.step(dt=1.0, activations={"n1": 1.0})
    assert engine.get_energy("n1") == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Diffusion
# ---------------------------------------------------------------------------

def test_diffusion_equalizes_energy():
    engine = EnergyFieldEngine(global_supply_rate=0.0, recovery_boost=0.0)
    engine.register_neuron("n1", baseline_supply=0.0, consumption_rate=0.0, diffusion_rate=0.5, initial_energy=1.0)
    engine.register_neuron("n2", baseline_supply=0.0, consumption_rate=0.0, diffusion_rate=0.5, initial_energy=0.0)
    engine.register_synapse("n1", "n2")
    engine.step(dt=0.1, activations={})
    # de1 = 0.5 * (0 - 1) * 0.1 = -0.05
    # de2 = 0.5 * (1 - 0) * 0.1 = +0.05
    assert engine.get_energy("n1") == pytest.approx(0.95)
    assert engine.get_energy("n2") == pytest.approx(0.05)


def test_diffusion_over_chain():
    engine = EnergyFieldEngine(global_supply_rate=0.0, recovery_boost=0.0)
    for i in range(3):
        engine.register_neuron(f"n{i}", baseline_supply=0.0, consumption_rate=0.0, diffusion_rate=1.0, initial_energy=0.0)
    engine._energy[0] = 1.0  # n0 high
    engine.register_synapse("n0", "n1")
    engine.register_synapse("n1", "n2")
    engine.step(dt=0.1, activations={})
    # n0 loses to n1 only: -1*(1-0)*0.1 = -0.1
    # n1 gains from n0 and loses to n2: +1*(1-0)*0.1 -1*(0-0)*0.1 = +0.1
    # n2 gains from n1: +1*(0-0)*0.1 = 0
    assert engine.get_energy("n0") == pytest.approx(0.9)
    assert engine.get_energy("n1") == pytest.approx(0.1)
    assert engine.get_energy("n2") == pytest.approx(0.0)


def test_diffusion_with_degree_greater_than_one():
    engine = EnergyFieldEngine(global_supply_rate=0.0, recovery_boost=0.0)
    engine.register_neuron("hub", baseline_supply=0.0, consumption_rate=0.0, diffusion_rate=0.2, initial_energy=1.0)
    for i in range(3):
        engine.register_neuron(f"leaf{i}", baseline_supply=0.0, consumption_rate=0.0, diffusion_rate=0.2, initial_energy=0.0)
        engine.register_synapse("hub", f"leaf{i}")
    engine.step(dt=1.0, activations={})
    # hub degree=3, leaves degree=1
    # de_hub = 0.2 * (0+0+0 - 3*1) = -0.6
    # de_leaf = 0.2 * (1 - 0) = +0.2 each
    assert engine.get_energy("hub") == pytest.approx(0.4)
    for i in range(3):
        assert engine.get_energy(f"leaf{i}") == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# Astrocyte-like supply
# ---------------------------------------------------------------------------

def test_add_supply():
    engine = EnergyFieldEngine()
    engine.register_neuron("n1", initial_energy=0.5)
    engine.add_supply("n1", 0.2)
    assert engine.get_energy("n1") == pytest.approx(0.7)


def test_add_supply_capped():
    engine = EnergyFieldEngine()
    engine.register_neuron("n1", initial_energy=0.95)
    engine.add_supply("n1", 0.1)
    assert engine.get_energy("n1") == pytest.approx(1.0)


def test_add_supply_unknown_neuron():
    engine = EnergyFieldEngine()
    with pytest.raises(KeyError):
        engine.add_supply("n1", 0.1)


# ---------------------------------------------------------------------------
# Combined dynamics
# ---------------------------------------------------------------------------

def test_combined_step():
    engine = EnergyFieldEngine(global_supply_rate=0.1, recovery_boost=0.05)
    engine.register_neuron("n1", baseline_supply=0.2, consumption_rate=0.1, diffusion_rate=0.1, initial_energy=0.5)
    engine.register_neuron("n2", baseline_supply=0.2, consumption_rate=0.1, diffusion_rate=0.1, initial_energy=0.5)
    engine.register_synapse("n1", "n2")
    engine.step(dt=1.0, activations={"n1": 1.0, "n2": 0.0})
    # n1: diffusion 0, consumption -0.1, supply 0.02, recovery 0 (active) => 0.42
    # n2: diffusion 0, consumption 0, supply 0.02, recovery 0.05 (resting) => 0.57
    assert engine.get_energy("n1") == pytest.approx(0.42)
    assert engine.get_energy("n2") == pytest.approx(0.57)


def test_multiple_steps_converge():
    engine = EnergyFieldEngine(global_supply_rate=0.0, recovery_boost=0.0)
    engine.register_neuron("n1", baseline_supply=0.0, consumption_rate=0.0, diffusion_rate=0.5, initial_energy=1.0)
    engine.register_neuron("n2", baseline_supply=0.0, consumption_rate=0.0, diffusion_rate=0.5, initial_energy=0.0)
    engine.register_synapse("n1", "n2")
    for _ in range(20):
        engine.step(dt=0.1, activations={})
    # diffusion should equalize toward 0.5 each
    assert engine.get_energy("n1") == pytest.approx(0.5, abs=1e-1)
    assert engine.get_energy("n2") == pytest.approx(0.5, abs=1e-1)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_step_with_empty_engine():
    engine = EnergyFieldEngine()
    engine.step(dt=1.0, activations={})
    assert engine.get_global_energy() == 0.0


def test_step_with_unknown_activation_keys():
    engine = EnergyFieldEngine(global_supply_rate=0.0, recovery_boost=0.0)
    engine.register_neuron("n1", baseline_supply=0.0, consumption_rate=0.0, initial_energy=0.5)
    engine.step(dt=1.0, activations={"ghost": 1.0})
    assert engine.get_energy("n1") == pytest.approx(0.5)


def test_get_energy_unknown_neuron():
    engine = EnergyFieldEngine()
    with pytest.raises(KeyError):
        engine.get_energy("n1")
