import pytest

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron


@pytest.mark.asyncio
async def test_neuron_firing():
    n = DigitalNeuron(cell_id="n1", role="digital_neuron", threshold=0.5)
    n.activation = 1.0
    signals = await n.tick()
    assert len(signals) == 0  # no targets yet
    assert n.activation == 0.0
    assert n.energy < 1.0


@pytest.mark.asyncio
async def test_neuron_no_fire_below_threshold():
    n = DigitalNeuron(cell_id="n1", role="digital_neuron", threshold=0.5)
    n.activation = 0.1
    signals = await n.tick()
    assert len(signals) == 0
    assert n.activation == 0.05


def test_neuron_adapt_positive():
    n = DigitalNeuron(cell_id="n1", role="digital_neuron", threshold=0.5)
    n.adapt(1.0)
    assert n.threshold < 0.5


def test_neuron_adapt_negative():
    n = DigitalNeuron(cell_id="n1", role="digital_neuron", threshold=0.5)
    n.adapt(-1.0)
    assert n.threshold > 0.5
    assert len(n.error_history) > 0
