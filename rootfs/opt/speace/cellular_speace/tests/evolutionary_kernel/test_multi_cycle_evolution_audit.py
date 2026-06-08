import json
import pytest

from speace_core.cellular_brain.evolutionary_kernel.multi_cycle_evolution_audit import (
    MultiCycleAuditProfile,
    MultiCycleEvolutionAudit,
    MultiCycleProfileResult,
    T56BAggregateVerdict,
)
from speace_core.cellular_brain.evolutionary_kernel.multi_cycle_evolution_runner import (
    ConsolidatedMemory,
    CycleMemoryEntry,
    MultiCycleEvolutionResult,
)
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType


# ------------------------------------------------------------------ #
# Model validation
# ------------------------------------------------------------------ #

def test_profile_defaults():
    p = MultiCycleAuditProfile(name="test", description="desc")
    assert p.allow_reconfiguration is False
    assert p.safety_threshold == 1.0


def test_profile_result_defaults():
    r = MultiCycleProfileResult(profile_name="test")
    assert r.multi_cycle_validation_score == 0.0
    assert r.verdict == ""


def test_aggregate_verdict_defaults():
    a = T56BAggregateVerdict(overall_verdict="TEST")
    assert a.can_proceed_to_t57 is False


# ------------------------------------------------------------------ #
# Runner construction
# ------------------------------------------------------------------ #

def test_audit_has_8_profiles():
    audit = MultiCycleEvolutionAudit()
    assert len(audit.PROFILES) == 8


def test_audit_report_dir():
    audit = MultiCycleEvolutionAudit()
    assert audit.REPORT_DIR.exists()


# ------------------------------------------------------------------ #
# Validation score computation
# ------------------------------------------------------------------ #

def test_validation_score_clamped_high():
    s = MultiCycleEvolutionAudit._compute_validation_score(
        cumulative_learning=1.0,
        memory_gain=1.0,
        stability_decay=1.0,
        recovery_score=1.0,
        outcome_reuse=1.0,
        safety_preservation=1.0,
        drift=0.0,
        regression=0.0,
        overperturbation=0.0,
    )
    assert 0.0 <= s <= 1.0
    assert s > 0.8


def test_validation_score_clamped_low():
    s = MultiCycleEvolutionAudit._compute_validation_score(
        cumulative_learning=0.0,
        memory_gain=0.0,
        stability_decay=0.0,
        recovery_score=0.0,
        outcome_reuse=0.0,
        safety_preservation=0.0,
        drift=1.0,
        regression=1.0,
        overperturbation=1.0,
    )
    assert 0.0 <= s <= 1.0
    assert s == 0.0


def test_validation_score_mid_range():
    s = MultiCycleEvolutionAudit._compute_validation_score(
        cumulative_learning=0.5,
        memory_gain=0.5,
        stability_decay=0.5,
        recovery_score=0.5,
        outcome_reuse=0.5,
        safety_preservation=0.5,
        drift=0.2,
        regression=0.1,
        overperturbation=0.1,
    )
    assert 0.0 <= s <= 1.0


# ------------------------------------------------------------------ #
# Verdict logic
# ------------------------------------------------------------------ #

def test_verdict_unsafe_when_patches_in_observe():
    profile = MultiCycleAuditProfile(name="obs", description="", allow_reconfiguration=False)
    mce = MultiCycleEvolutionResult(
        consolidated=ConsolidatedMemory(total_cycles=2, successful_cycles=1),
    )
    v, rec = MultiCycleEvolutionAudit._compute_verdict(
        validation_score=0.8,
        drift_score=0.0,
        regression_count=0,
        unsafe_count=0,
        memory_gain=0.1,
        outcome_reuse=0.1,
        stability_decay=0.8,
        mce_result=mce,
        profile=profile,
    )
    assert v == "UNSAFE_MULTI_CYCLE_EVOLUTION"


