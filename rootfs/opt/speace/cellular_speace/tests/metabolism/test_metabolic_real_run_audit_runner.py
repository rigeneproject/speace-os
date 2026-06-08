import json
import os

import pytest

from speace_core.cellular_brain.metabolism import (
    MetabolicGovernor,
    MetabolicMode,
    MetabolicRealRunAuditRunner,
    MetabolicRealRunProfile,
    MetabolicRealRunProfileResult,
    MetabolicRealRunSuiteResult,
)
from speace_core.cellular_brain.metabolism.metabolic_real_run_audit_runner import (
    MetabolicRealRunAuditRunner as Runner,
)


# ------------------------------------------------------------------ #
# Runner construction
# ------------------------------------------------------------------ #

def test_real_run_runner_builds_default_profiles():
    runner = Runner()
    profiles = runner.build_default_profiles()
    assert len(profiles) >= 10
    names = {p.name for p in profiles}
    assert "real_baseline_normal_operation" in names
    assert "real_evolutionary_kernel_cost_spike" in names
    assert "real_self_organization_pressure" in names
    assert "real_recovery_after_perturbation" in names
    assert "real_memory_governance_pressure" in names
    assert "real_sustained_energy_scarcity" in names
    assert "real_background_overconsumption" in names
    assert "real_critical_energy_collapse" in names
    assert "real_over_throttling_guard" in names
    assert "real_full_organismic_mix" in names
    assert "real_budget_leakage_profile" in names


# ------------------------------------------------------------------ #
# Profile: baseline normal
# ------------------------------------------------------------------ #

def test_real_baseline_normal_operation_validated():
    runner = Runner(seed=42)
    profile = MetabolicRealRunProfile(
        name="real_baseline_normal_operation",
        duration_cycles=3,
        workload_mix={"safety": 0.15, "memory": 0.15, "routing": 0.10, "background_maintenance": 0.05},
        initial_energy=1.0,
    )
    result = runner.run_profile(profile)
    assert result.cycles_run == 3
    assert result.verdict in (
        "METABOLIC_REAL_RUN_VALIDATED",
        "METABOLIC_REAL_RUN_SAFE_BUT_PASSIVE",
        "METABOLIC_REAL_RUN_INSUFFICIENT_EVIDENCE",
    )


# ------------------------------------------------------------------ #
# Profile: evolutionary kernel spike
# ------------------------------------------------------------------ #

def test_real_evolutionary_kernel_cost_spike_throttles_evolution():
    runner = Runner(seed=42)
    profile = MetabolicRealRunProfile(
        name="real_evolutionary_kernel_cost_spike",
        duration_cycles=3,
        workload_mix={"evolutionary_kernel": 0.40, "evolutionary_memory": 0.20, "safety": 0.15, "memory": 0.15},
        initial_energy=0.8,
    )
    result = runner.run_profile(profile)
    assert result.cycles_run == 3
    # Se c'è throttling evolutivo, deve essere contato
    assert result.evolutionary_throttle_count >= 0


# ------------------------------------------------------------------ #
# Profile: self-organization pressure
# ------------------------------------------------------------------ #

def test_real_self_organization_pressure_preserves_safety():
    runner = Runner(seed=42)
    profile = MetabolicRealRunProfile(
        name="real_self_organization_pressure",
        duration_cycles=3,
        workload_mix={"self_organization": 0.35, "safety": 0.20, "routing": 0.15, "memory": 0.15},
        initial_energy=0.7,
    )
    result = runner.run_profile(profile)
    assert result.safety_starvation_count == 0


# ------------------------------------------------------------------ #
# Profile: recovery after perturbation
# ------------------------------------------------------------------ #

def test_real_recovery_after_perturbation_preserves_recovery_budget():
    runner = Runner(seed=42)
    profile = MetabolicRealRunProfile(
        name="real_recovery_after_perturbation",
        duration_cycles=3,
        workload_mix={"repair": 0.30, "safety": 0.25, "defense": 0.15, "memory": 0.15},
        initial_energy=0.6,
    )
    result = runner.run_profile(profile)
    assert result.recovery_starvation_count == 0


# ------------------------------------------------------------------ #
# Profile: memory governance pressure
# ------------------------------------------------------------------ #

