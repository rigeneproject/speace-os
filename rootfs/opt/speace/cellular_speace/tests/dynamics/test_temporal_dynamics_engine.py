import numpy as np
import pytest

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse
from speace_core.cellular_brain.dynamics.temporal_dynamics_engine import TemporalDynamicsEngine


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def make_neuron(nid: str, threshold: float = 0.5) -> DigitalNeuron:
    return DigitalNeuron(cell_id=nid, role="excitatory", threshold=threshold)


def make_synapse(src: str, tgt: str, weight: float = 0.5, decay: float = 0.001) -> DigitalSynapse:
    return DigitalSynapse(cell_id=f"{src}_{tgt}", role="synapse", source=src, target=tgt, weight=weight, decay=decay)


# --------------------------------------------------------------------------- #
# Basic construction and step
# --------------------------------------------------------------------------- #

def test_construction_empty():
    engine = TemporalDynamicsEngine(neurons=[], synapses=[])
    assert engine.t == 0.0
    assert engine.num_neurons == 0
    assert engine.num_synapses == 0


def test_construction_with_neurons_and_synapses():
    n1 = make_neuron("n1")
    n2 = make_neuron("n2")
    s1 = make_synapse("n1", "n2")
    engine = TemporalDynamicsEngine(neurons=[n1, n2], synapses=[s1])
    assert engine.num_neurons == 2
    assert engine.num_synapses == 1
    assert engine.get_neuron_state("n1") == 0.0
    assert engine.get_neuron_state("n2") == 0.0
    assert engine.get_synapse_weight("n1", "n2") == 0.5


def test_step_advances_time():
    n1 = make_neuron("n1")
    engine = TemporalDynamicsEngine(neurons=[n1], synapses=[])
    engine.step(dt=0.1)
    assert engine.t == pytest.approx(0.1)
    engine.step(dt=0.2)
    assert engine.t == pytest.approx(0.3)


def test_step_empty_engine():
    engine = TemporalDynamicsEngine(neurons=[], synapses=[])
    engine.step(dt=0.1)
    assert engine.t == 0.1


# --------------------------------------------------------------------------- #
# Leaky decay without input
# --------------------------------------------------------------------------- #

def test_leaky_decay():
    n1 = make_neuron("n1")
    engine = TemporalDynamicsEngine(neurons=[n1], synapses=[], tau=1.0)
    # Prime activation via stimulus then let it decay
    engine.inject_input("n1", 1.0)
    engine.step(dt=0.1)
    a_after_stimulus = engine.get_neuron_state("n1")
    assert a_after_stimulus > 0.0

    # Decay for several steps with no input
    for _ in range(10):
        engine.step(dt=0.1)
    a_after_decay = engine.get_neuron_state("n1")
    assert a_after_decay < a_after_stimulus
    assert a_after_decay < 0.05  # should be close to zero


# --------------------------------------------------------------------------- #
# Response to stimulus
# --------------------------------------------------------------------------- #

def test_stimulus_response():
    n1 = make_neuron("n1")
    engine = TemporalDynamicsEngine(neurons=[n1], synapses=[], tau=1.0)
    engine.inject_input("n1", 2.0)
    engine.step(dt=0.1)
    a = engine.get_neuron_state("n1")
    # Euler: a_new = 0 + (-0/1 + 2.0) * 0.1 = 0.2
    assert a == pytest.approx(0.2, abs=1e-9)


def test_stimulus_accumulation_before_step():
    n1 = make_neuron("n1")
    engine = TemporalDynamicsEngine(neurons=[n1], synapses=[], tau=1.0)
    engine.inject_input("n1", 1.0)
    engine.inject_input("n1", 1.0)
    engine.step(dt=0.1)
    a = engine.get_neuron_state("n1")
    # Total input = 2.0
    assert a == pytest.approx(0.2, abs=1e-9)


def test_stimulus_cleared_after_step():
    n1 = make_neuron("n1")
    engine = TemporalDynamicsEngine(neurons=[n1], synapses=[], tau=1.0)
    engine.inject_input("n1", 1.0)
    engine.step(dt=0.1)
    # second step with no new input
    engine.step(dt=0.1)
    a = engine.get_neuron_state("n1")
    # a after first step = 0.1, then decay: a_new = 0.1 + (-0.1/1)*0.1 = 0.09
    assert a == pytest.approx(0.09, abs=1e-9)


# --------------------------------------------------------------------------- #
# Synaptic plasticity evolution
# --------------------------------------------------------------------------- #

