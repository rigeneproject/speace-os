import pytest

from speace_core.cellular_brain.analysis.deep_region_audit import (
    DeepRegionAuditProfile,
    DeepRegionAuditResult,
    DeepRegionAuditReport,
    DeepRegionAuditor,
)


# ---------------------------------------------------------------------------
# 1. Importabilità e modelli
# ---------------------------------------------------------------------------

def test_deep_region_audit_importable():
    assert DeepRegionAuditor is not None
    assert DeepRegionAuditProfile is not None
    assert DeepRegionAuditResult is not None
    assert DeepRegionAuditReport is not None


def test_default_profiles_count():
    profiles = DeepRegionAuditor.default_profiles()
    assert len(profiles) == 10
    ids = {p.profile_id for p in profiles}
    assert ids == {"d0", "d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8", "d9"}


def test_four_region_baseline_profile():
    profiles = DeepRegionAuditor.default_profiles()
    baseline = next(p for p in profiles if p.name == "four_region_baseline")
    assert baseline.deep_regions_enabled is False
    assert baseline.inter_region_plasticity_enabled is True
    assert baseline.region_signal_routing_enabled is False


def test_deep_regions_static_profile():
    profiles = DeepRegionAuditor.default_profiles()
    p = next(p for p in profiles if p.name == "deep_regions_static")
    assert p.deep_regions_enabled is True
    assert p.inter_region_plasticity_enabled is False
    assert p.region_signal_routing_enabled is False


def test_deep_regions_full_utility_profile():
    profiles = DeepRegionAuditor.default_profiles()
    p = next(p for p in profiles if p.name == "deep_regions_full_utility")
    assert p.deep_regions_enabled is True
    assert p.tuner_profile_id == "t9"


# ---------------------------------------------------------------------------
# 2. Orchestrator build
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_orchestrator_deep_regions():
    auditor = DeepRegionAuditor()
    orch = auditor.build_orchestrator(deep_regions_enabled=True)
    assert orch.deep_regions_enabled is True
    assert orch._region_registry is not None


@pytest.mark.asyncio
async def test_build_orchestrator_four_regions():
    auditor = DeepRegionAuditor()
    orch = auditor.build_orchestrator(deep_regions_enabled=False)
    assert orch.deep_regions_enabled is False
    assert orch._region_registry is not None
    assert "limbic" not in orch._region_registry.regions


# ---------------------------------------------------------------------------
# 3. Profile run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_four_region_baseline():
    auditor = DeepRegionAuditor(n_adaptive_cycles=2)
    profile = DeepRegionAuditProfile(
        profile_id="d0",
        name="four_region_baseline",
        deep_regions_enabled=False,
        inter_region_plasticity_enabled=True,
        region_signal_routing_enabled=False,
    )
    result = await auditor.run_profile(profile)
    assert result.passed is True
    assert result.profile.name == "four_region_baseline"


@pytest.mark.asyncio
async def test_run_deep_regions_static():
    auditor = DeepRegionAuditor(n_adaptive_cycles=2)
    profile = DeepRegionAuditProfile(
        profile_id="d1",
        name="deep_regions_static",
        deep_regions_enabled=True,
        inter_region_plasticity_enabled=False,
        region_signal_routing_enabled=False,
    )
    result = await auditor.run_profile(profile)
    assert result.passed is True


# ---------------------------------------------------------------------------
# 4. Net gain e verdict
# ---------------------------------------------------------------------------

def test_compute_deep_region_net_gain():
    baseline = DeepRegionAuditResult(
        profile=DeepRegionAuditProfile(profile_id="b", name="baseline"),
        cognitive_score=0.5,
        phi=0.5,
        energy_efficiency=0.5,
        functional_improvement=0.5,
        mean_pathway_utility=0.5,
    )
    result = DeepRegionAuditResult(
        profile=DeepRegionAuditProfile(profile_id="t", name="test"),
        cognitive_score=0.6,
        phi=0.6,
        energy_efficiency=0.6,
        functional_improvement=0.6,
        mean_pathway_utility=0.6,
        cognitive_score_delta=0.1,
        phi_delta=0.1,
        energy_efficiency_delta=0.1,
        functional_improvement_delta=0.1,
        pathway_utility_delta=0.1,
    )
    gain = DeepRegionAuditor.compute_deep_region_net_gain(result, baseline)
    assert gain > 0.0


def test_compute_verdict_validated():
    baseline = DeepRegionAuditResult(
        profile=DeepRegionAuditProfile(profile_id="b", name="baseline"),
        cognitive_score=0.5,
        phi=0.5,
        energy_efficiency=0.5,
    )
    result = DeepRegionAuditResult(
        profile=DeepRegionAuditProfile(profile_id="t", name="test", deep_regions_enabled=True),
        cognitive_score=0.6,
        phi=0.6,
        energy_efficiency=0.6,
        deep_region_net_gain=0.05,
    )
    verdict = DeepRegionAuditor._compute_verdict([result], baseline)
    assert verdict == "DEEP_REGIONS_VALIDATED"


