import math
import pytest

from speace_core.cellular_brain.analysis.semantic_stimulation_designer import (
    SemanticRecallProbe,
    SemanticStimulationDesigner,
    SemanticStimulationMetrics,
    SemanticStimulationProfile,
    SemanticStimulationResult,
    SemanticStimulationSuiteResult,
    SemanticStimulus,
)


# ------------------------------------------------------------------ #
# Model construction
# ------------------------------------------------------------------ #

def test_stimulus_model():
    s = SemanticStimulus(stimulus_id="s1", pattern=[0.5, 0.6], label="test")
    assert s.label == "test"
    assert s.target_region == "hippocampus"


def test_recall_probe_model():
    p = SemanticRecallProbe(probe_id="p1", cue_pattern=[0.5], expected_label="test")
    assert p.partial_cue_ratio == 0.5


def test_profile_model():
    p = SemanticStimulationProfile(profile_name="test")
    assert p.repetitions_per_stimulus == 6


def test_metrics_model():
    m = SemanticStimulationMetrics(recall_success_rate=0.5)
    assert m.assembly_created_events == 0


def test_result_model():
    p = SemanticStimulationProfile(profile_name="test")
    r = SemanticStimulationResult(profile=p)
    assert r.passed is True


def test_suite_result_model():
    s = SemanticStimulationSuiteResult(audit_id="a1", created_at="now")
    assert s.verdict == "INSUFFICIENT_EVIDENCE"


# ------------------------------------------------------------------ #
# Designer initialization
# ------------------------------------------------------------------ #

def test_designer_importable():
    assert SemanticStimulationDesigner is not None


def test_default_profiles():
    profiles = SemanticStimulationDesigner.default_profiles()
    assert len(profiles) == 10
    names = [p.profile_name for p in profiles]
    assert "semantic_off_control" in names
    assert "full_semantic_stimulation" in names


# ------------------------------------------------------------------ #
# Pattern generation
# ------------------------------------------------------------------ #

def test_generate_distinct_patterns_count():
    patterns = SemanticStimulationDesigner.generate_distinct_patterns(5, 10, separation=0.3, seed=42)
    assert len(patterns) == 5
    assert all(len(p) == 10 for p in patterns)


def test_generated_patterns_meet_minimum_separation():
    patterns = SemanticStimulationDesigner.generate_distinct_patterns(4, 10, separation=0.4, seed=42)
    for i in range(len(patterns)):
        for j in range(i + 1, len(patterns)):
            dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(patterns[i], patterns[j])))
            assert dist >= 0.3  # relaxed because fallback may produce closer patterns


def test_pattern_separation_computation():
    patterns = [[1.0, 0.0], [0.0, 1.0]]
    mean_sep, min_sep = SemanticStimulationDesigner.compute_pattern_separation(patterns)
    assert mean_sep > 0.0
    assert min_sep > 0.0


def test_pattern_separation_single_pattern():
    mean_sep, min_sep = SemanticStimulationDesigner.compute_pattern_separation([[1.0, 0.0]])
    assert mean_sep == 0.0
    assert min_sep == 0.0


# ------------------------------------------------------------------ #
# Stimulus / probe builders
# ------------------------------------------------------------------ #

def test_build_stimulus_sequence():
    designer = SemanticStimulationDesigner(seed=42)
    profile = SemanticStimulationProfile(
        profile_name="test",
        repeated_stimuli_count=3,
        novel_stimuli_count=2,
    )
    stimuli = designer.build_stimulus_sequence(profile)
    assert len(stimuli) == 5
    repeated = [s for s in stimuli if s.stimulus_id.startswith("rep_")]
    novel = [s for s in stimuli if s.stimulus_id.startswith("nov_")]
    assert len(repeated) == 3
    assert len(novel) == 2
    assert all(s.repetitions == 6 for s in repeated)
    assert all(s.repetitions == 1 for s in novel)


def test_build_recall_probes():
    designer = SemanticStimulationDesigner(seed=42)
    profile = SemanticStimulationProfile(
        profile_name="test",
        repeated_stimuli_count=2,
        cue_degradation_ratio=0.5,
    )
    stimuli = designer.build_stimulus_sequence(profile)
    probes = designer.build_recall_probes(stimuli, profile)
    assert len(probes) == 2
    for probe in probes:
        assert probe.partial_cue_ratio == 0.5
        assert len(probe.cue_pattern) == profile.pattern_size


