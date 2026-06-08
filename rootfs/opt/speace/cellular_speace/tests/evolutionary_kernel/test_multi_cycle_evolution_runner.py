import json
import pytest

from speace_core.cellular_brain.evolutionary_kernel.multi_cycle_evolution_runner import (
    ConsolidatedMemory,
    CycleMemoryEntry,
    MultiCycleEvolutionResult,
    MultiCycleEvolutionRunner,
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
def runner(orchestrator):
    return MultiCycleEvolutionRunner(
        orchestrator=orchestrator,
        cycle_count=2,
        cycle_interval_ticks=1,
        max_variants_per_cycle=1,
        safety_threshold=0.0,
    )


# ------------------------------------------------------------------ #
# Model validation
# ------------------------------------------------------------------ #

def test_cycle_memory_entry_defaults():
    e = CycleMemoryEntry(cycle_number=1, generation_id="g1")
    assert e.fitness_score == 0.0


def test_consolidated_memory_defaults():
    c = ConsolidatedMemory()
    assert c.total_cycles == 0
    assert c.recovery_pattern_found is False


def test_multi_cycle_result_defaults():
    r = MultiCycleEvolutionResult()
    assert r.cumulative_learning_score == 0.0
    assert r.verdict == ""


# ------------------------------------------------------------------ #
# Consolidation
# ------------------------------------------------------------------ #

def test_consolidate_empty():
    runner = MultiCycleEvolutionRunner(orchestrator=None, cycle_count=0)
    c = runner._consolidate([])
    assert c.total_cycles == 0


def test_consolidate_basic():
    runner = MultiCycleEvolutionRunner(orchestrator=None, cycle_count=0)
    entries = [
        CycleMemoryEntry(cycle_number=1, generation_id="g1", fitness_score=0.5),
        CycleMemoryEntry(cycle_number=2, generation_id="g2", fitness_score=0.7),
    ]
    c = runner._consolidate(entries)
    assert c.total_cycles == 2
    assert c.mean_fitness_score == 0.6
    assert c.best_fitness_score == 0.7
    assert c.best_cycle_number == 2
    assert c.worst_fitness_score == 0.5


def test_consolidate_detects_recovery():
    runner = MultiCycleEvolutionRunner(orchestrator=None, cycle_count=0)
    entries = [
        CycleMemoryEntry(cycle_number=1, generation_id="g1", fitness_score=0.5),
        CycleMemoryEntry(cycle_number=2, generation_id="g2", fitness_score=0.6, rollback_triggered=False),
    ]
    c = runner._consolidate(entries)
    assert c.recovery_pattern_found is True


def test_consolidate_detects_regression():
    runner = MultiCycleEvolutionRunner(orchestrator=None, cycle_count=0)
    entries = [
        CycleMemoryEntry(cycle_number=1, generation_id="g1", fitness_score=0.6),
        CycleMemoryEntry(cycle_number=2, generation_id="g2", fitness_score=0.5),
    ]
    c = runner._consolidate(entries)
    assert c.regression_pattern_found is True


def test_consolidate_parameter_trend():
    runner = MultiCycleEvolutionRunner(orchestrator=None, cycle_count=0)
    entries = [
        CycleMemoryEntry(cycle_number=1, generation_id="g1", parameter_state={"a": 1.0}),
        CycleMemoryEntry(cycle_number=2, generation_id="g2", parameter_state={"a": 1.2}),
    ]
    c = runner._consolidate(entries)
    assert c.parameter_trend.get("a") == [1.0, 1.2]


# ------------------------------------------------------------------ #
# Learning score
# ------------------------------------------------------------------ #

def test_learning_score_empty():
    c = ConsolidatedMemory()
    assert MultiCycleEvolutionRunner._compute_learning_score(c) == 0.0


def test_learning_score_high():
    c = ConsolidatedMemory(
        total_cycles=5,
        successful_cycles=5,
        mean_fitness_score=0.8,
        mean_entropy_delta=0.1,
        best_fitness_score=0.9,
        worst_fitness_score=0.5,
        recovery_pattern_found=True,
    )
    score = MultiCycleEvolutionRunner._compute_learning_score(c)
    assert score > 0.7


def test_learning_score_bounded():
    c = ConsolidatedMemory(total_cycles=1, mean_fitness_score=1.0, recovery_pattern_found=True)
    score = MultiCycleEvolutionRunner._compute_learning_score(c)
    assert 0.0 <= score <= 1.0


# ------------------------------------------------------------------ #
# Verdict
# ------------------------------------------------------------------ #

def test_verdict_insufficient_when_empty():
    c = ConsolidatedMemory()
    v, r = MultiCycleEvolutionRunner._compute_verdict(c, 0.0)
    assert v == "INSUFFICIENT_EVIDENCE"


def test_verdict_regression():
    c = ConsolidatedMemory(total_cycles=3, regression_pattern_found=True)
    v, r = MultiCycleEvolutionRunner._compute_verdict(c, 0.2)
    assert v == "REGRESSION_DETECTED"


def test_verdict_validated():
    c = ConsolidatedMemory(total_cycles=5, successful_cycles=5, recovery_pattern_found=True)
    v, r = MultiCycleEvolutionRunner._compute_verdict(c, 0.75)
    assert v == "MULTI_CYCLE_EVOLUTION_VALIDATED"


def test_verdict_partial():
    c = ConsolidatedMemory(total_cycles=5, successful_cycles=3)
    v, r = MultiCycleEvolutionRunner._compute_verdict(c, 0.5)
    assert v == "MULTI_CYCLE_EVOLUTION_PARTIAL"


# ------------------------------------------------------------------ #
# Run
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_run_returns_result(runner):
    result = await runner.run()
    assert isinstance(result, MultiCycleEvolutionResult)
    assert len(result.cycle_results) <= runner.cycle_count


@pytest.mark.asyncio
async def test_run_consolidates_memory(runner):
    result = await runner.run()
    assert result.consolidated.total_cycles <= runner.cycle_count


@pytest.mark.asyncio
async def test_run_learning_score_bounded(runner):
    result = await runner.run()
    assert 0.0 <= result.cumulative_learning_score <= 1.0


@pytest.mark.asyncio
async def test_run_logs_events(runner, orchestrator):
    before = len(orchestrator.memory.events)
    await runner.run()
    after = len(orchestrator.memory.events)
    assert after >= before


# ------------------------------------------------------------------ #
# Reports
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_generate_json_report(runner):
    result = await runner.run()
    path = runner.generate_json_report(result)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["run_id"] == result.run_id


@pytest.mark.asyncio
async def test_generate_markdown_report(runner):
    result = await runner.run()
    path = runner.generate_markdown_report(result)
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "T56" in text
    assert result.verdict in text


# ------------------------------------------------------------------ #
# Orchestrator hook
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_orchestrator_run_multi_cycle_evolution(orchestrator):
    result = await orchestrator.run_multi_cycle_evolution(cycle_count=1)
    assert isinstance(result, MultiCycleEvolutionResult)
