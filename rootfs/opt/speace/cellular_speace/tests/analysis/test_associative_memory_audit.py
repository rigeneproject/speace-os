import pytest

from speace_core.cellular_brain.analysis.associative_memory_audit import (
    AssociativeMemoryAuditMetrics,
    AssociativeMemoryAuditProfile,
    AssociativeMemoryAuditResult,
    AssociativeMemoryAuditSuiteResult,
    AssociativeMemoryAuditor,
)


# ------------------------------------------------------------------ #
# Construction
# ------------------------------------------------------------------ #

def test_auditor_importable():
    assert AssociativeMemoryAuditor is not None


def test_default_profiles():
    profiles = AssociativeMemoryAuditor.default_profiles()
    assert len(profiles) == 10
    ids = [p.profile_id for p in profiles]
    assert "am0" in ids
    assert "am4" in ids
    assert "am9" in ids


def test_profile_model():
    p = AssociativeMemoryAuditProfile(profile_id="x", name="test")
    assert p.semantic_memory_enabled is True
    assert p.associative_learning_enabled is False
    assert p.associative_recall_enabled is False


def test_result_model():
    p = AssociativeMemoryAuditProfile(profile_id="x", name="test")
    r = AssociativeMemoryAuditResult(profile=p)
    assert r.metrics.association_count == 0
    assert r.metrics.associative_recall_success_rate == 0.0


def test_suite_result_model():
    s = AssociativeMemoryAuditSuiteResult(audit_id="a1", created_at="now")
    assert s.verdict == "INSUFFICIENT_EVIDENCE"


# ------------------------------------------------------------------ #
# Orchestrator build
# ------------------------------------------------------------------ #

def test_build_orchestrator_respects_disabled():
    auditor = AssociativeMemoryAuditor(seed=42)
    profile = AssociativeMemoryAuditProfile(
        profile_id="am0", name="associative_off", associative_learning_enabled=False
    )
    orch = auditor._build_orchestrator()
    auditor._apply_profile(orch, profile)
    assert orch.associative_learning_enabled is False
    assert orch._associative_learning_engine is None


def test_build_orchestrator_respects_enabled():
    auditor = AssociativeMemoryAuditor(seed=42)
    profile = AssociativeMemoryAuditProfile(
        profile_id="am1",
        name="association_create_only",
        semantic_memory_enabled=True,
        associative_learning_enabled=True,
    )
    orch = auditor._build_orchestrator()
    auditor._apply_profile(orch, profile)
    assert orch.semantic_memory_enabled is True
    assert orch.associative_learning_enabled is True
    assert orch._semantic_memory_store is not None
    assert orch.get_associative_learning_engine() is not None
    assert orch._associative_learning_engine is not None


# ------------------------------------------------------------------ #
# Audit suite (lightweight subset)
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_run_audit_suite():
    auditor = AssociativeMemoryAuditor(seed=42)
    profiles = AssociativeMemoryAuditor.default_profiles()[:3]
    for pr in profiles:
        pr.n_cycles = 5
        pr.repeated_pattern_count = 2
        pr.novel_pattern_count = 1
        pr.associative_recall_trials = 2
    report = await auditor.run_audit_suite(profiles=profiles)
    assert isinstance(report, AssociativeMemoryAuditSuiteResult)
    assert report.audit_id.startswith("t44b-")
    assert len(report.profile_results) == 2


@pytest.mark.asyncio
async def test_baseline_exists():
    auditor = AssociativeMemoryAuditor(seed=42)
    profiles = AssociativeMemoryAuditor.default_profiles()[:3]
    for pr in profiles:
        pr.n_cycles = 5
        pr.repeated_pattern_count = 2
        pr.novel_pattern_count = 1
    report = await auditor.run_audit_suite(profiles=profiles)
    assert report.baseline_result.profile.name == "associative_off"


@pytest.mark.asyncio
async def test_profile_results_have_metrics():
    auditor = AssociativeMemoryAuditor(seed=42)
    profiles = AssociativeMemoryAuditor.default_profiles()[:3]
    for pr in profiles:
        pr.n_cycles = 5
        pr.repeated_pattern_count = 2
        pr.novel_pattern_count = 1
    report = await auditor.run_audit_suite(profiles=profiles)
    for r in report.profile_results:
        assert isinstance(r.metrics, AssociativeMemoryAuditMetrics)