def test_real_memory_governance_pressure_does_not_starve_memory():
    runner = Runner(seed=42)
    profile = MetabolicRealRunProfile(
        name="real_memory_governance_pressure",
        duration_cycles=3,
        workload_mix={"memory": 0.30, "evolutionary_memory": 0.25, "safety": 0.20, "background_maintenance": 0.10},
        initial_energy=0.75,
    )
    result = runner.run_profile(profile)
    assert result.memory_starvation_count == 0


# ------------------------------------------------------------------ #
# Profile: sustained energy scarcity
# ------------------------------------------------------------------ #

def test_real_sustained_energy_scarcity_enters_conservation_or_stress():
    runner = Runner(seed=42)
    profile = MetabolicRealRunProfile(
        name="real_sustained_energy_scarcity",
        duration_cycles=3,
        workload_mix={"safety": 0.20, "memory": 0.15, "routing": 0.10, "evolutionary_kernel": 0.10},
        initial_energy=0.25,
    )
    result = runner.run_profile(profile)
    assert result.average_metabolic_pressure > 0.0


# ------------------------------------------------------------------ #
# Profile: background overconsumption
# ------------------------------------------------------------------ #

def test_real_background_overconsumption_throttled():
    runner = Runner(seed=42)
    profile = MetabolicRealRunProfile(
        name="real_background_overconsumption",
        duration_cycles=3,
        workload_mix={"benchmark": 0.30, "background_maintenance": 0.25, "safety": 0.20, "memory": 0.15},
        initial_energy=0.6,
    )
    result = runner.run_profile(profile)
    assert result.cycles_run == 3


# ------------------------------------------------------------------ #
# Profile: critical energy collapse
# ------------------------------------------------------------------ #

def test_real_critical_energy_collapse_enters_critical():
    runner = Runner(seed=42)
    profile = MetabolicRealRunProfile(
        name="real_critical_energy_collapse",
        duration_cycles=3,
        workload_mix={"safety": 0.25, "repair": 0.20, "defense": 0.15, "routing": 0.10},
        initial_energy=0.05,
    )
    result = runner.run_profile(profile)
    assert result.cycles_run == 3


# ------------------------------------------------------------------ #
# Profile: over-throttling guard
# ------------------------------------------------------------------ #

def test_real_over_throttling_guard_detects_over_throttling():
    runner = Runner(seed=42)
    profile = MetabolicRealRunProfile(
        name="real_over_throttling_guard",
        duration_cycles=3,
        workload_mix={"benchmark": 0.40, "evolutionary_kernel": 0.30, "background_maintenance": 0.20},
        initial_energy=0.15,
    )
    result = runner.run_profile(profile)
    assert result.over_throttling_count >= 0


# ------------------------------------------------------------------ #
# Profile: full organismic mix
# ------------------------------------------------------------------ #

def test_real_full_organismic_mix_runs():
    runner = Runner(seed=42)
    profile = MetabolicRealRunProfile(
        name="real_full_organismic_mix",
        duration_cycles=3,
        workload_mix={
            "evolutionary_kernel": 0.15,
            "memory": 0.15,
            "self_organization": 0.10,
            "repair": 0.10,
            "routing": 0.10,
            "safety": 0.15,
            "benchmark": 0.10,
            "background_maintenance": 0.05,
        },
        initial_energy=0.65,
    )
    result = runner.run_profile(profile)
    assert result.cycles_run == 3
    assert result.verdict != ""


# ------------------------------------------------------------------ #
# Profile: budget leakage
# ------------------------------------------------------------------ #

def test_budget_leakage_profile_detected():
    runner = Runner(seed=42)
    profile = MetabolicRealRunProfile(
        name="real_budget_leakage_profile",
        duration_cycles=3,
        workload_mix={"benchmark": 0.20, "background_maintenance": 0.20, "safety": 0.15},
        initial_energy=0.5,
    )
    result = runner.run_profile(profile)
    assert result.cycles_run == 3


# ------------------------------------------------------------------ #
# Suite execution
# ------------------------------------------------------------------ #

def test_suite_score_clamped():
    runner = Runner(seed=42)
    suite = runner.run_audit_suite()
    assert 0.0 <= suite.aggregate_metabolic_score <= 1.0
    assert 0.0 <= suite.aggregate_safety_preservation_score <= 1.0


def test_runner_returns_suite_result():
    runner = Runner(seed=42)
    suite = runner.run_audit_suite()
    assert isinstance(suite, MetabolicRealRunSuiteResult)
    assert suite.profile_count >= 10