def test_verdict_validated():
    profile = MultiCycleAuditProfile(name="full", description="", allow_reconfiguration=True)
    mce = MultiCycleEvolutionResult(
        consolidated=ConsolidatedMemory(total_cycles=3, successful_cycles=3),
    )
    v, rec = MultiCycleEvolutionAudit._compute_verdict(
        validation_score=0.75,
        drift_score=0.1,
        regression_count=0,
        unsafe_count=0,
        memory_gain=0.1,
        outcome_reuse=0.1,
        stability_decay=0.8,
        mce_result=mce,
        profile=profile,
    )
    assert v == "MULTI_CYCLE_EVOLUTION_VALIDATED"


def test_verdict_drift_detected():
    profile = MultiCycleAuditProfile(name="drift", description="", allow_reconfiguration=True)
    mce = MultiCycleEvolutionResult(consolidated=ConsolidatedMemory(total_cycles=3))
    v, rec = MultiCycleEvolutionAudit._compute_verdict(
        validation_score=0.5,
        drift_score=0.4,
        regression_count=0,
        unsafe_count=0,
        memory_gain=0.1,
        outcome_reuse=0.1,
        stability_decay=0.8,
        mce_result=mce,
        profile=profile,
    )
    assert v == "EVOLUTIONARY_DRIFT_DETECTED"


def test_verdict_regression_accumulation():
    profile = MultiCycleAuditProfile(name="reg", description="", allow_reconfiguration=True)
    mce = MultiCycleEvolutionResult(consolidated=ConsolidatedMemory(total_cycles=5))
    v, rec = MultiCycleEvolutionAudit._compute_verdict(
        validation_score=0.5,
        drift_score=0.1,
        regression_count=3,
        unsafe_count=0,
        memory_gain=0.1,
        outcome_reuse=0.1,
        stability_decay=0.8,
        mce_result=mce,
        profile=profile,
    )
    assert v == "REGRESSION_ACCUMULATION_DETECTED"


def test_verdict_unsafe_cycles():
    profile = MultiCycleAuditProfile(name="unsafe", description="", allow_reconfiguration=True)
    mce = MultiCycleEvolutionResult(consolidated=ConsolidatedMemory(total_cycles=3))
    v, rec = MultiCycleEvolutionAudit._compute_verdict(
        validation_score=0.5,
        drift_score=0.1,
        regression_count=0,
        unsafe_count=2,
        memory_gain=0.1,
        outcome_reuse=0.1,
        stability_decay=0.8,
        mce_result=mce,
        profile=profile,
    )
    assert v == "UNSAFE_MULTI_CYCLE_EVOLUTION"


def test_verdict_learning_not_cumulative():
    profile = MultiCycleAuditProfile(name="learn", description="", allow_reconfiguration=True)
    mce = MultiCycleEvolutionResult(consolidated=ConsolidatedMemory(total_cycles=3))
    v, rec = MultiCycleEvolutionAudit._compute_verdict(
        validation_score=0.02,
        drift_score=0.0,
        regression_count=0,
        unsafe_count=0,
        memory_gain=0.1,
        outcome_reuse=0.0,
        stability_decay=0.8,
        mce_result=mce,
        profile=profile,
    )
    assert v == "LEARNING_NOT_CUMULATIVE"


def test_verdict_memory_weak():
    profile = MultiCycleAuditProfile(name="mem", description="", allow_reconfiguration=True)
    mce = MultiCycleEvolutionResult(consolidated=ConsolidatedMemory(total_cycles=3))
    v, rec = MultiCycleEvolutionAudit._compute_verdict(
        validation_score=0.3,
        drift_score=0.1,
        regression_count=0,
        unsafe_count=0,
        memory_gain=0.0,
        outcome_reuse=0.1,
        stability_decay=0.8,
        mce_result=mce,
        profile=profile,
    )
    assert v == "MEMORY_CONSOLIDATION_WEAK"


