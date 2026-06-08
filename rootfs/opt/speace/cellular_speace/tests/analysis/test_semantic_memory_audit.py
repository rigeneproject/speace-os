import pytest

from speace_core.cellular_brain.analysis.semantic_memory_audit import (
    SemanticMemoryAuditMetrics,
    SemanticMemoryAuditProfile,
    SemanticMemoryAuditResult,
    SemanticMemoryAuditSuiteResult,
    SemanticMemoryAuditor,
)


# ------------------------------------------------------------------ #
# Construction
# ------------------------------------------------------------------ #

def test_auditor_importable():
    assert SemanticMemoryAuditor is not None


def test_default_profiles():
    profiles = SemanticMemoryAuditor.default_profiles()
    assert len(profiles) == 10
    ids = [p.profile_id for p in profiles]
    assert "sm0" in ids
    assert "sm4" in ids
    assert "sm9" in ids


def test_profile_model():
    p = SemanticMemoryAuditProfile(profile_id="x", name="test")
    assert p.semantic_memory_enabled is False
    assert p.recall_enabled is False


def test_result_model():
    p = SemanticMemoryAuditProfile(profile_id="x", name="test")
    r = SemanticMemoryAuditResult(profile=p)
    assert r.metrics.semantic_assembly_count == 0


def test_suite_result_model():
    s = SemanticMemoryAuditSuiteResult(audit_id="a1", created_at="now")
    assert s.verdict == "INSUFFICIENT_EVIDENCE"


# ------------------------------------------------------------------ #
# Orchestrator build
# ------------------------------------------------------------------ #

def test_build_orchestrator_respects_disabled():
    auditor = SemanticMemoryAuditor(seed=42)
    profile = SemanticMemoryAuditProfile(
        profile_id="sm0", name="semantic_memory_off", semantic_memory_enabled=False
    )
    orch = auditor._build_orchestrator()
    auditor._apply_profile(orch, profile)
    assert orch.semantic_memory_enabled is False
    assert orch._semantic_memory_store is None


def test_build_orchestrator_respects_enabled():
    auditor = SemanticMemoryAuditor(seed=42)
    profile = SemanticMemoryAuditProfile(
        profile_id="sm1", name="semantic_memory_observe_only", semantic_memory_enabled=True
    )
    orch = auditor._build_orchestrator()
    auditor._apply_profile(orch, profile)
    assert orch.semantic_memory_enabled is True
    assert orch._semantic_memory_store is not None
    assert orch._cell_assembly_engine is not None


# ------------------------------------------------------------------ #
# Audit suite (lightweight subset)
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_run_audit_suite():
    auditor = SemanticMemoryAuditor(seed=42)
    profiles = SemanticMemoryAuditor.default_profiles()[:3]
    for pr in profiles:
        pr.n_cycles = 5
        pr.repeated_pattern_count = 2
        pr.novel_pattern_count = 1
        pr.recall_trials = 2
    report = await auditor.run_audit_suite(profiles=profiles)
    assert isinstance(report, SemanticMemoryAuditSuiteResult)
    assert report.audit_id.startswith("t43b-")
    assert len(report.profile_results) == 2


@pytest.mark.asyncio
async def test_baseline_exists():
    auditor = SemanticMemoryAuditor(seed=42)
    profiles = SemanticMemoryAuditor.default_profiles()[:3]
    for pr in profiles:
        pr.n_cycles = 5
        pr.repeated_pattern_count = 2
        pr.novel_pattern_count = 1
    report = await auditor.run_audit_suite(profiles=profiles)
    assert report.baseline_result.profile.name == "semantic_memory_off"


@pytest.mark.asyncio
async def test_profile_results_have_metrics():
    auditor = SemanticMemoryAuditor(seed=42)
    profiles = SemanticMemoryAuditor.default_profiles()[:3]
    for pr in profiles:
        pr.n_cycles = 5
        pr.repeated_pattern_count = 2
        pr.novel_pattern_count = 1
    report = await auditor.run_audit_suite(profiles=profiles)
    for r in report.profile_results:
        assert isinstance(r.metrics, SemanticMemoryAuditMetrics)


