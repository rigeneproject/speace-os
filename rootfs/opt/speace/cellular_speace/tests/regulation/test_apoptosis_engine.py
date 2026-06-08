import asyncio

import pytest

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regulation.apoptosis_engine import ApoptosisEngine
from speace_core.cellular_brain.regulation.homeostasis_engine import SystemMetrics


@pytest.fixture
def engine():
    return ApoptosisEngine(
        low_utility_threshold=0.15,
        high_energy_threshold=0.85,
        low_connectivity_threshold=1,
        apoptosis_risk_threshold=0.75,
        max_apoptosis_per_cycle=3,
        snooze_fire_threshold=5,
        snooze_duration=3,
        phi_threshold=0.55,
        synapse_prune_threshold=0.05,
    )


@pytest.fixture
def circuit():
    n1 = DigitalNeuron(cell_id="n1", role="digital_neuron")
    n2 = DigitalNeuron(cell_id="n2", role="digital_neuron")
    n3 = DigitalNeuron(cell_id="n3", role="digital_neuron")
    syn12 = DigitalSynapse(cell_id="s12", role="digital_synapse", source="n1", target="n2", weight=0.5, trust=0.5)
    syn23 = DigitalSynapse(cell_id="s23", role="digital_synapse", source="n2", target="n3", weight=0.01, trust=0.01)
    return NeuralCircuit(
        circuit_id="test",
        input_neurons=[n1],
        hidden_neurons=[n2],
        output_neurons=[n3],
        synapses=[syn12, syn23],
    )


def test_engine_does_not_remove_critical_neurons(engine, circuit):
    circuit.hidden_neurons[0].is_critical = True
    circuit.hidden_neurons[0].energy = 1.0
    metrics = SystemMetrics(tick=1, mean_energy=1.0, coherence_phi=0.4)
    result = engine.run(circuit, metrics=metrics)
    assert len(result.apoptosed) == 0
    assert len(circuit.hidden_neurons) == 1


def test_engine_does_not_remove_input_or_output_neurons(engine, circuit):
    # n1 is input, n3 is output
    circuit.input_neurons[0].energy = 1.0
    circuit.output_neurons[0].energy = 1.0
    metrics = SystemMetrics(tick=1, mean_energy=1.0, coherence_phi=0.4)
    result = engine.run(circuit, metrics=metrics)
    assert "n1" not in result.apoptosed
    assert "n3" not in result.apoptosed


def test_engine_removes_isolated_useless_neuron(engine, circuit):
    # Add an isolated hidden neuron with high energy and low utility
    isolated = DigitalNeuron(cell_id="iso", role="digital_neuron", energy=1.0, utility_score=0.0)
    circuit.hidden_neurons.append(isolated)
    metrics = SystemMetrics(tick=1, mean_energy=1.0, coherence_phi=0.4)
    result = engine.run(circuit, metrics=metrics)
    assert "iso" in result.apoptosed
    assert isolated not in circuit.hidden_neurons


def test_engine_removes_connected_synapses_on_apoptosis(engine, circuit):
    # n2 has synapses s12 and s23; lower threshold so n2 qualifies
    circuit.hidden_neurons[0].energy = 1.0
    circuit.hidden_neurons[0].utility_score = 0.0
    engine.apoptosis_risk_threshold = 0.4
    metrics = SystemMetrics(tick=1, mean_energy=1.0, coherence_phi=0.4)
    initial_syn_count = len(circuit.synapses)
    result = engine.run(circuit, metrics=metrics)
    assert "n2" in result.apoptosed
    # Both synapses involving n2 should be removed
    assert len(circuit.synapses) < initial_syn_count
    assert not any(s.source == "n2" or s.target == "n2" for s in circuit.synapses)


def test_engine_records_apoptosis_event(engine, circuit):
    isolated = DigitalNeuron(cell_id="iso", role="digital_neuron", energy=1.0, utility_score=0.0)
    circuit.hidden_neurons.append(isolated)
    mem = MorphologicalMemory()
    circuit.memory = mem
    metrics = SystemMetrics(tick=1, mean_energy=1.0, coherence_phi=0.4)
    engine.run(circuit, metrics=metrics)
    apoptosis_events = [
        e for e in mem.events
        if e.event_type == MorphologyEventType.NEURON_APOPTOSIS
    ]
    assert len(apoptosis_events) == 1
    event = apoptosis_events[0]
    assert event.target_id == "iso"
    assert event.metadata["apoptosis_risk"] >= engine.apoptosis_risk_threshold


def test_engine_applies_snooze_to_hyperactive_neuron(engine, circuit):
    n = DigitalNeuron(cell_id="hyper", role="digital_neuron")
    n.consecutive_fires = 10
    circuit.hidden_neurons.append(n)
    metrics = SystemMetrics(tick=1, mean_energy=0.5, coherence_phi=0.6)
    result = engine.run(circuit, metrics=metrics)
    assert "hyper" in result.snoozed
    assert n.snooze_counter == engine.snooze_duration


def test_engine_records_snooze_event(engine, circuit):
    n = DigitalNeuron(cell_id="hyper", role="digital_neuron")
    n.consecutive_fires = 10
    circuit.hidden_neurons.append(n)
    mem = MorphologicalMemory()
    circuit.memory = mem
    metrics = SystemMetrics(tick=1, mean_energy=0.5, coherence_phi=0.6)
    engine.run(circuit, metrics=metrics)
    assert mem.count_events(MorphologyEventType.NEURON_SNOOZED) == 1


def test_engine_prunes_weak_synapses(engine, circuit):
    # syn23 has weight=0.01 and trust=0.01, below threshold 0.05
    mem = MorphologicalMemory()
    circuit.memory = mem
    metrics = SystemMetrics(tick=1, mean_energy=0.5, coherence_phi=0.6)
    result = engine.run(circuit, metrics=metrics)
    assert any(s == "s23" for s in result.pruned_synapses)
    syn23 = next((s for s in circuit.synapses if s.cell_id == "s23"), None)
    if syn23 is not None:
        assert syn23.state == "pruned"


@pytest.mark.asyncio
async def test_neuron_snooze_blocks_firing():
    n = DigitalNeuron(cell_id="n", role="digital_neuron")
    n.activation = 1.0
    n.snooze_counter = 2
    signals = await n.tick()
    assert len(signals) == 0
    assert n.snooze_counter == 1


@pytest.mark.asyncio
async def test_neuron_refractory_blocks_firing():
    n = DigitalNeuron(cell_id="n", role="digital_neuron")
    n.activation = 1.0
    n.refractory_counter = 1
    signals = await n.tick()
    assert len(signals) == 0
    assert n.refractory_counter == 0
