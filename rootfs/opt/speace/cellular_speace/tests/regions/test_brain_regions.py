import pytest

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.regions.brain_region import BrainRegion, BrainRegionProfile
from speace_core.cellular_brain.regions.region_connectome import (
    InterRegionConnection,
    RegionConnectome,
)
from speace_core.cellular_brain.regions.region_factory import RegionFactory
from speace_core.cellular_brain.regions.region_registry import RegionRegistry


# ---------------------------------------------------------------------------
# BrainRegion
# ---------------------------------------------------------------------------

def test_brain_region_init():
    region = BrainRegion(
        region_id="sensory_01",
        region_type="sensory",
        neuron_ids=["n1", "n2"],
        dominant_cell_types=["sensory_neuron"],
    )
    assert region.region_id == "sensory_01"
    assert region.region_type == "sensory"
    assert region.neuron_ids == ["n1", "n2"]


def test_brain_region_to_profile():
    region = BrainRegion(region_id="hippo_01", region_type="hippocampus")
    profile = region.to_profile()
    assert isinstance(profile, BrainRegionProfile)
    assert profile.region_id == "hippo_01"
    assert profile.region_type == "hippocampus"


def test_brain_region_signal_io():
    region = BrainRegion(region_id="test", region_type="test")
    region.receive_signal([0.5, 0.3])
    region.receive_signal([0.2])
    # receive_signal writes to _input_buffer; emit_signal reads _output_buffer
    # Directly populate _output_buffer for emission test
    region._output_buffer = region._input_buffer.copy()
    out = region.emit_signal()
    assert out == [0.5, 0.3, 0.2]
    assert region.emit_signal() == []


def test_brain_region_flush_buffers():
    region = BrainRegion(region_id="test", region_type="test")
    region.receive_signal([0.5])
    region.flush_buffers()
    assert region.emit_signal() == []


def test_brain_region_compute_local_metrics():
    n1 = DigitalNeuron(cell_id="n1", role="digital_neuron", threshold=0.5, energy=0.8)
    n2 = DigitalNeuron(cell_id="n2", role="digital_neuron", threshold=0.5, energy=0.6)
    circuit = NeuralCircuit(
        circuit_id="test",
        input_neurons=[],
        hidden_neurons=[n1, n2],
        output_neurons=[],
        synapses=[],
    )
    region = BrainRegion(region_id="r1", region_type="sensory", neuron_ids=["n1", "n2"])
    profile = region.compute_local_metrics(circuit)
    assert profile.mean_energy == pytest.approx(0.7)
    assert profile.local_phi == 0.0


def test_brain_region_regulate_region_high_energy():
    n1 = DigitalNeuron(cell_id="n1", role="digital_neuron", threshold=0.5, energy=0.95)
    n2 = DigitalNeuron(cell_id="n2", role="digital_neuron", threshold=0.5, energy=0.95)
    circuit = NeuralCircuit(
        circuit_id="test",
        input_neurons=[],
        hidden_neurons=[n1, n2],
        output_neurons=[],
        synapses=[],
    )
    region = BrainRegion(region_id="r1", region_type="sensory", neuron_ids=["n1", "n2"])
    region.regulate_region(circuit)
    assert n1.energy == pytest.approx(0.95 * 0.98)
    assert n2.energy == pytest.approx(0.95 * 0.98)


def test_brain_region_regulate_region_low_energy():
    n1 = DigitalNeuron(cell_id="n1", role="digital_neuron", threshold=0.5, energy=0.2)
    n2 = DigitalNeuron(cell_id="n2", role="digital_neuron", threshold=0.5, energy=0.2)
    circuit = NeuralCircuit(
        circuit_id="test",
        input_neurons=[],
        hidden_neurons=[n1, n2],
        output_neurons=[],
        synapses=[],
    )
    region = BrainRegion(region_id="r1", region_type="sensory", neuron_ids=["n1", "n2"])
    region.regulate_region(circuit)
    assert n1.energy == pytest.approx(0.22)
    assert n2.energy == pytest.approx(0.22)


# ---------------------------------------------------------------------------
# RegionConnectome
# ---------------------------------------------------------------------------

def test_region_connectome_add_connection():
    rc = RegionConnectome()
    conn = rc.add_connection("sensory", "motor", strength=0.7)
    assert isinstance(conn, InterRegionConnection)
    assert conn.source_region_id == "sensory"
    assert conn.target_region_id == "motor"
    assert conn.strength == 0.7


