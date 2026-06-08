from speace_core.cellular_brain.cells.digital_microglia import DigitalMicroglia
from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse


def test_microglia_prune():
    mg = DigitalMicroglia(cell_id="m1", role="digital_microglia")
    syn = DigitalSynapse(cell_id="s1", role="digital_synapse", source="a", target="b", trust=0.05, use_count=2)
    pruned = mg.inspect([], [syn])
    assert syn.state == "pruned"
    assert "s1" in pruned


def test_microglia_quarantine():
    mg = DigitalMicroglia(cell_id="m1", role="digital_microglia")
    neuron = DigitalNeuron(cell_id="n1", role="digital_neuron")
    neuron.error_history = [-1.0] * 11
    mg.inspect([neuron], [])
    assert neuron.state == "quarantined"