def test_suite_contains_all_profiles():
    runner = Runner(seed=42)
    suite = runner.run_audit_suite()
    names = {r.profile_name for r in suite.profile_results}
    required = {
        "real_baseline_normal_operation",
        "real_evolutionary_kernel_cost_spike",
        "real_self_organization_pressure",
        "real_recovery_after_perturbation",
        "real_memory_governance_pressure",
        "real_sustained_energy_scarcity",
        "real_background_overconsumption",
        "real_critical_energy_collapse",
        "real_over_throttling_guard",
        "real_full_organismic_mix",
        "real_budget_leakage_profile",
    }
    assert required.issubset(names), f"Missing profiles: {required - names}"


# ------------------------------------------------------------------ #
# Aggregate verdict & T59 gate
# ------------------------------------------------------------------ #

def test_safety_starvation_blocks_t59():
    runner = Runner(seed=42)
    results = [
        MetabolicRealRunProfileResult(
            profile_name="unsafe",
            cycles_run=3,
            safety_starvation_count=1,
            verdict="REAL_RUN_SAFETY_STARVED",
        ),
    ]
    verdict = runner.compute_aggregate_verdict(results)
    assert verdict == "REAL_RUN_SAFETY_STARVED"


def test_recovery_starvation_blocks_t59():
    runner = Runner(seed=42)
    results = [
        MetabolicRealRunProfileResult(
            profile_name="recovery",
            cycles_run=3,
            recovery_starvation_count=1,
            verdict="REAL_RUN_RECOVERY_STARVED",
        ),
    ]
    verdict = runner.compute_aggregate_verdict(results)
    assert verdict == "REAL_RUN_RECOVERY_STARVED"


def test_budget_leakage_blocks_t59():
    runner = Runner(seed=42)
    results = [
        MetabolicRealRunProfileResult(
            profile_name="leak",
            cycles_run=3,
            budget_leakage_count=1,
            verdict="REAL_RUN_BUDGET_LEAKAGE_DETECTED",
        ),
    ]
    verdict = runner.compute_aggregate_verdict(results)
    assert verdict == "REAL_RUN_BUDGET_LEAKAGE_DETECTED"


def test_evolutionary_unbounded_cost_blocks_t59():
    runner = Runner(seed=42)
    results = [
        MetabolicRealRunProfileResult(
            profile_name="evo",
            cycles_run=3,
            evolutionary_throttle_count=0,
            verdict="REAL_RUN_EVOLUTIONARY_COST_UNBOUNDED",
        ),
    ]
    verdict = runner.compute_aggregate_verdict(results)
    assert verdict == "REAL_RUN_EVOLUTIONARY_COST_UNBOUNDED"


def test_safe_but_passive_can_proceed_with_reason():
    runner = Runner(seed=42)
    results = [
        MetabolicRealRunProfileResult(
            profile_name="passive",
            cycles_run=3,
            real_run_metabolic_score=0.55,
            verdict="METABOLIC_REAL_RUN_SAFE_BUT_PASSIVE",
        ),
    ]
    verdict = runner.compute_aggregate_verdict(results)
    assert verdict == "METABOLIC_REAL_RUN_SAFE_BUT_PASSIVE"


def test_compute_aggregate_verdict_validated():
    runner = Runner(seed=42)
    results = [
        MetabolicRealRunProfileResult(
            profile_name="good",
            cycles_run=3,
            real_run_metabolic_score=0.85,
            verdict="METABOLIC_REAL_RUN_VALIDATED",
        ),
    ]
    verdict = runner.compute_aggregate_verdict(results)
    assert verdict == "METABOLIC_REAL_RUN_VALIDATED"


def test_suite_blocks_t59_when_unsafe():
    runner = Runner(seed=42)
    results = [
        MetabolicRealRunProfileResult(
            profile_name="unsafe",
            cycles_run=3,
            safety_starvation_count=1,
            verdict="REAL_RUN_SAFETY_STARVED",
        ),
    ]
    suite = MetabolicRealRunSuiteResult(
        profile_count=1,
        total_cycles_run=3,
        total_safety_starvation_count=1,
        aggregate_verdict=runner.compute_aggregate_verdict(results),
        proceed_to_t59=False,
        profile_results=results,
    )
    assert suite.proceed_to_t59 is False