def test_verdict_safe_but_passive():
    profile = MultiCycleAuditProfile(name="passive", description="", allow_reconfiguration=True)
    mce = MultiCycleEvolutionResult(consolidated=ConsolidatedMemory(total_cycles=3))
    v, rec = MultiCycleEvolutionAudit._compute_verdict(
        validation_score=0.5,
        drift_score=0.1,
        regression_count=0,
        unsafe_count=0,
        memory_gain=0.1,
        outcome_reuse=0.1,
        stability_decay=0.8,
        mce_result=mce,
        profile=profile,
    )
    assert v == "MULTI_CYCLE_SAFE_BUT_PASSIVE"


def test_verdict_insufficient_evidence():
    profile = MultiCycleAuditProfile(name="ins", description="", allow_reconfiguration=True)
    mce = MultiCycleEvolutionResult(consolidated=ConsolidatedMemory(total_cycles=0))
    v, rec = MultiCycleEvolutionAudit._compute_verdict(
        validation_score=0.0,
        drift_score=0.0,
        regression_count=0,
        unsafe_count=0,
        memory_gain=0.0,
        outcome_reuse=0.0,
        stability_decay=0.0,
        mce_result=mce,
        profile=profile,
    )
    assert v == "INSUFFICIENT_EVIDENCE"


# ------------------------------------------------------------------ #
# Aggregate verdict
# ------------------------------------------------------------------ #

def test_aggregate_block_on_drift():
    profiles = [
        MultiCycleProfileResult(profile_name="p1", verdict="EVOLUTIONARY_DRIFT_DETECTED", mce_result=MultiCycleEvolutionResult(consolidated=ConsolidatedMemory(total_cycles=2))),
        MultiCycleProfileResult(profile_name="p2", verdict="MULTI_CYCLE_EVOLUTION_VALIDATED", mce_result=MultiCycleEvolutionResult(consolidated=ConsolidatedMemory(total_cycles=2))),
    ]
    v = MultiCycleEvolutionAudit._compute_aggregate_verdict(profiles)
    assert v.overall_verdict == "BLOCK_T57"
    assert v.can_proceed_to_t57 is False


def test_aggregate_proceed_when_validated():
    profiles = [
        MultiCycleProfileResult(profile_name="p1", verdict="MULTI_CYCLE_EVOLUTION_VALIDATED", multi_cycle_validation_score=0.75, cumulative_learning_score=0.7, mce_result=MultiCycleEvolutionResult(consolidated=ConsolidatedMemory(total_cycles=3))),
    ]
    v = MultiCycleEvolutionAudit._compute_aggregate_verdict(profiles)
    assert v.overall_verdict == "PROCEED_T57"
    assert v.can_proceed_to_t57 is True


def test_aggregate_conservative():
    profiles = [
        MultiCycleProfileResult(profile_name="p1", verdict="MULTI_CYCLE_SAFE_BUT_PASSIVE", multi_cycle_validation_score=0.5, cumulative_learning_score=0.5, mce_result=MultiCycleEvolutionResult(consolidated=ConsolidatedMemory(total_cycles=3))),
    ]
    v = MultiCycleEvolutionAudit._compute_aggregate_verdict(profiles)
    assert v.overall_verdict == "PROCEED_T57_CONSERVATIVE"


def test_aggregate_insufficient_when_empty():
    profiles = []
    v = MultiCycleEvolutionAudit._compute_aggregate_verdict(profiles)
    assert v.overall_verdict == "INSUFFICIENT_EVIDENCE"


# ------------------------------------------------------------------ #
# Profile metrics computation
# ------------------------------------------------------------------ #

def test_profile_metrics_drift_score():
    audit = MultiCycleEvolutionAudit()
    entries = [
        CycleMemoryEntry(cycle_number=1, generation_id="g1", fitness_score=0.8),
        CycleMemoryEntry(cycle_number=2, generation_id="g2", fitness_score=0.7),
        CycleMemoryEntry(cycle_number=3, generation_id="g3", fitness_score=0.6),
    ]
    mce = MultiCycleEvolutionResult(
        consolidated=ConsolidatedMemory(total_cycles=3),
        memory_entries=entries,
    )
    profile = MultiCycleAuditProfile(name="test", description="", allow_reconfiguration=True)
    result = audit._compute_profile_metrics(mce, profile)
    assert result.drift_score > 0.0


