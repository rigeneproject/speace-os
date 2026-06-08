import copy
import pytest
import random

from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import (
    BenchmarkMetrics,
    BenchmarkResult,
    BenchmarkState,
)
from speace_core.cellular_brain.evolution.genome_database import GenomeDatabase, GenomeRecord
from speace_core.cellular_brain.evolution.evolution_engine import EvolutionEngine, FitnessResult
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType


@pytest.fixture
def db(tmp_path):
    return GenomeDatabase(base_path=str(tmp_path / "evolution"))


@pytest.fixture
def engine(db):
    return EvolutionEngine(
        genome_database=db,
        mutation_rate=1.0,  # force mutation for testing
        mutation_strength=0.20,
        crossover_rate=0.5,
        elite_fraction=0.2,
    )


@pytest.fixture
def sample_genome():
    return {
        "identity": {"entity_name": "test"},
        "homeostasis": {
            "default_threshold": 0.5,
            "default_plasticity_rate": 0.05,
            "overload_threshold": 0.85,
            "noise_suppression_rate": 0.2,
            "energy_recovery_rate": 0.01,
        },
        "immune": {
            "prune_threshold": 0.1,
            "quarantine_error_limit": 10,
            "myelination_success_threshold": 0.8,
            "latency_reduction": 0.3,
        },
    }


