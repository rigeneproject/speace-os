import pytest

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regulation.stdp_plasticity_engine import (
    STDPPlasticityEngine,
)


@pytest.fixture
def engine():
    return STDPPlasticityEngine(
        ltp_rate=0.05,
        ltd_rate=0.03,
        stdp_window=1,
        min_weight=0.0,
        max_weight=1.0,
    )


@pytest.fixture
def circuit():
    pre = DigitalNeuron(cell_id="pre", role="digital_neuron", threshold=0.5)
    post = DigitalNeuron(cell_id="post", role="digital_neuron", threshold=0.5)
    syn = DigitalSynapse(
        cell_id="s1", role="digital_synapse", source="pre", target="post", weight=0.5
    )
    return NeuralCircuit(
        circuit_id="stdp_test",
        input_neurons=[pre],
        output_neurons=[post],
        synapses=[syn],
    )


def test_ltp_pre_before_post(engine, circuit):
    pre = circuit.input_neurons[0]
    post = circuit.output_neurons[0]
    syn = circuit.synapses[0]

    pre.last_fired_burst = 3
    post.last_fired_burst = 4

    delta = engine.apply_stdp_to_synapse(syn, pre, post)
    assert delta == pytest.approx(0.05)
    assert syn.weight == pytest.approx(0.55)


def test_ltd_post_before_pre(engine, circuit):
    pre = circuit.input_neurons[0]
    post = circuit.output_neurons[0]
    syn = circuit.synapses[0]

    pre.last_fired_burst = 4
    post.last_fired_burst = 3

    delta = engine.apply_stdp_to_synapse(syn, pre, post)
    assert delta == pytest.approx(-0.03)
    assert syn.weight == pytest.approx(0.47)


def test_no_change_same_burst(engine, circuit):
    pre = circuit.input_neurons[0]
    post = circuit.output_neurons[0]
    syn = circuit.synapses[0]

    pre.last_fired_burst = 5
    post.last_fired_burst = 5

    delta = engine.apply_stdp_to_synapse(syn, pre, post)
    assert delta is None
    assert syn.weight == pytest.approx(0.5)


def test_no_change_outside_window(engine, circuit):
    pre = circuit.input_neurons[0]
    post = circuit.output_neurons[0]
    syn = circuit.synapses[0]

    pre.last_fired_burst = 1
    post.last_fired_burst = 5

    delta = engine.apply_stdp_to_synapse(syn, pre, post)
    assert delta is None
    assert syn.weight == pytest.approx(0.5)


def test_never_fired_no_change(engine, circuit):
    pre = circuit.input_neurons[0]
    post = circuit.output_neurons[0]
    syn = circuit.synapses[0]

    pre.last_fired_burst = 0
    post.last_fired_burst = 1

    delta = engine.apply_stdp_to_synapse(syn, pre, post)
    assert delta is None
    assert syn.weight == pytest.approx(0.5)


def test_weight_clamped_at_max(engine, circuit):
    pre = circuit.input_neurons[0]
    post = circuit.output_neurons[0]
    syn = circuit.synapses[0]
    syn.weight = 0.98

    pre.last_fired_burst = 2
    post.last_fired_burst = 3

    delta = engine.apply_stdp_to_synapse(syn, pre, post)
    assert delta == pytest.approx(0.05)
    assert syn.weight == pytest.approx(1.0)


def test_weight_clamped_at_min(engine, circuit):
    pre = circuit.input_neurons[0]
    post = circuit.output_neurons[0]
    syn = circuit.synapses[0]
    syn.weight = 0.02

    pre.last_fired_burst = 3
    post.last_fired_burst = 2

    delta = engine.apply_stdp_to_synapse(syn, pre, post)
    assert delta == pytest.approx(-0.03)
    assert syn.weight == pytest.approx(0.0)


def test_pruned_synapse_unchanged(engine, circuit):
    pre = circuit.input_neurons[0]
    post = circuit.output_neurons[0]
    syn = circuit.synapses[0]
    syn.state = "pruned"

    pre.last_fired_burst = 2
    post.last_fired_burst = 3

    results = engine.apply_stdp(circuit)
    assert results["unchanged"] == 0  # pruned synapses are skipped entirely
    assert results["reinforced"] == 0
    assert results["weakened"] == 0


def test_missing_target_neuron_unchanged(engine):
    pre = DigitalNeuron(cell_id="pre", role="digital_neuron")
    syn = DigitalSynapse(
        cell_id="s1", role="digital_synapse", source="pre", target="ghost", weight=0.5
    )
    circ = NeuralCircuit(
        circuit_id="stdp_test", input_neurons=[pre], synapses=[syn]
    )
    pre.last_fired_burst = 2

    results = engine.apply_stdp(circ)
    assert results["unchanged"] == 0


def test_memory_records_reinforced_event(engine, circuit):
    pre = circuit.input_neurons[0]
    post = circuit.output_neurons[0]
    syn = circuit.synapses[0]
    mem = MorphologicalMemory()
    circuit.memory = mem

    pre.last_fired_burst = 2
    post.last_fired_burst = 3

    engine.apply_stdp_to_synapse(syn, pre, post, memory=mem)

    assert len(mem.events) == 1
    event = mem.events[0]
    assert event.event_type == MorphologyEventType.SYNAPSE_REINFORCED
    assert event.metadata["mechanism"] == "stdp"
    assert event.metadata["delta_burst"] == 1
    assert event.metadata["old_weight"] == 0.5
    assert event.metadata["new_weight"] == pytest.approx(0.55)


def test_memory_records_weakened_event(engine, circuit):
    pre = circuit.input_neurons[0]
    post = circuit.output_neurons[0]
    syn = circuit.synapses[0]
    mem = MorphologicalMemory()
    circuit.memory = mem

    pre.last_fired_burst = 3
    post.last_fired_burst = 2

    engine.apply_stdp_to_synapse(syn, pre, post, memory=mem)

    assert len(mem.events) == 1
    event = mem.events[0]
    assert event.event_type == MorphologyEventType.SYNAPSE_WEAKENED
    assert event.metadata["mechanism"] == "stdp"
    assert event.metadata["delta_burst"] == -1
    assert event.metadata["old_weight"] == 0.5
    assert event.metadata["new_weight"] == pytest.approx(0.47)


def test_apply_stdp_counts_correctly(engine, circuit):
    # Add a second synapse that will also trigger LTP
    pre = circuit.input_neurons[0]
    post = circuit.output_neurons[0]
    pre.last_fired_burst = 1
    post.last_fired_burst = 2

    syn2 = DigitalSynapse(
        cell_id="s2", role="digital_synapse", source="pre", target="post", weight=0.4
    )
    circuit.synapses.append(syn2)

    results = engine.apply_stdp(circuit)
    assert results["reinforced"] == 2
    assert results["weakened"] == 0
    assert results["unchanged"] == 0
    assert syn2.weight == pytest.approx(0.45)