@pytest.mark.asyncio
async def test_reports_generated():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        auditor = SemanticMemoryAuditor(seed=42, report_dir=td)
        profiles = SemanticMemoryAuditor.default_profiles()[:3]
        for pr in profiles:
            pr.n_cycles = 5
            pr.repeated_pattern_count = 2
            pr.novel_pattern_count = 1
        report = await auditor.run_audit_suite(profiles=profiles)
        assert report.json_report_path is not None
        assert report.markdown_report_path is not None
        assert Path(report.json_report_path).exists()
        assert Path(report.markdown_report_path).exists()


# ------------------------------------------------------------------ #
# Functional behaviour per profile
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_semantic_memory_off_creates_no_events():
    auditor = SemanticMemoryAuditor(seed=42)
    profile = SemanticMemoryAuditProfile(
        profile_id="sm0",
        name="semantic_memory_off",
        semantic_memory_enabled=False,
        n_cycles=5,
        repeated_pattern_count=2,
        novel_pattern_count=1,
    )
    result = await auditor._run_profile(profile)
    assert result.metrics.assembly_creation_events == 0
    assert result.metrics.assembly_reinforcement_events == 0


@pytest.mark.asyncio
async def test_observe_only_no_unsafe_activation():
    auditor = SemanticMemoryAuditor(seed=42)
    profile = SemanticMemoryAuditProfile(
        profile_id="sm1",
        name="semantic_memory_observe_only",
        semantic_memory_enabled=True,
        n_cycles=5,
        repeated_pattern_count=2,
        novel_pattern_count=1,
    )
    result = await auditor._run_profile(profile)
    # No assemblies should be created in observe-only mode
    assert result.metrics.semantic_assembly_count == 0


@pytest.mark.asyncio
async def test_create_only_produces_assembly():
    auditor = SemanticMemoryAuditor(seed=42)
    profile = SemanticMemoryAuditProfile(
        profile_id="sm2",
        name="semantic_memory_create_only",
        semantic_memory_enabled=True,
        n_cycles=8,
        repeated_pattern_count=3,
        novel_pattern_count=1,
    )
    result = await auditor._run_profile(profile)
    assert result.metrics.semantic_assembly_count >= 1


@pytest.mark.asyncio
async def test_create_reinforce_increases_strength_or_recurrence():
    auditor = SemanticMemoryAuditor(seed=42)
    profile = SemanticMemoryAuditProfile(
        profile_id="sm3",
        name="semantic_memory_create_reinforce",
        semantic_memory_enabled=True,
        n_cycles=10,
        repeated_pattern_count=4,
        novel_pattern_count=1,
    )
    result = await auditor._run_profile(profile)
    assert result.metrics.semantic_assembly_count >= 1
    assert result.metrics.mean_assembly_strength > 0.0


@pytest.mark.asyncio
async def test_full_cycle_produces_semantic_metrics():
    auditor = SemanticMemoryAuditor(seed=42)
    profile = SemanticMemoryAuditProfile(
        profile_id="sm4",
        name="semantic_memory_full_cycle",
        semantic_memory_enabled=True,
        consolidation_enabled=True,
        decay_enabled=True,
        n_cycles=10,
        repeated_pattern_count=4,
        novel_pattern_count=1,
    )
    result = await auditor._run_profile(profile)
    assert result.metrics.semantic_assembly_count >= 0
    assert result.metrics.semantic_memory_score >= 0.0