def test_compute_verdict_energy_regression():
    baseline = DeepRegionAuditResult(
        profile=DeepRegionAuditProfile(profile_id="b", name="baseline"),
        cognitive_score=0.5,
        phi=0.5,
        energy_efficiency=0.5,
    )
    result = DeepRegionAuditResult(
        profile=DeepRegionAuditProfile(profile_id="t", name="test", deep_regions_enabled=True),
        cognitive_score=0.5,
        phi=0.5,
        energy_efficiency=0.3,
        deep_region_cost=0.02,
        deep_region_net_gain=-0.1,
    )
    verdict = DeepRegionAuditor._compute_verdict([result], baseline)
    assert verdict == "DEEP_REGION_ENERGY_REGRESSION"


def test_compute_verdict_phi_regression():
    baseline = DeepRegionAuditResult(
        profile=DeepRegionAuditProfile(profile_id="b", name="baseline"),
        cognitive_score=0.5,
        phi=0.5,
        energy_efficiency=0.5,
    )
    result = DeepRegionAuditResult(
        profile=DeepRegionAuditProfile(profile_id="t", name="test", deep_regions_enabled=True),
        cognitive_score=0.5,
        phi=0.3,
        energy_efficiency=0.5,
        deep_region_net_gain=-0.1,
    )
    verdict = DeepRegionAuditor._compute_verdict([result], baseline)
    assert verdict == "DEEP_REGION_PHI_REGRESSION"


def test_compute_verdict_cognitive_regression():
    baseline = DeepRegionAuditResult(
        profile=DeepRegionAuditProfile(profile_id="b", name="baseline"),
        cognitive_score=0.5,
        phi=0.5,
        energy_efficiency=0.5,
    )
    result = DeepRegionAuditResult(
        profile=DeepRegionAuditProfile(profile_id="t", name="test", deep_regions_enabled=True),
        cognitive_score=0.3,
        phi=0.5,
        energy_efficiency=0.5,
        deep_region_net_gain=-0.1,
    )
    verdict = DeepRegionAuditor._compute_verdict([result], baseline)
    assert verdict == "DEEP_REGION_COGNITIVE_REGRESSION"


def test_compute_verdict_neutral():
    baseline = DeepRegionAuditResult(
        profile=DeepRegionAuditProfile(profile_id="b", name="baseline"),
        cognitive_score=0.5,
        phi=0.5,
        energy_efficiency=0.5,
    )
    result = DeepRegionAuditResult(
        profile=DeepRegionAuditProfile(profile_id="t", name="test", deep_regions_enabled=True),
        cognitive_score=0.5,
        phi=0.5,
        energy_efficiency=0.5,
        deep_region_net_gain=0.0,
        deep_region_signal_flow=0.0,
    )
    verdict = DeepRegionAuditor._compute_verdict([result], baseline)
    assert verdict == "DEEP_REGIONS_NEUTRAL"


def test_compute_verdict_no_effect():
    baseline = DeepRegionAuditResult(
        profile=DeepRegionAuditProfile(profile_id="b", name="baseline"),
        cognitive_score=0.5,
        phi=0.5,
        energy_efficiency=0.5,
    )
    result = DeepRegionAuditResult(
        profile=DeepRegionAuditProfile(profile_id="t", name="test", deep_regions_enabled=True),
        cognitive_score=0.5,
        phi=0.5,
        energy_efficiency=0.5,
        deep_region_net_gain=0.0,
        deep_region_signal_flow=0.1,
    )
    verdict = DeepRegionAuditor._compute_verdict([result], baseline)
    assert verdict == "DEEP_REGION_NO_EFFECT"


def test_compute_verdict_insufficient_evidence():
    baseline = DeepRegionAuditResult(
        profile=DeepRegionAuditProfile(profile_id="b", name="baseline"),
        cognitive_score=0.5,
        phi=0.5,
        energy_efficiency=0.5,
    )
    result = DeepRegionAuditResult(
        profile=DeepRegionAuditProfile(profile_id="t", name="test", deep_regions_enabled=True),
        passed=False,
    )
    verdict = DeepRegionAuditor._compute_verdict([result], baseline)
    assert verdict == "INSUFFICIENT_EVIDENCE"