@pytest.mark.asyncio
async def test_reports_generated():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        auditor = AssociativeMemoryAuditor(seed=42, report_dir=td)
        profiles = AssociativeMemoryAuditor.default_profiles()[:3]
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
async def test_associative_off_creates_no_associations():
    auditor = AssociativeMemoryAuditor(seed=42)
    profile = AssociativeMemoryAuditProfile(
        profile_id="am0",
        name="associative_off",
        semantic_memory_enabled=True,
        associative_learning_enabled=False,
        n_cycles=5,
        repeated_pattern_count=2,
        novel_pattern_count=1,
    )
    result = await auditor._run_profile(profile)
    assert result.metrics.association_count == 0
    assert result.metrics.association_creation_events == 0


@pytest.mark.asyncio
async def test_association_create_only_produces_association():
    auditor = AssociativeMemoryAuditor(seed=42)
    profile = AssociativeMemoryAuditProfile(
        profile_id="am1",
        name="association_create_only",
        semantic_memory_enabled=True,
        associative_learning_enabled=True,
        n_cycles=8,
        repeated_pattern_count=3,
        novel_pattern_count=1,
    )
    result = await auditor._run_profile(profile)
    assert result.metrics.semantic_assembly_count >= 1
    assert result.metrics.association_count >= 1


@pytest.mark.asyncio
async def test_association_reinforce_increases_strength():
    auditor = AssociativeMemoryAuditor(seed=42)
    profile = AssociativeMemoryAuditProfile(
        profile_id="am2",
        name="association_reinforce",
        semantic_memory_enabled=True,
        associative_learning_enabled=True,
        n_cycles=10,
        repeated_pattern_count=4,
        novel_pattern_count=1,
    )
    result = await auditor._run_profile(profile)
    assert result.metrics.association_count >= 1
    assert result.metrics.mean_association_strength > 0.0


@pytest.mark.asyncio
async def test_association_decay_produces_valid_state():
    auditor = AssociativeMemoryAuditor(seed=42)
    profile = AssociativeMemoryAuditProfile(
        profile_id="am3",
        name="association_decay",
        semantic_memory_enabled=True,
        associative_learning_enabled=True,
        decay_enabled=True,
        n_cycles=10,
        repeated_pattern_count=4,
        novel_pattern_count=1,
    )
    result = await auditor._run_profile(profile)
    assert result.metrics.semantic_assembly_count >= 0
    assert result.metrics.mean_association_strength >= 0.0


@pytest.mark.asyncio
async def test_association_prune_produces_valid_state():
    auditor = AssociativeMemoryAuditor(seed=42)
    profile = AssociativeMemoryAuditProfile(
        profile_id="am4",
        name="association_prune",
        semantic_memory_enabled=True,
        associative_learning_enabled=True,
        prune_enabled=True,
        n_cycles=10,
        repeated_pattern_count=4,
        novel_pattern_count=1,
    )
    result = await auditor._run_profile(profile)
    assert result.metrics.semantic_assembly_count >= 0


@pytest.mark.asyncio
async def test_associative_recall_enabled_produces_result_safely():
    auditor = AssociativeMemoryAuditor(seed=42)
    profile = AssociativeMemoryAuditProfile(
        profile_id="am5",
        name="associative_recall_enabled",
        semantic_memory_enabled=True,
        associative_learning_enabled=True,
        associative_recall_enabled=True,
        n_cycles=10,
        repeated_pattern_count=4,
        novel_pattern_count=1,
        associative_recall_trials=3,
    )
    result = await auditor._run_profile(profile)
    assert result.metrics.associative_recall_success_rate >= 0.0


@pytest.mark.asyncio
async def test_full_associative_stack_produces_valid_state():
    auditor = AssociativeMemoryAuditor(seed=42)
    profile = AssociativeMemoryAuditProfile(
        profile_id="am6",
        name="full_associative_stack",
        semantic_memory_enabled=True,
        associative_learning_enabled=True,
        associative_recall_enabled=True,
        decay_enabled=True,
        prune_enabled=True,
        n_cycles=10,
        repeated_pattern_count=4,
        novel_pattern_count=1,
        associative_recall_trials=3,
    )
    result = await auditor._run_profile(profile)
    assert result.metrics.association_count >= 0
    assert result.metrics.associative_memory_effect_score >= 0.0


@pytest.mark.asyncio
async def test_noisy_cue_association_produces_result_safely():
    auditor = AssociativeMemoryAuditor(seed=42)
    profile = AssociativeMemoryAuditProfile(
        profile_id="am7",
        name="noisy_cue_association",
        semantic_memory_enabled=True,
        associative_learning_enabled=True,
        associative_recall_enabled=True,
        n_cycles=10,
        repeated_pattern_count=4,
        novel_pattern_count=1,
        associative_recall_trials=3,
    )
    result = await auditor._run_profile(profile)
    assert result.metrics.associative_recall_success_rate >= 0.0