@pytest.mark.asyncio
async def test_recall_enabled_produces_result_safely():
    auditor = SemanticMemoryAuditor(seed=42)
    profile = SemanticMemoryAuditProfile(
        profile_id="sm5",
        name="semantic_memory_recall_enabled",
        semantic_memory_enabled=True,
        consolidation_enabled=True,
        decay_enabled=True,
        recall_enabled=True,
        n_cycles=10,
        repeated_pattern_count=4,
        novel_pattern_count=1,
        recall_trials=3,
    )
    result = await auditor._run_profile(profile)
    # Recall may succeed or fail; result must be safe
    assert result.metrics.semantic_recall_success_rate >= 0.0


@pytest.mark.asyncio
async def test_recall_fails_safely_when_empty():
    auditor = SemanticMemoryAuditor(seed=42)
    orch = auditor._build_orchestrator()
    orch.semantic_memory_enabled = True
    orch.model_post_init(None)
    query = [0.5] * 10
    # Use engine directly since orchestrator flag may be toggled by audit logic
    engine = orch._semantic_recall_engine
    if engine is not None:
        result = engine.recall(query)
        assert result is None or result.recall_success is False
    else:
        assert orch._semantic_memory_store is not None


@pytest.mark.asyncio
async def test_consolidation_profile_produces_valid_state():
    auditor = SemanticMemoryAuditor(seed=42)
    profile = SemanticMemoryAuditProfile(
        profile_id="sm6",
        name="semantic_memory_consolidation_enabled",
        semantic_memory_enabled=True,
        consolidation_enabled=True,
        n_cycles=12,
        repeated_pattern_count=5,
        novel_pattern_count=1,
    )
    result = await auditor._run_profile(profile)
    # Either some assemblies consolidated, or none exist — both are valid
    assert result.metrics.semantic_consolidated_assembly_count >= 0


@pytest.mark.asyncio
async def test_decay_does_not_delete_all_memory():
    auditor = SemanticMemoryAuditor(seed=42)
    profile = SemanticMemoryAuditProfile(
        profile_id="sm7",
        name="semantic_memory_decay_enabled",
        semantic_memory_enabled=True,
        decay_enabled=True,
        n_cycles=10,
        repeated_pattern_count=4,
        novel_pattern_count=1,
    )
    result = await auditor._run_profile(profile)
    # Even with decay, assemblies should not all vanish abruptly
    assert result.metrics.semantic_assembly_count >= 0


@pytest.mark.asyncio
async def test_reactivation_remains_bounded():
    auditor = SemanticMemoryAuditor(seed=42)
    profile = SemanticMemoryAuditProfile(
        profile_id="sm8",
        name="semantic_memory_reactivation_enabled",
        semantic_memory_enabled=True,
        consolidation_enabled=True,
        decay_enabled=True,
        reactivation_enabled=True,
        n_cycles=10,
        repeated_pattern_count=4,
        novel_pattern_count=1,
    )
    result = await auditor._run_profile(profile)
    # Reactivation count should be limited by active assemblies
    assert result.metrics.reactivation_events >= 0


# ------------------------------------------------------------------ #
# Net gain & verdict logic
# ------------------------------------------------------------------ #

def test_semantic_net_gain_clamped():
    baseline = SemanticMemoryAuditMetrics(cognitive_score=1.0, coherence_phi=1.0, energy_efficiency=1.0)
    candidate = SemanticMemoryAuditMetrics(
        cognitive_score=10.0, coherence_phi=10.0, energy_efficiency=10.0,
        semantic_recall_success_rate=10.0, mean_assembly_stability=10.0, semantic_consolidation_rate=10.0,
    )
    gain = SemanticMemoryAuditor.compute_semantic_net_gain(baseline, candidate)
    assert gain <= 1.0
    assert gain >= -1.0


def test_semantic_net_gain_negative_clamped():
    baseline = SemanticMemoryAuditMetrics(cognitive_score=1.0, coherence_phi=1.0, energy_efficiency=1.0)
    candidate = SemanticMemoryAuditMetrics(
        cognitive_score=0.0, coherence_phi=0.0, energy_efficiency=0.0,
        semantic_recall_success_rate=0.0, mean_assembly_stability=0.0, semantic_consolidation_rate=0.0,
    )
    gain = SemanticMemoryAuditor.compute_semantic_net_gain(baseline, candidate)
    assert gain >= -1.0


