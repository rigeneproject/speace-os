import pytest

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regulation.cell_differentiation_engine import (
    CellDifferentiationEngine,
    DifferentiationContext,
)
from speace_core.dna.models import SharedGenome
from speace_core.dna.parser import load_genome


@pytest.fixture
def genome():
    return load_genome("speace_core/dna/genome/default_genome.yaml")


@pytest.fixture
def engine(genome):
    return CellDifferentiationEngine(genome=genome)


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


def test_input_becomes_sensory_neuron(engine, circuit):
    n = DigitalNeuron(cell_id="in", role="digital_neuron")
    n.neuron_role = "input"
    circuit.input_neurons.append(n)
    context = engine.evaluate_cell_context(n, circuit)
    new_type = engine.select_cell_fate(context)
    assert new_type == "sensory_neuron"


def test_output_becomes_motor_neuron(engine, circuit):
    n = DigitalNeuron(cell_id="out", role="digital_neuron")
    n.neuron_role = "output"
    circuit.output_neurons.append(n)
    context = engine.evaluate_cell_context(n, circuit)
    new_type = engine.select_cell_fate(context)
    assert new_type == "motor_neuron"


def test_hippocampus_region_becomes_hippocampal_neuron(engine, circuit):
    n = DigitalNeuron(cell_id="hip", role="digital_neuron")
    n.region = "hippocampus"
    circuit.hidden_neurons.append(n)
    context = engine.evaluate_cell_context(n, circuit)
    new_type = engine.select_cell_fate(context)
    assert new_type == "hippocampal_neuron"


def test_prefrontal_region_becomes_prefrontal_neuron(engine, circuit):
    n = DigitalNeuron(cell_id="pfc", role="digital_neuron")
    n.region = "prefrontal"
    circuit.hidden_neurons.append(n)
    context = engine.evaluate_cell_context(n, circuit)
    new_type = engine.select_cell_fate(context)
    assert new_type == "prefrontal_neuron"


def test_hyperactive_becomes_inhibitory_neuron(engine, circuit):
    n = DigitalNeuron(cell_id="hyper", role="digital_neuron")
    n.consecutive_fires = 10
    circuit.hidden_neurons.append(n)
    context = engine.evaluate_cell_context(n, circuit)
    new_type = engine.select_cell_fate(context)
    assert new_type == "inhibitory_neuron"


def test_apply_differentiation_changes_phenotype(engine, circuit):
    n = DigitalNeuron(cell_id="n", role="digital_neuron")
    n.cell_type = "generic_neuron"
    n.threshold = 0.5
    n.plasticity_rate = 0.05
    circuit.hidden_neurons.append(n)
    context = engine.evaluate_cell_context(n, circuit)
    engine.apply_differentiation(n, "sensory_neuron", context)
    assert n.cell_type == "sensory_neuron"
    assert n.differentiation_state == "differentiated"
    assert n.differentiation_score > 0
    assert "gene_expression" in n.gene_expression or n.gene_expression


def test_differentiation_records_event(engine, circuit):
    n = DigitalNeuron(cell_id="n", role="digital_neuron")
    n.cell_type = "generic_neuron"
    circuit.hidden_neurons.append(n)
    mem = MorphologicalMemory()
    circuit.memory = mem
    engine.differentiate_cell(n, circuit)
    assert mem.count_events(MorphologyEventType.CELL_DIFFERENTIATED) == 1
    event = mem.events[0]
    assert event.target_id == "n"
    assert event.metadata["from_type"] == "generic_neuron"
    assert event.metadata["to_type"] is not None


def test_differentiate_circuit_skips_already_differentiated(engine, circuit):
    for n in circuit.input_neurons + circuit.output_neurons:
        n.differentiation_state = "differentiated"
    n1 = DigitalNeuron(cell_id="n1", role="digital_neuron")
    n1.differentiation_state = "differentiated"
    n1.cell_type = "generic_neuron"
    circuit.hidden_neurons.append(n1)
    results = engine.differentiate_circuit(circuit)
    assert len(results) == 0


def test_differentiate_circuit_differentiates_undifferentiated(engine, circuit):
    for n in circuit.input_neurons + circuit.output_neurons:
        n.differentiation_state = "differentiated"
    n1 = DigitalNeuron(cell_id="n1", role="digital_neuron")
    n1.differentiation_state = "undifferentiated"
    n1.region = "prefrontal"
    circuit.hidden_neurons.append(n1)
    results = engine.differentiate_circuit(circuit)
    assert len(results) == 1
    assert results[0] == "prefrontal_neuron"
    assert n1.cell_type == "prefrontal_neuron"


