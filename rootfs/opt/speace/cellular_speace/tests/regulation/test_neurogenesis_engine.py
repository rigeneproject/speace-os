import pytest

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regulation.neurogenesis_engine import NeurogenesisEngine


@pytest.fixture
def engine():
    return NeurogenesisEngine(
        error_threshold=3,
        phi_threshold=0.55,
        min_energy=0.25,
        max_new_neurons_per_cycle=3,
    )


@pytest.fixture
def circuit():
    n1 = DigitalNeuron(cell_id="n1", role="digital_neuron")
    n2 = DigitalNeuron(cell_id="n2", role="digital_neuron")
    syn = DigitalSynapse(cell_id="s1", role="digital_synapse", source="n1", target="n2")
    return NeuralCircuit(
        circuit_id="test",
        input_neurons=[n1],
        output_neurons=[n2],
        synapses=[syn],
    )


def test_should_generate_false_low_error(engine):
    assert not engine.should_generate(error_count=1, phi=0.5, energy=0.5)


def test_should_generate_false_low_energy(engine):
    assert not engine.should_generate(error_count=5, phi=0.5, energy=0.1)


def test_should_generate_false_high_phi(engine):
    assert not engine.should_generate(error_count=5, phi=0.8, energy=0.5)


def test_should_generate_true(engine):
    assert engine.should_generate(error_count=3, phi=0.5, energy=0.5)


def test_generate_neuron_increases_count(engine, circuit):
    initial = len(circuit.input_neurons + circuit.hidden_neurons + circuit.output_neurons)
    result = engine.generate_neuron(circuit, phi_before=0.5, reason="test")
    assert result.created
    assert result.neuron_id is not None
    final = len(circuit.input_neurons + circuit.hidden_neurons + circuit.output_neurons)
    assert final == initial + 1


def test_generate_neuron_creates_synapses(engine, circuit):
    initial_syn = len(circuit.synapses)
    engine.generate_neuron(circuit, phi_before=0.5, reason="test")
    assert len(circuit.synapses) > initial_syn


def test_generate_neuron_records_event(engine, circuit):
    mem = MorphologicalMemory()
    circuit.memory = mem
    engine.generate_neuron(circuit, phi_before=0.5, reason="test")
    assert mem.count_events(MorphologyEventType.NEURON_CREATED) == 1
    assert mem.events[0].metadata["reason"] == "test"


def test_generate_neuron_respects_max_limit(engine, circuit):
    # artificially fill circuit to near limit
    for i in range(999):
        circuit.hidden_neurons.append(
            DigitalNeuron(cell_id=f"fill_{i}", role="digital_neuron")
        )
    result = engine.generate_neuron(circuit, phi_before=0.5, reason="test")
    assert not result.created
    assert result.reason == "max_neuron_limit_reached"