def test_synaptic_plasticity_potentiation():
    n1 = make_neuron("n1")
    n2 = make_neuron("n2")
    s1 = make_synapse("n1", "n2", weight=0.5, decay=0.0)
    engine = TemporalDynamicsEngine(
        neurons=[n1, n2],
        synapses=[s1],
        tau=1.0,
        tau_w=10.0,
        plasticity_rate=0.1,
    )
    # Drive both neurons so correlation is positive
    engine.inject_input("n1", 1.0)
    engine.inject_input("n2", 1.0)
    engine.step(dt=0.1)

    # correlation = a_pre * a_post ≈ 0.2 * 0.2 = 0.04 (after first step)
    # dw = (-0.5/10 + 0.1 * 0.04 - 0) * 0.1
    # dw = (-0.05 + 0.004) * 0.1 = -0.0046
    # weight should have decreased slightly because -w/tau_w dominates.
    # Let's run more steps to see the plasticity term win.
    for _ in range(50):
        engine.inject_input("n1", 1.0)
        engine.inject_input("n2", 1.0)
        engine.step(dt=0.1)

    w_final = engine.get_synapse_weight("n1", "n2")
    # With strong sustained correlation, weight should grow toward upper bound
    assert w_final > 0.5


def test_synaptic_plasticity_depression():
    n1 = make_neuron("n1")
    n2 = make_neuron("n2")
    s1 = make_synapse("n1", "n2", weight=0.5, decay=0.01)
    engine = TemporalDynamicsEngine(
        neurons=[n1, n2],
        synapses=[s1],
        tau=1.0,
        tau_w=10.0,
        plasticity_rate=0.05,
    )
    # No activation → correlation = 0 → weight decays
    for _ in range(20):
        engine.step(dt=0.1)
    w_final = engine.get_synapse_weight("n1", "n2")
    assert w_final < 0.5


# --------------------------------------------------------------------------- #
# Energy consumption during activation
# --------------------------------------------------------------------------- #

def test_energy_consumption_during_activation():
    n1 = make_neuron("n1")
    engine = TemporalDynamicsEngine(
        neurons=[n1],
        synapses=[],
        tau=1.0,
        tau_e=5.0,
        supply=0.0,
        consumption=0.5,
    )
    # Initial energy is 0.5
    e0 = engine.e[0]
    assert e0 == 0.5

    # Stimulate to raise activation
    engine.inject_input("n1", 2.0)
    engine.step(dt=0.1)
    a = engine.get_neuron_state("n1")
    e1 = engine.e[0]
    # de = (-0.5/5 + 0 - 0.5 * |a|) * 0.1
    assert e1 < e0


def test_energy_recovery_when_quiescent():
    n1 = make_neuron("n1")
    engine = TemporalDynamicsEngine(
        neurons=[n1],
        synapses=[],
        tau=1.0,
        tau_e=1.0,
        supply=0.2,
        consumption=0.5,
    )
    # Start from low energy
    engine.e[0] = 0.1
    for _ in range(10):
        engine.step(dt=0.1)
    e_final = engine.e[0]
    assert e_final > 0.1


# --------------------------------------------------------------------------- #
# Noise injection
# --------------------------------------------------------------------------- #

def test_noise_changes_trajectory():
    np.random.seed(42)
    n1 = make_neuron("n1")
    engine_noisy = TemporalDynamicsEngine(
        neurons=[n1],
        synapses=[],
        tau=1.0,
        noise_std=1.0,
    )
    engine_noisy.inject_input("n1", 1.0)
    engine_noisy.step(dt=0.1)
    a_noisy = engine_noisy.get_neuron_state("n1")

    np.random.seed(42)
    n1b = make_neuron("n1b")
    engine_clean = TemporalDynamicsEngine(
        neurons=[n1b],
        synapses=[],
        tau=1.0,
        noise_std=0.0,
    )
    engine_clean.inject_input("n1b", 1.0)
    engine_clean.step(dt=0.1)
    a_clean = engine_clean.get_neuron_state("n1b")

    # The noisy trajectory should differ from the clean one
    assert a_noisy != pytest.approx(a_clean, abs=1e-6)