# ---------------------------------------------------------------------------
# 5. Suite run (lightweight)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_audit_suite_lightweight():
    auditor = DeepRegionAuditor(n_adaptive_cycles=2)
    # Use only 2 profiles for speed
    profiles = [
        DeepRegionAuditProfile(
            profile_id="d0",
            name="four_region_baseline",
            deep_regions_enabled=False,
            inter_region_plasticity_enabled=True,
            region_signal_routing_enabled=False,
        ),
        DeepRegionAuditProfile(
            profile_id="d1",
            name="deep_regions_static",
            deep_regions_enabled=True,
            inter_region_plasticity_enabled=False,
            region_signal_routing_enabled=False,
        ),
    ]
    report = await auditor.run_audit_suite(profiles=profiles)
    assert report.verdict in {
        "DEEP_REGIONS_VALIDATED",
        "DEEP_REGIONS_NEUTRAL",
        "DEEP_REGION_ENERGY_REGRESSION",
        "DEEP_REGION_PHI_REGRESSION",
        "DEEP_REGION_COGNITIVE_REGRESSION",
        "DEEP_REGION_NO_EFFECT",
        "INSUFFICIENT_EVIDENCE",
    }
    assert len(report.profile_results) == 2
    assert report.json_report_path is not None
    assert report.markdown_report_path is not None


# ---------------------------------------------------------------------------
# 6. Report generation
# ---------------------------------------------------------------------------

def test_generate_json_report(tmp_path):
    auditor = DeepRegionAuditor(report_dir=str(tmp_path))
    report = DeepRegionAuditReport(
        audit_id="test123",
        created_at="2026-05-16T00:00:00+00:00",
    )
    path = auditor.generate_json_report(report)
    assert path.exists()
    assert path.suffix == ".json"


def test_generate_markdown_report(tmp_path):
    auditor = DeepRegionAuditor(report_dir=str(tmp_path))
    report = DeepRegionAuditReport(
        audit_id="test123",
        created_at="2026-05-16T00:00:00+00:00",
    )
    path = auditor.generate_markdown_report(report)
    assert path.exists()
    assert path.suffix == ".md"
    content = path.read_text(encoding="utf-8")
    assert "Deep Region Functional Audit" in content


# ---------------------------------------------------------------------------
# 7. Select best profile
# ---------------------------------------------------------------------------

def test_select_best_profile():
    p1 = DeepRegionAuditProfile(profile_id="a", name="a", deep_regions_enabled=True)
    p2 = DeepRegionAuditProfile(profile_id="b", name="b", deep_regions_enabled=True)
    r1 = DeepRegionAuditResult(profile=p1, deep_region_net_gain=0.1, passed=True)
    r2 = DeepRegionAuditResult(profile=p2, deep_region_net_gain=0.2, passed=True)
    best = DeepRegionAuditor._select_best_profile([r1, r2])
    assert best is not None
    assert best.profile.profile_id == "b"


def test_select_best_profile_none():
    p1 = DeepRegionAuditProfile(profile_id="a", name="a", deep_regions_enabled=False)
    r1 = DeepRegionAuditResult(profile=p1, deep_region_net_gain=0.1, passed=True)
    best = DeepRegionAuditor._select_best_profile([r1])
    assert best is None


# ---------------------------------------------------------------------------
# 8. Deep metrics present when deep regions enabled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deep_metrics_present_with_deep_regions():
    auditor = DeepRegionAuditor(n_adaptive_cycles=2)
    profile = DeepRegionAuditProfile(
        profile_id="d1",
        name="deep_regions_static",
        deep_regions_enabled=True,
        inter_region_plasticity_enabled=False,
        region_signal_routing_enabled=False,
    )
    result = await auditor.run_profile(profile)
    assert result.passed is True
    # Metrics may be zero but should be present (not None)
    assert isinstance(result.limbic_salience_score, float)
    assert isinstance(result.cerebellar_error_correction_score, float)
    assert isinstance(result.default_mode_consolidation_score, float)
    assert isinstance(result.brainstem_homeostatic_stability_score, float)


@pytest.mark.asyncio
async def test_deep_metrics_absent_without_deep_regions():
    auditor = DeepRegionAuditor(n_adaptive_cycles=2)
    profile = DeepRegionAuditProfile(
        profile_id="d0",
        name="four_region_baseline",
        deep_regions_enabled=False,
        inter_region_plasticity_enabled=True,
        region_signal_routing_enabled=False,
    )
    result = await auditor.run_profile(profile)
    assert result.passed is True
    # 4-region baseline has no limbic/cerebellar/default_mode/brainstem
    assert result.limbic_salience_score == 0.0
    assert result.cerebellar_error_correction_score == 0.0
    assert result.default_mode_consolidation_score == 0.0
    assert result.brainstem_homeostatic_stability_score == 0.0
    # deep_region_count should be 4 (not 8)
    assert result.benchmark_metrics.get("deep_region_count", 0) == 4