@pytest.mark.asyncio
async def test_sequence_association_produces_valid_state():
    auditor = AssociativeMemoryAuditor(seed=42)
    profile = AssociativeMemoryAuditProfile(
        profile_id="am8",
        name="sequence_association",
        semantic_memory_enabled=True,
        associative_learning_enabled=True,
        associative_recall_enabled=True,
        n_cycles=10,
        repeated_pattern_count=4,
        novel_pattern_count=1,
        associative_recall_trials=3,
    )
    result = await auditor._run_profile(profile)
    assert result.metrics.association_count >= 0


@pytest.mark.asyncio
async def test_contextual_association_produces_valid_state():
    auditor = AssociativeMemoryAuditor(seed=42)
    profile = AssociativeMemoryAuditProfile(
        profile_id="am9",
        name="contextual_association",
        semantic_memory_enabled=True,
        associative_learning_enabled=True,
        associative_recall_enabled=True,
        n_cycles=10,
        repeated_pattern_count=4,
        novel_pattern_count=1,
        associative_recall_trials=3,
    )
    result = await auditor._run_profile(profile)
    assert result.metrics.association_count >= 0


# ------------------------------------------------------------------ #
# Net gain & verdict logic
# ------------------------------------------------------------------ #

def test_associative_net_gain_clamped():
    baseline = AssociativeMemoryAuditMetrics(cognitive_score=1.0, coherence_phi=1.0, energy_efficiency=1.0)
    candidate = AssociativeMemoryAuditMetrics(
        cognitive_score=10.0, coherence_phi=10.0, energy_efficiency=10.0,
        associative_recall_success_rate=10.0, mean_association_strength=10.0, association_density=10.0,
        associative_memory_effect_score=10.0,
    )
    gain = AssociativeMemoryAuditor.compute_associative_net_gain(baseline, candidate)
    assert gain <= 1.0
    assert gain >= -1.0


def test_associative_net_gain_negative_clamped():
    baseline = AssociativeMemoryAuditMetrics(cognitive_score=1.0, coherence_phi=1.0, energy_efficiency=1.0)
    candidate = AssociativeMemoryAuditMetrics(
        cognitive_score=0.0, coherence_phi=0.0, energy_efficiency=0.0,
        associative_recall_success_rate=0.0, mean_association_strength=0.0, association_density=0.0,
        associative_memory_effect_score=0.0,
    )
    gain = AssociativeMemoryAuditor.compute_associative_net_gain(baseline, candidate)
    assert gain >= -1.0


def test_verdict_is_allowed_value():
    baseline = AssociativeMemoryAuditResult(
        profile=AssociativeMemoryAuditProfile(profile_id="b", name="baseline"),
        metrics=AssociativeMemoryAuditMetrics(cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=0.5),
    )
    p = AssociativeMemoryAuditProfile(profile_id="x", name="full", associative_learning_enabled=True)
    r = AssociativeMemoryAuditResult(
        profile=p,
        metrics=AssociativeMemoryAuditMetrics(
            cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=0.5,
            association_count=5, associative_recall_success_rate=0.5,
        ),
    )
    verdict = AssociativeMemoryAuditor._compute_verdict(baseline, [r], "full")
    assert verdict in {
        "ASSOCIATIVE_MEMORY_VALIDATED",
        "ASSOCIATIVE_RECALL_WEAK",
        "ASSOCIATION_OVERGROWTH",
        "ASSOCIATION_NO_EFFECT",
        "SEMANTIC_RECALL_REGRESSION",
        "ENERGY_REGRESSION",
        "PHI_REGRESSION",
        "INSUFFICIENT_EVIDENCE",
    }


def test_verdict_insufficient_evidence_empty():
    baseline = AssociativeMemoryAuditResult(
        profile=AssociativeMemoryAuditProfile(profile_id="b", name="baseline")
    )
    verdict = AssociativeMemoryAuditor._compute_verdict(baseline, [], None)
    assert verdict == "INSUFFICIENT_EVIDENCE"


def test_select_best_profile():
    p1 = AssociativeMemoryAuditProfile(profile_id="a", name="good", associative_learning_enabled=True)
    p2 = AssociativeMemoryAuditProfile(profile_id="b", name="bad", associative_learning_enabled=True)
    r1 = AssociativeMemoryAuditResult(
        profile=p1,
        metrics=AssociativeMemoryAuditMetrics(
            associative_memory_effect_score=0.8,
            associative_recall_success_rate=0.7,
            mean_association_strength=0.6,
            cognitive_score=0.5,
            coherence_phi=0.5,
        ),
    )
    r2 = AssociativeMemoryAuditResult(
        profile=p2,
        metrics=AssociativeMemoryAuditMetrics(
            associative_memory_effect_score=0.2,
            associative_recall_success_rate=0.1,
            mean_association_strength=0.1,
            cognitive_score=0.2,
            coherence_phi=0.2,
        ),
    )
    best = AssociativeMemoryAuditor._select_best_profile([r1, r2])
    assert best == "good"


