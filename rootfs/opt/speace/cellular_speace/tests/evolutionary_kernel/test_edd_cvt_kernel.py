import json
import pytest

from speace_core.cellular_brain.evolutionary_kernel import (
    DigitalDNAExpressionManager,
    EDDCVTEvolutionaryKernel,
    EntropyDynamicsMonitor,
    EvolutionPhase,
    PerturbationField,
)
from speace_core.cellular_brain.evolutionary_kernel.digital_dna_expression_manager import (
    DigitalDNAVariant,
)
from speace_core.cellular_brain.evolutionary_kernel.entropy_dynamics_monitor import (
    EntropySnapshot,
)
from speace_core.cellular_brain.evolutionary_kernel.evolutionary_cycle_models import (
    EvolutionCycleResult,
    EvolutionCycleState,
)
from speace_core.cellular_brain.evolutionary_kernel.perturbation_field import (
    PerturbationPulse,
)
from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator


@pytest.fixture
def orchestrator():
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.region_signal_routing_enabled = False
    orch.brainstem_controller_enabled = False
    orch.region_stability_controller_enabled = False
    orch.perturbation_recovery_audit_enabled = False
    orch.edd_cvt_kernel_enabled = False
    return orch


@pytest.fixture
def kernel(orchestrator):
    return EDDCVTEvolutionaryKernel(
        orchestrator=orchestrator,
        enabled=False,
        cycle_interval_ticks=1,
        max_variants_per_cycle=2,
        safety_threshold=0.0,
    )


# ------------------------------------------------------------------ #
# EntropyDynamicsMonitor
# ------------------------------------------------------------------ #

def test_entropy_snapshot_defaults():
    s = EntropySnapshot(tick=1)
    assert s.total_entropy == 0.0


def test_shannon_entropy_uniform():
    m = EntropyDynamicsMonitor()
    e = m._shannon_entropy([1.0, 1.0, 1.0, 1.0])
    assert e > 0.0


def test_shannon_entropy_zero():
    m = EntropyDynamicsMonitor()
    assert m._shannon_entropy([0.0, 0.0]) == 0.0


def test_compute_informational_entropy():
    m = EntropyDynamicsMonitor()
    e = m.compute_informational_entropy(activations=[0.2, 0.8])
    assert e >= 0.0


def test_compute_total_entropy():
    m = EntropyDynamicsMonitor()
    t = m.compute_total_entropy(1.0, 2.0, alpha=1.0, beta=0.5)
    assert t == 2.0


def test_capture_appends_history():
    m = EntropyDynamicsMonitor(history_window=5)
    m.capture(tick=1, activations=[0.1, 0.9], energies=[0.5, 0.5], mean_energy=0.5)
    assert len(m._history) == 1


def test_history_window_eviction():
    m = EntropyDynamicsMonitor(history_window=2)
    m.capture(tick=1, activations=[0.1])
    m.capture(tick=2, activations=[0.2])
    m.capture(tick=3, activations=[0.3])
    assert len(m._history) == 2
    assert m._history[0].tick == 2


def test_entropy_derivative_requires_history():
    m = EntropyDynamicsMonitor()
    assert m.entropy_derivative() == 0.0


def test_should_mutate_when_low_derivative():
    m = EntropyDynamicsMonitor()
    m.capture(tick=1, activations=[0.5], energies=[0.5], mean_energy=0.5)
    m.capture(tick=2, activations=[0.5], energies=[0.5], mean_energy=0.5)
    assert m.should_mutate(threshold=0.01) is True


def test_summarize_empty():
    m = EntropyDynamicsMonitor()
    s = m.summarize()
    assert s["total_entropy"] == 0.0


# ------------------------------------------------------------------ #
# PerturbationField
# ------------------------------------------------------------------ #

def test_pulse_defaults():
    p = PerturbationPulse(pulse_id="p1", target_type="activation")
    assert p.strength == 0.0


def test_generate_pulse_selects_targets():
    f = PerturbationField()
    pulse = f.generate_pulse("activation", ["n1", "n2", "n3"], top_k=2)
    assert len(pulse.target_ids) == 2


