import math

import pytest

from speace_core.cellular_brain.dynamics.neural_oscillator_bank import NeuralOscillatorBank


@pytest.fixture
def bank():
    return NeuralOscillatorBank()


def test_default_bands_present(bank):
    assert set(bank.bands.keys()) == {"theta", "alpha", "beta", "gamma"}
    assert bank.bands["theta"]["freq"] == 5.0
    assert bank.bands["alpha"]["freq"] == 10.0
    assert bank.bands["beta"]["freq"] == 20.0
    assert bank.bands["gamma"]["freq"] == 40.0


def test_initial_phases_are_zero(bank):
    for band in bank.bands:
        assert bank.get_phase(band) == pytest.approx(0.0)


def test_step_advances_phase(bank):
    dt = 0.1
    bank.step(dt)
    expected_theta = (2.0 * math.pi * 5.0) * dt
    assert bank.get_phase("theta") == pytest.approx(expected_theta % (2.0 * math.pi))


def test_step_wraps_phase(bank):
    # After 1/5 seconds, theta should complete exactly 1 cycle
    bank.step(1.0 / 5.0)
    assert bank.get_phase("theta") == pytest.approx(0.0, abs=1e-12)


def test_step_with_coupling_input(bank):
    bank.set_coupling_input("theta", math.pi)
    dt = 0.1
    bank.step(dt)
    expected = (2.0 * math.pi * 5.0 + math.pi) * dt
    assert bank.get_phase("theta") == pytest.approx(expected % (2.0 * math.pi))


def test_get_envelope_returns_amplitude(bank):
    for band in bank.bands:
        assert bank.get_envelope(band) == 1.0


def test_register_and_modulate_neuron(bank):
    bank.register_neuron("n1", "theta", coupling_strength=0.5)
    assert bank.get_band_for_neuron("n1") == "theta"

    # phase is 0, sin(0)=0, so modulation = 1.0
    modulation = bank.get_neural_modulation("n1")
    assert modulation == pytest.approx(1.0)

    # advance phase to pi/2, sin(pi/2)=1, modulation = 1 + 0.5
    bank.phases["theta"] = math.pi / 2.0
    modulation = bank.get_neural_modulation("n1")
    assert modulation == pytest.approx(1.5)


def test_modulation_with_negative_coupling(bank):
    bank.register_neuron("n2", "alpha", coupling_strength=-0.3)
    bank.phases["alpha"] = math.pi / 2.0
    modulation = bank.get_neural_modulation("n2")
    assert modulation == pytest.approx(1.0 - 0.3)


def test_multiple_steps_monotonic_phase(bank):
    # For alpha (10Hz), phase should increase each step until wrap
    dt = 0.01
    prev = bank.get_phase("alpha")
    for _ in range(10):
        bank.step(dt)
        curr = bank.get_phase("alpha")
        # modulo wrap can make curr < prev, but not inside 10 small steps
        assert curr >= prev or abs(curr - prev) > math.pi  # wrap case
        prev = curr


def test_unregister_neuron(bank):
    bank.register_neuron("n3", "gamma", 0.2)
    bank.unregister_neuron("n3")
    assert "n3" not in bank.list_registered_neurons()


def test_unknown_band_raises(bank):
    with pytest.raises(KeyError):
        bank.get_phase("delta")
    with pytest.raises(KeyError):
        bank.get_envelope("delta")
    with pytest.raises(KeyError):
        bank.register_neuron("n", "delta", 0.1)
    with pytest.raises(KeyError):
        bank.set_coupling_input("delta", 0.1)


def test_unregistered_neuron_raises(bank):
    with pytest.raises(KeyError):
        bank.get_neural_modulation("unknown")


def test_custom_bands():
    custom = {
        "slow": {"freq": 1.0, "amplitude": 2.0},
        "fast": {"freq": 100.0, "amplitude": 0.5},
    }
    b = NeuralOscillatorBank(bands=custom)
    assert b.get_envelope("slow") == 2.0
    assert b.get_envelope("fast") == 0.5
    b.step(0.01)
    assert b.get_phase("slow") == pytest.approx(2.0 * math.pi * 1.0 * 0.01)
    # fast band completes exactly one cycle in 0.01s, so wraps to 0
    expected_fast = (2.0 * math.pi * 100.0 * 0.01) % (2.0 * math.pi)
    assert b.get_phase("fast") == pytest.approx(expected_fast, abs=1e-12)
