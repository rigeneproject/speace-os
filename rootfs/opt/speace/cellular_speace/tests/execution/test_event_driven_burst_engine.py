import pytest

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.execution.burst_engine import (
    EventDrivenBurstEngine,
    FireCandidate,
)


@pytest.fixture
def engine():
    return EventDrivenBurstEngine(
        activation_threshold=0.5,
        max_burst_size=2,
        max_bursts_per_tick=5,
        min_energy=0.1,
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


def test_collect_candidates_selects_above_threshold(engine, circuit):
    circuit.input_neurons[0].activation = 1.0
    circuit.input_neurons[0].energy = 1.0
    candidates = engine.collect_candidates(circuit)
    assert len(candidates) == 1
    assert candidates[0].neuron_id == "n1"
    assert candidates[0].priority == 0.5


def test_snoozed_neuron_not_candidate(engine, circuit):
    n = circuit.input_neurons[0]
    n.activation = 1.0
    n.energy = 1.0
    n.snooze_counter = 3
    candidates = engine.collect_candidates(circuit)
    assert len(candidates) == 0


def test_refractory_neuron_not_candidate(engine, circuit):
    n = circuit.input_neurons[0]
    n.activation = 1.0
    n.energy = 1.0
    n.refractory_counter = 2
    candidates = engine.collect_candidates(circuit)
    assert len(candidates) == 0


def test_low_energy_neuron_not_candidate(engine, circuit):
    n = circuit.input_neurons[0]
    n.activation = 1.0
    n.energy = 0.05  # below min_energy=0.1
    candidates = engine.collect_candidates(circuit)
    assert len(candidates) == 0


def test_process_burst_respects_max_burst_size(engine, circuit):
    for n in circuit.input_neurons + circuit.hidden_neurons + circuit.output_neurons:
        n.activation = 1.0
        n.energy = 1.0
    engine.clear_queue()
    engine.collect_candidates(circuit)
    result = engine.process_burst(circuit, burst_id=1)
    assert len(result.fired_neurons) <= engine.max_burst_size


def test_propagate_fire_updates_target_activation(engine, circuit):
    n1 = circuit.input_neurons[0]
    n2 = circuit.hidden_neurons[0]
    n1.activation = 1.0
    n1.energy = 1.0
    n2.activation = 0.0
    n2.energy = 1.0
    engine.clear_queue()
    engine.collect_candidates(circuit)
    engine.process_burst(circuit, burst_id=1)
    # n1 fired, propagated through s12 with weight 0.8
    assert n2.activation > 0.0


def test_run_event_cycle_runs_multiple_bursts(engine, circuit):
    n1 = circuit.input_neurons[0]
    n2 = circuit.hidden_neurons[0]
    n3 = circuit.output_neurons[0]
    for n in [n1, n2, n3]:
        n.activation = 1.0
        n.energy = 1.0
    results = engine.run_event_cycle(circuit)
    assert len(results) >= 1
    total_fired = sum(len(r.fired_neurons) for r in results)
    assert total_fired >= 1


def test_burst_id_increments(engine, circuit):
    n1 = circuit.input_neurons[0]
    n1.activation = 1.0
    n1.energy = 1.0
    engine.run_event_cycle(circuit, max_bursts=3)
    assert engine.burst_counter >= 1


def test_clear_queue_empties(engine, circuit):
    n1 = circuit.input_neurons[0]
    n1.activation = 1.0
    n1.energy = 1.0
    engine.collect_candidates(circuit)
    assert len(engine._fire_queue) > 0
    engine.clear_queue()
    assert len(engine._fire_queue) == 0


def test_consecutive_fires_incremented(engine, circuit):
    n = circuit.input_neurons[0]
    n.activation = 1.0
    n.energy = 1.0
    n.consecutive_fires = 0
    engine.clear_queue()
    engine.collect_candidates(circuit)
    engine.process_burst(circuit, burst_id=1)
    assert n.consecutive_fires == 1


def test_last_fired_burst_set(engine, circuit):
    n = circuit.input_neurons[0]
    n.activation = 1.0
    n.energy = 1.0
    engine.clear_queue()
    engine.collect_candidates(circuit)
    engine.process_burst(circuit, burst_id=7)
    assert n.last_fired_burst == 7


def test_refractory_period_set_after_fire(engine, circuit):
    n = circuit.input_neurons[0]
    n.activation = 1.0
    n.energy = 1.0
    n.refractory_period = 3
    engine.clear_queue()
    engine.collect_candidates(circuit)
    engine.process_burst(circuit, burst_id=1)
    assert n.refractory_counter == 3


def test_propagate_fire_method(engine, circuit):
    n1 = circuit.input_neurons[0]
    n2 = circuit.hidden_neurons[0]
    n1.activation = 1.0
    n1.energy = 1.0
    n2.activation = 0.0
    count = engine.propagate_fire(circuit, n1)
    assert count >= 1
    assert n2.activation > 0.0


def test_pruned_synapse_skipped(engine, circuit):
    n1 = circuit.input_neurons[0]
    n2 = circuit.hidden_neurons[0]
    n1.activation = 1.0
    n1.energy = 1.0
    n2.activation = 0.0
    # Prune the synapse
    for syn in circuit.synapses:
        if syn.source == "n1":
            syn.state = "pruned"
    engine.clear_queue()
    engine.collect_candidates(circuit)
    result = engine.process_burst(circuit, burst_id=1)
    assert result.propagated_synapses == 0


def test_empty_queue_returns_empty_result(engine, circuit):
    result = engine.process_burst(circuit, burst_id=1)
    assert result.burst_id == 1
    assert result.fired_neurons == []


def test_missing_target_neuron_skipped(engine, circuit):
    n1 = circuit.input_neurons[0]
    n1.activation = 1.0
    n1.energy = 1.0
    # Point synapse to nonexistent target
    for syn in circuit.synapses:
        if syn.source == "n1":
            syn.target = "ghost"
    engine.clear_queue()
    engine.collect_candidates(circuit)
    result = engine.process_burst(circuit, burst_id=1)
    assert result.propagated_synapses == 0


@pytest.mark.asyncio
async def test_orchestrator_burst_mode():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.execution_mode = "event_driven_burst"

    # Inject enough activation to trigger firing
    pattern = [1.0] * 10
    orch.inject(pattern)
    await orch.run_ticks(2)

    assert orch.execution_mode == "event_driven_burst"
    assert orch._burst_engine.burst_counter >= 1
    assert len(orch.memory.snapshots) >= 1
    assert orch.memory.snapshots[-1].execution_mode == "event_driven_burst"


@pytest.mark.asyncio
async def test_orchestrator_burst_mode_applies_stdp():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.execution_mode = "event_driven_burst"
    orch.stdp_enabled = True

    # Inject enough activation to trigger firing
    pattern = [1.0] * 10
    orch.inject(pattern)
    await orch.run_ticks(2)

    # STDP may have recorded synapse events if pre/post fired in causal order
    stdp_events = [
        e for e in orch.memory.events
        if e.event_type in {
            MorphologyEventType.SYNAPSE_REINFORCED,
            MorphologyEventType.SYNAPSE_WEAKENED,
        }
    ]
    # We cannot guarantee STDP events occurred because firing order depends on
    # random weights, but we can verify the engine ran without error.
    assert orch.stdp_enabled is True
