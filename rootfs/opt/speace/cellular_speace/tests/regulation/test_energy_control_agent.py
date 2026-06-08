import pytest

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.execution.burst_engine import EventDrivenBurstEngine
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regulation.energy_control_agent import (
    EnergyControlAgent,
    EnergyControlDecision,
)
from speace_core.cellular_brain.regulation.homeostasis_engine import SystemMetrics


@pytest.fixture
def agent():
    return EnergyControlAgent(
        critical_low_replenish=0.05,
        normal_replenish=0.01,
        overflow_drain=0.03,
    )


@pytest.fixture
def circuit():
    n1 = DigitalNeuron(cell_id="n1", role="digital_neuron", threshold=0.5, energy=0.5)
    n2 = DigitalNeuron(cell_id="n2", role="digital_neuron", threshold=0.5, energy=0.5)
    n3 = DigitalNeuron(cell_id="n3", role="digital_neuron", threshold=0.5, energy=0.5)
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


# ---------------------------------------------------------------------------
# State classification
# ---------------------------------------------------------------------------

def test_classify_critical_low(agent):
    assert agent._classify_state(0.10) == "critical_low"
    assert agent._classify_state(0.20) == "critical_low"


def test_classify_low(agent):
    assert agent._classify_state(0.30) == "low"
    assert agent._classify_state(0.40) == "low"


def test_classify_optimal(agent):
    assert agent._classify_state(0.50) == "optimal"
    assert agent._classify_state(0.60) == "optimal"


def test_classify_high(agent):
    assert agent._classify_state(0.70) == "high"
    assert agent._classify_state(0.80) == "high"


def test_classify_critical_high(agent):
    assert agent._classify_state(0.90) == "critical_high"
    assert agent._classify_state(0.85) == "critical_high"


# ---------------------------------------------------------------------------
# Decision builders
# ---------------------------------------------------------------------------

def test_decision_critical_low(agent):
    d = agent._build_decision("critical_low", 0.15, 0.3)
    assert d.metabolic_state == "critical_low"
    assert d.burst_size_multiplier == 0.25
    assert d.stdp_rate_multiplier == 0.0
    assert d.plasticity_rate_multiplier == 0.0
    assert d.neurogenesis_allowance_multiplier == 0.0
    assert d.inhibition_decay_multiplier == 2.0
    assert d.apoptosis_pressure_multiplier == 0.0
    assert d.energy_replenish_rate == 0.05


def test_decision_low(agent):
    d = agent._build_decision("low", 0.35, 0.4)
    assert d.metabolic_state == "low"
    assert d.burst_size_multiplier == 0.50
    assert d.stdp_rate_multiplier == 0.50
    assert d.plasticity_rate_multiplier == 0.50
    assert d.neurogenesis_allowance_multiplier == 0.0
    assert d.inhibition_decay_multiplier == 1.5
    assert d.apoptosis_pressure_multiplier == 0.5
    assert d.energy_replenish_rate == 0.01


def test_decision_optimal(agent):
    d = agent._build_decision("optimal", 0.55, 0.6)
    assert d.metabolic_state == "optimal"
    assert d.burst_size_multiplier == 1.0
    assert d.stdp_rate_multiplier == 1.0
    assert d.plasticity_rate_multiplier == 1.0
    assert d.neurogenesis_allowance_multiplier == 1.0
    assert d.inhibition_decay_multiplier == 1.0
    assert d.apoptosis_pressure_multiplier == 1.0
    assert d.energy_replenish_rate == 0.01


def test_decision_high(agent):
    d = agent._build_decision("high", 0.75, 0.7)
    assert d.metabolic_state == "high"
    assert d.burst_size_multiplier == 1.50
    assert d.stdp_rate_multiplier == 1.25
    assert d.plasticity_rate_multiplier == 1.25
    assert d.neurogenesis_allowance_multiplier == 1.50
    assert d.inhibition_decay_multiplier == 0.5
    assert d.apoptosis_pressure_multiplier == 1.0
    assert d.energy_replenish_rate == 0.01


def test_decision_critical_high(agent):
    d = agent._build_decision("critical_high", 0.90, 0.8)
    assert d.metabolic_state == "critical_high"
    assert d.burst_size_multiplier == 2.0
    assert d.stdp_rate_multiplier == 1.50
    assert d.plasticity_rate_multiplier == 1.50
    assert d.neurogenesis_allowance_multiplier == 2.0
    assert d.inhibition_decay_multiplier == 0.25
    assert d.apoptosis_pressure_multiplier == 2.0
    assert d.energy_replenish_rate == -0.03


# ---------------------------------------------------------------------------
# Energy replenishment / drainage
# ---------------------------------------------------------------------------

def test_replenish_in_critical_low(agent, circuit):
    n = circuit.input_neurons[0]
    n.energy = 0.1
    d = agent._build_decision("critical_low", 0.15, 0.3)
    agent._replenish_or_drain(circuit, d)
    assert n.energy == pytest.approx(0.15)