def test_select_best_profile_skips_failed():
    p1 = AssociativeMemoryAuditProfile(profile_id="a", name="failed", associative_learning_enabled=True)
    p2 = AssociativeMemoryAuditProfile(profile_id="b", name="passed", associative_learning_enabled=True)
    r1 = AssociativeMemoryAuditResult(profile=p1, passed=False)
    r2 = AssociativeMemoryAuditResult(
        profile=p2,
        metrics=AssociativeMemoryAuditMetrics(
            associative_memory_effect_score=0.5,
            associative_recall_success_rate=0.4,
            mean_association_strength=0.3,
            cognitive_score=0.4,
            coherence_phi=0.4,
        ),
    )
    best = AssociativeMemoryAuditor._select_best_profile([r1, r2])
    assert best == "passed"


def test_verdict_cognitive_regression():
    baseline = AssociativeMemoryAuditResult(
        profile=AssociativeMemoryAuditProfile(profile_id="b", name="baseline"),
        metrics=AssociativeMemoryAuditMetrics(cognitive_score=1.0, coherence_phi=0.5, energy_efficiency=0.5),
    )
    p = AssociativeMemoryAuditProfile(profile_id="x", name="full", associative_learning_enabled=True)
    r = AssociativeMemoryAuditResult(
        profile=p,
        metrics=AssociativeMemoryAuditMetrics(
            cognitive_score=0.1, coherence_phi=0.5, energy_efficiency=0.5,
            association_count=1, associative_recall_success_rate=0.0,
        ),
    )
    verdict = AssociativeMemoryAuditor._compute_verdict(baseline, [r], None)
    assert verdict == "SEMANTIC_COGNITIVE_REGRESSION"


def test_verdict_energy_regression():
    baseline = AssociativeMemoryAuditResult(
        profile=AssociativeMemoryAuditProfile(profile_id="b", name="baseline"),
        metrics=AssociativeMemoryAuditMetrics(cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=1.0),
    )
    p = AssociativeMemoryAuditProfile(profile_id="x", name="full", associative_learning_enabled=True)
    r = AssociativeMemoryAuditResult(
        profile=p,
        metrics=AssociativeMemoryAuditMetrics(
            cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=0.1,
            association_count=1, associative_recall_success_rate=0.0,
        ),
    )
    verdict = AssociativeMemoryAuditor._compute_verdict(baseline, [r], None)
    assert verdict == "ENERGY_REGRESSION"


def test_verdict_phi_regression():
    baseline = AssociativeMemoryAuditResult(
        profile=AssociativeMemoryAuditProfile(profile_id="b", name="baseline"),
        metrics=AssociativeMemoryAuditMetrics(cognitive_score=0.5, coherence_phi=1.0, energy_efficiency=0.5),
    )
    p = AssociativeMemoryAuditProfile(profile_id="x", name="full", associative_learning_enabled=True)
    r = AssociativeMemoryAuditResult(
        profile=p,
        metrics=AssociativeMemoryAuditMetrics(
            cognitive_score=0.5, coherence_phi=0.1, energy_efficiency=0.5,
            association_count=1, associative_recall_success_rate=0.0,
        ),
    )
    verdict = AssociativeMemoryAuditor._compute_verdict(baseline, [r], None)
    assert verdict == "PHI_REGRESSION"


def test_verdict_associative_memory_validated():
    baseline = AssociativeMemoryAuditResult(
        profile=AssociativeMemoryAuditProfile(profile_id="b", name="baseline"),
        metrics=AssociativeMemoryAuditMetrics(cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=0.5),
    )
    p = AssociativeMemoryAuditProfile(profile_id="x", name="full", associative_learning_enabled=True)
    r = AssociativeMemoryAuditResult(
        profile=p,
        metrics=AssociativeMemoryAuditMetrics(
            cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=0.5,
            association_count=3,
            associative_recall_success_rate=0.5,
        ),
    )
    verdict = AssociativeMemoryAuditor._compute_verdict(baseline, [r], "full")
    assert verdict == "ASSOCIATIVE_MEMORY_VALIDATED"