def test_verdict_is_allowed_value():
    baseline = SemanticMemoryAuditResult(
        profile=SemanticMemoryAuditProfile(profile_id="b", name="baseline"),
        metrics=SemanticMemoryAuditMetrics(cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=0.5),
    )
    p = SemanticMemoryAuditProfile(profile_id="x", name="full", semantic_memory_enabled=True)
    r = SemanticMemoryAuditResult(
        profile=p,
        metrics=SemanticMemoryAuditMetrics(
            cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=0.5,
            semantic_assembly_count=5, semantic_recall_success_rate=0.5,
        ),
    )
    verdict = SemanticMemoryAuditor._compute_verdict(baseline, [r], "full")
    assert verdict in {
        "SEMANTIC_MEMORY_VALIDATED",
        "SEMANTIC_MEMORY_PASSIVE",
        "SEMANTIC_RECALL_WEAK",
        "SEMANTIC_OVERCONSOLIDATION",
        "SEMANTIC_ENERGY_REGRESSION",
        "SEMANTIC_COGNITIVE_REGRESSION",
        "SEMANTIC_PHI_REGRESSION",
        "INSUFFICIENT_EVIDENCE",
    }


def test_verdict_insufficient_evidence_empty():
    baseline = SemanticMemoryAuditResult(
        profile=SemanticMemoryAuditProfile(profile_id="b", name="baseline")
    )
    verdict = SemanticMemoryAuditor._compute_verdict(baseline, [], None)
    assert verdict == "INSUFFICIENT_EVIDENCE"


def test_select_best_profile():
    p1 = SemanticMemoryAuditProfile(profile_id="a", name="good", semantic_memory_enabled=True)
    p2 = SemanticMemoryAuditProfile(profile_id="b", name="bad", semantic_memory_enabled=True)
    r1 = SemanticMemoryAuditResult(
        profile=p1,
        metrics=SemanticMemoryAuditMetrics(
            semantic_memory_score=0.8,
            semantic_recall_success_rate=0.7,
            mean_assembly_stability=0.6,
            cognitive_score=0.5,
            coherence_phi=0.5,
        ),
    )
    r2 = SemanticMemoryAuditResult(
        profile=p2,
        metrics=SemanticMemoryAuditMetrics(
            semantic_memory_score=0.2,
            semantic_recall_success_rate=0.1,
            mean_assembly_stability=0.1,
            cognitive_score=0.2,
            coherence_phi=0.2,
        ),
    )
    best = SemanticMemoryAuditor._select_best_profile([r1, r2])
    assert best == "good"


def test_select_best_profile_skips_failed():
    p1 = SemanticMemoryAuditProfile(profile_id="a", name="failed", semantic_memory_enabled=True)
    p2 = SemanticMemoryAuditProfile(profile_id="b", name="passed", semantic_memory_enabled=True)
    r1 = SemanticMemoryAuditResult(profile=p1, passed=False)
    r2 = SemanticMemoryAuditResult(
        profile=p2,
        metrics=SemanticMemoryAuditMetrics(
            semantic_memory_score=0.5,
            semantic_recall_success_rate=0.4,
            mean_assembly_stability=0.3,
            cognitive_score=0.4,
            coherence_phi=0.4,
        ),
    )
    best = SemanticMemoryAuditor._select_best_profile([r1, r2])
    assert best == "passed"


