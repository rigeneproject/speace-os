import pytest

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regions.brain_region import BrainRegion
from speace_core.cellular_brain.regions.region_connectome import RegionConnectome, InterRegionConnection
from speace_core.cellular_brain.regions.region_registry import RegionRegistry
from speace_core.cellular_brain.regions.inter_region_plasticity import (
    InterRegionPlasticityEngine,
    RegionPathwayState,
    InterRegionPlasticityResult,
)
from speace_core.cellular_brain.regulation.homeostasis_engine import SystemMetrics


@pytest.fixture
def engine():
    return InterRegionPlasticityEngine(
        ltp_rate=0.05,
        ltd_rate=0.03,
        min_strength=0.0,
        max_strength=1.0,
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
# 1. Engine is importable and initializable
# ---------------------------------------------------------------------------

def test_engine_importable():
    assert InterRegionPlasticityEngine is not None


def test_engine_initializable(engine):
    assert engine.ltp_rate == 0.05
    assert engine.ltd_rate == 0.03


# ---------------------------------------------------------------------------
# 2. Compute region activation
# ---------------------------------------------------------------------------

def test_compute_region_activation_true(circuit):
    engine = InterRegionPlasticityEngine()
    circuit.hidden_neurons[0].activation = 1.0
    assert engine.compute_region_activation("hippocampus", circuit) is True


def test_compute_region_activation_false(circuit):
    engine = InterRegionPlasticityEngine()
    circuit.hidden_neurons[0].activation = 0.0
    assert engine.compute_region_activation("hippocampus", circuit) is False


# ---------------------------------------------------------------------------
# 3. Reinforce pathway when source precedes target
# ---------------------------------------------------------------------------

def test_apply_pathway_ltp(engine):
    pw = RegionPathwayState(source_region_id="a", target_region_id="b", pathway_strength=0.5)
    engine.apply_pathway_ltp(pw)
    assert pw.pathway_strength == pytest.approx(0.55)
    assert pw.ltp_events == 1


# ---------------------------------------------------------------------------
# 4. Weaken pathway when target precedes source
# ---------------------------------------------------------------------------

def test_apply_pathway_ltd(engine):
    pw = RegionPathwayState(source_region_id="a", target_region_id="b", pathway_strength=0.5)
    engine.apply_pathway_ltd(pw)
    assert pw.pathway_strength == pytest.approx(0.47)
    assert pw.ltd_events == 1


# ---------------------------------------------------------------------------
# 5. Clamp pathway_strength in [0,1]
# ---------------------------------------------------------------------------

def test_clamp_max(engine):
    pw = RegionPathwayState(source_region_id="a", target_region_id="b", pathway_strength=0.98)
    engine.apply_pathway_ltp(pw)
    assert pw.pathway_strength == 1.0


def test_clamp_min(engine):
    pw = RegionPathwayState(source_region_id="a", target_region_id="b", pathway_strength=0.02)
    engine.apply_pathway_ltd(pw)
    assert pw.pathway_strength == 0.0


# ---------------------------------------------------------------------------
# 6. Low energy reduces plasticity but does not zero it
# ---------------------------------------------------------------------------

def test_modulate_by_energy_low(engine):
    pw = RegionPathwayState(source_region_id="a", target_region_id="b")
    engine.modulate_by_energy(pw, 0.1)
    assert pw.plasticity_rate == pytest.approx(0.1)


def test_modulate_by_energy_normal(engine):
    pw = RegionPathwayState(source_region_id="a", target_region_id="b")
    engine.modulate_by_energy(pw, 0.5)
    assert pw.plasticity_rate == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 7. Confidence modulates plasticity
# ---------------------------------------------------------------------------

def test_modulate_by_confidence_high(engine):
    pw = RegionPathwayState(source_region_id="a", target_region_id="b")
    engine.modulate_by_confidence(pw, confidence_score=0.7, coherence_phi=0.3)
    assert pw.confidence_modulation == pytest.approx(0.7)
    assert pw.plasticity_rate == pytest.approx(0.7)


def test_modulate_by_confidence_low(engine):
    pw = RegionPathwayState(source_region_id="a", target_region_id="b")
    engine.modulate_by_confidence(pw, confidence_score=0.2, coherence_phi=0.1)
    assert pw.confidence_modulation == pytest.approx(1.3)
    assert pw.plasticity_rate == pytest.approx(1.3)


# ---------------------------------------------------------------------------
# 8. Records events in MorphologicalMemory
# ---------------------------------------------------------------------------

def test_update_pathways_records_events(engine, registry, circuit):
    mem = MorphologicalMemory()
    # Activate source before target
    for n in circuit.hidden_neurons + circuit.input_neurons + circuit.output_neurons:
        if getattr(n, "region", None) == "sensory":
            n.activation = 1.0
    result = engine.update_pathways(
        circuit=circuit,
        registry=registry,
        metrics=SystemMetrics(tick=1, mean_energy=0.5, coherence_phi=0.2),
        memory=mem,
        tick=2,
        confidence_score=0.5,
    )
    # At least one event should be recorded (inter_region_plasticity_applied)
    assert len(mem.events) > 0
    types = [e.event_type for e in mem.events]
    assert MorphologyEventType.INTER_REGION_PLASTICITY_APPLIED in types


# ---------------------------------------------------------------------------
# 9. Orchestrator integrates inter_region_plasticity_enabled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orchestrator_inter_region_plasticity_enabled():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    assert orch.inter_region_plasticity_enabled is True
    assert orch._inter_region_plasticity is not None


@pytest.mark.asyncio
async def test_orchestrator_inter_region_plasticity_disabled():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.inter_region_plasticity_enabled = False
    orch.execution_mode = "event_driven_burst"
    await orch.run_ticks(1)
    # Should run without error even when disabled
    assert orch.current_tick == 1


# ---------------------------------------------------------------------------
# 10. Benchmark includes pathway metrics
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_benchmark_includes_pathway_metrics():
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
    assert hasattr(m, "mean_pathway_strength")
    assert hasattr(m, "reinforced_pathways")
    assert hasattr(m, "weakened_pathways")


# ---------------------------------------------------------------------------
# 11. Audit remains compatible
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audit_compatible_with_inter_region_plasticity():
    from speace_core.cellular_brain.audit.integrated_neurocellular_audit import (
        IntegratedNeurocellularAudit,
        AuditConfiguration,
    )

    audit = IntegratedNeurocellularAudit()
    configs = audit.default_configurations()
    full = configs[-1]
    assert hasattr(full, "inter_region_plasticity_enabled")
    result = await audit.run_configuration(full)
    assert result.test_passed is True


# ---------------------------------------------------------------------------
# 12. Compute delta tick
# ---------------------------------------------------------------------------

def test_compute_delta_tick_within_window(engine):
    pw = RegionPathwayState(source_region_id="a", target_region_id="b")
    pw.last_source_activation_tick = 1
    pw.last_target_activation_tick = 2
    assert engine.compute_delta_tick(pw, tick=2) == 1


def test_compute_delta_tick_outside_window(engine):
    pw = RegionPathwayState(source_region_id="a", target_region_id="b")
    pw.last_source_activation_tick = 1
    pw.last_target_activation_tick = 5
    assert engine.compute_delta_tick(pw, tick=5) is None


# ---------------------------------------------------------------------------
# 13. Isolated region compensatory strengthening
# ---------------------------------------------------------------------------

def test_isolated_region_compensatory_strengthening(engine, registry):
    reg = RegionRegistry()
    reg.register(BrainRegion("iso", "iso", ["n_iso"], ["iso_neuron"]))
    reg.connectome.add_connection("iso", "sensory", strength=0.2, plasticity_enabled=True)
    assert engine._is_isolated_region("iso", reg) is True