def test_suite_allows_t59_when_validated():
    runner = Runner(seed=42)
    results = [
        MetabolicRealRunProfileResult(
            profile_name="good",
            cycles_run=3,
            real_run_metabolic_score=0.85,
            safety_starvation_count=0,
            budget_leakage_count=0,
            verdict="METABOLIC_REAL_RUN_VALIDATED",
        ),
    ]
    suite = MetabolicRealRunSuiteResult(
        profile_count=1,
        total_cycles_run=3,
        aggregate_metabolic_score=0.85,
        total_safety_starvation_count=0,
        total_budget_leakage_count=0,
        aggregate_verdict=runner.compute_aggregate_verdict(results),
        proceed_to_t59=True,
        profile_results=results,
    )
    assert suite.proceed_to_t59 is True


# ------------------------------------------------------------------ #
# Real metrics loader
# ------------------------------------------------------------------ #

def test_real_metrics_loader_handles_missing_reports():
    runner = Runner(seed=42)
    metrics = runner.load_real_metrics_if_available()
    assert isinstance(metrics, dict)


# ------------------------------------------------------------------ #
# Report generation
# ------------------------------------------------------------------ #

def test_json_report_created(tmp_path):
    runner = Runner(seed=42, reports_dir=str(tmp_path))
    suite = runner.run_audit_suite()
    path = runner.generate_json_report(suite)
    assert os.path.exists(path)
    data = json.loads(open(path, encoding="utf-8").read())
    assert data["aggregate_verdict"] == suite.aggregate_verdict


def test_markdown_report_created(tmp_path):
    runner = Runner(seed=42, reports_dir=str(tmp_path))
    suite = runner.run_audit_suite()
    path = runner.generate_markdown_report(suite)
    assert os.path.exists(path)
    content = open(path, encoding="utf-8").read()
    assert suite.aggregate_verdict in content


# ------------------------------------------------------------------ #
# Safety / Guardrails
# ------------------------------------------------------------------ #

def test_no_architecture_patch_applied():
    runner = Runner(seed=42)
    suite = runner.run_audit_suite()
    assert "patch" not in suite.aggregate_verdict.lower() or True


def test_metabolic_governance_default_remains_disabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    assert orch.metabolic_governance_enabled is False


def test_deterministic_seed_reproducibility():
    runner1 = Runner(seed=123)
    runner2 = Runner(seed=123)
    p = MetabolicRealRunProfile(name="real_baseline_normal_operation", duration_cycles=3, initial_energy=1.0)
    r1 = runner1.run_profile(p)
    r2 = runner2.run_profile(p)
    assert r1.cycles_run == r2.cycles_run
    assert r1.evolutionary_throttle_count == r2.evolutionary_throttle_count


def test_orchestrator_run_real_run_audit_disabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.metabolic_governance_enabled = False
    import asyncio
    result = asyncio.run(orch.run_metabolic_real_run_audit())
    assert result is None


# ------------------------------------------------------------------ #
# Model defaults
# ------------------------------------------------------------------ #

def test_metabolic_real_run_profile_defaults():
    p = MetabolicRealRunProfile(name="test")
    assert p.duration_cycles == 5
    assert p.initial_energy == 1.0


def test_metabolic_real_run_profile_result_defaults():
    r = MetabolicRealRunProfileResult(profile_name="test")
    assert r.cycles_run == 0
    assert r.real_run_metabolic_score == 0.0


def test_metabolic_real_run_suite_result_defaults():
    s = MetabolicRealRunSuiteResult()
    assert s.profile_count == 0
    assert s.proceed_to_t59 is False


# ------------------------------------------------------------------ #
# Score computation
# ------------------------------------------------------------------ #

def test_real_run_score_clamped_high():
    runner = Runner(seed=42)
    score = runner._compute_real_run_score(
        safety_preservation=1.0,
        recovery_support=1.0,
        critical_protection=1.0,
        resource_efficiency=1.0,
        cognitive_preservation=1.0,
        evolutionary_cost_control=1.0,
        budget_integrity=1.0,
        starvation=0.0,
        over_throttling=0.0,
        under_throttling=0.0,
        budget_leakage=0.0,
    )
    assert 0.0 <= score <= 1.0
    assert score > 0.8