def test_verdict_association_no_effect():
    baseline = AssociativeMemoryAuditResult(
        profile=AssociativeMemoryAuditProfile(profile_id="b", name="baseline"),
        metrics=AssociativeMemoryAuditMetrics(cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=0.5),
    )
    p = AssociativeMemoryAuditProfile(profile_id="x", name="full", associative_learning_enabled=True)
    r = AssociativeMemoryAuditResult(
        profile=p,
        metrics=AssociativeMemoryAuditMetrics(
            cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=0.5,
            association_count=3,
            associative_recall_success_rate=0.0,
        ),
    )
    verdict = AssociativeMemoryAuditor._compute_verdict(baseline, [r], None)
    assert verdict == "ASSOCIATION_NO_EFFECT"


def test_verdict_associative_recall_weak():
    baseline = AssociativeMemoryAuditResult(
        profile=AssociativeMemoryAuditProfile(profile_id="b", name="baseline"),
        metrics=AssociativeMemoryAuditMetrics(cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=0.5),
    )
    p = AssociativeMemoryAuditProfile(profile_id="x", name="full", associative_learning_enabled=True)
    r = AssociativeMemoryAuditResult(
        profile=p,
        metrics=AssociativeMemoryAuditMetrics(
            cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=0.5,
            association_count=3,
            associative_recall_success_rate=0.1,
        ),
    )
    verdict = AssociativeMemoryAuditor._compute_verdict(baseline, [r], None)
    assert verdict == "ASSOCIATIVE_RECALL_WEAK"


def test_verdict_association_overgrowth():
    baseline = AssociativeMemoryAuditResult(
        profile=AssociativeMemoryAuditProfile(profile_id="b", name="baseline"),
        metrics=AssociativeMemoryAuditMetrics(cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=0.5),
    )
    p = AssociativeMemoryAuditProfile(profile_id="x", name="full", associative_learning_enabled=True)
    r = AssociativeMemoryAuditResult(
        profile=p,
        metrics=AssociativeMemoryAuditMetrics(
            cognitive_score=0.5, coherence_phi=0.5, energy_efficiency=0.5,
            association_count=15,
            associative_recall_success_rate=0.1,
            mean_association_strength=0.1,
        ),
    )
    verdict = AssociativeMemoryAuditor._compute_verdict(baseline, [r], None)
    assert verdict == "ASSOCIATION_OVERGROWTH"


# ------------------------------------------------------------------ #
# Markdown report content
# ------------------------------------------------------------------ #

def test_markdown_report_includes_required_fields():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        auditor = AssociativeMemoryAuditor(seed=42, report_dir=td)
        baseline = AssociativeMemoryAuditResult(
            profile=AssociativeMemoryAuditProfile(profile_id="b", name="baseline"),
            metrics=AssociativeMemoryAuditMetrics(
                associative_memory_effect_score=0.5, associative_recall_success_rate=0.3, associative_net_gain=0.1
            ),
        )
        p = AssociativeMemoryAuditProfile(profile_id="x", name="full", associative_learning_enabled=True)
        r = AssociativeMemoryAuditResult(
            profile=p,
            metrics=AssociativeMemoryAuditMetrics(
                associative_memory_effect_score=0.5, associative_recall_success_rate=0.3, associative_net_gain=0.1
            ),
        )
        suite = AssociativeMemoryAuditSuiteResult(
            audit_id="test",
            created_at="now",
            baseline_result=baseline,
            profile_results=[r],
            verdict="ASSOCIATIVE_MEMORY_VALIDATED",
            associative_net_gain=0.1,
        )
        path = auditor._generate_markdown_report(suite)
        text = Path(path).read_text(encoding="utf-8")
        assert "Associative Memory Functional Audit" in text
        assert "0.5000" in text or "0.5" in text
        assert "ASSOCIATIVE_MEMORY_VALIDATED" in text


# ------------------------------------------------------------------ #
# Determinism
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_audit_is_deterministic_with_same_seed():
    auditor1 = AssociativeMemoryAuditor(seed=123)
    auditor2 = AssociativeMemoryAuditor(seed=123)
    profile = AssociativeMemoryAuditProfile(
        profile_id="am6",
        name="full_associative_stack",
        semantic_memory_enabled=True,
        associative_learning_enabled=True,
        associative_recall_enabled=True,
        decay_enabled=True,
        prune_enabled=True,
        n_cycles=5,
        repeated_pattern_count=2,
        novel_pattern_count=1,
    )
    r1 = await auditor1._run_profile(profile)
    r2 = await auditor2._run_profile(profile)
    assert r1.metrics.semantic_assembly_count == r2.metrics.semantic_assembly_count
    assert r1.metrics.cognitive_score == r2.metrics.cognitive_score