def test_generate_field_pulse_batch():
    f = PerturbationField()
    pulses = f.generate_field_pulse_batch(
        neuron_ids=["n1", "n2", "n3", "n4"],
        synapse_ids=["s1", "s2"],
        strength=0.2,
    )
    assert len(pulses) == 3


def test_adaptive_strength_increases_on_stagnation():
    f = PerturbationField(base_strength=0.2)
    s = f.adaptive_strength(entropy_delta=-0.1, fitness_delta=-0.1)
    assert s > 0.2


def test_adaptive_strength_decreases_on_progress():
    f = PerturbationField(base_strength=0.2)
    s = f.adaptive_strength(entropy_delta=0.2, fitness_delta=0.2)
    assert s < 0.2


def test_apply_pulse_activation():
    class FakeNeuron:
        cell_id = "n1"
        activation = 0.0
        energy = 1.0

    n = FakeNeuron()
    p = PerturbationPulse(pulse_id="p1", target_type="activation", strength=0.5, target_ids=["n1"])
    PerturbationField.apply_pulse(p, neurons=[n])
    assert n.activation == 0.5


def test_apply_pulse_energy():
    class FakeNeuron:
        cell_id = "n1"
        activation = 0.0
        energy = 1.0

    n = FakeNeuron()
    p = PerturbationPulse(pulse_id="p1", target_type="energy", strength=0.3, target_ids=["n1"])
    PerturbationField.apply_pulse(p, neurons=[n])
    assert n.energy == 0.7


# ------------------------------------------------------------------ #
# DigitalDNAExpressionManager
# ------------------------------------------------------------------ #

def test_variant_defaults():
    v = DigitalDNAVariant()
    assert v.fitness_score == 0.0
    assert v.variant_id.startswith("ddna_")


def test_create_variant_inherits_parent():
    mgr = DigitalDNAExpressionManager()
    parent = DigitalDNAVariant(mutation_rate=1.5)
    child = mgr.create_variant(parent=parent, parameter_changes={"routing_gain": 2.0})
    assert child.parent_id == parent.variant_id
    assert child.generation == parent.generation + 1
    assert child.routing_gain == 2.0


def test_mutate_variant_changes_params():
    mgr = DigitalDNAExpressionManager()
    v = mgr.create_variant()
    mutated = mgr.mutate_variant(v, mutation_sigma=0.5)
    assert mutated.parent_id == v.variant_id


def test_crossover_variants():
    mgr = DigitalDNAExpressionManager()
    a = mgr.create_variant(parameter_changes={"routing_gain": 1.0})
    b = mgr.create_variant(parameter_changes={"routing_gain": 2.0})
    c = mgr.crossover_variants(a, b)
    assert c.routing_gain in (1.0, 2.0)


def test_evaluate_fitness():
    mgr = DigitalDNAExpressionManager()
    v = mgr.create_variant()
    f = mgr.evaluate_fitness(v, coherence_phi=0.8, mean_energy=0.7, cognitive_score=0.6)
    assert f > 0.0
    assert v.fitness_score == f


def test_select_best_variant():
    mgr = DigitalDNAExpressionManager()
    v1 = mgr.create_variant(parameter_changes={"fitness_score": 0.5})
    v1.fitness_score = 0.5
    v2 = mgr.create_variant(parameter_changes={"fitness_score": 0.9})
    v2.fitness_score = 0.9
    best = mgr.select_best_variant()
    assert best is not None
    assert best.fitness_score == 0.9


def test_express():
    mgr = DigitalDNAExpressionManager()
    v = mgr.create_variant(parameter_changes={"routing_gain": 1.2})
    params = mgr.express(v)
    assert params["routing_gain"] == 1.2


def test_save_and_load_variants(tmp_path):
    mgr = DigitalDNAExpressionManager(report_dir=str(tmp_path))
    mgr.create_variant(parameter_changes={"routing_gain": 1.2})
    path = mgr.save_variants()
    assert path.exists()
    mgr2 = DigitalDNAExpressionManager(report_dir=str(tmp_path))
    mgr2.load_variants(path)
    assert len(mgr2._variants) == 1