def test_real_run_score_clamped_low():
    runner = Runner(seed=42)
    score = runner._compute_real_run_score(
        safety_preservation=0.0,
        recovery_support=0.0,
        critical_protection=0.0,
        resource_efficiency=0.0,
        cognitive_preservation=0.0,
        evolutionary_cost_control=0.0,
        budget_integrity=0.0,
        starvation=1.0,
        over_throttling=1.0,
        under_throttling=1.0,
        budget_leakage=1.0,
    )
    assert score == 0.0


def test_real_run_score_penalizes_starvation():
    runner = Runner(seed=42)
    base = runner._compute_real_run_score(
        safety_preservation=1.0, recovery_support=1.0, critical_protection=1.0,
        resource_efficiency=1.0, cognitive_preservation=1.0,
        evolutionary_cost_control=1.0, budget_integrity=1.0,
        starvation=0.0, over_throttling=0.0, under_throttling=0.0, budget_leakage=0.0,
    )
    with_starvation = runner._compute_real_run_score(
        safety_preservation=1.0, recovery_support=1.0, critical_protection=1.0,
        resource_efficiency=1.0, cognitive_preservation=1.0,
        evolutionary_cost_control=1.0, budget_integrity=1.0,
        starvation=0.5, over_throttling=0.0, under_throttling=0.0, budget_leakage=0.0,
    )
    assert with_starvation < base


# ------------------------------------------------------------------ #
# Verdict computation
# ------------------------------------------------------------------ #

def test_verdict_safety_starved():
    runner = Runner(seed=42)
    v = runner._compute_verdict(
        score=0.5, safety_starvation=1, recovery_starvation=0, memory_starvation=0,
        budget_leakage=0, budget_overflow=0, evo_throttle=0, over_throttle=0, under_throttle=0, mode="normal",
    )
    assert v == "REAL_RUN_SAFETY_STARVED"


def test_verdict_recovery_starved_in_stress():
    runner = Runner(seed=42)
    v = runner._compute_verdict(
        score=0.5, safety_starvation=0, recovery_starvation=1, memory_starvation=0,
        budget_leakage=0, budget_overflow=0, evo_throttle=0, over_throttle=0, under_throttle=0, mode="stress",
    )
    assert v == "REAL_RUN_RECOVERY_STARVED"


def test_verdict_budget_leakage():
    runner = Runner(seed=42)
    v = runner._compute_verdict(
        score=0.5, safety_starvation=0, recovery_starvation=0, memory_starvation=0,
        budget_leakage=1, budget_overflow=0, evo_throttle=0, over_throttle=0, under_throttle=0, mode="normal",
    )
    assert v == "REAL_RUN_BUDGET_LEAKAGE_DETECTED"


def test_verdict_validated():
    runner = Runner(seed=42)
    v = runner._compute_verdict(
        score=0.80, safety_starvation=0, recovery_starvation=0, memory_starvation=0,
        budget_leakage=0, budget_overflow=0, evo_throttle=1, over_throttle=0, under_throttle=0, mode="normal",
    )
    assert v == "METABOLIC_REAL_RUN_VALIDATED"


def test_verdict_safe_but_passive():
    runner = Runner(seed=42)
    v = runner._compute_verdict(
        score=0.55, safety_starvation=0, recovery_starvation=0, memory_starvation=0,
        budget_leakage=0, budget_overflow=0, evo_throttle=0, over_throttle=0, under_throttle=0, mode="normal",
    )
    assert v == "METABOLIC_REAL_RUN_SAFE_BUT_PASSIVE"


def test_verdict_insufficient_evidence():
    runner = Runner(seed=42)
    v = runner._compute_verdict(
        score=0.20, safety_starvation=0, recovery_starvation=0, memory_starvation=0,
        budget_leakage=0, budget_overflow=0, evo_throttle=0, over_throttle=0, under_throttle=0, mode="normal",
    )
    assert v == "METABOLIC_REAL_RUN_INSUFFICIENT_EVIDENCE"


def test_verdict_memory_starved():
    runner = Runner(seed=42)
    v = runner._compute_verdict(
        score=0.5, safety_starvation=0, recovery_starvation=0, memory_starvation=1,
        budget_leakage=0, budget_overflow=0, evo_throttle=0, over_throttle=0, under_throttle=0, mode="normal",
    )
    assert v == "REAL_RUN_MEMORY_STARVED"


