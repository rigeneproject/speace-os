import math

import pytest

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.metacognition.confidence_engine import (
    ConfidenceEngine,
    ConfidenceState,
)
from speace_core.cellular_brain.regulation.homeostasis_engine import SystemMetrics


@pytest.fixture
def engine():
    return ConfidenceEngine()


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
# Core computations
# ---------------------------------------------------------------------------

def test_compute_output_entropy_flat_output(engine):
    # All equal activations → high entropy
    flat = [0.5, 0.5, 0.5, 0.5]
    entropy = engine.compute_output_entropy(flat)
    assert entropy > 0.8


def test_compute_output_entropy_peaked_output(engine):
    # One dominant activation → low entropy
    peaked = [0.9, 0.05, 0.03, 0.02]
    entropy = engine.compute_output_entropy(peaked)
    assert entropy < 0.5


def test_compute_output_entropy_empty(engine):
    assert engine.compute_output_entropy([]) == 0.0


def test_compute_activation_margin_clear_winner(engine):
    acts = [0.9, 0.4, 0.2]
    margin = engine.compute_activation_margin(acts)
    assert margin == pytest.approx(0.5)


def test_compute_activation_margin_tie(engine):
    acts = [0.5, 0.5, 0.3]
    margin = engine.compute_activation_margin(acts)
    assert margin == pytest.approx(0.0)


def test_compute_activation_margin_single_output(engine):
    assert engine.compute_activation_margin([0.5]) == 0.0


def test_decision_stability_first_call(engine):
    acts = [0.5, 0.3, 0.2]
    stability = engine.compute_decision_stability(acts)
    assert stability == 1.0


def test_decision_stability_similar_outputs(engine):
    acts1 = [0.5, 0.3, 0.2]
    engine.compute_decision_stability(acts1)
    acts2 = [0.52, 0.28, 0.20]
    stability = engine.compute_decision_stability(acts2)
    assert stability > 0.9


def test_decision_stability_different_outputs(engine):
    acts1 = [0.9, 0.05, 0.05]
    engine.compute_decision_stability(acts1)
    acts2 = [0.1, 0.8, 0.1]
    stability = engine.compute_decision_stability(acts2)
    assert stability < 0.5


def test_compute_error_risk_high(engine):
    risk = engine.compute_error_risk(confidence=0.2, phi=0.2, mean_energy=0.1)
    assert risk > 0.5


def test_compute_error_risk_low(engine):
    risk = engine.compute_error_risk(confidence=0.9, phi=0.8, mean_energy=0.5)
    assert risk < 0.5


def test_error_risk_clamped(engine):
    risk = engine.compute_error_risk(confidence=0.0, phi=0.0, mean_energy=0.0)
    assert 0.0 <= risk <= 1.0


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

def test_recommend_maintain_high_confidence_high_phi(engine):
    action = engine.recommend_action(confidence=0.8, phi=0.6, mean_energy=0.5, error_risk=0.2)
    assert action == "maintain"


def test_recommend_reduce_plasticity_high_confidence_high_error(engine):
    action = engine.recommend_action(confidence=0.8, phi=0.6, mean_energy=0.5, error_risk=0.6)
    assert action == "reduce_plasticity"


def test_recommend_stabilize_low_confidence_low_phi(engine):
    action = engine.recommend_action(confidence=0.2, phi=0.2, mean_energy=0.5, error_risk=0.5)
    assert action == "stabilize"


def test_recommend_neurogenesis_low_confidence_sufficient_energy(engine):
    action = engine.recommend_action(confidence=0.2, phi=0.5, mean_energy=0.5, error_risk=0.3)
    assert action == "recommend_neurogenesis"


def test_recommend_increase_inhibition_unstable(engine):
    action = engine.recommend_action(confidence=0.3, phi=0.5, mean_energy=0.5, error_risk=0.5)
    assert action == "increase_inhibition"


def test_recommend_community_guided(engine):
    from speace_core.cellular_brain.analysis.community_detection_engine import CommunityDetectionResult
    result = CommunityDetectionResult(isolated_neurons=["a", "b", "c", "d"])
    action = engine.recommend_action(
        confidence=0.2, phi=0.5, mean_energy=0.5, error_risk=0.3, community_result=result
    )
    assert action == "community_guided_neurogenesis"


# ---------------------------------------------------------------------------
# Full evaluation
# ---------------------------------------------------------------------------

def test_evaluate_returns_confidence_state(engine, circuit):
    metrics = SystemMetrics(tick=1, coherence_phi=0.6, mean_energy=0.7)
    state = engine.evaluate(circuit, metrics=metrics)
    assert isinstance(state, ConfidenceState)
    assert 0.0 <= state.confidence_score <= 1.0
    assert state.uncertainty_score == pytest.approx(1.0 - state.confidence_score)


def test_evaluate_records_event(engine, circuit):
    mem = MorphologicalMemory()
    metrics = SystemMetrics(tick=1, coherence_phi=0.6, mean_energy=0.7)
    engine.evaluate(circuit, metrics=metrics, memory=mem)
    events = [e for e in mem.events if e.event_type == MorphologyEventType.CONFIDENCE_EVALUATED]
    assert len(events) == 1
    assert "confidence_score" in events[0].metadata


def test_evaluate_produces_recommendation(engine, circuit):
    metrics = SystemMetrics(tick=1, coherence_phi=0.6, mean_energy=0.7)
    state = engine.evaluate(circuit, metrics=metrics)
    assert state.recommended_action in {
        "maintain",
        "stabilize",
        "reduce_plasticity",
        "recommend_neurogenesis",
        "increase_inhibition",
        "community_guided_neurogenesis",
        "increase_plasticity",
    }


# ---------------------------------------------------------------------------
# Orchestrator integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orchestrator_confidence_enabled():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    assert orch.confidence_enabled is True
    assert orch._confidence is not None


@pytest.mark.asyncio
async def test_orchestrator_tick_populates_last_confidence_state():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.execution_mode = "event_driven_burst"
    await orch.run_ticks(1)
    assert orch.last_confidence_state is not None
    assert 0.0 <= orch.last_confidence_state.confidence_score <= 1.0


@pytest.mark.asyncio
async def test_orchestrator_confidence_disabled():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.confidence_enabled = False
    orch.execution_mode = "event_driven_burst"
    await orch.run_ticks(1)
    assert orch.last_confidence_state is None


# ---------------------------------------------------------------------------
# Benchmark integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_benchmark_includes_confidence_metrics():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import NeuroFunctionalBenchmark

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    benchmark = NeuroFunctionalBenchmark(orch)
    pattern = [1.0 if i % 2 == 0 else 0.0 for i in range(10)]
    result = await benchmark.run_case(
        "adaptation_after_error",
        execution_mode="event_driven_burst",
        input_pattern=pattern,
        target_output=pattern,
        n_ticks=3,
    )
    assert 0.0 <= result.metrics.confidence_score <= 1.0
    assert 0.0 <= result.metrics.uncertainty_score <= 1.0
    assert 0.0 <= result.metrics.output_entropy <= 1.0
    assert 0.0 <= result.metrics.decision_stability <= 1.0
    assert 0.0 <= result.metrics.error_risk <= 1.0
    assert result.metrics.recommended_action != ""
    assert 0.0 <= result.metrics.meta_cognitive_score <= 1.0
