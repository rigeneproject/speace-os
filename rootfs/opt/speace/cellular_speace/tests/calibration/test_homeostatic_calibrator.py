import os

import pytest

from speace_core.cellular_brain.calibration.homeostatic_calibrator import (
    CalibrationAuditReport,
    CalibrationProfile,
    CalibrationResult,
    HomeostaticCalibrator,
)
from speace_core.dna.parser import load_genome


@pytest.fixture
def calibrator():
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    return HomeostaticCalibrator(
        genome=genome.model_dump(),
        seed=42,
        n_adaptive_cycles=2,
        benchmark_case="morphological_memory_trace",
    )


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

def test_calibrator_importable():
    assert HomeostaticCalibrator is not None
    assert CalibrationProfile is not None
    assert CalibrationResult is not None
    assert CalibrationAuditReport is not None


def test_default_profiles_count(calibrator):
    profiles = calibrator.default_profiles()
    assert len(profiles) >= 8
    names = {p.name for p in profiles}
    assert "current_full_organism" in names
    assert "energy_control_off" in names
    assert "energy_soft" in names
    assert "energy_medium" in names
    assert "energy_strict" in names
    assert "stdp_preserved_energy_soft" in names
    assert "inhibition_soft_decay_soft" in names
    assert "neurogenesis_preserved_energy_soft" in names


# ---------------------------------------------------------------------------
# Profile application
# ---------------------------------------------------------------------------

def test_apply_profile_disables_energy_control(calibrator):
    orch = calibrator.build_orchestrator()
    profile = CalibrationProfile(
        profile_id="test",
        name="energy_off",
        energy_control_enabled=False,
        stdp_enabled=False,
        inhibition_enabled=False,
    )
    HomeostaticCalibrator.apply_profile_to_orchestrator(profile, orch)
    assert orch.energy_control_enabled is False
    assert orch.stdp_enabled is False
    assert orch.inhibition_enabled is False


def test_apply_profile_state_profiles(calibrator):
    orch = calibrator.build_orchestrator()
    profile = CalibrationProfile(
        profile_id="test",
        name="soft",
        state_profiles={
            "low": {"burst_size_multiplier": 0.99, "stdp_rate_multiplier": 0.99}
        },
    )
    HomeostaticCalibrator.apply_profile_to_orchestrator(profile, orch)
    assert orch._energy_control is not None
    low_profile = orch._energy_control.state_profiles["low"]
    assert low_profile["burst_size_multiplier"] == 0.99
    assert low_profile["stdp_rate_multiplier"] == 0.99


# ---------------------------------------------------------------------------
# Single profile run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_profile_produces_result(calibrator):
    profile = CalibrationProfile(profile_id="t1", name="test_run")
    result = await calibrator.run_profile(profile)
    assert isinstance(result, CalibrationResult)
    assert result.passed is True
    assert result.cognitive_score >= 0.0
    assert result.coherence_phi >= 0.0


@pytest.mark.asyncio
async def test_run_profile_energy_off(calibrator):
    profile = CalibrationProfile(
        profile_id="t2",
        name="energy_off",
        energy_control_enabled=False,
    )
    result = await calibrator.run_profile(profile)
    assert result.passed is True
    assert 0.0 <= result.energy_efficiency <= 1.0


# ---------------------------------------------------------------------------
# Regression score
# ---------------------------------------------------------------------------

def test_compute_regression_score_improvement():
    baseline = {
        "speace_cognitive_score": 0.5,
        "coherence_phi": 0.5,
        "energy_efficiency": 0.5,
    }
    result = CalibrationResult(
        profile=CalibrationProfile(profile_id="x", name="x"),
        cognitive_score=0.6,
        coherence_phi=0.6,
        energy_efficiency=0.6,
        functional_improvement=0.1,
        meta_cognitive_score=0.1,
    )
    score = HomeostaticCalibrator.compute_regression_score(result, baseline)
    assert score > 0.0


def test_compute_regression_score_no_improvement():
    baseline = {
        "speace_cognitive_score": 0.5,
        "coherence_phi": 0.5,
        "energy_efficiency": 0.5,
    }
    result = CalibrationResult(
        profile=CalibrationProfile(profile_id="x", name="x"),
        cognitive_score=0.4,
        coherence_phi=0.4,
        energy_efficiency=0.4,
    )
    score = HomeostaticCalibrator.compute_regression_score(result, baseline)
    assert score == 0.0


