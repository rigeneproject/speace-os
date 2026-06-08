from speace_core.cellular_brain.immune.digital_immune_controller import DigitalImmuneController
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory


class FakeOrchestrator:
    def __init__(self):
        self.current_tick = 0
        n1 = DigitalNeuron(cell_id="n1", role="input", activation=5.0)
        n2 = DigitalNeuron(cell_id="n2", role="output")
        syn = DigitalSynapse(cell_id="s1", role="synapse", source="n1", target="n2", weight=3.0)
        self.circuit = NeuralCircuit(circuit_id="c1", input_neurons=[n1], output_neurons=[n2], synapses=[syn])
        self._memory = MorphologicalMemory()
        self._memory.load()


def test_controller_detects_anomalies():
    orch = FakeOrchestrator()
    ctrl = DigitalImmuneController()
    ctrl.tick(orch)
    assert ctrl.immune_state["active_alerts"] > 0
    assert ctrl.immune_state["last_action_count"] > 0
