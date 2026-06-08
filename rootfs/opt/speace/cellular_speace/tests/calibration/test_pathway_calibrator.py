import pytest

from speace_core.cellular_brain.calibration.pathway_calibrator import (
    PathwayCalibrator,
    PathwayCalibrationProfile,
    PathwayCalibrationResult,
    PathwayAuditReport,
)


@pytest.fixture
def calibrator():
    return PathwayCalibrator(
        seed=42,
        n_adaptive_cycles=2,
        benchmark_case="morphological_memory_trace",
    )


# ---------------------------------------------------------------------------
# 1. PathwayCalibrator importabile
# ---------------------------------------------------------------------------

def test_calibrator_importable():
    assert PathwayCalibrator is not None


# ---------------------------------------------------------------------------
# 2. default_profiles contiene almeno 8 profili
# ---------------------------------------------------------------------------

def test_default_profiles_count(calibrator):
    profiles = calibrator.default_profiles()
    assert len(profiles) >= 8


# ---------------------------------------------------------------------------
# 3. inter_region_off disabilita la plasticità inter-regionale
# ---------------------------------------------------------------------------

def test_inter_region_off_profile(calibrator):
    profiles = calibrator.default_profiles()
    off = next(p for p in profiles if p.name == "inter_region_off")
    assert off.inter_region_plasticity_enabled is False


# ---------------------------------------------------------------------------
# 4. routing_only abilita routing ma non plasticity
# ---------------------------------------------------------------------------

def test_routing_only_profile(calibrator):
    profiles = calibrator.default_profiles()
    routing = next(p for p in profiles if p.name == "routing_only")
    assert routing.inter_region_plasticity_enabled is False
    assert routing.region_signal_routing_enabled is True


# ---------------------------------------------------------------------------
# 5. low/medium/high modificano LTP/LTD
# ---------------------------------------------------------------------------

def test_routing_plus_low_plasticity_rates(calibrator):
    profiles = calibrator.default_profiles()
    low = next(p for p in profiles if p.name == "routing_plus_low_plasticity")
    assert low.ltp_rate == pytest.approx(0.02)
    assert low.ltd_rate == pytest.approx(0.01)


def test_routing_plus_medium_plasticity_rates(calibrator):
    profiles = calibrator.default_profiles()
    med = next(p for p in profiles if p.name == "routing_plus_medium_plasticity")
    assert med.ltp_rate == pytest.approx(0.04)
    assert med.ltd_rate == pytest.approx(0.025)


def test_routing_plus_high_plasticity_rates(calibrator):
    profiles = calibrator.default_profiles()
    high = next(p for p in profiles if p.name == "routing_plus_high_plasticity")
    assert high.ltp_rate == pytest.approx(0.08)
    assert high.ltd_rate == pytest.approx(0.06)


# ---------------------------------------------------------------------------
# 6. routing_plus_energy_conservative riduce costo energetico
# ---------------------------------------------------------------------------

def test_routing_plus_energy_conservative_cost(calibrator):
    profiles = calibrator.default_profiles()
    eco = next(p for p in profiles if p.name == "routing_plus_energy_conservative")
    assert eco.energy_cost_per_update == pytest.approx(0.0005)
    assert eco.energy_modulation_strength == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# 7. routing_plus_plasticity abilita entrambi
# ---------------------------------------------------------------------------

def test_routing_plus_plasticity_profile(calibrator):
    profiles = calibrator.default_profiles()
    rp = next(p for p in profiles if p.name == "routing_plus_plasticity")
    assert rp.inter_region_plasticity_enabled is True
    assert rp.region_signal_routing_enabled is True


# ---------------------------------------------------------------------------
# 8. run_profile produce PathwayCalibrationResult
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_profile_produces_result(calibrator):
    profiles = calibrator.default_profiles()
    profile = next(p for p in profiles if p.name == "inter_region_off")
    result = await calibrator.run_profile(profile)
    assert isinstance(result, PathwayCalibrationResult)
    assert result.passed is True


# ---------------------------------------------------------------------------
# 9. regional_signal_flow_score calcolato in [0,1] o range controllato
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_regional_signal_flow_score_range(calibrator):
    profiles = calibrator.default_profiles()
    profile = next(p for p in profiles if p.name == "routing_plus_plasticity")
    result = await calibrator.run_profile(profile)
    assert 0.0 <= result.regional_signal_flow_score <= 1.0


