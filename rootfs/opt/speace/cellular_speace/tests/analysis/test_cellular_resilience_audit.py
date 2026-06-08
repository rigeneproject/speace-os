import pytest

from speace_core.cellular_brain.analysis.cellular_resilience_audit import (
    CellularResilienceAuditReport,
    CellularResilienceAuditor,
    CellularResilienceMetrics,
    CellularResilienceProfile,
    CellularResilienceProfileResult,
)


# ------------------------------------------------------------------ #
# Construction
# ------------------------------------------------------------------ #

def test_auditor_importable():
    assert CellularResilienceAuditor is not None


def test_default_profiles():
    profiles = CellularResilienceAuditor.default_profiles()
    assert len(profiles) == 11
    ids = [p.profile_id for p in profiles]
    assert "cr0" in ids
    assert "cr6" in ids
    assert "cr10" in ids


def test_profile_model():
    p = CellularResilienceProfile(profile_id="x", name="test")
    assert p.cellular_defense_enabled is False


# ------------------------------------------------------------------ #
# Audit suite (lightweight subset)
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_run_audit_suite():
    auditor = CellularResilienceAuditor(seed=42)
    # Use only first 3 profiles and reduce ticks for speed
    profiles = CellularResilienceAuditor.default_profiles()[:3]
    for pr in profiles:
        pr.n_ticks = 5
    report = await auditor.run_audit_suite(profiles=profiles)
    assert isinstance(report, CellularResilienceAuditReport)
    assert report.audit_id.startswith("t42c-")
    assert len(report.profile_results) == 2


@pytest.mark.asyncio
async def test_baseline_exists():
    auditor = CellularResilienceAuditor(seed=42)
    profiles = CellularResilienceAuditor.default_profiles()[:3]
    for pr in profiles:
        pr.n_ticks = 5
    report = await auditor.run_audit_suite(profiles=profiles)
    assert report.baseline_result.profile.name == "cellular_defense_repair_off"


@pytest.mark.asyncio
async def test_profile_results_have_metrics():
    auditor = CellularResilienceAuditor(seed=42)
    profiles = CellularResilienceAuditor.default_profiles()[:3]
    for pr in profiles:
        pr.n_ticks = 5
    report = await auditor.run_audit_suite(profiles=profiles)
    for r in report.profile_results:
        assert isinstance(r.metrics, CellularResilienceMetrics)


@pytest.mark.asyncio
async def test_reports_generated():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        auditor = CellularResilienceAuditor(seed=42, report_dir=td)
        profiles = CellularResilienceAuditor.default_profiles()[:3]
        for pr in profiles:
            pr.n_ticks = 5
        report = await auditor.run_audit_suite(profiles=profiles)
        assert report.json_report_path is not None
        assert report.markdown_report_path is not None
        assert Path(report.json_report_path).exists()
        assert Path(report.markdown_report_path).exists()


# ------------------------------------------------------------------ #
# Verdict logic
# ------------------------------------------------------------------ #

def test_verdict_insufficient_evidence_empty_profiles():
    baseline = CellularResilienceProfileResult(
        profile=CellularResilienceProfile(profile_id="b", name="baseline")
    )
    verdict = CellularResilienceAuditor._compute_verdict(baseline, [], None)
    assert verdict == "INSUFFICIENT_EVIDENCE"


def test_select_best_profile():
    p1 = CellularResilienceProfile(profile_id="a", name="good", cellular_defense_enabled=True)
    p2 = CellularResilienceProfile(profile_id="b", name="bad", cellular_defense_enabled=True)
    r1 = CellularResilienceProfileResult(
        profile=p1,
        metrics=CellularResilienceMetrics(
            cellular_resilience_score=0.8,
            cognitive_score=0.6,
            cellular_survival_score=0.7,
            mean_cellular_stress=0.1,
            mean_damage_score=0.1,
            energy_efficiency=0.5,
        ),
    )
    r2 = CellularResilienceProfileResult(
        profile=p2,
        metrics=CellularResilienceMetrics(
            cellular_resilience_score=0.2,
            cognitive_score=0.3,
            cellular_survival_score=0.3,
            mean_cellular_stress=0.8,
            mean_damage_score=0.8,
            energy_efficiency=0.2,
        ),
    )
    best = CellularResilienceAuditor._select_best_profile([r1, r2])
    assert best == "good"


def test_select_best_profile_skips_failed():
    p1 = CellularResilienceProfile(profile_id="a", name="failed", cellular_defense_enabled=True)
    p2 = CellularResilienceProfile(profile_id="b", name="passed", cellular_defense_enabled=True)
    r1 = CellularResilienceProfileResult(profile=p1, passed=False)
    r2 = CellularResilienceProfileResult(
        profile=p2,
        metrics=CellularResilienceMetrics(
            cellular_resilience_score=0.5,
            cognitive_score=0.4,
            cellular_survival_score=0.5,
            mean_cellular_stress=0.3,
            mean_damage_score=0.3,
            energy_efficiency=0.4,
        ),
    )
    best = CellularResilienceAuditor._select_best_profile([r1, r2])
    assert best == "passed"