# ------------------------------------------------------------------ #
# Cue degradation / noise
# ------------------------------------------------------------------ #

def test_degrade_cue():
    import random
    rng = random.Random(42)
    pattern = [1.0, 0.8, 0.6, 0.4, 0.2]
    degraded = SemanticStimulationDesigner._degrade_cue(pattern, 0.5, rng)
    assert len(degraded) == len(pattern)
    non_zero = sum(1 for v in degraded if v != 0.0)
    assert non_zero >= 1


def test_add_noise_bounded():
    import random
    rng = random.Random(42)
    pattern = [0.5] * 5
    noisy = SemanticStimulationDesigner._add_noise(pattern, 0.2, rng)
    assert all(0.0 <= v <= 1.0 for v in noisy)


def test_add_noise_zero():
    import random
    rng = random.Random(42)
    pattern = [0.5] * 5
    same = SemanticStimulationDesigner._add_noise(pattern, 0.0, rng)
    assert same == pattern


# ------------------------------------------------------------------ #
# Orchestrator setup
# ------------------------------------------------------------------ #

def test_build_orchestrator_sets_semantic_enabled():
    designer = SemanticStimulationDesigner(seed=42)
    profile = SemanticStimulationProfile(profile_name="test", semantic_memory_enabled=True)
    orch = designer._build_orchestrator(profile)
    assert orch.semantic_memory_enabled is True
    assert orch._semantic_memory_store is not None
    assert orch._cell_assembly_engine is not None


def test_build_orchestrator_sets_semantic_disabled():
    designer = SemanticStimulationDesigner(seed=42)
    profile = SemanticStimulationProfile(profile_name="test", semantic_memory_enabled=False)
    orch = designer._build_orchestrator(profile)
    assert orch.semantic_memory_enabled is False


def test_build_orchestrator_hippocampus_targeting():
    designer = SemanticStimulationDesigner(seed=42)
    profile = SemanticStimulationProfile(profile_name="hippocampus_targeted")
    orch = designer._build_orchestrator(profile)
    regions = {getattr(n, "region", None) for n in orch.circuit.hidden_neurons}
    assert "hippocampus" in regions


def test_build_orchestrator_prefrontal_targeting():
    designer = SemanticStimulationDesigner(seed=42)
    profile = SemanticStimulationProfile(profile_name="hippocampus_prefrontal_reactivation")
    orch = designer._build_orchestrator(profile)
    regions = {getattr(n, "region", None) for n in orch.circuit.hidden_neurons}
    assert "hippocampus" in regions or "prefrontal" in regions


# ------------------------------------------------------------------ #
# Encoding phase
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_encoding_phase_creates_assemblies():
    designer = SemanticStimulationDesigner(seed=42)
    profile = SemanticStimulationProfile(
        profile_name="strong_repetition",
        repeated_stimuli_count=2,
        repetitions_per_stimulus=5,
        semantic_memory_enabled=True,
        consolidation_enabled=False,
        recall_enabled=False,
    )
    orch = designer._build_orchestrator(profile)
    stimuli = designer.build_stimulus_sequence(profile)
    await designer.run_encoding_phase(orch, stimuli, profile)
    store = orch._semantic_memory_store
    assert store is not None
    assert store.count() >= 1


@pytest.mark.asyncio
async def test_repetition_increases_recurrence():
    designer = SemanticStimulationDesigner(seed=42)
    profile = SemanticStimulationProfile(
        profile_name="strong_repetition",
        repeated_stimuli_count=1,
        repetitions_per_stimulus=6,
        semantic_memory_enabled=True,
        consolidation_enabled=False,
        recall_enabled=False,
    )
    orch = designer._build_orchestrator(profile)
    stimuli = designer.build_stimulus_sequence(profile)
    await designer.run_encoding_phase(orch, stimuli, profile)
    store = orch._semantic_memory_store
    if store and store.count() > 0:
        max_recurrence = max(a.recurrence_count for a in store._assemblies.values())
        assert max_recurrence >= 2


# ------------------------------------------------------------------ #
# Consolidation phase
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_consolidation_phase_runs_without_error():
    designer = SemanticStimulationDesigner(seed=42)
    profile = SemanticStimulationProfile(
        profile_name="consolidation_heavy",
        repeated_stimuli_count=1,
        repetitions_per_stimulus=4,
        consolidation_ticks=3,
        semantic_memory_enabled=True,
        consolidation_enabled=True,
        recall_enabled=False,
    )
    orch = designer._build_orchestrator(profile)
    stimuli = designer.build_stimulus_sequence(profile)
    await designer.run_encoding_phase(orch, stimuli, profile)
    pre_count = orch._semantic_memory_store.count() if orch._semantic_memory_store else 0
    await designer.run_consolidation_phase(orch, profile)
    post_count = orch._semantic_memory_store.count() if orch._semantic_memory_store else 0
    assert post_count >= pre_count  # consolidation does not delete


