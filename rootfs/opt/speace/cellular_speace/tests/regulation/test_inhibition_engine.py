import pytest

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.execution.burst_engine import EventDrivenBurstEngine
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regulation.inhibition_engine import InhibitionEngine


@pytest.fixture
def engine():
    return InhibitionEngine(
        max_consecutive_fires=3,
        default_snooze_duration=2,
        activation_decay=0.10,
        runaway_activation_threshold=1.5,
    )


@pytest.fixture
def circuit():
    n1 = DigitalNeuron(cell_id="n1", role="digital_neuron", threshold=0.5)
    n2 = DigitalNeuron(cell_id="n2", role="digital_neuron", threshold=0.5)
    n3 = DigitalNeuron(cell_id="n3", role="digital_neuron", threshold=0.5)
    s12 = DigitalSynapse(
        cell_id="s12", role="digital_synapse", source="n1", target="n2", weight=0.8
    )
    s23 = DigitalSynapse(
        cell_id="s23", role="digital_synapse", source="n2", target="n3", weight=0.8
    )
    return NeuralCircuit(
        circuit_id="test",
        input_neurons=[n1],
        output_neurons=[n3],
        hidden_neurons=[n2],
        synapses=[s12, s23],
    )


def test_inhibitory_neuron_decreases_target_activation(engine, circuit):
    n1 = circuit.input_neurons[0]
    n2 = circuit.hidden_neurons[0]
    n1.inhibitory = True
    n1.inhibition_strength = 1.0
    n1.activation = 1.0
    n1.energy = 1.0
    n2.activation = 0.5

    burst = EventDrivenBurstEngine()
    burst.clear_queue()
    burst.collect_candidates(circuit)
    burst.process_burst(circuit, burst_id=1)

    assert n2.activation < 0.5


def test_excitatory_neuron_increases_target_activation(engine, circuit):
    n1 = circuit.input_neurons[0]
    n2 = circuit.hidden_neurons[0]
    n1.inhibitory = False
    n1.activation = 1.0
    n1.energy = 1.0
    n2.activation = 0.0

    burst = EventDrivenBurstEngine()
    burst.clear_queue()
    burst.collect_candidates(circuit)
    burst.process_burst(circuit, burst_id=1)

    assert n2.activation > 0.0


def test_refractory_neuron_skipped_by_fire_queue(engine, circuit):
    n1 = circuit.input_neurons[0]
    n1.activation = 1.0
    n1.energy = 1.0
    n1.refractory_counter = 2

    engine.update_refractory_states(circuit)
    assert n1.refractory_counter == 1

    burst = EventDrivenBurstEngine()
    burst.clear_queue()
    candidates = burst.collect_candidates(circuit)
    assert all(c.neuron_id != "n1" for c in candidates)


def test_refractory_counter_decays(engine, circuit):
    n1 = circuit.input_neurons[0]
    n1.refractory_counter = 3
    engine.update_refractory_states(circuit)
    assert n1.refractory_counter == 2
    engine.update_refractory_states(circuit)
    assert n1.refractory_counter == 1
    engine.update_refractory_states(circuit)
    assert n1.refractory_counter == 0


def test_snooze_applied_after_max_consecutive_fires(engine, circuit):
    n1 = circuit.input_neurons[0]
    n1.consecutive_fires = 3
    snoozed = engine.apply_dynamic_snooze(circuit)
    assert "n1" in snoozed
    assert n1.snooze_counter > 0
    assert n1.activation == 0.0
    assert n1.consecutive_fires == 0


def test_snoozed_neuron_skipped_by_fire_queue(engine, circuit):
    n1 = circuit.input_neurons[0]
    n1.activation = 1.0
    n1.energy = 1.0
    n1.snooze_counter = 2

    engine.update_snooze_states(circuit)
    assert n1.snooze_counter == 1

    burst = EventDrivenBurstEngine()
    burst.clear_queue()
    candidates = burst.collect_candidates(circuit)
    assert all(c.neuron_id != "n1" for c in candidates)


def test_snooze_event_registered(engine, circuit):
    mem = MorphologicalMemory()
    circuit.memory = mem
    n1 = circuit.input_neurons[0]
    n1.consecutive_fires = 3
    engine.apply_dynamic_snooze(circuit, memory=mem)
    assert len(mem.events) == 1
    event = mem.events[0]
    assert event.event_type == MorphologyEventType.NEURON_SNOOZED
    assert event.metadata["mechanism"] == "inhibition_engine"


def test_apply_decay_reduces_activation(engine, circuit):
    n1 = circuit.input_neurons[0]
    n1.activation = 1.0
    engine.apply_decay(circuit)
    assert n1.activation == pytest.approx(0.9)


def test_apply_decay_clamps_to_zero(engine, circuit):
    n1 = circuit.input_neurons[0]
    n1.activation = 1e-7
    engine.apply_decay(circuit)
    assert n1.activation == 0.0


def test_detect_runaway_dampens_high_activation(engine, circuit):
    n1 = circuit.input_neurons[0]
    n1.activation = 2.0
    handled = engine.detect_and_handle_runaway(circuit)
    assert "n1" in handled
    assert n1.activation < 2.0


def test_is_inhibitory_by_flag(engine, circuit):
    n = circuit.input_neurons[0]
    n.inhibitory = True
    assert InhibitionEngine.is_inhibitory(n) is True


def test_is_inhibitory_by_role(engine, circuit):
    n = circuit.input_neurons[0]
    n.inhibitory = False
    n.neuron_role = "inhibitory"
    assert InhibitionEngine.is_inhibitory(n) is True


def test_apply_inhibitory_signal(engine, circuit):
    source = DigitalNeuron(cell_id="src", role="digital_neuron", inhibitory=True, inhibition_strength=1.5)
    target = circuit.input_neurons[0]
    target.activation = 1.0
    InhibitionEngine.apply_inhibitory_signal(source, target, 0.5)
    assert target.activation == pytest.approx(1.0 - 0.5 * 1.5)


def test_stabilize_after_burst_composite(engine, circuit):
    n1 = circuit.input_neurons[0]
    n1.activation = 1.5
    n1.refractory_counter = 2
    n1.consecutive_fires = 3
    engine.stabilize_after_burst(circuit)
    assert n1.refractory_counter == 1
    assert n1.snooze_counter > 0
    assert n1.activation < 1.5