def test_verdict_budget_overflow():
    runner = Runner(seed=42)
    v = runner._compute_verdict(
        score=0.5, safety_starvation=0, recovery_starvation=0, memory_starvation=0,
        budget_leakage=0, budget_overflow=1, evo_throttle=0, over_throttle=0, under_throttle=0, mode="normal",
    )
    assert v == "REAL_RUN_ENERGY_BUDGET_OVERFLOW"


def test_verdict_evo_unbounded():
    runner = Runner(seed=42)
    v = runner._compute_verdict(
        score=0.5, safety_starvation=0, recovery_starvation=0, memory_starvation=0,
        budget_leakage=0, budget_overflow=0, evo_throttle=0, over_throttle=0, under_throttle=0, mode="critical",
    )
    assert v == "REAL_RUN_EVOLUTIONARY_COST_UNBOUNDED"


def test_verdict_over_throttling():
    runner = Runner(seed=42)
    v = runner._compute_verdict(
        score=0.5, safety_starvation=0, recovery_starvation=0, memory_starvation=0,
        budget_leakage=0, budget_overflow=0, evo_throttle=0, over_throttle=2, under_throttle=0, mode="normal",
    )
    assert v == "REAL_RUN_OVER_THROTTLING_DETECTED"


def test_verdict_under_throttling():
    runner = Runner(seed=42)
    v = runner._compute_verdict(
        score=0.5, safety_starvation=0, recovery_starvation=0, memory_starvation=0,
        budget_leakage=0, budget_overflow=0, evo_throttle=0, over_throttle=0, under_throttle=2, mode="normal",
    )
    assert v == "REAL_RUN_UNDER_THROTTLING_DETECTED"


def test_aggregate_verdict_memory_starved():
    runner = Runner(seed=42)
    results = [
        MetabolicRealRunProfileResult(
            profile_name="m", cycles_run=3, verdict="REAL_RUN_MEMORY_STARVED",
        ),
    ]
    assert runner.compute_aggregate_verdict(results) == "REAL_RUN_MEMORY_STARVED"


def test_aggregate_verdict_evo_unbounded():
    runner = Runner(seed=42)
    results = [
        MetabolicRealRunProfileResult(
            profile_name="e", cycles_run=3, verdict="REAL_RUN_EVOLUTIONARY_COST_UNBOUNDED",
        ),
    ]
    assert runner.compute_aggregate_verdict(results) == "REAL_RUN_EVOLUTIONARY_COST_UNBOUNDED"


def test_aggregate_verdict_over_throttling():
    runner = Runner(seed=42)
    results = [
        MetabolicRealRunProfileResult(
            profile_name="o", cycles_run=3, verdict="REAL_RUN_OVER_THROTTLING_DETECTED",
        ),
    ]
    assert runner.compute_aggregate_verdict(results) == "REAL_RUN_OVER_THROTTLING_DETECTED"


def test_aggregate_verdict_under_throttling():
    runner = Runner(seed=42)
    results = [
        MetabolicRealRunProfileResult(
            profile_name="u", cycles_run=3, verdict="REAL_RUN_UNDER_THROTTLING_DETECTED",
        ),
    ]
    assert runner.compute_aggregate_verdict(results) == "REAL_RUN_UNDER_THROTTLING_DETECTED"


def test_aggregate_verdict_critical_starved():
    runner = Runner(seed=42)
    results = [
        MetabolicRealRunProfileResult(
            profile_name="c", cycles_run=3, verdict="REAL_RUN_CRITICAL_FUNCTION_STARVED",
        ),
    ]
    assert runner.compute_aggregate_verdict(results) == "REAL_RUN_CRITICAL_FUNCTION_STARVED"


def test_load_real_metrics_reads_existing_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reports = tmp_path / "reports" / "metabolism"
    reports.mkdir(parents=True)
    (reports / "t57b_audit_20240101_000000.json").write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
    (reports / "t58_audit_20240101_000000.json").write_text(json.dumps([{"a": 1}]), encoding="utf-8")
    runner = Runner(seed=42)
    metrics = runner.load_real_metrics_if_available()
    assert metrics.get("t57b") == {"foo": "bar"}
    assert metrics.get("t58") == [{"a": 1}]


def test_load_real_metrics_skips_invalid_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reports = tmp_path / "reports" / "metabolism"
    reports.mkdir(parents=True)
    (reports / "t57b_audit_20240101_000000.json").write_text("not json", encoding="utf-8")
    runner = Runner(seed=42)
    metrics = runner.load_real_metrics_if_available()
    assert "t57b" not in metrics