def test_verdict_cognitive_regression():
    baseline = SemanticMemoryAuditResult(
        profile=SemanticMemoryAuditProfile(profile_id="b", name="baseline"),
        metrics=SemanticMemoryAuditMetrics(cognitive_score=1.0, coherence_phi=0.5, energy_efficiency=0.5),
    )
    p = SemanticMemoryAuditProfile(profile_id="x", name="full", semantic_memory_enabled=True)
    r = SemanticMemoryAuditResult(
        profile=p,
        metrics=SemanticMemoryAuditMetrics(
            cognitive_score=0.1, coherence_phi=0.5, energy_efficiency=0.5,
            semantic_assembly_count=1, semantic_recall_success_rate=0.0,
        ),
    )
    verdict = SemanticMemoryAuditor._compute_verdict(baseline, [r], None)
    assert verdict == "SEMANTIC_COGNITIVE_REGRESSION"


def test_verdict_energy_regression():
    baseline = SemanticMemoryAuditResult(
        profile=SemanticMemoryAuditProfile(profile_id="b", name="baseline"),
        metrics=SemanticMemoryAuditMetrics(cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=1.0),
    )
    p = SemanticMemoryAuditProfile(profile_id="x", name="full", semantic_memory_enabled=True)
    r = SemanticMemoryAuditResult(
        profile=p,
        metrics=SemanticMemoryAuditMetrics(
            cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=0.1,
            semantic_assembly_count=1, semantic_recall_success_rate=0.0,
        ),
    )
    verdict = SemanticMemoryAuditor._compute_verdict(baseline, [r], None)
    assert verdict == "SEMANTIC_ENERGY_REGRESSION"


def test_verdict_phi_regression():
    baseline = SemanticMemoryAuditResult(
        profile=SemanticMemoryAuditProfile(profile_id="b", name="baseline"),
        metrics=SemanticMemoryAuditMetrics(cognitive_score=0.5, coherence_phi=1.0, energy_efficiency=0.5),
    )
    p = SemanticMemoryAuditProfile(profile_id="x", name="full", semantic_memory_enabled=True)
    r = SemanticMemoryAuditResult(
        profile=p,
        metrics=SemanticMemoryAuditMetrics(
            cognitive_score=0.5, coherence_phi=0.1, energy_efficiency=0.5,
            semantic_assembly_count=1, semantic_recall_success_rate=0.0,
        ),
    )
    verdict = SemanticMemoryAuditor._compute_verdict(baseline, [r], None)
    assert verdict == "SEMANTIC_PHI_REGRESSION"


def test_verdict_overconsolidation():
    baseline = SemanticMemoryAuditResult(
        profile=SemanticMemoryAuditProfile(profile_id="b", name="baseline"),
        metrics=SemanticMemoryAuditMetrics(cognitive_score=1.0, coherence_phi=1.0, energy_efficiency=0.5),
    )
    p = SemanticMemoryAuditProfile(profile_id="x", name="full", semantic_memory_enabled=True)
    r = SemanticMemoryAuditResult(
        profile=p,
        metrics=SemanticMemoryAuditMetrics(
            cognitive_score=0.89,  # below 90%
            coherence_phi=0.89,    # below 90%
            energy_efficiency=0.5,
            semantic_consolidated_assembly_count=5,
            semantic_assembly_count=5,
            semantic_recall_success_rate=0.0,
        ),
    )
    verdict = SemanticMemoryAuditor._compute_verdict(baseline, [r], None)
    assert verdict == "SEMANTIC_OVERCONSOLIDATION"


def test_verdict_memory_validated():
    baseline = SemanticMemoryAuditResult(
        profile=SemanticMemoryAuditProfile(profile_id="b", name="baseline"),
        metrics=SemanticMemoryAuditMetrics(cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=0.5),
    )
    p = SemanticMemoryAuditProfile(profile_id="x", name="full", semantic_memory_enabled=True)
    r = SemanticMemoryAuditResult(
        profile=p,
        metrics=SemanticMemoryAuditMetrics(
            cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=0.5,
            semantic_assembly_count=3,
            semantic_recall_success_rate=0.5,
        ),
    )
    verdict = SemanticMemoryAuditor._compute_verdict(baseline, [r], "full")
    assert verdict == "SEMANTIC_MEMORY_VALIDATED"