def test_drain_in_critical_high(agent, circuit):
    n = circuit.input_neurons[0]
    n.energy = 0.95
    d = agent._build_decision("critical_high", 0.90, 0.8)
    agent._replenish_or_drain(circuit, d)
    assert n.energy == pytest.approx(0.92)


def test_replenish_caps_at_one(agent, circuit):
    n = circuit.input_neurons[0]
    n.energy = 0.98
    d = agent._build_decision("critical_low", 0.15, 0.3)
    agent._replenish_or_drain(circuit, d)
    assert n.energy == 1.0


def test_drain_floors_at_zero(agent, circuit):
    n = circuit.input_neurons[0]
    n.energy = 0.02
    d = agent._build_decision("critical_high", 0.90, 0.8)
    agent._replenish_or_drain(circuit, d)
    assert n.energy == 0.0


# ---------------------------------------------------------------------------
# Burst engine multiplier application
# ---------------------------------------------------------------------------

def test_burst_size_reduced_in_low_energy(agent, circuit):
    burst = EventDrivenBurstEngine(max_burst_size=100)
    d = agent._build_decision("low", 0.35, 0.4)
    agent._apply_multipliers(d, burst)
    assert burst.max_burst_size == 50


def test_burst_size_increased_in_high_energy(agent, circuit):
    burst = EventDrivenBurstEngine(max_burst_size=100)
    d = agent._build_decision("high", 0.75, 0.7)
    agent._apply_multipliers(d, burst)
    assert burst.max_burst_size == 150


def test_burst_size_minimum_one(agent, circuit):
    burst = EventDrivenBurstEngine(max_burst_size=1)
    d = agent._build_decision("critical_low", 0.15, 0.3)
    agent._apply_multipliers(d, burst)
    assert burst.max_burst_size == 1


def test_apply_multipliers_restores_original(agent, circuit):
    burst = EventDrivenBurstEngine(max_burst_size=100)
    d1 = agent._build_decision("low", 0.35, 0.4)
    agent._apply_multipliers(d1, burst)
    assert burst.max_burst_size == 50
    d2 = agent._build_decision("optimal", 0.55, 0.6)
    agent._apply_multipliers(d2, burst)
    assert burst.max_burst_size == 100


# ---------------------------------------------------------------------------
# Full regulation integration
# ---------------------------------------------------------------------------

def test_regulate_returns_decision(agent, circuit):
    metrics = SystemMetrics(tick=1, mean_energy=0.15, coherence_phi=0.3)
    decision = agent.regulate(circuit, metrics=metrics)
    assert isinstance(decision, EnergyControlDecision)
    assert decision.metabolic_state == "critical_low"


def test_regulate_records_event_in_memory(agent, circuit):
    mem = MorphologicalMemory()
    circuit.memory = mem
    metrics = SystemMetrics(tick=1, mean_energy=0.15, coherence_phi=0.3)
    agent.regulate(circuit, metrics=metrics, memory=mem)
    events = [e for e in mem.events if e.event_type == MorphologyEventType.ENERGY_CHANGED]
    assert len(events) == 1
    assert events[0].metadata["metabolic_state"] == "critical_low"


def test_get_last_decision(agent, circuit):
    assert agent.get_last_decision() is None
    metrics = SystemMetrics(tick=1, mean_energy=0.55, coherence_phi=0.6)
    agent.regulate(circuit, metrics=metrics)
    last = agent.get_last_decision()
    assert last is not None
    assert last.metabolic_state == "optimal"


# ---------------------------------------------------------------------------
# Orchestrator integration (end-to-end)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orchestrator_energy_control_enabled():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    assert orch.energy_control_enabled is True
    assert orch._energy_control is not None


@pytest.mark.asyncio
async def test_orchestrator_tick_applies_energy_control():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.execution_mode = "event_driven_burst"

    # Force low energy to trigger replenishment
    for n in orch.circuit.input_neurons + orch.circuit.hidden_neurons + orch.circuit.output_neurons:
        n.energy = 0.15

    before = orch.circuit.input_neurons[0].energy
    await orch.run_ticks(1)
    after = orch.circuit.input_neurons[0].energy

    # Energy should be replenished in critical_low state
    assert after > before
    decision = orch._energy_control.get_last_decision()
    assert decision is not None
    assert decision.metabolic_state == "critical_low"


@pytest.mark.asyncio
async def test_orchestrator_energy_control_disabled():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.energy_control_enabled = False
    orch.execution_mode = "event_driven_burst"

    for n in orch.circuit.input_neurons + orch.circuit.hidden_neurons + orch.circuit.output_neurons:
        n.energy = 0.15

    before = orch.circuit.input_neurons[0].energy
    await orch.run_ticks(1)
    after = orch.circuit.input_neurons[0].energy

    # No energy control applied, energy should stay roughly same (minus burst cost)
    assert after <= before
    assert orch._energy_control.get_last_decision() is None
