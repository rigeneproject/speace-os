import json
import pytest

from speace_core.cellular_brain.evolutionary_kernel.evolution_audit_runner import (
    EvolutionAuditProfile,
    EvolutionAuditRunner,
    EvolutionProfileResult,
    T55BAggregateVerdict,
)
from speace_core.cellular_brain.evolutionary_kernel.evolutionary_cycle_models import (
    EDDCVTMetrics,
    EvolutionCycleResult,
)


# ------------------------------------------------------------------ #
# Model validation
# ------------------------------------------------------------------ #

def test_profile_defaults():
    p = EvolutionAuditProfile(name="test", description="desc")
    assert p.edd_cvt_kernel_enabled is False
    assert p.cycle_count == 3


def test_profile_result_defaults():
    r = EvolutionProfileResult(profile_name="test")
    assert r.cycles_completed == 0
    assert r.verdict == ""


def test_aggregate_verdict_defaults():
    a = T55BAggregateVerdict(overall_verdict="TEST")
    assert a.can_proceed_to_t56 is False


# ------------------------------------------------------------------ #
# Runner construction
# ------------------------------------------------------------------ #

def test_runner_has_profiles():
    runner = EvolutionAuditRunner()
    assert len(runner.PROFILES) == 6


# ------------------------------------------------------------------ #
# Verdict helpers
# ------------------------------------------------------------------ #

def test_verdict_insufficient_when_no_cycles():
    m = EDDCVTMetrics()
    v, rec = EvolutionAuditRunner._compute_verdict(m)
    assert v == "INSUFFICIENT_EVIDENCE"


def test_verdict_collapse_when_more_failures():
    m = EDDCVTMetrics(total_cycles=5, successful_cycles=1, failed_cycles=4)
    v, rec = EvolutionAuditRunner._compute_verdict(m)
    assert v == "EVOLUTION_COLLAPSE"


def test_verdict_high_rollback():
    m = EDDCVTMetrics(total_cycles=4, successful_cycles=3, rollback_rate=0.6)
    v, rec = EvolutionAuditRunner._compute_verdict(m)
    assert v == "HIGH_ROLLBACK"


def test_verdict_validated():
    m = EDDCVTMetrics(total_cycles=4, successful_cycles=4, mean_fitness_score=0.7, safety_pass_rate=0.8)
    v, rec = EvolutionAuditRunner._compute_verdict(m)
    assert v == "EVOLUTION_VALIDATED"


def test_verdict_partial():
    m = EDDCVTMetrics(total_cycles=4, successful_cycles=2, mean_fitness_score=0.5, safety_pass_rate=0.6)
    v, rec = EvolutionAuditRunner._compute_verdict(m)
    assert v == "EVOLUTION_PARTIAL"


# ------------------------------------------------------------------ #
# Aggregate verdict
# ------------------------------------------------------------------ #

def test_aggregate_block_on_collapse():
    profiles = [
        EvolutionProfileResult(profile_name="p1", verdict="EVOLUTION_VALIDATED", cycles_completed=3),
        EvolutionProfileResult(profile_name="p2", verdict="EVOLUTION_COLLAPSE", cycles_completed=3),
    ]
    v = EvolutionAuditRunner._compute_aggregate_verdict(profiles)
    assert v.overall_verdict == "BLOCK_T56"
    assert v.can_proceed_to_t56 is False


def test_aggregate_insufficient_when_empty():
    profiles = []
    v = EvolutionAuditRunner._compute_aggregate_verdict(profiles)
    assert v.overall_verdict == "INSUFFICIENT_EVIDENCE"


def test_aggregate_proceed_when_validated():
    profiles = [
        EvolutionProfileResult(profile_name="p1", verdict="EVOLUTION_VALIDATED", cycles_completed=3, mean_fitness_score=0.7, safety_pass_rate=0.8),
        EvolutionProfileResult(profile_name="p2", verdict="EVOLUTION_VALIDATED", cycles_completed=3, mean_fitness_score=0.7, safety_pass_rate=0.8),
    ]
    v = EvolutionAuditRunner._compute_aggregate_verdict(profiles)
    assert v.overall_verdict == "PROCEED_T56"
    assert v.can_proceed_to_t56 is True


def test_aggregate_conservative():
    profiles = [
        EvolutionProfileResult(profile_name="p1", verdict="EVOLUTION_PARTIAL", cycles_completed=3, mean_fitness_score=0.5, safety_pass_rate=0.6),
    ]
    v = EvolutionAuditRunner._compute_aggregate_verdict(profiles)
    assert v.overall_verdict == "PROCEED_T56_CONSERVATIVE"


# ------------------------------------------------------------------ #
# Profile execution
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_run_profile_no_op_when_disabled():
    runner = EvolutionAuditRunner()
    profile = EvolutionAuditProfile(name="off", description="off", edd_cvt_kernel_enabled=False, cycle_count=0)
    result = await runner.run_profile(profile)
    assert result.verdict == "NO_OP"


@pytest.mark.asyncio
async def test_run_profile_returns_result():
    runner = EvolutionAuditRunner()
    profile = EvolutionAuditProfile(name="on", description="on", edd_cvt_kernel_enabled=True, cycle_count=1, cycle_interval_ticks=1)
    result = await runner.run_profile(profile)
    assert isinstance(result, EvolutionProfileResult)
    assert result.profile_name == "on"
    assert result.cycles_completed >= 0


@pytest.mark.asyncio
async def test_run_profile_metrics_bounded():
    runner = EvolutionAuditRunner()
    profile = EvolutionAuditProfile(name="on", description="on", edd_cvt_kernel_enabled=True, cycle_count=1, cycle_interval_ticks=1)
    result = await runner.run_profile(profile)
    assert 0.0 <= result.mean_fitness_score <= 1.0
    assert 0.0 <= result.reconfiguration_rate <= 1.0


# ------------------------------------------------------------------ #
# Suite execution
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_run_suite_returns_aggregate():
    runner = EvolutionAuditRunner()
    verdict = await runner.run_suite()
    assert isinstance(verdict, T55BAggregateVerdict)
    assert len(verdict.profile_results) == 6


# ------------------------------------------------------------------ #
# Reports
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_generate_json_report():
    runner = EvolutionAuditRunner()
    verdict = await runner.run_suite()
    path = runner.generate_json_report(verdict)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["overall_verdict"] == verdict.overall_verdict


@pytest.mark.asyncio
async def test_generate_markdown_report():
    runner = EvolutionAuditRunner()
    verdict = await runner.run_suite()
    path = runner.generate_markdown_report(verdict)
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "T55B" in text
    assert verdict.overall_verdict in text