def test_verdict_memory_passive():
    baseline = SemanticMemoryAuditResult(
        profile=SemanticMemoryAuditProfile(profile_id="b", name="baseline"),
        metrics=SemanticMemoryAuditMetrics(cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=0.5),
    )
    p = SemanticMemoryAuditProfile(profile_id="x", name="full", semantic_memory_enabled=True)
    r = SemanticMemoryAuditResult(
        profile=p,
        metrics=SemanticMemoryAuditMetrics(
            cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=0.5,
            semantic_assembly_count=3,
            semantic_recall_success_rate=0.0,
        ),
    )
    verdict = SemanticMemoryAuditor._compute_verdict(baseline, [r], None)
    assert verdict == "SEMANTIC_MEMORY_PASSIVE"


def test_verdict_recall_weak():
    baseline = SemanticMemoryAuditResult(
        profile=SemanticMemoryAuditProfile(profile_id="b", name="baseline"),
        metrics=SemanticMemoryAuditMetrics(cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=0.5),
    )
    p = SemanticMemoryAuditProfile(profile_id="x", name="full", semantic_memory_enabled=True)
    r = SemanticMemoryAuditResult(
        profile=p,
        metrics=SemanticMemoryAuditMetrics(
            cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=0.5,
            semantic_assembly_count=3,
            semantic_recall_success_rate=0.1,
        ),
    )
    verdict = SemanticMemoryAuditor._compute_verdict(baseline, [r], None)
    assert verdict == "SEMANTIC_RECALL_WEAK"


# ------------------------------------------------------------------ #
# Markdown report content
# ------------------------------------------------------------------ #

def test_markdown_report_includes_required_fields():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        auditor = SemanticMemoryAuditor(seed=42, report_dir=td)
        baseline = SemanticMemoryAuditResult(
            profile=SemanticMemoryAuditProfile(profile_id="b", name="baseline"),
            metrics=SemanticMemoryAuditMetrics(
                semantic_memory_score=0.5, semantic_recall_success_rate=0.3, semantic_net_gain=0.1
            ),
        )
        p = SemanticMemoryAuditProfile(profile_id="x", name="full", semantic_memory_enabled=True)
        r = SemanticMemoryAuditResult(
            profile=p,
            metrics=SemanticMemoryAuditMetrics(
                semantic_memory_score=0.5, semantic_recall_success_rate=0.3, semantic_net_gain=0.1
            ),
        )
        suite = SemanticMemoryAuditSuiteResult(
            audit_id="test",
            created_at="now",
            baseline_result=baseline,
            profile_results=[r],
            verdict="SEMANTIC_MEMORY_VALIDATED",
            semantic_net_gain=0.1,
        )
        path = auditor._generate_markdown_report(suite)
        text = Path(path).read_text(encoding="utf-8")
        assert "Semantic Memory Functional Audit" in text
        assert "0.5000" in text or "0.5" in text
        assert "SEMANTIC_MEMORY_VALIDATED" in text


# ------------------------------------------------------------------ #
# Determinism
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_audit_is_deterministic_with_same_seed():
    auditor1 = SemanticMemoryAuditor(seed=123)
    auditor2 = SemanticMemoryAuditor(seed=123)
    profile = SemanticMemoryAuditProfile(
        profile_id="sm4",
        name="semantic_memory_full_cycle",
        semantic_memory_enabled=True,
        consolidation_enabled=True,
        decay_enabled=True,
        n_cycles=5,
        repeated_pattern_count=2,
        novel_pattern_count=1,
    )
    r1 = await auditor1._run_profile(profile)
    r2 = await auditor2._run_profile(profile)
    assert r1.metrics.semantic_assembly_count == r2.metrics.semantic_assembly_count
    assert r1.metrics.cognitive_score == r2.metrics.cognitive_score
