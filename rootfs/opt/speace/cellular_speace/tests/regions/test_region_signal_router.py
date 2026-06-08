import pytest

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regions.brain_region import BrainRegion
from speace_core.cellular_brain.regions.region_connectome import RegionConnectome
from speace_core.cellular_brain.regions.region_registry import RegionRegistry
from speace_core.cellular_brain.regions.region_signal_router import (
    RegionSignalRouter,
    RegionSignal,
    RegionRoutingResult,
)
from speace_core.cellular_brain.regulation.homeostasis_engine import SystemMetrics


@pytest.fixture
def router():
    return RegionSignalRouter(
        min_source_activation=0.05,
        min_pathway_strength=0.01,
        signal_gain=1.0,
        energy_cost_per_signal=0.001,
        max_signals_per_tick=16,
    )


@pytest.fixture
def registry():
    reg = RegionRegistry()
    reg.register(BrainRegion("sensory", "sensory", ["n1"], ["sensory_neuron"]))
    reg.register(BrainRegion("hippocampus", "hippocampus", ["n2"], ["hippocampal_neuron"]))
    reg.register(BrainRegion("prefrontal", "prefrontal", ["n3"], ["prefrontal_neuron"]))
    reg.connectome.add_connection("sensory", "hippocampus", strength=0.5, plasticity_enabled=True)
    reg.connectome.add_connection("hippocampus", "prefrontal", strength=0.5, plasticity_enabled=True)
    return reg


@pytest.fixture
def circuit():
    n1 = DigitalNeuron(cell_id="n1", role="digital_neuron", threshold=0.5)
    n1.region = "sensory"
    n2 = DigitalNeuron(cell_id="n2", role="digital_neuron", threshold=0.5)
    n2.region = "hippocampus"
    n3 = DigitalNeuron(cell_id="n3", role="digital_neuron", threshold=0.5)
    n3.region = "prefrontal"
    return NeuralCircuit(
        circuit_id="test",
        input_neurons=[n1],
        hidden_neurons=[n2],
        output_neurons=[n3],
    )


# ---------------------------------------------------------------------------
# 1. RegionSignalRouter importabile
# ---------------------------------------------------------------------------

def test_router_importable():
    assert RegionSignalRouter is not None
    assert RegionSignal is not None
    assert RegionRoutingResult is not None


# ---------------------------------------------------------------------------
# 2. compute_soft_region_activation restituisce valore > 0 con attivazioni deboli
# ---------------------------------------------------------------------------

def test_soft_activation_positive_with_weak_activations(router, circuit):
    circuit.input_neurons[0].activation = 0.1
    score = router.compute_soft_region_activation("sensory", circuit)
    assert score > 0.0


def test_soft_activation_zero_when_no_neurons(router, circuit):
    score = router.compute_soft_region_activation("nonexistent", circuit)
    assert score == 0.0


# ---------------------------------------------------------------------------
# 3. route_all produce segnali quando source_activation è bassa ma non nulla
# ---------------------------------------------------------------------------

def test_route_all_produces_signals_with_low_activation(router, registry, circuit):
    circuit.input_neurons[0].activation = 0.1  # weak but above min_source_activation=0.05
    mem = MorphologicalMemory()
    metrics = SystemMetrics(tick=1, mean_energy=0.5, coherence_phi=0.2)
    result = router.route_all(
        region_connectome=registry.connectome,
        circuit=circuit,
        metrics=metrics,
        memory=mem,
    )
    assert result.routed_signals > 0
    assert result.delivered_signals > 0


# ---------------------------------------------------------------------------
# 4. route_all non produce segnali se pathway_strength = 0
# ---------------------------------------------------------------------------

