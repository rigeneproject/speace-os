import asyncio
import json

import pytest

from speace_core.cellular_brain.self_organization.perturbation_recovery_audit import (
    PerturbationRecoveryResult,
    PerturbationVerdict,
)
from speace_core.cellular_brain.self_organization.perturbation_recovery_audit_runner import (
    PerturbationProfileConfig,
    PerturbationRecoveryAuditRunner,
    ProfileResult,
    T54BAggregateVerdict,
)


# ------------------------------------------------------------------ #
# Model validation
# ------------------------------------------------------------------ #

def test_profile_config_defaults():
    c = PerturbationProfileConfig(name="test", description="desc")
    assert c.region_stability_controller_enabled is False
    assert c.brainstem_controller_enabled is False
    assert c.perturbation_recovery_audit_enabled is True


def test_profile_result_defaults():
    p = ProfileResult(profile_name="p1", results=[])
    assert p.mean_recovery_score == 0.0
    assert p.worst_verdict == ""


def test_aggregate_verdict_defaults():
    a = T54BAggregateVerdict(overall_verdict="TEST")
    assert a.can_proceed_to_t55 is False


# ------------------------------------------------------------------ #
# Runner construction
# ------------------------------------------------------------------ #

def test_runner_has_profiles():
    runner = PerturbationRecoveryAuditRunner()
    assert len(runner.PROFILES) == 6


def test_runner_report_dir():
    runner = PerturbationRecoveryAuditRunner()
    assert runner.REPORT_DIR.exists()


# ------------------------------------------------------------------ #
# Verdict helpers
# ------------------------------------------------------------------ #

def test_worst_verdict_collapse_priority():
    verdicts = [
        PerturbationVerdict.RECOVERY_PARTIAL,
        PerturbationVerdict.PHI_COLLAPSE,
        PerturbationVerdict.PERTURBATION_RECOVERY_VALIDATED,
    ]
    worst = PerturbationRecoveryAuditRunner._worst_verdict(verdicts)
    assert worst == PerturbationVerdict.PHI_COLLAPSE


def test_worst_verdict_empty():
    assert PerturbationRecoveryAuditRunner._worst_verdict([]) is None


def test_profile_recommendation_block_on_collapse():
    r = PerturbationRecoveryAuditRunner._profile_recommendation(
        PerturbationVerdict.PHI_COLLAPSE, [0.5]
    )
    assert r == "BLOCK_T55"


def test_profile_recommendation_tune_on_suppression():
    r = PerturbationRecoveryAuditRunner._profile_recommendation(
        PerturbationVerdict.OVER_SUPPRESSION, [0.5]
    )
    assert r == "TUNE_T53"


def test_profile_recommendation_increase_strength():
    r = PerturbationRecoveryAuditRunner._profile_recommendation(
        PerturbationVerdict.PERTURBATION_NO_EFFECT, [0.02]
    )
    assert r == "INCREASE_STRENGTH"


def test_profile_recommendation_proceed():
    r = PerturbationRecoveryAuditRunner._profile_recommendation(
        PerturbationVerdict.PERTURBATION_RECOVERY_VALIDATED, [0.7, 0.8]
    )
    assert r == "PROCEED_T55"


def test_profile_recommendation_conservative():
    r = PerturbationRecoveryAuditRunner._profile_recommendation(
        PerturbationVerdict.RECOVERY_PARTIAL, [0.5, 0.6]
    )
    assert r == "PROCEED_T55_CONSERVATIVE"


# ------------------------------------------------------------------ #
# Aggregate verdict
# ------------------------------------------------------------------ #

def test_aggregate_block_when_collapse():
    profiles = [
        ProfileResult(profile_name="p1", results=[], recommended_next_step="PROCEED_T55"),
        ProfileResult(profile_name="p2", results=[], recommended_next_step="BLOCK_T55"),
    ]
    v = PerturbationRecoveryAuditRunner._compute_aggregate_verdict(profiles)
    assert v.overall_verdict == "BLOCK_T55"
    assert v.can_proceed_to_t55 is False