# ------------------------------------------------------------------ #
# EDDCVTEvolutionaryKernel
# ------------------------------------------------------------------ #

def test_kernel_disabled_returns_none(kernel):
    assert kernel.enabled is False


@pytest.mark.asyncio
async def test_run_cycle_disabled(kernel):
    kernel.enabled = False
    result = await kernel.run_cycle(tick=1)
    assert result is None


@pytest.mark.asyncio
async def test_run_cycle_enabled(kernel, orchestrator):
    kernel.enabled = True
    result = await kernel.run_cycle(tick=1)
    assert isinstance(result, EvolutionCycleResult)
    assert result.cycle_number == 1


@pytest.mark.asyncio
async def test_run_cycle_phases_present(kernel, orchestrator):
    kernel.enabled = True
    result = await kernel.run_cycle(tick=1)
    assert EvolutionPhase.EXPLORATION in result.phases_completed
    assert EvolutionPhase.SELECTION in result.phases_completed
    assert EvolutionPhase.FEEDBACK in result.phases_completed
    assert EvolutionPhase.RECONFIGURATION in result.phases_completed


@pytest.mark.asyncio
async def test_run_cycle_metrics_updated(kernel, orchestrator):
    kernel.enabled = True
    result = await kernel.run_cycle(tick=1)
    metrics = kernel.get_metrics()
    assert metrics.total_cycles == 1
    if result.success:
        assert metrics.current_phase == EvolutionPhase.RECONFIGURATION
    else:
        assert metrics.current_phase in (EvolutionPhase.SELECTION, EvolutionPhase.RECONFIGURATION)


@pytest.mark.asyncio
async def test_run_cycle_logs_events(kernel, orchestrator):
    kernel.enabled = True
    before = len(orchestrator.memory.events)
    await kernel.run_cycle(tick=1)
    after = len(orchestrator.memory.events)
    assert after >= before


@pytest.mark.asyncio
async def test_run_cycle_safety_blocks_low_fitness(kernel, orchestrator):
    kernel.enabled = True
    kernel.safety_threshold = 1.0  # Impossibly high
    result = await kernel.run_cycle(tick=1)
    assert result.reconfiguration_applied is False


@pytest.mark.asyncio
async def test_tick_respects_interval(kernel, orchestrator):
    kernel.enabled = True
    kernel.cycle_interval_ticks = 5
    r1 = await kernel.tick(tick=5)
    assert r1 is not None
    r2 = await kernel.tick(tick=6)
    assert r2 is None
    r3 = await kernel.tick(tick=10)
    assert r3 is not None


@pytest.mark.asyncio
async def test_generate_json_report(kernel, orchestrator):
    kernel.enabled = True
    await kernel.run_cycle(tick=1)
    path = kernel.generate_json_report()
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["total_cycles"] == 1


@pytest.mark.asyncio
async def test_generate_markdown_report(kernel, orchestrator):
    kernel.enabled = True
    await kernel.run_cycle(tick=1)
    path = kernel.generate_markdown_report()
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "EDD-CVT" in text


# ------------------------------------------------------------------ #
# Orchestrator hook
# ------------------------------------------------------------------ #

def test_orchestrator_get_kernel_lazy(orchestrator):
    orchestrator.edd_cvt_kernel_enabled = True
    k = orchestrator.get_edd_cvt_kernel()
    assert k is not None
    assert orchestrator._edd_cvt_kernel is k


@pytest.mark.asyncio
async def test_orchestrator_run_cycle_disabled(orchestrator):
    orchestrator.edd_cvt_kernel_enabled = False
    result = await orchestrator.run_edd_cvt_cycle()
    assert result is None


@pytest.mark.asyncio
async def test_orchestrator_run_cycle_enabled(orchestrator):
    orchestrator.edd_cvt_kernel_enabled = True
    result = await orchestrator.run_edd_cvt_cycle()
    assert isinstance(result, EvolutionCycleResult)
