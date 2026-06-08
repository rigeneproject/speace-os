from speace_core.cellular_brain.sleep.memory_consolidation_engine import (
    MemoryConsolidationEngine,
)
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse


def _make_circuit():
    n1 = DigitalNeuron(cell_id="n1", role="input")
    n2 = DigitalNeuron(cell_id="n2", role="output")
    syn = DigitalSynapse(cell_id="s1", role="synapse", source="n1", target="n2", weight=0.02)
    syn2 = DigitalSynapse(cell_id="s2", role="synapse", source="n2", target="n1", weight=0.50, consolidated=True)
    circuit = NeuralCircuit(circuit_id="c1", input_neurons=[n1], output_neurons=[n2], synapses=[syn, syn2])
    return circuit


def test_prune_transient_synapses():
    engine = MemoryConsolidationEngine()
    circuit = _make_circuit()
    pruned = engine.prune_transient_synapses(circuit)
    assert pruned == 1
    assert len(circuit.synapses) == 1
    assert circuit.synapses[0].source == "n2"


def test_reinforce_stable_pathways():
    engine = MemoryConsolidationEngine(reinforcement_boost=0.05)
    circuit = _make_circuit()
    reinforced = engine.reinforce_stable_pathways(circuit)
    assert reinforced == 1
    assert circuit.synapses[1].weight == 0.55


def test_run_full_cycle():
    engine = MemoryConsolidationEngine()
    circuit = _make_circuit()
    result = engine.run_full_cycle(circuit)
    assert result.pruned_synapses == 1
    assert result.reinforced_synapses == 1
    assert result.consolidated_assemblies == 0


def test_consolidate_semantic_assemblies():
    engine = MemoryConsolidationEngine()

    class FakeAssembly:
        def __init__(self, stability, recurrence, consolidated=False):
            self.stability = stability
            self.recurrence_count = recurrence
            self.consolidated = consolidated

    assemblies = [
        FakeAssembly(0.5, 5, False),
        FakeAssembly(0.1, 1, False),
        FakeAssembly(0.4, 3, True),
    ]
    consolidated = engine.consolidate_semantic(assemblies)
    assert consolidated == 1
    assert assemblies[0].consolidated is True