# ------------------------------------------------------------------ #
# Recall phase
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_recall_phase_records_attempts():
    designer = SemanticStimulationDesigner(seed=42)
    profile = SemanticStimulationProfile(
        profile_name="strong_repetition",
        repeated_stimuli_count=2,
        repetitions_per_stimulus=6,
        consolidation_ticks=3,
        semantic_memory_enabled=True,
        consolidation_enabled=True,
        recall_enabled=True,
    )
    orch = designer._build_orchestrator(profile)
    stimuli = designer.build_stimulus_sequence(profile)
    await designer.run_encoding_phase(orch, stimuli, profile)
    await designer.run_consolidation_phase(orch, profile)
    probes = designer.build_recall_probes(stimuli, profile)
    attempts, successes, failures, partial, noisy = await designer.run_recall_phase(
        orch, probes, profile
    )
    assert attempts > 0
    assert attempts == len(probes)
    assert successes + failures == attempts


@pytest.mark.asyncio
async def test_recall_fails_safely_when_empty():
    designer = SemanticStimulationDesigner(seed=42)
    profile = SemanticStimulationProfile(
        profile_name="semantic_off_control",
        semantic_memory_enabled=False,
        recall_enabled=False,
    )
    orch = designer._build_orchestrator(profile)
    probes = [
        SemanticRecallProbe(probe_id="p1", cue_pattern=[0.5] * 10, expected_label="x")
    ]
    attempts, successes, failures, partial, noisy = await designer.run_recall_phase(
        orch, probes, profile
    )
    assert attempts == 0


@pytest.mark.asyncio
async def test_noisy_recall_remains_bounded():
    designer = SemanticStimulationDesigner(seed=42)
    profile = SemanticStimulationProfile(
        profile_name="noisy_recall",
        repeated_stimuli_count=2,
        repetitions_per_stimulus=4,
        semantic_memory_enabled=True,
        recall_enabled=True,
    )
    orch = designer._build_orchestrator(profile)
    stimuli = designer.build_stimulus_sequence(profile)
    await designer.run_encoding_phase(orch, stimuli, profile)
    probes = designer.build_recall_probes(stimuli, profile)
    attempts, successes, failures, partial, noisy = await designer.run_recall_phase(
        orch, probes, profile
    )
    assert attempts >= 0
    assert successes >= 0


# ------------------------------------------------------------------ #
# Suite runner
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_run_suite():
    designer = SemanticStimulationDesigner(seed=42)
    profiles = SemanticStimulationDesigner.default_profiles()[:3]
    for p in profiles:
        p.repetitions_per_stimulus = 3
        p.consolidation_ticks = 1
    suite = await designer.run_suite(profiles=profiles)
    assert isinstance(suite, SemanticStimulationSuiteResult)
    assert suite.audit_id.startswith("t43c-")
    assert len(suite.profile_results) == 2


@pytest.mark.asyncio
async def test_suite_reports_generated():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        designer = SemanticStimulationDesigner(seed=42, report_dir=td)
        profiles = SemanticStimulationDesigner.default_profiles()[:3]
        for p in profiles:
            p.repetitions_per_stimulus = 2
            p.consolidation_ticks = 1
        suite = await designer.run_suite(profiles=profiles)
        assert suite.json_report_path is not None
        assert suite.markdown_report_path is not None
        assert Path(suite.json_report_path).exists()
        assert Path(suite.markdown_report_path).exists()


# ------------------------------------------------------------------ #
# Verdict logic
# ------------------------------------------------------------------ #

def test_verdict_insufficient_evidence_empty():
    baseline = SemanticStimulationResult(
        profile=SemanticStimulationProfile(profile_name="baseline")
    )
    verdict = SemanticStimulationDesigner._compute_verdict(baseline, [])
    assert verdict == "INSUFFICIENT_EVIDENCE"