@pytest.fixture
def sample_benchmark_result():
    baseline = BenchmarkState(neuron_count=10, synapse_count=50)
    final = BenchmarkState(
        neuron_count=12,
        synapse_count=55,
        coherence_phi=0.6,
        mean_energy=0.7,
        accuracy=0.8,
    )
    metrics = BenchmarkMetrics(
        accuracy_score=0.8,
        coherence_phi=0.6,
        energy_efficiency=0.7,
        morphological_stability=0.9,
        functional_improvement=0.4,
        speace_cognitive_score=0.75,
        modularity_proxy=0.5,
    )
    return BenchmarkResult(
        case_name="test",
        baseline_state=baseline,
        final_state=final,
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# Fitness
# ---------------------------------------------------------------------------

def test_compute_fitness_in_range(engine, sample_benchmark_result):
    fitness = engine.compute_fitness(sample_benchmark_result)
    assert isinstance(fitness, FitnessResult)
    assert 0.0 <= fitness.fitness_score <= 1.0


def test_compute_fitness_components(engine, sample_benchmark_result):
    fitness = engine.compute_fitness(sample_benchmark_result)
    assert fitness.accuracy_score == 0.8
    assert fitness.coherence_phi == 0.6
    assert fitness.energy_efficiency == 0.7


# ---------------------------------------------------------------------------
# Mutation
# ---------------------------------------------------------------------------

def test_mutate_genome_changes_mutable_gene(engine, sample_genome):
    mutated = engine.mutate_genome(sample_genome, strength=0.30)
    changed = False
    for path in engine.MUTABLE_GENE_PATHS:
        keys = path.split(".")
        old_node = sample_genome
        new_node = mutated
        for key in keys[:-1]:
            old_node = old_node[key]
            new_node = new_node[key]
        if old_node[keys[-1]] != new_node[keys[-1]]:
            changed = True
            break
    assert changed


def test_mutate_genome_preserves_identity(engine, sample_genome):
    mutated = engine.mutate_genome(sample_genome, strength=0.30)
    assert mutated["identity"] == sample_genome["identity"]


def test_mutate_genome_clamps_rates(engine, sample_genome):
    # Force extreme mutation
    mutated = engine.mutate_genome(sample_genome, strength=1.0)
    homeostasis = mutated["homeostasis"]
    assert 0.0 <= homeostasis["default_threshold"] <= 1.0
    assert 0.0 <= homeostasis["default_plasticity_rate"] <= 1.0


def test_mutate_genome_clamps_counts(engine, sample_genome):
    mutated = engine.mutate_genome(sample_genome, strength=1.0)
    immune = mutated["immune"]
    assert immune["quarantine_error_limit"] >= 1


# ---------------------------------------------------------------------------
# Crossover
# ---------------------------------------------------------------------------

def test_crossover_combines_parents(engine, sample_genome):
    parent_b = copy.deepcopy(sample_genome)
    parent_b["homeostasis"]["default_threshold"] = 0.9
    child = engine.crossover_genomes(sample_genome, parent_b)
    # Child should have homeostasis present
    assert "homeostasis" in child
    # Value should be between or equal to one parent
    val = child["homeostasis"]["default_threshold"]
    assert val in {0.5, 0.9, 0.7}


def test_crossover_preserves_non_mutable(engine, sample_genome):
    parent_b = copy.deepcopy(sample_genome)
    parent_b["identity"] = {"entity_name": "other"}
    child = engine.crossover_genomes(sample_genome, parent_b)
    # Crossover only touches mutable paths; identity should remain from parent_a
    assert child["identity"] == sample_genome["identity"]


# ---------------------------------------------------------------------------
# Adaptive strength
# ---------------------------------------------------------------------------

def test_adaptive_strength_critical(engine):
    assert engine.adaptive_strength(0.40) == 0.30


def test_adaptive_strength_medium(engine):
    assert engine.adaptive_strength(0.60) == 0.10


def test_adaptive_strength_high(engine):
    assert engine.adaptive_strength(0.85) == 0.05


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def test_select_parents_top_k(engine, sample_genome):
    records = [
        GenomeRecord(genome_id="a", generation=0, genome=sample_genome, created_at="", fitness_score=0.2),
        GenomeRecord(genome_id="b", generation=0, genome=sample_genome, created_at="", fitness_score=0.8),
        GenomeRecord(genome_id="c", generation=0, genome=sample_genome, created_at="", fitness_score=0.5),
    ]
    selected = engine.select_parents(records, strategy="top_k", k=2)
    assert len(selected) == 2
    assert selected[0].genome_id == "b"
    assert selected[1].genome_id == "c"


def test_select_parents_falls_back_when_no_fitness(engine, sample_genome):
    records = [
        GenomeRecord(genome_id="a", generation=0, genome=sample_genome, created_at=""),
        GenomeRecord(genome_id="b", generation=0, genome=sample_genome, created_at=""),
    ]
    selected = engine.select_parents(records, strategy="top_k", k=2)
    assert len(selected) == 2


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_validate_genome_safety_valid(engine, sample_genome):
    assert engine.validate_genome_safety(sample_genome) is True


def test_validate_genome_safety_rejects_zero_threshold(engine, sample_genome):
    bad = copy.deepcopy(sample_genome)
    bad["homeostasis"]["default_threshold"] = 0.0
    assert engine.validate_genome_safety(bad) is False


def test_validate_genome_safety_rejects_negative_prune(engine, sample_genome):
    bad = copy.deepcopy(sample_genome)
    bad["immune"]["prune_threshold"] = -0.1
    assert engine.validate_genome_safety(bad) is False


def test_validate_genome_safety_rejects_overload_above_max(engine, sample_genome):
    bad = copy.deepcopy(sample_genome)
    bad["homeostasis"]["overload_threshold"] = 1.5
    assert engine.validate_genome_safety(bad) is False


# ---------------------------------------------------------------------------
# Candidate generation
# ---------------------------------------------------------------------------

def test_create_candidate_generation_with_parent_ids(engine, sample_genome):
    parent = GenomeRecord(
        genome_id="parent_1", generation=0, genome=sample_genome, created_at="", fitness_score=0.6
    )
    candidates = engine.create_candidate_generation([parent], n_candidates=3, generation=1)
    assert len(candidates) == 3
    for c in candidates:
        assert c.parent_ids == ["parent_1"]
        assert c.generation == 1


def test_create_candidate_generation_records_events(engine, sample_genome):
    mem = MorphologicalMemory()
    parent = GenomeRecord(
        genome_id="parent_1", generation=0, genome=sample_genome, created_at="", fitness_score=0.6
    )
    engine.create_candidate_generation([parent], n_candidates=2, generation=1, memory=mem)
    events = [e for e in mem.events if e.event_type in {
        MorphologyEventType.GENOME_MUTATED,
        MorphologyEventType.GENOME_CROSSED,
    }]
    assert len(events) >= 1


# ---------------------------------------------------------------------------
# Evolution step
# ---------------------------------------------------------------------------

def test_run_evolution_step_saves_run_record(engine, sample_genome):
    parent = GenomeRecord(
        genome_id="parent_1", generation=0, genome=sample_genome, created_at="", fitness_score=0.6
    )
    run = engine.run_evolution_step([parent], generation=1, n_candidates=3)
    assert run is not None
    assert run.generation == 1
    assert len(run.candidate_genome_ids) == 3
    runs = engine.db.list_evolution_runs()
    assert len(runs) >= 1


def test_run_evolution_step_with_benchmark_results(engine, sample_genome, sample_benchmark_result):
    parent = GenomeRecord(
        genome_id="parent_1", generation=0, genome=sample_genome, created_at="", fitness_score=0.6
    )
    candidates = engine.create_candidate_generation([parent], n_candidates=2, generation=1)
    benchmark_results = {candidates[0].genome_id: sample_benchmark_result}
    run = engine.run_evolution_step(
        [parent],
        benchmark_results=benchmark_results,
        generation=1,
        n_candidates=2,
        candidate_records=candidates,
    )
    assert run.best_genome_id is not None
    assert run.best_fitness is not None
    assert 0.0 <= run.best_fitness <= 1.0


# ---------------------------------------------------------------------------
# Integration: evaluate_genome
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_evaluate_genome_runs_benchmark(engine, sample_genome):
    record = GenomeRecord(
        genome_id="test_gen", generation=0, genome=sample_genome, created_at=""
    )
    result = await engine.evaluate_genome(record, benchmark_case="adaptation_after_error", n_ticks=2)
    assert isinstance(result, BenchmarkResult)
    assert result.case_name == "adaptation_after_error"
    assert result.metrics.speace_cognitive_score >= 0.0


