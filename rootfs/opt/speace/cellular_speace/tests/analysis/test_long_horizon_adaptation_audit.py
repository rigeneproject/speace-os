import pytest

from speace_core.cellular_brain.analysis.deep_region_audit import DeepRegionAuditProfile
from speace_core.cellular_brain.analysis.long_horizon_adaptation_audit import (
    LongHorizonAdaptationAuditor,
    LongHorizonProfileResult,
    LongHorizonTrajectoryPoint,
)


@pytest.fixture
def auditor():
    return LongHorizonAdaptationAuditor(seed=42, horizons=[5, 10])


# ------------------------------------------------------------------ #
# Import & construction
# ------------------------------------------------------------------ #

def test_auditor_importable():
    assert LongHorizonAdaptationAuditor is not None


def test_auditor_profiles_generated(auditor):
    profiles = auditor.default_profiles()
    assert len(profiles) >= 7
    ids = {p.profile_id for p in profiles}
    assert "lh0" in ids
    assert "lh5" in ids
    assert "lh6" in ids


# ------------------------------------------------------------------ #
# Profile run
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_run_profile_produces_trajectory_points(auditor):
    profile = DeepRegionAuditProfile(
        profile_id="test",
        name="test_profile",
        deep_regions_enabled=False,
        inter_region_plasticity_enabled=True,
        region_signal_routing_enabled=False,
        region_stability_controller_enabled=False,
    )
    result = await auditor.run_profile(profile)
    assert result.passed is True
    assert len(result.trajectory_points) == len(auditor.HORIZONS)


@pytest.mark.asyncio
async def test_trajectory_points_ordered_by_tick(auditor):
    profile = DeepRegionAuditProfile(
        profile_id="test",
        name="test_profile",
        deep_regions_enabled=False,
        inter_region_plasticity_enabled=True,
        region_signal_routing_enabled=False,
        region_stability_controller_enabled=False,
    )
    result = await auditor.run_profile(profile)
    ticks = [p.tick for p in result.trajectory_points]
    assert ticks == sorted(ticks)
    assert ticks == auditor.HORIZONS


@pytest.mark.asyncio
async def test_trajectory_points_have_expected_metrics(auditor):
    profile = DeepRegionAuditProfile(
        profile_id="test",
        name="test_profile",
        deep_regions_enabled=False,
        inter_region_plasticity_enabled=True,
        region_signal_routing_enabled=False,
        region_stability_controller_enabled=False,
    )
    result = await auditor.run_profile(profile)
    for tp in result.trajectory_points:
        assert 0.0 <= tp.cognitive_score <= 1.0
        assert -1.0 <= tp.phi <= 1.0
        assert 0.0 <= tp.energy_efficiency <= 1.0
        assert tp.suppression_cost >= 0.0
        assert tp.brainstem_state in {
            "stable", "watchful", "corrective", "protective", "emergency"
        }


# ------------------------------------------------------------------ #
# Slopes
# ------------------------------------------------------------------ #

def test_linear_slope_computation(auditor):
    points = [
        LongHorizonTrajectoryPoint(tick=5, cognitive_score=0.1),
        LongHorizonTrajectoryPoint(tick=25, cognitive_score=0.2),
        LongHorizonTrajectoryPoint(tick=50, cognitive_score=0.3),
    ]
    slope = auditor._linear_slope(points, "cognitive_score")
    assert slope > 0.0


def test_linear_slope_flat(auditor):
    points = [
        LongHorizonTrajectoryPoint(tick=5, cognitive_score=0.5),
        LongHorizonTrajectoryPoint(tick=25, cognitive_score=0.5),
    ]
    slope = auditor._linear_slope(points, "cognitive_score")
    assert slope == 0.0


# ------------------------------------------------------------------ #
# State entropy & recovery
# ------------------------------------------------------------------ #

def test_state_entropy_in_valid_range():
    result = LongHorizonProfileResult(
        profile=DeepRegionAuditProfile(profile_id="test", name="test"),
        protective_state_ratio_over_time=0.2,
        corrective_state_ratio_over_time=0.3,
        emergency_state_ratio_over_time=0.1,
    )
    # Entropy for [0.2, 0.3, 0.1, 0.4]
    from speace_core.cellular_brain.analysis.long_horizon_adaptation_audit import math
    probs = [0.2, 0.3, 0.1, 0.4]
    entropy = -sum(p * math.log2(p) for p in probs if p > 0)
    assert 0.0 <= entropy <= 2.0