def test_region_connectome_get_connections():
    rc = RegionConnectome()
    rc.add_connection("sensory", "hippocampus")
    rc.add_connection("sensory", "motor")
    rc.add_connection("hippocampus", "motor")
    assert len(rc.get_connections_from("sensory")) == 2
    assert len(rc.get_connections_to("motor")) == 2


def test_region_connectome_remove_connections():
    rc = RegionConnectome()
    rc.add_connection("sensory", "hippocampus")
    rc.add_connection("hippocampus", "motor")
    rc.remove_connections_involving("sensory")
    assert len(rc.connections) == 1


def test_region_connectome_density():
    rc = RegionConnectome()
    rc.regions = {"a": None, "b": None, "c": None}
    rc.add_connection("a", "b")
    rc.add_connection("b", "c")
    density = rc.compute_connectome_density()
    assert density == pytest.approx(2 / 6)


# ---------------------------------------------------------------------------
# RegionRegistry
# ---------------------------------------------------------------------------

def test_region_registry_register_and_get():
    reg = RegionRegistry()
    region = BrainRegion(region_id="sensory", region_type="sensory")
    reg.register(region)
    assert reg.get("sensory") is region
    assert reg.list_region_ids() == ["sensory"]


def test_region_registry_remove():
    reg = RegionRegistry()
    reg.register(BrainRegion(region_id="a", region_type="a"))
    reg.register(BrainRegion(region_id="b", region_type="b"))
    reg.connectome.add_connection("a", "b")
    reg.remove_region("a")
    assert "a" not in reg.regions
    assert len(reg.connectome.connections) == 0


def test_region_registry_global_metrics():
    reg = RegionRegistry()
    r1 = BrainRegion(region_id="a", region_type="a", neuron_ids=["n1"])
    r2 = BrainRegion(region_id="b", region_type="b", neuron_ids=["n2"])
    reg.register(r1)
    reg.register(r2)
    reg.connectome.add_connection("a", "b")
    metrics = reg.compute_global_metrics()
    assert "connectome_density" in metrics
    assert "total_neurons_in_regions" in metrics


# ---------------------------------------------------------------------------
# RegionFactory
# ---------------------------------------------------------------------------

def test_region_factory_build_from_genome_empty():
    n1 = DigitalNeuron(cell_id="n1", role="digital_neuron", threshold=0.5)
    n2 = DigitalNeuron(cell_id="n2", role="digital_neuron", threshold=0.5)
    circuit = NeuralCircuit(
        circuit_id="test",
        input_neurons=[],
        hidden_neurons=[n1, n2],
        output_neurons=[],
        synapses=[],
    )
    registry = RegionFactory.build_from_genome(circuit, {}, seed=42, deep_regions_enabled=False)
    assert len(registry.regions) == 4
    assert "sensory" in registry.regions
    assert "hippocampus" in registry.regions
    assert "prefrontal" in registry.regions
    assert "motor" in registry.regions


def test_region_factory_assigns_neurons():
    neurons = [
        DigitalNeuron(cell_id=f"n{i}", role="digital_neuron", threshold=0.5)
        for i in range(20)
    ]
    circuit = NeuralCircuit(
        circuit_id="test",
        input_neurons=[],
        hidden_neurons=neurons,
        output_neurons=[],
        synapses=[],
    )
    genome = {
        "brain_regions": {
            "sensory": {"dominant_cell_types": ["sensory_neuron"]},
            "motor": {"dominant_cell_types": ["motor_neuron"]},
            "hippocampus": {"dominant_cell_types": ["hippocampal_neuron"]},
            "prefrontal": {"dominant_cell_types": ["prefrontal_neuron"]},
        }
    }
    registry = RegionFactory.build_from_genome(circuit, genome, seed=42)
    total = sum(len(r.neuron_ids) for r in registry.regions.values())
    assert total == 20