def test_noise_std_zero_is_deterministic():
    n1 = make_neuron("n1")
    engine = TemporalDynamicsEngine(neurons=[n1], synapses=[], tau=1.0, noise_std=0.0)
    engine.inject_input("n1", 1.0)
    engine.step(dt=0.1)
    a1 = engine.get_neuron_state("n1")
    engine.inject_input("n1", 1.0)
    engine.step(dt=0.1)
    a2 = engine.get_neuron_state("n1")
    # Since noise is zero and Euler is deterministic, steps are reproducible
    engine2 = TemporalDynamicsEngine(neurons=[make_neuron("n1")], synapses=[], tau=1.0, noise_std=0.0)
    engine2.inject_input("n1", 1.0)
    engine2.step(dt=0.1)
    assert a1 == pytest.approx(engine2.get_neuron_state("n1"), abs=1e-9)


# --------------------------------------------------------------------------- #
# Integration with multiple neurons
# --------------------------------------------------------------------------- #

def test_multi_neuron_state_isolation():
    n1 = make_neuron("n1")
    n2 = make_neuron("n2")
    engine = TemporalDynamicsEngine(neurons=[n1, n2], synapses=[], tau=1.0)
    engine.inject_input("n1", 2.0)
    engine.step(dt=0.1)
    assert engine.get_neuron_state("n1") == pytest.approx(0.2, abs=1e-9)
    assert engine.get_neuron_state("n2") == pytest.approx(0.0, abs=1e-9)


def test_multi_neuron_synapse_correlation():
    n1 = make_neuron("n1")
    n2 = make_neuron("n2")
    n3 = make_neuron("n3")
    s12 = make_synapse("n1", "n2", weight=0.3)
    s23 = make_synapse("n2", "n3", weight=0.7)
    engine = TemporalDynamicsEngine(
        neurons=[n1, n2, n3],
        synapses=[s12, s23],
        tau=1.0,
        tau_w=10.0,
        plasticity_rate=0.1,
    )
    # Stimulate n1 and n3 but not n2
    engine.inject_input("n1", 1.0)
    engine.inject_input("n3", 1.0)
    for _ in range(20):
        engine.inject_input("n1", 1.0)
        engine.inject_input("n3", 1.0)
        engine.step(dt=0.1)

    # s12 sees n1 active, n2 inactive → low correlation → weight likely decays
    w12 = engine.get_synapse_weight("n1", "n2")
    # s23 sees n2 inactive, n3 active → low correlation → weight likely decays
    w23 = engine.get_synapse_weight("n2", "n3")
    assert w12 < 0.3
    assert w23 < 0.7


# --------------------------------------------------------------------------- #
# Oscillatory coupling
# --------------------------------------------------------------------------- #

def test_couple_oscillations_affects_dynamics():
    n1 = make_neuron("n1")
    engine = TemporalDynamicsEngine(neurons=[n1], synapses=[], tau=1.0, noise_std=0.0)
    engine.couple_oscillations({"n1": 0.5})
    engine.step(dt=0.1)
    a = engine.get_neuron_state("n1")
    # With oscillatory forcing of 0.5, activation should be 0.05
    assert a == pytest.approx(0.05, abs=1e-9)


def test_couple_oscillations_overwrite():
    n1 = make_neuron("n1")
    engine = TemporalDynamicsEngine(neurons=[n1], synapses=[], tau=1.0, noise_std=0.0)
    engine.couple_oscillations({"n1": 1.0})
    engine.step(dt=0.1)
    a1 = engine.get_neuron_state("n1")
    # overwrite with zero forcing
    engine.couple_oscillations({})
    engine.step(dt=0.1)
    a2 = engine.get_neuron_state("n1")
    # second step only decayed a1
    assert a2 < a1


# --------------------------------------------------------------------------- #
# Error handling
# --------------------------------------------------------------------------- #

def test_missing_neuron_raises():
    n1 = make_neuron("n1")
    engine = TemporalDynamicsEngine(neurons=[n1], synapses=[])
    # T156-fix: late-added neurons are now auto-registered with a=0,
    # not raised as KeyError. Verify the new contract: a previously
    # unseen neuron_id becomes queryable with activation 0.0.
    assert engine.get_neuron_state("missing") == 0.0
    assert "missing" in engine.neuron_id_to_idx


def test_missing_synapse_raises():
    n1 = make_neuron("n1")
    n2 = make_neuron("n2")
    engine = TemporalDynamicsEngine(neurons=[n1, n2], synapses=[])
    with pytest.raises(KeyError):
        engine.get_synapse_weight("n1", "n2")


def test_synapse_with_unknown_neuron_raises():
    n1 = make_neuron("n1")
    s_bad = make_synapse("n1", "n2")
    with pytest.raises(ValueError):
        TemporalDynamicsEngine(neurons=[n1], synapses=[s_bad])