def test_route_all_no_signals_when_pathway_zero(router, registry, circuit):
    circuit.input_neurons[0].activation = 1.0
    # Override connection strength to 0
    for c in registry.connectome.connections:
        c.strength = 0.0
    mem = MorphologicalMemory()
    metrics = SystemMetrics(tick=1, mean_energy=0.5, coherence_phi=0.2)
    result = router.route_all(
        region_connectome=registry.connectome,
        circuit=circuit,
        metrics=metrics,
        memory=mem,
    )
    assert result.routed_signals == 0
    assert result.delivered_signals == 0


# ---------------------------------------------------------------------------
# 5. route_signal aumenta l'attivazione della regione target
# ---------------------------------------------------------------------------

def test_route_signal_increases_target_activation(router, circuit):
    before = circuit.hidden_neurons[0].activation
    signal = RegionSignal(
        source_region_id="sensory",
        target_region_id="hippocampus",
        signal_strength=0.5,
        pathway_strength=0.5,
        energy_cost=0.001,
    )
    delivered = router.route_signal(signal, "hippocampus", circuit)
    assert delivered is True
    assert circuit.hidden_neurons[0].activation > before


# ---------------------------------------------------------------------------
# 6. energy_cost viene calcolato
# ---------------------------------------------------------------------------

def test_energy_cost_computed(router, registry, circuit):
    circuit.input_neurons[0].activation = 1.0
    mem = MorphologicalMemory()
    metrics = SystemMetrics(tick=1, mean_energy=0.5, coherence_phi=0.2)
    result = router.route_all(
        region_connectome=registry.connectome,
        circuit=circuit,
        metrics=metrics,
        memory=mem,
    )
    assert result.total_energy_cost > 0.0


# ---------------------------------------------------------------------------
# 7. max_signals_per_tick viene rispettato
# ---------------------------------------------------------------------------

def test_max_signals_per_tick_respected(router, registry, circuit):
    router.max_signals_per_tick = 1
    circuit.input_neurons[0].activation = 1.0
    circuit.hidden_neurons[0].activation = 1.0
    mem = MorphologicalMemory()
    metrics = SystemMetrics(tick=1, mean_energy=0.5, coherence_phi=0.2)
    result = router.route_all(
        region_connectome=registry.connectome,
        circuit=circuit,
        metrics=metrics,
        memory=mem,
    )
    assert result.routed_signals <= 1


# ---------------------------------------------------------------------------
# 8. eventi REGION_SIGNAL_ROUTED / DELIVERED vengono registrati
# ---------------------------------------------------------------------------

def test_events_recorded(router, registry, circuit):
    circuit.input_neurons[0].activation = 1.0
    mem = MorphologicalMemory()
    metrics = SystemMetrics(tick=1, mean_energy=0.5, coherence_phi=0.2)
    router.route_all(
        region_connectome=registry.connectome,
        circuit=circuit,
        metrics=metrics,
        memory=mem,
    )
    types = [e.event_type for e in mem.events]
    assert MorphologyEventType.REGION_SIGNAL_ROUTED in types
    assert MorphologyEventType.REGION_SIGNAL_DELIVERED in types


# ---------------------------------------------------------------------------
# 9. orchestrator integra region_signal_routing_enabled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orchestrator_integrates_routing_enabled():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    assert orch.region_signal_routing_enabled is True
    assert orch._region_signal_router is not None


@pytest.mark.asyncio
async def test_orchestrator_routing_disabled():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.region_signal_routing_enabled = False
    orch.execution_mode = "event_driven_burst"
    await orch.run_ticks(1)
    assert orch.current_tick == 1
    assert orch.last_routing_result is None


# ---------------------------------------------------------------------------
# 10. benchmark include metriche routing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_benchmark_includes_routing_metrics():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import NeuroFunctionalBenchmark

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    bench = NeuroFunctionalBenchmark(orch)
    result = await bench.run_case(
        "morphological_memory_trace",
        execution_mode="event_driven_burst",
        n_ticks=3,
    )
    m = result.metrics
    assert hasattr(m, "routed_signals")
    assert hasattr(m, "delivered_signals")
    assert hasattr(m, "blocked_signals")
    assert hasattr(m, "routing_energy_cost")
    assert hasattr(m, "active_inter_region_pathways")