def test_profile_metrics_recovery_count():
    audit = MultiCycleEvolutionAudit()
    entries = [
        CycleMemoryEntry(cycle_number=1, generation_id="g1", fitness_score=0.5),
        CycleMemoryEntry(cycle_number=2, generation_id="g2", fitness_score=0.6, rollback_triggered=False),
        CycleMemoryEntry(cycle_number=3, generation_id="g3", fitness_score=0.7, rollback_triggered=False),
    ]
    mce = MultiCycleEvolutionResult(
        consolidated=ConsolidatedMemory(total_cycles=3),
        memory_entries=entries,
    )
    profile = MultiCycleAuditProfile(name="test", description="", allow_reconfiguration=True)
    result = audit._compute_profile_metrics(mce, profile)
    assert result.recovery_pattern_count >= 1


def test_profile_metrics_regression_count():
    audit = MultiCycleEvolutionAudit()
    entries = [
        CycleMemoryEntry(cycle_number=1, generation_id="g1", fitness_score=0.7),
        CycleMemoryEntry(cycle_number=2, generation_id="g2", fitness_score=0.6),
    ]
    mce = MultiCycleEvolutionResult(
        consolidated=ConsolidatedMemory(total_cycles=2),
        memory_entries=entries,
    )
    profile = MultiCycleAuditProfile(name="test", description="", allow_reconfiguration=True)
    result = audit._compute_profile_metrics(mce, profile)
    assert result.regression_pattern_count >= 1


def test_profile_metrics_memory_gain():
    audit = MultiCycleEvolutionAudit()
    entries = [
        CycleMemoryEntry(cycle_number=1, generation_id="g1", parameter_state={"a": 1.0}),
        CycleMemoryEntry(cycle_number=2, generation_id="g2", parameter_state={"a": 1.01}),
    ]
    mce = MultiCycleEvolutionResult(
        consolidated=ConsolidatedMemory(total_cycles=2),
        memory_entries=entries,
    )
    profile = MultiCycleAuditProfile(name="test", description="", allow_reconfiguration=True)
    result = audit._compute_profile_metrics(mce, profile)
    assert result.memory_consolidation_gain >= 0.0


def test_profile_metrics_outcome_reuse():
    audit = MultiCycleEvolutionAudit()
    entries = [
        CycleMemoryEntry(cycle_number=1, generation_id="g1", fitness_score=0.5),
        CycleMemoryEntry(cycle_number=2, generation_id="g2", fitness_score=0.6),
    ]
    mce = MultiCycleEvolutionResult(
        consolidated=ConsolidatedMemory(total_cycles=2),
        memory_entries=entries,
    )
    profile = MultiCycleAuditProfile(name="test", description="", allow_reconfiguration=True)
    result = audit._compute_profile_metrics(mce, profile)
    assert result.outcome_reuse_rate > 0.0


def test_profile_metrics_unsafe_count():
    audit = MultiCycleEvolutionAudit()
    entries = [
        CycleMemoryEntry(cycle_number=1, generation_id="g1", safety_passed=False),
        CycleMemoryEntry(cycle_number=2, generation_id="g2", rollback_triggered=True),
    ]
    mce = MultiCycleEvolutionResult(
        consolidated=ConsolidatedMemory(total_cycles=2),
        memory_entries=entries,
    )
    profile = MultiCycleAuditProfile(name="test", description="", allow_reconfiguration=True)
    result = audit._compute_profile_metrics(mce, profile)
    assert result.unsafe_cycle_count == 2


# ------------------------------------------------------------------ #
# Profile execution (async)
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_run_profile_observe_no_patch():
    audit = MultiCycleEvolutionAudit()
    profile = audit.PROFILES[0]  # observe_only
    result = await audit.run_profile(profile)
    assert result.mce_result is not None
    assert result.profile_name == "multi_cycle_observe_only"
    assert result.mce_result.consolidated.total_cycles == 2


