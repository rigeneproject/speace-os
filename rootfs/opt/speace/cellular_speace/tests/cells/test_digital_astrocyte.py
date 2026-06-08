from speace_core.cellular_brain.cells.digital_astrocyte import DigitalAstrocyte
from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron


def test_astrocyte_regulate_overload():
    astro = DigitalAstrocyte(cell_id="a1", role="digital_astrocyte")
    neurons = [DigitalNeuron(cell_id=f"n{i}", role="digital_neuron", threshold=0.5, activation=0.9) for i in range(5)]
    astro.regulate(neurons)
    assert all(n.threshold > 0.5 for n in neurons)


def test_astrocyte_suppress_noise():
    astro = DigitalAstrocyte(cell_id="a1", role="digital_astrocyte", noise_level=0.7)
    neurons = [DigitalNeuron(cell_id=f"n{i}", role="digital_neuron", activation=1.0) for i in range(5)]
    astro.regulate(neurons)
    assert all(n.activation < 1.0 for n in neurons)