def test_compute_distance_from_baseline():
    baseline = {
        "speace_cognitive_score": 0.5,
        "coherence_phi": 0.5,
        "energy_efficiency": 0.5,
    }
    result = CalibrationResult(
        profile=CalibrationProfile(profile_id="x", name="x"),
        cognitive_score=0.4,
        coherence_phi=0.6,
        energy_efficiency=0.5,
    )
    dist = HomeostaticCalibrator.compute_distance_from_baseline(result, baseline)
    assert dist == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# Best profile selection
# ---------------------------------------------------------------------------

def test_select_best_profile_improver():
    baseline = {
        "speace_cognitive_score": 0.5,
        "coherence_phi": 0.5,
        "energy_efficiency": 0.5,
    }
    r1 = CalibrationResult(
        profile=CalibrationProfile(profile_id="a", name="a"),
        regression_score=0.1,
        distance_from_baseline=0.5,
    )
    r2 = CalibrationResult(
        profile=CalibrationProfile(profile_id="b", name="b"),
        regression_score=0.2,
        distance_from_baseline=0.3,
    )
    best = HomeostaticCalibrator.select_best_profile([r1, r2], baseline)
    assert best is not None
    assert best.profile.name == "b"


def test_select_best_profile_least_regressive():
    baseline = {
        "speace_cognitive_score": 0.5,
        "coherence_phi": 0.5,
        "energy_efficiency": 0.5,
    }
    r1 = CalibrationResult(
        profile=CalibrationProfile(profile_id="a", name="a"),
        regression_score=0.0,
        distance_from_baseline=0.5,
    )
    r2 = CalibrationResult(
        profile=CalibrationProfile(profile_id="b", name="b"),
        regression_score=0.0,
        distance_from_baseline=0.2,
    )
    best = HomeostaticCalibrator.select_best_profile([r1, r2], baseline)
    assert best is not None
    assert best.profile.name == "b"


# ---------------------------------------------------------------------------
# Verdict logic
# ---------------------------------------------------------------------------

def test_verdict_regression_reduced():
    baseline = {"speace_cognitive_score": 0.5}
    r = CalibrationResult(
        profile=CalibrationProfile(profile_id="x", name="x"),
        regression_score=0.1,
        passed=True,
    )
    assert HomeostaticCalibrator._compute_verdict([r], baseline) == "regression_reduced"


def test_verdict_partially_stabilized():
    baseline = {"speace_cognitive_score": 0.5}
    current = CalibrationResult(
        profile=CalibrationProfile(profile_id="c", name="current_full_organism"),
        regression_score=0.0,
        distance_from_baseline=0.5,
        passed=True,
    )
    better = CalibrationResult(
        profile=CalibrationProfile(profile_id="b", name="better"),
        regression_score=0.0,
        distance_from_baseline=0.3,
        passed=True,
    )
    assert (
        HomeostaticCalibrator._compute_verdict([current, better], baseline)
        == "partially_stabilized"
    )


def test_verdict_regression_persists():
    baseline = {"speace_cognitive_score": 0.5}
    current = CalibrationResult(
        profile=CalibrationProfile(profile_id="c", name="current_full_organism"),
        regression_score=0.0,
        distance_from_baseline=0.5,
        passed=True,
    )
    assert (
        HomeostaticCalibrator._compute_verdict([current], baseline)
        == "regression_persists"
    )


# ---------------------------------------------------------------------------
# Full suite run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_calibration_suite(calibrator):
    # Use only 3 profiles for speed
    profiles = calibrator.default_profiles()[:3]
    report = await calibrator.run_calibration_suite(profiles=profiles)
    assert isinstance(report, CalibrationAuditReport)
    assert report.audit_id is not None
    assert len(report.profile_results) == 3
    assert report.verdict in {
        "regression_reduced",
        "partially_stabilized",
        "regression_persists",
        "insufficient_evidence",
    }


@pytest.mark.asyncio
async def test_suite_generates_reports(calibrator):
    profiles = calibrator.default_profiles()[:2]
    report = await calibrator.run_calibration_suite(profiles=profiles)
    assert report.json_report_path is not None
    assert os.path.exists(report.json_report_path)
    assert report.markdown_report_path is not None
    assert os.path.exists(report.markdown_report_path)
    md_text = open(report.markdown_report_path, encoding="utf-8").read()
    assert "## Comparative Results" in md_text
    assert "## Baseline Metrics" in md_text


# ---------------------------------------------------------------------------
# Region compatibility
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_calibration_with_regions_enabled(calibrator):
    profile = CalibrationProfile(
        profile_id="r1",
        name="region_test",
        region_architecture_enabled=True,
    )
    result = await calibrator.run_profile(profile)
    assert result.passed is True
    assert result.benchmark_metrics.get("region_count", 0) >= 4