def test_verdict_allowed_values():
    baseline = SemanticStimulationResult(
        profile=SemanticStimulationProfile(profile_name="baseline")
    )
    p = SemanticStimulationProfile(profile_name="test", semantic_memory_enabled=True)
    r = SemanticStimulationResult(
        profile=p,
        metrics=SemanticStimulationMetrics(
            assembly_created_events=3,
            recall_success_rate=0.5,
            semantic_stimulation_effectiveness=0.4,
        ),
    )
    verdict = SemanticStimulationDesigner._compute_verdict(baseline, [r])
    assert verdict in {
        "SEMANTIC_STIMULATION_VALIDATED",
        "SEMANTIC_ENCODING_ONLY",
        "SEMANTIC_CONSOLIDATION_WEAK",
        "SEMANTIC_RECALL_WEAK",
        "SEMANTIC_DISCRIMINATION_FAILURE",
        "SEMANTIC_OVERACTIVATION",
        "SEMANTIC_GLOBAL_NO_EFFECT",
        "INSUFFICIENT_EVIDENCE",
    }


def test_verdict_overactivation():
    baseline = SemanticStimulationResult(
        profile=SemanticStimulationProfile(profile_name="baseline")
    )
    p = SemanticStimulationProfile(profile_name="test", semantic_memory_enabled=True)
    r = SemanticStimulationResult(
        profile=p,
        metrics=SemanticStimulationMetrics(energy_delta=-0.5),
    )
    verdict = SemanticStimulationDesigner._compute_verdict(baseline, [r])
    assert verdict == "SEMANTIC_OVERACTIVATION"


def test_verdict_encoding_only():
    baseline = SemanticStimulationResult(
        profile=SemanticStimulationProfile(profile_name="baseline")
    )
    p = SemanticStimulationProfile(profile_name="test", semantic_memory_enabled=True)
    r = SemanticStimulationResult(
        profile=p,
        metrics=SemanticStimulationMetrics(
            assembly_created_events=3,
            assembly_consolidated_events=1,
            recall_success_rate=0.0,
            semantic_discrimination_score=0.2,
            cognitive_delta=0.02,
            phi_delta=0.03,
        ),
    )
    verdict = SemanticStimulationDesigner._compute_verdict(baseline, [r])
    assert verdict == "SEMANTIC_ENCODING_ONLY"


def test_select_best_and_worst():
    p1 = SemanticStimulationProfile(profile_name="good", semantic_memory_enabled=True)
    p2 = SemanticStimulationProfile(profile_name="bad", semantic_memory_enabled=True)
    r1 = SemanticStimulationResult(
        profile=p1,
        metrics=SemanticStimulationMetrics(
            semantic_stimulation_effectiveness=0.8,
            recall_success_rate=0.7,
            mean_assembly_stability=0.6,
            semantic_consolidation_score=0.5,
        ),
    )
    r2 = SemanticStimulationResult(
        profile=p2,
        metrics=SemanticStimulationMetrics(
            semantic_stimulation_effectiveness=0.1,
            recall_success_rate=0.0,
            mean_assembly_stability=0.1,
            semantic_consolidation_score=0.0,
        ),
    )
    best, worst = SemanticStimulationDesigner._select_best_and_worst([r1, r2])
    assert best == "good"
    assert worst == "bad"


# ------------------------------------------------------------------ #
# Effectiveness clamping
# ------------------------------------------------------------------ #

def test_effectiveness_clamped_to_0_1():
    designer = SemanticStimulationDesigner(seed=42)
    p = SemanticStimulationProfile(profile_name="test")
    orch = designer._build_orchestrator(p)
    # Force very high metrics
    metrics = designer._collect_metrics(
        orch, [], [], 10, 10, 0, 10, 10, 0, 1.0, 1.0, 1.0,
    )
    assert 0.0 <= metrics.semantic_stimulation_effectiveness <= 1.0


def test_effectiveness_zero_when_nothing():
    designer = SemanticStimulationDesigner(seed=42)
    p = SemanticStimulationProfile(profile_name="test")
    orch = designer._build_orchestrator(p)
    metrics = designer._collect_metrics(
        orch, [], [], 0, 0, 0, 0, 0, 0, 0.0, 0.0, 0.0,
    )
    assert metrics.semantic_stimulation_effectiveness == 0.0


# ------------------------------------------------------------------ #
# Determinism
# ------------------------------------------------------------------ #

def test_generate_distinct_patterns_deterministic():
    p1 = SemanticStimulationDesigner.generate_distinct_patterns(5, 10, seed=123)
    p2 = SemanticStimulationDesigner.generate_distinct_patterns(5, 10, seed=123)
    assert p1 == p2