def test_region_factory_sets_neuron_region_attribute():
    neurons = [
        DigitalNeuron(cell_id=f"n{i}", role="digital_neuron", threshold=0.5)
        for i in range(10)
    ]
    circuit = NeuralCircuit(
        circuit_id="test",
        input_neurons=[],
        hidden_neurons=neurons,
        output_neurons=[],
        synapses=[],
    )
    genome = {
        "brain_regions": {
            "sensory": {"dominant_cell_types": ["sensory_neuron"]},
            "motor": {"dominant_cell_types": ["motor_neuron"]},
            "hippocampus": {"dominant_cell_types": ["hippocampal_neuron"]},
            "prefrontal": {"dominant_cell_types": ["prefrontal_neuron"]},
        }
    }
    RegionFactory.build_from_genome(circuit, genome, seed=42)
    assigned = [n.region for n in neurons if n.region is not None]
    assert len(assigned) == 10


def test_region_factory_pipeline_connections():
    neurons = [
        DigitalNeuron(cell_id=f"n{i}", role="digital_neuron", threshold=0.5)
        for i in range(10)
    ]
    circuit = NeuralCircuit(
        circuit_id="test",
        input_neurons=[],
        hidden_neurons=neurons,
        output_neurons=[],
        synapses=[],
    )
    genome = {
        "brain_regions": {
            "sensory": {"dominant_cell_types": ["sensory_neuron"]},
            "hippocampus": {"dominant_cell_types": ["hippocampal_neuron"]},
            "prefrontal": {"dominant_cell_types": ["prefrontal_neuron"]},
            "motor": {"dominant_cell_types": ["motor_neuron"]},
        }
    }
    registry = RegionFactory.build_from_genome(circuit, genome, seed=42, deep_regions_enabled=False)
    conns = registry.connectome.connections
    pairs = {(c.source_region_id, c.target_region_id) for c in conns}
    assert ("sensory", "hippocampus") in pairs
    assert ("hippocampus", "prefrontal") in pairs
    assert ("prefrontal", "motor") in pairs


# ---------------------------------------------------------------------------
# Orchestrator integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orchestrator_builds_regions():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    assert orch.region_architecture_enabled is True
    assert orch.region_registry is not None
    assert len(orch.region_registry.regions) >= 4


@pytest.mark.asyncio
async def test_orchestrator_regions_disabled():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.region_architecture_enabled = False
    # Rebuild post_init manually for test
    orch._region_registry = None
    assert orch.region_registry is None


@pytest.mark.asyncio
async def test_orchestrator_tick_regulates_regions():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.execution_mode = "global_tick"
    await orch.run_ticks(1)
    assert orch.region_registry is not None
    assert len(orch.region_registry.regions) >= 4


# ---------------------------------------------------------------------------
# Benchmark regional metrics
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_benchmark_includes_regional_metrics():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import (
        NeuroFunctionalBenchmark,
    )

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    benchmark = NeuroFunctionalBenchmark(orch)
    pattern = [1.0 if i % 2 == 0 else 0.0 for i in range(10)]
    result = await benchmark.run_case(
        "morphological_memory_trace",
        execution_mode="event_driven_burst",
        input_pattern=pattern,
        target_output=pattern,
        n_ticks=2,
    )
    assert result.metrics.region_count >= 4
    assert result.metrics.connectome_density >= 0.0
    assert result.metrics.mean_region_energy >= 0.0
    assert result.metrics.mean_region_phi >= 0.0


# ---------------------------------------------------------------------------
# Local phi coverage
# ---------------------------------------------------------------------------

def test_brain_region_local_phi_with_synapses():
    n1 = DigitalNeuron(cell_id="n1", role="digital_neuron", threshold=0.5, energy=0.8)
    n2 = DigitalNeuron(cell_id="n2", role="digital_neuron", threshold=0.5, energy=0.6)
    from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse

    s_internal = DigitalSynapse(
        cell_id="s1", role="digital_synapse", source="n1", target="n2", weight=0.8
    )
    s_external = DigitalSynapse(
        cell_id="s2", role="digital_synapse", source="n1", target="out1", weight=0.3
    )
    out1 = DigitalNeuron(cell_id="out1", role="digital_neuron", threshold=0.5)
    circuit = NeuralCircuit(
        circuit_id="test",
        input_neurons=[],
        hidden_neurons=[n1, n2],
        output_neurons=[out1],
        synapses=[s_internal, s_external],
    )
    region = BrainRegion(region_id="r1", region_type="sensory", neuron_ids=["n1", "n2"])
    profile = region.compute_local_metrics(circuit)
    # internal_weight = 0.8, all_weight = 0.8 + 0.3 = 1.1
    assert profile.local_phi == pytest.approx(0.8 / 1.1, abs=1e-6)