def test_aggregate_tune_when_suppression():
    profiles = [
        ProfileResult(profile_name="p1", results=[], recommended_next_step="TUNE_T53"),
    ]
    v = PerturbationRecoveryAuditRunner._compute_aggregate_verdict(profiles)
    assert v.overall_verdict == "TUNE_T53"


def test_aggregate_proceed_when_validated():
    profiles = [
        ProfileResult(
            profile_name="p1", results=[],
            mean_recovery_score=0.7, recommended_next_step="PROCEED_T55"
        ),
        ProfileResult(
            profile_name="p2", results=[],
            mean_recovery_score=0.7, recommended_next_step="PROCEED_T55"
        ),
    ]
    v = PerturbationRecoveryAuditRunner._compute_aggregate_verdict(profiles)
    assert v.overall_verdict == "PROCEED_T55"
    assert v.can_proceed_to_t55 is True


def test_aggregate_conservative():
    profiles = [
        ProfileResult(
            profile_name="p1", results=[],
            mean_recovery_score=0.5, recommended_next_step="PROCEED_T55_CONSERVATIVE"
        ),
    ]
    v = PerturbationRecoveryAuditRunner._compute_aggregate_verdict(profiles)
    assert v.overall_verdict == "PROCEED_T55_CONSERVATIVE"
    assert v.t55_conservative_mode is True


def test_aggregate_insufficient():
    profiles = [
        ProfileResult(
            profile_name="p1", results=[],
            mean_recovery_score=0.1, recommended_next_step="BLOCK_T55"
        ),
    ]
    v = PerturbationRecoveryAuditRunner._compute_aggregate_verdict(profiles)
    assert v.can_proceed_to_t55 is False


# ------------------------------------------------------------------ #
# Profile execution (async)
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_run_profile_returns_result():
    runner = PerturbationRecoveryAuditRunner(warmup_ticks=1, perturbation_ticks=1, recovery_ticks=2)
    profile = runner.PROFILES[0]
    result = await runner.run_profile(profile)
    assert isinstance(result, ProfileResult)
    assert result.profile_name == profile.name
    assert len(result.results) >= 6


@pytest.mark.asyncio
async def test_run_profile_scores_bounded():
    runner = PerturbationRecoveryAuditRunner(warmup_ticks=1, perturbation_ticks=1, recovery_ticks=2)
    result = await runner.run_profile(runner.PROFILES[0])
    assert 0.0 <= result.mean_recovery_score <= 1.0
    assert 0.0 <= result.min_recovery_score <= 1.0


@pytest.mark.asyncio
async def test_run_profile_verdict_counts():
    runner = PerturbationRecoveryAuditRunner(warmup_ticks=1, perturbation_ticks=1, recovery_ticks=2)
    result = await runner.run_profile(runner.PROFILES[0])
    total = (
        result.validated_count
        + result.partial_count
        + result.collapse_count
        + result.over_suppression_count
        + result.no_effect_count
        + result.insufficient_count
    )
    assert total == len(result.results)


# ------------------------------------------------------------------ #
# Suite execution (async)
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_run_suite_returns_aggregate():
    runner = PerturbationRecoveryAuditRunner(warmup_ticks=1, perturbation_ticks=1, recovery_ticks=2)
    verdict = await runner.run_suite()
    assert isinstance(verdict, T54BAggregateVerdict)
    assert len(verdict.profile_results) == 6
    assert verdict.overall_verdict in {
        "BLOCK_T55",
        "TUNE_T53",
        "PROCEED_T55",
        "PROCEED_T55_CONSERVATIVE",
        "INSUFFICIENT_EVIDENCE",
    }


# ------------------------------------------------------------------ #
# Reports
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_generate_json_report():
    runner = PerturbationRecoveryAuditRunner(warmup_ticks=1, perturbation_ticks=1, recovery_ticks=2)
    verdict = await runner.run_suite()
    path = runner.generate_json_report(verdict)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["overall_verdict"] == verdict.overall_verdict


@pytest.mark.asyncio
async def test_generate_markdown_report():
    runner = PerturbationRecoveryAuditRunner(warmup_ticks=1, perturbation_ticks=1, recovery_ticks=2)
    verdict = await runner.run_suite()
    path = runner.generate_markdown_report(verdict)
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "T54B" in text
    assert verdict.overall_verdict in text