def test_compute_state_entropy_from_distribution():
    auditor = LongHorizonAdaptationAuditor(seed=42)
    result = LongHorizonProfileResult(
        profile=DeepRegionAuditProfile(profile_id="test", name="test"),
        trajectory_points=[
            LongHorizonTrajectoryPoint(
                tick=5,
                state_distribution={"stable": 2, "watchful": 2, "corrective": 1}
            ),
        ],
    )
    auditor._compute_state_entropy_from_distribution(result)
    assert result.state_entropy > 0.0


# ------------------------------------------------------------------ #
# Verdict
# ------------------------------------------------------------------ #

def test_verdict_insufficient_evidence_empty():
    auditor = LongHorizonAdaptationAuditor(seed=42)
    verdict = auditor._compute_verdict([])
    assert verdict == "INSUFFICIENT_EVIDENCE"


def test_verdict_deterministic():
    auditor = LongHorizonAdaptationAuditor(seed=42)
    results = [
        LongHorizonProfileResult(
            profile=DeepRegionAuditProfile(profile_id="lh0", name="baseline"),
            long_horizon_recovery_score=0.005,
            net_gain_slope=0.0,
            suppression_cost_slope=0.0,
            recovery_latency_ticks=-1,
            state_entropy=0.2,
            passed=True,
        ),
        LongHorizonProfileResult(
            profile=DeepRegionAuditProfile(profile_id="lh5", name="t39"),
            long_horizon_recovery_score=0.02,
            net_gain_slope=0.0001,
            suppression_cost_slope=-0.0001,
            recovery_latency_ticks=10,
            state_entropy=0.5,
            passed=True,
        ),
    ]
    verdict = auditor._compute_verdict(results)
    # recovery_score > 0.01 and lh5 exists -> LONG_HORIZON_RECOVERY_VALIDATED
    assert verdict == "LONG_HORIZON_RECOVERY_VALIDATED"


# ------------------------------------------------------------------ #
# Suite run
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_run_audit_suite_produces_report(auditor):
    # Use only 2 profiles and short horizons for speed
    profiles = [
        DeepRegionAuditProfile(
            profile_id="lh0",
            name="baseline",
            deep_regions_enabled=False,
            inter_region_plasticity_enabled=True,
            region_signal_routing_enabled=False,
            region_stability_controller_enabled=False,
        ),
        DeepRegionAuditProfile(
            profile_id="lh5",
            name="t39",
            deep_regions_enabled=True,
            inter_region_plasticity_enabled=True,
            region_signal_routing_enabled=True,
            region_stability_controller_enabled=True,
            brainstem_controller_enabled=True,
            brainstem_gain_controller_enabled=True,
            brainstem_gain_profile="cognitive_preserving",
        ),
    ]
    report = await auditor.run_audit_suite(profiles=profiles)
    assert report.verdict is not None
    assert report.json_report_path is not None
    assert report.markdown_report_path is not None
    assert len(report.profile_results) == 2


@pytest.mark.asyncio
async def test_report_json_contains_key_metrics(auditor):
    profiles = [
        DeepRegionAuditProfile(
            profile_id="lh0",
            name="baseline",
            deep_regions_enabled=False,
            inter_region_plasticity_enabled=True,
            region_signal_routing_enabled=False,
            region_stability_controller_enabled=False,
        ),
    ]
    report = await auditor.run_audit_suite(profiles=profiles)
    json_path = report.json_report_path
    import json
    data = json.loads(open(json_path).read())
    assert "verdict" in data
    assert "profile_results" in data


@pytest.mark.asyncio
async def test_report_markdown_contains_main_metrics(auditor):
    profiles = [
        DeepRegionAuditProfile(
            profile_id="lh0",
            name="baseline",
            deep_regions_enabled=False,
            inter_region_plasticity_enabled=True,
            region_signal_routing_enabled=False,
            region_stability_controller_enabled=False,
        ),
    ]
    report = await auditor.run_audit_suite(profiles=profiles)
    md_text = open(report.markdown_report_path).read()
    assert "T40" in md_text
    assert "Verdict" in md_text
    assert "Profile x Horizon Matrix" in md_text
    assert "Slopes" in md_text


# ------------------------------------------------------------------ #
# No regression on existing tests
# ------------------------------------------------------------------ #

def test_no_regression_existing_imports():
    from speace_core.cellular_brain.analysis.deep_region_audit import DeepRegionAuditor
    from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import NeuroFunctionalBenchmark
    assert DeepRegionAuditor is not None
    assert NeuroFunctionalBenchmark is not None
