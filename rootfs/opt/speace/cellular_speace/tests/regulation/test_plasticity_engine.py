from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse
from speace_core.cellular_brain.regulation.plasticity_engine import PlasticityEngine


def test_plasticity_positive():
    engine = PlasticityEngine()
    syn = DigitalSynapse(cell_id="s1", role="digital_synapse", source="a", target="b", weight=0.5)
    neuron = DigitalNeuron(cell_id="n1", role="digital_neuron", threshold=0.5)
    engine.update([syn], [neuron], 1.0)
    assert syn.weight > 0.5
    assert neuron.threshold < 0.5


def test_plasticity_negative():
    engine = PlasticityEngine()
    syn = DigitalSynapse(cell_id="s1", role="digital_synapse", source="a", target="b", weight=0.5)
    neuron = DigitalNeuron(cell_id="n1", role="digital_neuron", threshold=0.5)
    engine.update([syn], [neuron], -1.0)
    assert syn.weight < 0.5
    assert neuron.threshold > 0.5
