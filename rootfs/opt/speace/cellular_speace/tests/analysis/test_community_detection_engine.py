import pytest

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.analysis.community_detection_engine import (
    CommunityDetectionEngine,
    CommunityProfile,
    CommunityDetectionResult,
)


@pytest.fixture
def engine():
    return CommunityDetectionEngine()


@pytest.fixture
def connected_circuit():
    """Circuit with two separate connected components plus one isolated neuron."""
    n1 = DigitalNeuron(cell_id="n1", role="digital_neuron", threshold=0.5, energy=0.5)
    n2 = DigitalNeuron(cell_id="n2", role="digital_neuron", threshold=0.5, energy=0.5)
    n3 = DigitalNeuron(cell_id="n3", role="digital_neuron", threshold=0.5, energy=0.5)
    n4 = DigitalNeuron(cell_id="n4", role="digital_neuron", threshold=0.5, energy=0.5)
    n5 = DigitalNeuron(cell_id="n5", role="digital_neuron", threshold=0.5, energy=0.5)
    # Component A: n1 <-> n2
    s12 = DigitalSynapse(cell_id="s12", role="digital_synapse", source="n1", target="n2", weight=0.8)
    s21 = DigitalSynapse(cell_id="s21", role="digital_synapse", source="n2", target="n1", weight=0.8)
    # Component B: n3 <-> n4
    s34 = DigitalSynapse(cell_id="s34", role="digital_synapse", source="n3", target="n4", weight=0.8)
    s43 = DigitalSynapse(cell_id="s43", role="digital_synapse", source="n4", target="n3", weight=0.8)
    # n5 is isolated (no synapses)
    return NeuralCircuit(
        circuit_id="test",
        input_neurons=[n1],
        hidden_neurons=[n2, n3, n4, n5],
        output_neurons=[],
        synapses=[s12, s21, s34, s43],
    )


@pytest.fixture
def single_component_circuit():
    """Circuit with one connected component."""
    n1 = DigitalNeuron(cell_id="n1", role="digital_neuron", threshold=0.5, energy=0.5)
    n2 = DigitalNeuron(cell_id="n2", role="digital_neuron", threshold=0.5, energy=0.5)
    n3 = DigitalNeuron(cell_id="n3", role="digital_neuron", threshold=0.5, energy=0.5)
    s12 = DigitalSynapse(cell_id="s12", role="digital_synapse", source="n1", target="n2", weight=0.8)
    s23 = DigitalSynapse(cell_id="s23", role="digital_synapse", source="n2", target="n3", weight=0.8)
    return NeuralCircuit(
        circuit_id="single",
        input_neurons=[n1],
        output_neurons=[n3],
        hidden_neurons=[n2],
        synapses=[s12, s23],
    )


# ---------------------------------------------------------------------------
# Core engine tests
# ---------------------------------------------------------------------------

def test_engine_is_importable():
    assert CommunityDetectionEngine is not None
    assert CommunityProfile is not None
    assert CommunityDetectionResult is not None


def test_build_adjacency_map(engine, connected_circuit):
    adj = engine.build_adjacency_map(connected_circuit)
    assert "n1" in adj
    assert "n2" in adj["n1"]
    assert "n3" in adj
    assert "n4" in adj["n3"]
    assert "n5" not in adj  # isolated


def test_detect_communities_finds_two_components(engine, connected_circuit):
    communities = engine.detect_communities(connected_circuit)
    assert len(communities) == 2
    # Each component should have 2 neurons
    assert all(len(c) == 2 for c in communities)
    all_members = [nid for c in communities for nid in c]
    assert "n1" in all_members
    assert "n2" in all_members
    assert "n3" in all_members
    assert "n4" in all_members
    assert "n5" not in all_members


def test_detect_communities_single_component(engine, single_component_circuit):
    communities = engine.detect_communities(single_component_circuit)
    assert len(communities) == 1
    assert set(communities[0]) == {"n1", "n2", "n3"}


def test_find_isolated_neurons(engine, connected_circuit):
    isolated = engine.find_isolated_neurons(connected_circuit)
    assert "n5" in isolated
    assert "n1" not in isolated
    assert "n2" not in isolated