def test_verdict_repair_weak():
    baseline = CellularResilienceProfileResult(
        profile=CellularResilienceProfile(profile_id="b", name="baseline"),
        metrics=CellularResilienceMetrics(cognitive_score=0.5, energy_efficiency=0.5),
    )
    p = CellularResilienceProfile(profile_id="x", name="repair_defense")
    r = CellularResilienceProfileResult(
        profile=p,
        metrics=CellularResilienceMetrics(
            cognitive_score=0.5,
            energy_efficiency=0.5,
            repair_success_rate=0.1,
            repair_failure_rate=0.8,
            cellular_resilience_score=0.1,
        ),
    )
    verdict = CellularResilienceAuditor._compute_verdict(baseline, [r], None)
    assert verdict == "CELLULAR_REPAIR_WEAK"


def test_verdict_defense_overactive():
    baseline = CellularResilienceProfileResult(
        profile=CellularResilienceProfile(profile_id="b", name="baseline"),
        metrics=CellularResilienceMetrics(cognitive_score=1.0, energy_efficiency=0.5),
    )
    p = CellularResilienceProfile(profile_id="x", name="defense_only")
    r = CellularResilienceProfileResult(
        profile=p,
        metrics=CellularResilienceMetrics(
            cognitive_score=0.89,  # below 90% of baseline but above 85%
            energy_efficiency=0.5,
            plasticity_locks=1,
            repair_success_rate=0.5,
            cellular_resilience_score=0.5,
        ),
    )
    verdict = CellularResilienceAuditor._compute_verdict(baseline, [r], None)
    assert verdict == "CELLULAR_DEFENSE_OVERACTIVE"


def test_verdict_resilience_validated():
    baseline = CellularResilienceProfileResult(
        profile=CellularResilienceProfile(profile_id="b", name="baseline"),
        metrics=CellularResilienceMetrics(
            cognitive_score=0.5, energy_efficiency=0.5, cellular_resilience_score=0.1
        ),
    )
    p = CellularResilienceProfile(profile_id="x", name="full")
    r = CellularResilienceProfileResult(
        profile=p,
        metrics=CellularResilienceMetrics(
            cognitive_score=0.5,
            energy_efficiency=0.5,
            repair_success_rate=0.5,
            cellular_resilience_score=0.5,
        ),
    )
    verdict = CellularResilienceAuditor._compute_verdict(baseline, [r], None)
    assert verdict == "CELLULAR_RESILIENCE_VALIDATED"


def test_verdict_epigenetic_no_effect():
    baseline = CellularResilienceProfileResult(
        profile=CellularResilienceProfile(profile_id="b", name="baseline"),
        metrics=CellularResilienceMetrics(
            cognitive_score=0.5, energy_efficiency=0.5, cellular_resilience_score=0.1
        ),
    )
    p = CellularResilienceProfile(profile_id="x", name="epi", cellular_epigenetics_enabled=True)
    r = CellularResilienceProfileResult(
        profile=p,
        metrics=CellularResilienceMetrics(
            cognitive_score=0.5,
            energy_efficiency=0.5,
            repair_success_rate=0.5,
            cellular_resilience_score=0.1,
            epigenetic_adaptation_score=0.0,
        ),
    )
    verdict = CellularResilienceAuditor._compute_verdict(baseline, [r], None)
    assert verdict == "CELLULAR_EPIGENETIC_NO_EFFECT"


def test_verdict_cognitive_regression():
    baseline = CellularResilienceProfileResult(
        profile=CellularResilienceProfile(profile_id="b", name="baseline"),
        metrics=CellularResilienceMetrics(cognitive_score=1.0, energy_efficiency=0.5),
    )
    p = CellularResilienceProfile(profile_id="x", name="full")
    r = CellularResilienceProfileResult(
        profile=p,
        metrics=CellularResilienceMetrics(
            cognitive_score=0.1,  # < 0.85
            energy_efficiency=0.5,
            cellular_resilience_score=0.1,
        ),
    )
    verdict = CellularResilienceAuditor._compute_verdict(baseline, [r], None)
    assert verdict == "CELLULAR_COGNITIVE_REGRESSION"


def test_verdict_energy_regression():
    baseline = CellularResilienceProfileResult(
        profile=CellularResilienceProfile(profile_id="b", name="baseline"),
        metrics=CellularResilienceMetrics(cognitive_score=0.5, energy_efficiency=1.0),
    )
    p = CellularResilienceProfile(profile_id="x", name="full")
    r = CellularResilienceProfileResult(
        profile=p,
        metrics=CellularResilienceMetrics(
            cognitive_score=0.5,
            energy_efficiency=0.1,  # < 0.85
            cellular_resilience_score=0.1,
        ),
    )
    verdict = CellularResilienceAuditor._compute_verdict(baseline, [r], None)
    assert verdict == "CELLULAR_ENERGY_REGRESSION"