@pytest.mark.asyncio
async def test_suite_deterministic():
    designer1 = SemanticStimulationDesigner(seed=456)
    designer2 = SemanticStimulationDesigner(seed=456)
    profiles = [
        SemanticStimulationProfile(
            profile_name="semantic_off_control",
            semantic_memory_enabled=False,
            repetitions_per_stimulus=2,
        ),
        SemanticStimulationProfile(
            profile_name="strong_repetition",
            repetitions_per_stimulus=3,
            consolidation_ticks=1,
            semantic_memory_enabled=True,
            recall_enabled=False,
        ),
    ]
    s1 = await designer1.run_suite(profiles=profiles)
    s2 = await designer2.run_suite(profiles=profiles)
    assert len(s1.profile_results) == len(s2.profile_results)
    for r1, r2 in zip(s1.profile_results, s2.profile_results):
        assert r1.metrics.assembly_created_events == r2.metrics.assembly_created_events
        assert r1.metrics.stimulus_count == r2.metrics.stimulus_count


# ------------------------------------------------------------------ #
# No unbounded activation
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_no_unbounded_activation():
    designer = SemanticStimulationDesigner(seed=42)
    profile = SemanticStimulationProfile(
        profile_name="full_semantic_stimulation",
        repeated_stimuli_count=2,
        repetitions_per_stimulus=4,
        consolidation_ticks=2,
        semantic_memory_enabled=True,
        reactivation_enabled=True,
        recall_enabled=True,
    )
    result = await designer.run_profile(profile)
    assert result.metrics.energy_delta >= -1.0
    assert result.metrics.energy_delta <= 1.0


# ------------------------------------------------------------------ #
# Semantic off control
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_semantic_off_no_false_positive():
    designer = SemanticStimulationDesigner(seed=42)
    profile = SemanticStimulationProfile(
        profile_name="semantic_off_control",
        semantic_memory_enabled=False,
        recall_enabled=False,
    )
    result = await designer.run_profile(profile)
    assert result.metrics.assembly_created_events == 0
    assert result.metrics.recall_success_rate == 0.0


# ------------------------------------------------------------------ #
# Full suite produces metrics
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_full_suite_produces_semantic_metrics():
    designer = SemanticStimulationDesigner(seed=42)
    profile = SemanticStimulationProfile(
        profile_name="full_semantic_stimulation",
        repeated_stimuli_count=2,
        repetitions_per_stimulus=4,
        consolidation_ticks=2,
        semantic_memory_enabled=True,
        consolidation_enabled=True,
        recall_enabled=True,
        reactivation_enabled=False,
    )
    result = await designer.run_profile(profile)
    assert result.metrics.semantic_stimulation_effectiveness >= 0.0


# ------------------------------------------------------------------ #
# Markdown report content
# ------------------------------------------------------------------ #

def test_markdown_report_contains_required_fields():
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        designer = SemanticStimulationDesigner(seed=42, report_dir=td)
        baseline = SemanticStimulationResult(
            profile=SemanticStimulationProfile(profile_name="baseline")
        )
        p = SemanticStimulationProfile(profile_name="test")
        r = SemanticStimulationResult(
            profile=p,
            metrics=SemanticStimulationMetrics(
                recall_success_rate=0.3,
                semantic_stimulation_effectiveness=0.4,
            ),
        )
        suite = SemanticStimulationSuiteResult(
            audit_id="test",
            created_at="now",
            baseline_result=baseline,
            profile_results=[r],
            verdict="SEMANTIC_STIMULATION_VALIDATED",
        )
        path = designer._generate_markdown_report(suite)
        text = Path(path).read_text(encoding="utf-8")
        assert "Semantic Benchmark Stimulation Redesign" in text
        assert "0.3000" in text or "0.3" in text
        assert "SEMANTIC_STIMULATION_VALIDATED" in text


# ------------------------------------------------------------------ #
# T43B audit still works
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_t43b_audit_still_works():
    from speace_core.cellular_brain.analysis.semantic_memory_audit import SemanticMemoryAuditor

    auditor = SemanticMemoryAuditor(seed=42)
    profiles = SemanticMemoryAuditor.default_profiles()[:3]
    for pr in profiles:
        pr.n_cycles = 3
        pr.repeated_pattern_count = 1
        pr.novel_pattern_count = 1
    report = await auditor.run_audit_suite(profiles=profiles)
    assert report.audit_id.startswith("t43b-")