# ---------------------------------------------------------------------------
# 10. report JSON generato
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_json_report(calibrator, tmp_path):
    calibrator.report_dir = tmp_path
    report = PathwayAuditReport(
        audit_id="test_json",
        created_at="2026-01-01T00:00:00+00:00",
        baseline_metrics={},
        profile_results=[],
        verdict="insufficient_evidence",
    )
    path = calibrator.generate_json_report(report)
    assert path.exists()
    assert path.suffix == ".json"


# ---------------------------------------------------------------------------
# 11. report Markdown generato
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_markdown_report(calibrator, tmp_path):
    calibrator.report_dir = tmp_path
    report = PathwayAuditReport(
        audit_id="test_md",
        created_at="2026-01-01T00:00:00+00:00",
        baseline_metrics={},
        profile_results=[],
        verdict="insufficient_evidence",
    )
    path = calibrator.generate_markdown_report(report)
    assert path.exists()
    assert path.suffix == ".md"
    content = path.read_text(encoding="utf-8")
    assert "Post-T25 T26 Regional Plasticity Audit Report (Routing Enabled)" in content


# ---------------------------------------------------------------------------
# 12. verdict prodotto
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_suite_produces_verdict(calibrator):
    # Run only first 2 profiles to keep test fast
    all_profiles = calibrator.default_profiles()
    report = await calibrator.run_pathway_calibration_suite(profiles=all_profiles[:2])
    assert report.verdict in [
        "routing_plasticity_validated",
        "routing_validated_plasticity_weak",
        "routing_active_but_no_plasticity",
        "pathway_overplasticity_detected",
        "routing_energy_regression",
        "routing_no_effect",
        "insufficient_evidence",
    ]


# ---------------------------------------------------------------------------
# 13. compute_regression_score positive when metrics improve
# ---------------------------------------------------------------------------

def test_compute_regression_score_positive():
    result = PathwayCalibrationResult(
        profile=PathwayCalibrationProfile(profile_id="x", name="x"),
        speace_cognitive_score=0.6,
        coherence_phi=0.4,
        energy_efficiency=0.5,
        regional_signal_flow_score=0.3,
    )
    baseline = {
        "speace_cognitive_score": 0.5,
        "coherence_phi": 0.3,
        "energy_efficiency": 0.4,
        "regional_signal_flow_score": 0.2,
    }
    score = PathwayCalibrator.compute_regression_score(result, baseline)
    assert score > 0.0


def test_compute_regression_score_zero_when_worse():
    result = PathwayCalibrationResult(
        profile=PathwayCalibrationProfile(profile_id="x", name="x"),
        speace_cognitive_score=0.3,
        coherence_phi=0.2,
        energy_efficiency=0.2,
        regional_signal_flow_score=0.1,
    )
    baseline = {
        "speace_cognitive_score": 0.5,
        "coherence_phi": 0.3,
        "energy_efficiency": 0.4,
        "regional_signal_flow_score": 0.2,
    }
    score = PathwayCalibrator.compute_regression_score(result, baseline)
    assert score == 0.0


# ---------------------------------------------------------------------------
# 14. apply_pathway_profile mutates orchestrator correctly
# ---------------------------------------------------------------------------

def test_apply_pathway_profile():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    profile = PathwayCalibrationProfile(
        profile_id="test",
        name="test",
        inter_region_plasticity_enabled=True,
        ltp_rate=0.99,
        ltd_rate=0.88,
        stdp_window=7,
        confidence_modulation_strength=2.0,
        energy_modulation_strength=3.0,
    )
    PathwayCalibrator.apply_pathway_profile(profile, orch)
    assert orch.inter_region_plasticity_enabled is True
    assert orch._inter_region_plasticity.ltp_rate == pytest.approx(0.99)
    assert orch._inter_region_plasticity.ltd_rate == pytest.approx(0.88)
    assert orch._inter_region_plasticity.stdp_window == 7
    assert orch._inter_region_plasticity.confidence_modulation_strength == pytest.approx(2.0)
    assert orch._inter_region_plasticity.energy_modulation_strength == pytest.approx(3.0)