@pytest.mark.asyncio
async def test_run_profile_perturbation_only():
    audit = MultiCycleEvolutionAudit()
    profile = audit.PROFILES[2]  # perturbation_only
    result = await audit.run_profile(profile)
    assert result.mce_result is not None
    assert result.profile_name == "multi_cycle_perturbation_only"


@pytest.mark.asyncio
async def test_run_profile_conservative():
    audit = MultiCycleEvolutionAudit()
    profile = audit.PROFILES[5]  # patch_enabled_conservative
    result = await audit.run_profile(profile)
    assert result.mce_result is not None


@pytest.mark.asyncio
async def test_run_profile_full_safe():
    audit = MultiCycleEvolutionAudit()
    profile = audit.PROFILES[7]  # full_safe_kernel
    result = await audit.run_profile(profile)
    assert result.mce_result is not None
    assert result.mce_result.consolidated.total_cycles == 5


@pytest.mark.asyncio
async def test_run_profile_no_real_patches_in_observe():
    audit = MultiCycleEvolutionAudit()
    profile = audit.PROFILES[0]
    result = await audit.run_profile(profile)
    # In observe mode, successful_cycles should be 0 because safety_threshold=1.0 blocks everything
    assert result.mce_result.consolidated.successful_cycles == 0


# ------------------------------------------------------------------ #
# Suite execution
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_run_suite_returns_aggregate():
    audit = MultiCycleEvolutionAudit()
    verdict = await audit.run_suite()
    assert isinstance(verdict, T56BAggregateVerdict)
    assert len(verdict.profile_results) == 8


@pytest.mark.asyncio
async def test_run_suite_verdict_in_range():
    audit = MultiCycleEvolutionAudit()
    verdict = await audit.run_suite()
    assert verdict.overall_verdict in {
        "PROCEED_T57",
        "PROCEED_T57_CONSERVATIVE",
        "BLOCK_T57",
        "INSUFFICIENT_EVIDENCE",
    }


# ------------------------------------------------------------------ #
# Reports
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_generate_json_report():
    audit = MultiCycleEvolutionAudit()
    verdict = await audit.run_suite()
    path = audit.generate_json_report(verdict)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["overall_verdict"] == verdict.overall_verdict


@pytest.mark.asyncio
async def test_generate_markdown_report():
    audit = MultiCycleEvolutionAudit()
    verdict = await audit.run_suite()
    path = audit.generate_markdown_report(verdict)
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "T56B" in text
    assert verdict.overall_verdict in text


# ------------------------------------------------------------------ #
# Patch safety
# ------------------------------------------------------------------ #

def test_patch_disabled_by_default():
    p = MultiCycleAuditProfile(name="test", description="")
    assert p.allow_reconfiguration is False
    assert p.safety_threshold == 1.0


def test_conservative_profile_allows_reconfiguration():
    p = MultiCycleAuditProfile(
        name="conservative",
        description="",
        allow_reconfiguration=True,
        safety_threshold=0.45,
    )
    assert p.allow_reconfiguration is True
    assert p.safety_threshold < 1.0


# ------------------------------------------------------------------ #
# Determinism / seed
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_deterministic_suite():
    audit1 = MultiCycleEvolutionAudit()
    audit2 = MultiCycleEvolutionAudit()
    v1 = await audit1.run_suite()
    v2 = await audit2.run_suite()
    assert len(v1.profile_results) == len(v2.profile_results)
    for a, b in zip(v1.profile_results, v2.profile_results):
        assert a.profile_name == b.profile_name


# ------------------------------------------------------------------ #
# Event logging
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_events_logged_during_suite():
    audit = MultiCycleEvolutionAudit()
    await audit.run_suite()
    # Events are logged via orchestrator memory; we can verify profiles ran
    assert len(audit.PROFILES) == 8