# ---------------------------------------------------------------------------
# 11. T24 può generare regional_signal_flow_score > 0 con routing attivo
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_regional_signal_flow_score_positive_with_routing():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import NeuroFunctionalBenchmark

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    bench = NeuroFunctionalBenchmark(orch)
    result = await bench.run_case(
        "morphological_memory_trace",
        execution_mode="event_driven_burst",
        n_ticks=5,
        region_signal_routing_enabled=True,
    )
    # With routing enabled, at least one signal should be routed in the benchmark
    assert result.metrics.routed_signals > 0
    assert result.metrics.regional_signal_flow_score >= 0.0


# ---------------------------------------------------------------------------
# 12. compute_regional_signal_flow_score in [0, 1]
# ---------------------------------------------------------------------------

def test_signal_flow_score_range():
    result = RegionRoutingResult(routed_signals=10, delivered_signals=5, mean_signal_strength=0.5)
    score = RegionSignalRouter.compute_regional_signal_flow_score(result)
    assert 0.0 <= score <= 1.0


def test_signal_flow_score_zero_when_no_routing():
    result = RegionRoutingResult()
    score = RegionSignalRouter.compute_regional_signal_flow_score(result)
    assert score == 0.0


# ---------------------------------------------------------------------------
# 13. T35 — Homeostatic activation clamp
# ---------------------------------------------------------------------------

def test_router_clamps_max_activation_after_routing(router, registry, circuit):
    circuit.input_neurons[0].activation = 10.0
    circuit.hidden_neurons[0].activation = 10.0
    mem = MorphologicalMemory()
    metrics = SystemMetrics(tick=1, mean_energy=0.5, coherence_phi=0.2)
    router.route_all(
        region_connectome=registry.connectome,
        circuit=circuit,
        metrics=metrics,
        memory=mem,
    )
    assert abs(circuit.input_neurons[0].activation) <= RegionSignalRouter.MAX_REGION_NEURON_ACTIVATION
    assert abs(circuit.hidden_neurons[0].activation) <= RegionSignalRouter.MAX_REGION_NEURON_ACTIVATION


def test_router_clamps_mean_activation_after_routing(router, registry, circuit):
    # Two neurons in hippocampus with activation 2.0 each -> mean 2.0 > 1.0
    circuit.hidden_neurons[0].activation = 2.0
    n4 = DigitalNeuron(cell_id="n4", role="digital_neuron", threshold=0.5)
    n4.region = "hippocampus"
    n4.activation = 2.0
    circuit.hidden_neurons.append(n4)
    mem = MorphologicalMemory()
    metrics = SystemMetrics(tick=1, mean_energy=0.5, coherence_phi=0.2)
    router.route_all(
        region_connectome=registry.connectome,
        circuit=circuit,
        metrics=metrics,
        memory=mem,
    )
    # After clamp, mean should be scaled down to ~1.0
    acts = [n.activation for n in circuit.hidden_neurons if getattr(n, "region", None) == "hippocampus"]
    mean_act = sum(abs(a) for a in acts) / len(acts)
    assert mean_act <= RegionSignalRouter.MAX_MEAN_REGION_ACTIVATION + 0.01


def test_router_records_clamp_event(router, registry, circuit):
    circuit.hidden_neurons[0].activation = 10.0
    mem = MorphologicalMemory()
    metrics = SystemMetrics(tick=1, mean_energy=0.5, coherence_phi=0.2)
    router.route_all(
        region_connectome=registry.connectome,
        circuit=circuit,
        metrics=metrics,
        memory=mem,
    )
    types = [e.event_type for e in mem.events]
    assert MorphologyEventType.REGION_ACTIVATION_CLAMPED in types