def test_inhibitory_neuron_phenotype(engine, circuit):
    n = DigitalNeuron(cell_id="inh", role="digital_neuron")
    n.cell_type = "generic_neuron"
    circuit.hidden_neurons.append(n)
    context = engine.evaluate_cell_context(n, circuit)
    engine.apply_differentiation(n, "inhibitory_neuron", context)
    assert n.cell_type == "inhibitory_neuron"
    assert n.inhibitory is True
    assert n.neuron_role == "inhibitory"
    assert n.inhibition_strength > 0
    assert n.refractory_period > 0


def test_genome_has_differentiation_rules(genome):
    assert "sensory_neuron" in genome.cell_differentiation_rules
    assert "motor_neuron" in genome.cell_differentiation_rules
    assert "hippocampal_neuron" in genome.cell_differentiation_rules
    assert "prefrontal_neuron" in genome.cell_differentiation_rules
    assert "inhibitory_neuron" in genome.cell_differentiation_rules
    assert "regulatory_neuron" in genome.cell_differentiation_rules
    assert "memory_neuron" in genome.cell_differentiation_rules
    assert "generic_neuron" in genome.cell_differentiation_rules
    # T132 — Linguistic cell types
    assert "auditory_neuron" in genome.cell_differentiation_rules
    assert "broca_neuron" in genome.cell_differentiation_rules
    assert "wernicke_neuron" in genome.cell_differentiation_rules
    assert "semantic_pointer_neuron" in genome.cell_differentiation_rules


def test_auditory_region_becomes_auditory_neuron(engine, circuit):
    n = DigitalNeuron(cell_id="aud", role="digital_neuron")
    n.region = "auditory"
    circuit.hidden_neurons.append(n)
    context = engine.evaluate_cell_context(n, circuit)
    new_type = engine.select_cell_fate(context)
    assert new_type == "auditory_neuron"


def test_wernicke_region_becomes_wernicke_neuron(engine, circuit):
    n = DigitalNeuron(cell_id="wer", role="digital_neuron")
    n.region = "wernicke"
    circuit.hidden_neurons.append(n)
    context = engine.evaluate_cell_context(n, circuit)
    new_type = engine.select_cell_fate(context)
    assert new_type == "wernicke_neuron"


def test_broca_region_becomes_broca_neuron(engine, circuit):
    n = DigitalNeuron(cell_id="bro", role="digital_neuron")
    n.region = "broca"
    circuit.hidden_neurons.append(n)
    context = engine.evaluate_cell_context(n, circuit)
    new_type = engine.select_cell_fate(context)
    assert new_type == "broca_neuron"


def test_semantic_region_becomes_semantic_pointer_neuron(engine, circuit):
    n = DigitalNeuron(cell_id="sem", role="digital_neuron")
    n.region = "semantic"
    circuit.hidden_neurons.append(n)
    context = engine.evaluate_cell_context(n, circuit)
    new_type = engine.select_cell_fate(context)
    assert new_type == "semantic_pointer_neuron"


def test_linguistic_phenotypes(engine, circuit):
    n = DigitalNeuron(cell_id="ling", role="digital_neuron")
    circuit.hidden_neurons.append(n)
    context = engine.evaluate_cell_context(n, circuit)

    engine.apply_differentiation(n, "auditory_neuron", context)
    assert n.cell_type == "auditory_neuron"
    assert n.neuron_role == "auditory"
    assert getattr(n, "phoneme_sensitivity", 0) > 0

    n2 = DigitalNeuron(cell_id="ling2", role="digital_neuron")
    circuit.hidden_neurons.append(n2)
    engine.apply_differentiation(n2, "wernicke_neuron", context)
    assert n2.cell_type == "wernicke_neuron"
    assert n2.neuron_role == "comprehension"
    assert getattr(n2, "comprehension_strength", 0) > 0

    n3 = DigitalNeuron(cell_id="ling3", role="digital_neuron")
    circuit.hidden_neurons.append(n3)
    engine.apply_differentiation(n3, "broca_neuron", context)
    assert n3.cell_type == "broca_neuron"
    assert n3.neuron_role == "production"
    assert isinstance(getattr(n3, "sequence_buffer", None), list)

    n4 = DigitalNeuron(cell_id="ling4", role="digital_neuron")
    circuit.hidden_neurons.append(n4)
    engine.apply_differentiation(n4, "semantic_pointer_neuron", context)
    assert n4.cell_type == "semantic_pointer_neuron"
    assert n4.neuron_role == "semantic_pointer"
    assert hasattr(n4, "symbol")