def test_find_isolated_neurons_none(engine, single_component_circuit):
    isolated = engine.find_isolated_neurons(single_component_circuit)
    assert len(isolated) == 0


def test_profile_community_fields(engine, single_component_circuit):
    profile = engine.profile_community(
        single_component_circuit, ["n1", "n2", "n3"], community_id="comm_0"
    )
    assert profile.community_id == "comm_0"
    assert profile.size == 3
    assert profile.mean_activation == pytest.approx(0.0)
    assert profile.internal_synapse_count == 2
    assert profile.external_synapse_count == 0
    assert profile.cohesion_score == pytest.approx(2 / (2 + 0 + 1))
    assert profile.isolation_score == pytest.approx(1 - 2 / 3)


def test_cohesion_score_in_range(engine, single_component_circuit):
    profile = engine.profile_community(single_component_circuit, ["n1", "n2", "n3"])
    assert 0.0 <= profile.cohesion_score <= 1.0


def test_modularity_proxy_in_range(engine, connected_circuit):
    result = engine.analyze(connected_circuit)
    assert 0.0 <= result.modularity_proxy <= 1.0


def test_modularity_proxy_single_component(engine, single_component_circuit):
    result = engine.analyze(single_component_circuit)
    # Single fully-connected component should have high modularity
    assert result.modularity_proxy > 0.5


def test_weak_communities_detected(engine, connected_circuit):
    # Manually lower cohesion threshold to force weak detection
    engine.cohesion_weak_threshold = 0.9
    result = engine.analyze(connected_circuit)
    assert len(result.weak_communities) >= 1


def test_overloaded_communities_detected(engine, single_component_circuit):
    # Raise activation/energy to trigger overload
    for n in single_component_circuit.input_neurons + single_component_circuit.hidden_neurons + single_component_circuit.output_neurons:
        n.activation = 1.0
        n.energy = 1.0
    result = engine.analyze(single_component_circuit)
    assert len(result.overloaded_communities) >= 1


def test_analyze_records_event(engine, connected_circuit):
    mem = MorphologicalMemory()
    connected_circuit.memory = mem
    result = engine.analyze(connected_circuit, memory=mem)
    events = [e for e in mem.events if e.event_type == MorphologyEventType.COMMUNITY_DETECTED]
    assert len(events) == 1
    assert events[0].metadata["community_count"] == result.community_count


def test_dominant_cell_type_and_region(engine, connected_circuit):
    connected_circuit.hidden_neurons[0].cell_type = "sensory_neuron"
    connected_circuit.hidden_neurons[1].cell_type = "sensory_neuron"
    connected_circuit.hidden_neurons[2].cell_type = "motor_neuron"
    connected_circuit.hidden_neurons[0].region = "prefrontal"
    connected_circuit.hidden_neurons[1].region = "prefrontal"
    connected_circuit.hidden_neurons[2].region = "hippocampus"
    adj = engine.build_adjacency_map(connected_circuit)
    communities = engine.detect_communities(connected_circuit, adj)
    for idx, c in enumerate(communities):
        profile = engine.profile_community(connected_circuit, c, community_id=f"comm_{idx}")
        assert profile.dominant_cell_type is not None
        assert profile.dominant_region is not None


# ---------------------------------------------------------------------------
# Orchestrator integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orchestrator_community_detection_enabled():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    assert orch.community_detection_enabled is True
    assert orch._community is not None


@pytest.mark.asyncio
async def test_orchestrator_tick_populates_last_community_result():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.execution_mode = "event_driven_burst"
    await orch.run_ticks(1)
    assert orch.last_community_result is not None
    assert orch.last_community_result.community_count >= 1


@pytest.mark.asyncio
async def test_orchestrator_community_detection_disabled():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.community_detection_enabled = False
    orch.execution_mode = "event_driven_burst"
    await orch.run_ticks(1)
    assert orch.last_community_result is None


# ---------------------------------------------------------------------------
# Benchmark integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_benchmark_includes_community_metrics():
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
    assert result.metrics.community_count >= 1
    assert 0.0 <= result.metrics.modularity_proxy <= 1.0
    assert result.metrics.isolated_neuron_count >= 0
    assert result.metrics.weak_community_count >= 0
    assert result.metrics.overloaded_community_count >= 0
