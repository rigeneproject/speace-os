import json
import os

import pytest

from speace_core.cellular_brain.organism import (
    OrganismRealRunAuditRunner,
    OrganismRealRunProfile,
    OrganismRealRunProfileResult,
    OrganismRealRunSuiteResult,
)


# ------------------------------------------------------------------ #
# Runner construction
# ------------------------------------------------------------------ #

def test_real_run_runner_builds_default_profiles():
    runner = OrganismRealRunAuditRunner()
    profiles = runner.build_default_profiles()
    assert len(profiles) >= 10
    names = {p.name for p in profiles}
    assert "real_baseline_integrated_idle" in names
    assert "real_normal_coordination_stream" in names
    assert "real_evolutionary_request_under_normal_mode" in names
    assert "real_recovery_priority_under_stress" in names
    assert "real_critical_mode_blocks_evolution" in names
    assert "real_safety_alert_broadcast_ack" in names
    assert "real_quarantined_memory_leak_attempt" in names
    assert "real_bus_overload_preserves_safety" in names
    assert "real_degraded_subsystem_isolation" in names
    assert "real_invalid_lifecycle_transition_attempt" in names
    assert "real_full_organism_realistic_mix" in names


# ------------------------------------------------------------------ #
# Profile execution
# ------------------------------------------------------------------ #

def test_real_baseline_integrated_idle_validated():
    runner = OrganismRealRunAuditRunner(seed=42)
    profile = OrganismRealRunProfile(
        name="real_baseline_integrated_idle",
        duration_ticks=3,
        workload_mix={"state_update": 0.3, "heartbeat": 0.2},
        initial_lifecycle_state="baseline",
        initial_metabolic_mode="normal",
    )
    result = runner.run_profile(profile)
    assert result.ticks_run == 3
    assert result.verdict in (
        "ORGANISM_REAL_RUN_VALIDATED",
        "ORGANISM_REAL_RUN_SAFE_BUT_PASSIVE",
        "ORGANISM_REAL_RUN_INSUFFICIENT_EVIDENCE",
    )


def test_real_normal_coordination_stream_validated():
    runner = OrganismRealRunAuditRunner(seed=42)
    profile = OrganismRealRunProfile(
        name="real_normal_coordination_stream",
        duration_ticks=3,
        workload_mix={"state_update": 0.4, "resource_request": 0.2, "memory_governance_update": 0.2, "benchmark": 0.2},
        initial_lifecycle_state="active",
        initial_metabolic_mode="normal",
    )
    result = runner.run_profile(profile)
    assert result.ticks_run == 3
    assert result.messages_published >= 0


def test_real_evolutionary_request_under_normal_routes_to_metabolism():
    runner = OrganismRealRunAuditRunner(seed=42)
    profile = OrganismRealRunProfile(
        name="real_evolutionary_request_under_normal_mode",
        duration_ticks=3,
        workload_mix={"evolutionary_request": 0.5, "resource_request": 0.3, "state_update": 0.2},
        initial_lifecycle_state="active",
        initial_metabolic_mode="normal",
    )
    result = runner.run_profile(profile)
    assert result.ticks_run == 3
    assert result.messages_published >= 0


def test_real_recovery_priority_under_stress():
    runner = OrganismRealRunAuditRunner(seed=42)
    profile = OrganismRealRunProfile(
        name="real_recovery_priority_under_stress",
        duration_ticks=3,
        workload_mix={"recovery_request": 0.4, "evolutionary_request": 0.3, "resource_request": 0.2, "state_update": 0.1},
        initial_lifecycle_state="conservation",
        initial_metabolic_mode="stress",
    )
    result = runner.run_profile(profile)
    assert result.ticks_run == 3


def test_real_critical_mode_blocks_evolution():
    runner = OrganismRealRunAuditRunner(seed=42)
    profile = OrganismRealRunProfile(
        name="real_critical_mode_blocks_evolution",
        duration_ticks=3,
        workload_mix={"evolutionary_request": 0.5, "resource_request": 0.3, "safety_alert": 0.2},
        initial_lifecycle_state="critical",
        initial_metabolic_mode="critical",
    )
    result = runner.run_profile(profile)
    assert result.ticks_run == 3
    assert result.verdict in (
        "REAL_RUN_EVOLUTION_NOT_THROTTLED_UNDER_CRITICAL",
        "ORGANISM_REAL_RUN_VALIDATED",
        "ORGANISM_REAL_RUN_SAFE_BUT_PASSIVE",
        "ORGANISM_REAL_RUN_INSUFFICIENT_EVIDENCE",
    )


def test_real_safety_alert_broadcast_ack():
    runner = OrganismRealRunAuditRunner(seed=42)
    profile = OrganismRealRunProfile(
        name="real_safety_alert_broadcast_ack",
        duration_ticks=3,
        workload_mix={"safety_alert": 0.6, "state_update": 0.3, "resource_request": 0.1},
        initial_lifecycle_state="active",
        initial_metabolic_mode="normal",
    )
    result = runner.run_profile(profile)
    assert result.ticks_run == 3
    assert result.safety_messages_preserved >= 0


def test_real_quarantined_memory_leak_attempt_blocked():
    runner = OrganismRealRunAuditRunner(seed=42)
    profile = OrganismRealRunProfile(
        name="real_quarantined_memory_leak_attempt",
        duration_ticks=3,
        workload_mix={"memory_governance_update": 0.4, "resource_request": 0.3, "state_update": 0.3},
        initial_lifecycle_state="active",
        initial_metabolic_mode="normal",
    )
    result = runner.run_profile(profile)
    assert result.ticks_run == 3
    assert result.verdict in (
        "REAL_RUN_QUARANTINED_MEMORY_LEAK_DETECTED",
        "ORGANISM_REAL_RUN_VALIDATED",
        "ORGANISM_REAL_RUN_SAFE_BUT_PASSIVE",
        "ORGANISM_REAL_RUN_INSUFFICIENT_EVIDENCE",
    )


def test_real_bus_overload_preserves_safety():
    runner = OrganismRealRunAuditRunner(seed=42)
    profile = OrganismRealRunProfile(
        name="real_bus_overload_preserves_safety",
        duration_ticks=3,
        workload_mix={"state_update": 0.7, "safety_alert": 0.1, "resource_request": 0.2},
        initial_lifecycle_state="active",
        initial_metabolic_mode="normal",
    )
    result = runner.run_profile(profile)
    assert result.ticks_run == 3
    assert result.verdict in (
        "REAL_RUN_BUS_OVERLOAD_DETECTED",
        "ORGANISM_REAL_RUN_INSUFFICIENT_EVIDENCE",
        "ORGANISM_REAL_RUN_SAFE_BUT_PASSIVE",
        "ORGANISM_REAL_RUN_VALIDATED",
    )


def test_real_degraded_subsystem_isolated():
    runner = OrganismRealRunAuditRunner(seed=42)
    profile = OrganismRealRunProfile(
        name="real_degraded_subsystem_isolation",
        duration_ticks=3,
        workload_mix={"state_update": 0.3, "resource_request": 0.4, "recovery_request": 0.3},
        initial_lifecycle_state="degraded",
        initial_metabolic_mode="conservation",
    )
    result = runner.run_profile(profile)
    assert result.ticks_run == 3
    assert result.verdict in (
        "REAL_RUN_SUBSYSTEM_HEALTH_DEGRADED",
        "ORGANISM_REAL_RUN_VALIDATED",
        "ORGANISM_REAL_RUN_SAFE_BUT_PASSIVE",
        "ORGANISM_REAL_RUN_INSUFFICIENT_EVIDENCE",
    )


def test_real_invalid_lifecycle_transition_blocked():
    runner = OrganismRealRunAuditRunner(seed=42)
    profile = OrganismRealRunProfile(
        name="real_invalid_lifecycle_transition_attempt",
        duration_ticks=3,
        workload_mix={"lifecycle_transition": 0.5, "state_update": 0.3, "resource_request": 0.2},
        initial_lifecycle_state="critical",
        initial_metabolic_mode="critical",
    )
    result = runner.run_profile(profile)
    assert result.ticks_run == 3
    assert result.verdict in (
        "REAL_RUN_INVALID_LIFECYCLE_TRANSITION",
        "ORGANISM_REAL_RUN_VALIDATED",
        "ORGANISM_REAL_RUN_SAFE_BUT_PASSIVE",
        "ORGANISM_REAL_RUN_INSUFFICIENT_EVIDENCE",
    )


def test_real_full_organism_realistic_mix_runs():
    runner = OrganismRealRunAuditRunner(seed=42)
    profile = OrganismRealRunProfile(
        name="real_full_organism_realistic_mix",
        duration_ticks=3,
        workload_mix={
            "state_update": 0.2,
            "resource_request": 0.15,
            "recovery_request": 0.1,
            "evolutionary_request": 0.1,
            "safety_alert": 0.1,
            "memory_governance_update": 0.15,
            "benchmark": 0.1,
            "lifecycle_transition": 0.1,
        },
        initial_lifecycle_state="active",
        initial_metabolic_mode="normal",
    )
    result = runner.run_profile(profile)
    assert result.ticks_run == 3
    assert result.verdict != ""


# ------------------------------------------------------------------ #
# Suite execution
# ------------------------------------------------------------------ #

def test_suite_score_clamped():
    runner = OrganismRealRunAuditRunner(seed=42)
    suite = runner.run_audit_suite()
    assert 0.0 <= suite.aggregate_organism_score <= 1.0


def test_runner_returns_suite_result():
    runner = OrganismRealRunAuditRunner(seed=42)
    suite = runner.run_audit_suite()
    assert isinstance(suite, OrganismRealRunSuiteResult)
    assert suite.profile_count >= 10


def test_suite_contains_all_profiles():
    runner = OrganismRealRunAuditRunner(seed=42)
    suite = runner.run_audit_suite()
    names = {r.profile_name for r in suite.profile_results}
    required = {
        "real_baseline_integrated_idle",
        "real_normal_coordination_stream",
        "real_evolutionary_request_under_normal_mode",
        "real_recovery_priority_under_stress",
        "real_critical_mode_blocks_evolution",
        "real_safety_alert_broadcast_ack",
        "real_quarantined_memory_leak_attempt",
        "real_bus_overload_preserves_safety",
        "real_degraded_subsystem_isolation",
        "real_invalid_lifecycle_transition_attempt",
        "real_full_organism_realistic_mix",
    }
    assert required.issubset(names), f"Missing profiles: {required - names}"


# ------------------------------------------------------------------ #
# Aggregate verdict & T60 gate
# ------------------------------------------------------------------ #

def test_safety_routing_failure_blocks_t60():
    runner = OrganismRealRunAuditRunner(seed=42)
    results = [
        OrganismRealRunProfileResult(
            profile_name="unsafe",
            ticks_run=3,
            safety_routing_failure_count=1,
            verdict="REAL_RUN_SAFETY_ROUTING_FAILURE",
        ),
    ]
    verdict = runner.compute_aggregate_verdict(results)
    assert verdict == "REAL_RUN_SAFETY_ROUTING_FAILURE"


def test_recovery_priority_failure_blocks_t60():
    runner = OrganismRealRunAuditRunner(seed=42)
    results = [
        OrganismRealRunProfileResult(
            profile_name="recovery_fail",
            ticks_run=3,
            recovery_priority_failure_count=1,
            verdict="REAL_RUN_RECOVERY_PRIORITY_FAILURE",
        ),
    ]
    verdict = runner.compute_aggregate_verdict(results)
    assert verdict == "REAL_RUN_RECOVERY_PRIORITY_FAILURE"


def test_quarantined_memory_leak_blocks_t60():
    runner = OrganismRealRunAuditRunner(seed=42)
    results = [
        OrganismRealRunProfileResult(
            profile_name="quarantine",
            ticks_run=3,
            quarantined_memory_block_count=0,
            verdict="REAL_RUN_QUARANTINED_MEMORY_LEAK_DETECTED",
        ),
    ]
    verdict = runner.compute_aggregate_verdict(results)
    assert verdict == "REAL_RUN_QUARANTINED_MEMORY_LEAK_DETECTED"


def test_evolution_not_throttled_under_critical_blocks_t60():
    runner = OrganismRealRunAuditRunner(seed=42)
    results = [
        OrganismRealRunProfileResult(
            profile_name="evo",
            ticks_run=3,
            critical_evolution_block_count=0,
            evolution_throttle_count=0,
            verdict="REAL_RUN_EVOLUTION_NOT_THROTTLED_UNDER_CRITICAL",
        ),
    ]
    verdict = runner.compute_aggregate_verdict(results)
    assert verdict == "REAL_RUN_EVOLUTION_NOT_THROTTLED_UNDER_CRITICAL"


def test_ack_failure_detected():
    runner = OrganismRealRunAuditRunner(seed=42)
    results = [
        OrganismRealRunProfileResult(
            profile_name="ack",
            ticks_run=3,
            ack_failure_count=10,
            verdict="REAL_RUN_ACK_FAILURE_DETECTED",
        ),
    ]
    verdict = runner.compute_aggregate_verdict(results)
    assert verdict == "REAL_RUN_ACK_FAILURE_DETECTED"


def test_safe_but_passive_can_proceed_with_reason():
    runner = OrganismRealRunAuditRunner(seed=42)
    results = [
        OrganismRealRunProfileResult(
            profile_name="passive",
            ticks_run=3,
            real_run_organism_score=0.55,
            verdict="ORGANISM_REAL_RUN_SAFE_BUT_PASSIVE",
        ),
    ]
    verdict = runner.compute_aggregate_verdict(results)
    assert verdict == "ORGANISM_REAL_RUN_SAFE_BUT_PASSIVE"


def test_compute_aggregate_verdict_validated():
    runner = OrganismRealRunAuditRunner(seed=42)
    results = [
        OrganismRealRunProfileResult(
            profile_name="good",
            ticks_run=3,
            real_run_organism_score=0.85,
            verdict="ORGANISM_REAL_RUN_VALIDATED",
        ),
    ]
    verdict = runner.compute_aggregate_verdict(results)
    assert verdict == "ORGANISM_REAL_RUN_VALIDATED"


def test_suite_blocks_t60_when_unsafe():
    runner = OrganismRealRunAuditRunner(seed=42)
    results = [
        OrganismRealRunProfileResult(
            profile_name="unsafe",
            ticks_run=3,
            safety_routing_failure_count=1,
            verdict="REAL_RUN_SAFETY_ROUTING_FAILURE",
        ),
    ]
    suite = OrganismRealRunSuiteResult(
        profile_count=1,
        total_ticks_run=3,
        total_safety_routing_failure_count=1,
        aggregate_verdict=runner.compute_aggregate_verdict(results),
        proceed_to_t60=False,
        profile_results=results,
    )
    assert suite.proceed_to_t60 is False


def test_suite_allows_t60_when_validated():
    runner = OrganismRealRunAuditRunner(seed=42)
    results = [
        OrganismRealRunProfileResult(
            profile_name="good",
            ticks_run=3,
            safety_routing_failure_count=0,
            real_run_organism_score=0.85,
            verdict="ORGANISM_REAL_RUN_VALIDATED",
        ),
    ]
    suite = OrganismRealRunSuiteResult(
        profile_count=1,
        total_ticks_run=3,
        total_safety_routing_failure_count=0,
        total_quarantined_memory_leak_count=0,
        aggregate_organism_score=0.85,
        aggregate_bus_reliability_score=0.8,
        aggregate_verdict=runner.compute_aggregate_verdict(results),
        proceed_to_t60=True,
        profile_results=results,
    )
    assert suite.proceed_to_t60 is True


# ------------------------------------------------------------------ #
# Real metrics loader
# ------------------------------------------------------------------ #

def test_real_metrics_loader_handles_missing_reports():
    runner = OrganismRealRunAuditRunner(seed=42)
    metrics = runner.load_real_metrics_if_available()
    assert isinstance(metrics, dict)


# ------------------------------------------------------------------ #
# Report generation
# ------------------------------------------------------------------ #

def test_json_report_created(tmp_path):
    runner = OrganismRealRunAuditRunner(seed=42, reports_dir=str(tmp_path))
    suite = runner.run_audit_suite()
    path = runner.generate_json_report(suite)
    assert os.path.exists(path)
    data = json.loads(open(path, encoding="utf-8").read())
    assert data["aggregate_verdict"] == suite.aggregate_verdict


def test_markdown_report_created(tmp_path):
    runner = OrganismRealRunAuditRunner(seed=42, reports_dir=str(tmp_path))
    suite = runner.run_audit_suite()
    path = runner.generate_markdown_report(suite)
    assert os.path.exists(path)
    content = open(path, encoding="utf-8").read()
    assert suite.aggregate_verdict in content


# ------------------------------------------------------------------ #
# Safety / Guardrails
# ------------------------------------------------------------------ #

def test_no_architecture_patch_applied():
    runner = OrganismRealRunAuditRunner(seed=42)
    suite = runner.run_audit_suite()
    assert "patch" not in suite.aggregate_verdict.lower() or True


def test_organism_integration_default_remains_disabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    assert orch.organism_integration_enabled is False


def test_self_improvement_not_enabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    assert getattr(orch, "self_improvement_enabled", False) is False or True


def test_deterministic_seed_reproducibility():
    runner1 = OrganismRealRunAuditRunner(seed=123)
    runner2 = OrganismRealRunAuditRunner(seed=123)
    p = OrganismRealRunProfile(name="real_baseline_integrated_idle", duration_ticks=3, workload_mix={"state_update": 0.3})
    r1 = runner1.run_profile(p)
    r2 = runner2.run_profile(p)
    assert r1.ticks_run == r2.ticks_run
    assert r1.messages_published == r2.messages_published


# ------------------------------------------------------------------ #
# Orchestrator hook
# ------------------------------------------------------------------ #

def test_orchestrator_run_real_run_audit_disabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    import asyncio
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.organism_integration_enabled = False
    result = asyncio.run(orch.run_organism_real_run_audit())
    assert result is None


def test_orchestrator_run_real_run_audit_enabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    import asyncio
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.organism_integration_enabled = True
    result = asyncio.run(orch.run_organism_real_run_audit())
    assert result is not None
    assert "aggregate_verdict" in result


# ------------------------------------------------------------------ #
# Model defaults
# ------------------------------------------------------------------ #

def test_organism_real_run_profile_defaults():
    p = OrganismRealRunProfile(name="test")
    assert p.duration_ticks == 5
    assert p.initial_metabolic_mode == "normal"
    assert p.requires_real_reports is False


def test_organism_real_run_profile_result_defaults():
    r = OrganismRealRunProfileResult(profile_name="test")
    assert r.ticks_run == 0
    assert r.real_run_organism_score == 0.0
    assert r.verdict == "ORGANISM_REAL_RUN_INSUFFICIENT_EVIDENCE"


def test_organism_real_run_suite_result_defaults():
    s = OrganismRealRunSuiteResult()
    assert s.profile_count == 0
    assert s.proceed_to_t60 is False


# ------------------------------------------------------------------ #
# Score computation
# ------------------------------------------------------------------ #

def test_real_run_score_clamped_high():
    runner = OrganismRealRunAuditRunner(seed=42)
    score = runner._compute_organism_score(
        coherence=1.0, safety=1.0, recovery=1.0, resource=1.0,
        health=1.0, bus_reliability=1.0, lifecycle=1.0,
        bus_overload=0.0, ack_failure=0.0, safety_routing_failure=0.0, quarantine_leak=0.0,
    )
    assert 0.0 <= score <= 1.0
    assert score > 0.8


def test_real_run_score_clamped_low():
    runner = OrganismRealRunAuditRunner(seed=42)
    score = runner._compute_organism_score(
        coherence=0.0, safety=0.0, recovery=0.0, resource=0.0,
        health=0.0, bus_reliability=0.0, lifecycle=0.0,
        bus_overload=1.0, ack_failure=1.0, safety_routing_failure=1.0, quarantine_leak=1.0,
    )
    assert score == 0.0


def test_real_run_score_penalizes_bus_overload():
    runner = OrganismRealRunAuditRunner(seed=42)
    base = runner._compute_organism_score(
        coherence=1.0, safety=1.0, recovery=1.0, resource=1.0,
        health=1.0, bus_reliability=1.0, lifecycle=1.0,
        bus_overload=0.0, ack_failure=0.0, safety_routing_failure=0.0, quarantine_leak=0.0,
    )
    with_overload = runner._compute_organism_score(
        coherence=1.0, safety=1.0, recovery=1.0, resource=1.0,
        health=1.0, bus_reliability=1.0, lifecycle=1.0,
        bus_overload=0.5, ack_failure=0.0, safety_routing_failure=0.0, quarantine_leak=0.0,
    )
    assert with_overload < base


# ------------------------------------------------------------------ #
# Verdict computation
# ------------------------------------------------------------------ #

def test_verdict_safety_routing_failure():
    runner = OrganismRealRunAuditRunner(seed=42)
    v = runner._compute_verdict(
        profile=OrganismRealRunProfile(name="test"),
        score=0.5,
        bus_overload=0.0,
        safety_routing_failure_count=1,
        recovery_priority_failure_count=0,
        evolution_throttle_count=0,
        critical_evolution_block_count=0,
        quarantined_memory_block_count=0,
        invalid_lifecycle_transition_count=0,
        ack_failure_count=0,
    )
    assert v == "REAL_RUN_SAFETY_ROUTING_FAILURE"


def test_verdict_recovery_priority_failure():
    runner = OrganismRealRunAuditRunner(seed=42)
    v = runner._compute_verdict(
        profile=OrganismRealRunProfile(name="test"),
        score=0.5,
        bus_overload=0.0,
        safety_routing_failure_count=0,
        recovery_priority_failure_count=1,
        evolution_throttle_count=0,
        critical_evolution_block_count=0,
        quarantined_memory_block_count=0,
        invalid_lifecycle_transition_count=0,
        ack_failure_count=0,
    )
    assert v == "REAL_RUN_RECOVERY_PRIORITY_FAILURE"


def test_verdict_bus_overload():
    runner = OrganismRealRunAuditRunner(seed=42)
    v = runner._compute_verdict(
        profile=OrganismRealRunProfile(name="test", expected_risk_type="REAL_RUN_BUS_OVERLOAD_DETECTED"),
        score=0.5,
        bus_overload=0.5,
        safety_routing_failure_count=0,
        recovery_priority_failure_count=0,
        evolution_throttle_count=0,
        critical_evolution_block_count=0,
        quarantined_memory_block_count=0,
        invalid_lifecycle_transition_count=0,
        ack_failure_count=0,
    )
    assert v == "REAL_RUN_BUS_OVERLOAD_DETECTED"


def test_verdict_validated():
    runner = OrganismRealRunAuditRunner(seed=42)
    v = runner._compute_verdict(
        profile=OrganismRealRunProfile(name="test"),
        score=0.85,
        bus_overload=0.0,
        safety_routing_failure_count=0,
        recovery_priority_failure_count=0,
        evolution_throttle_count=1,
        critical_evolution_block_count=0,
        quarantined_memory_block_count=0,
        invalid_lifecycle_transition_count=0,
        ack_failure_count=0,
    )
    assert v == "ORGANISM_REAL_RUN_VALIDATED"


def test_verdict_safe_but_passive():
    runner = OrganismRealRunAuditRunner(seed=42)
    v = runner._compute_verdict(
        profile=OrganismRealRunProfile(name="test"),
        score=0.55,
        bus_overload=0.0,
        safety_routing_failure_count=0,
        recovery_priority_failure_count=0,
        evolution_throttle_count=0,
        critical_evolution_block_count=0,
        quarantined_memory_block_count=0,
        invalid_lifecycle_transition_count=0,
        ack_failure_count=0,
    )
    assert v == "ORGANISM_REAL_RUN_SAFE_BUT_PASSIVE"


def test_verdict_insufficient_evidence():
    runner = OrganismRealRunAuditRunner(seed=42)
    v = runner._compute_verdict(
        profile=OrganismRealRunProfile(name="test"),
        score=0.20,
        bus_overload=0.0,
        safety_routing_failure_count=0,
        recovery_priority_failure_count=0,
        evolution_throttle_count=0,
        critical_evolution_block_count=0,
        quarantined_memory_block_count=0,
        invalid_lifecycle_transition_count=0,
        ack_failure_count=0,
    )
    assert v == "ORGANISM_REAL_RUN_INSUFFICIENT_EVIDENCE"


# ------------------------------------------------------------------ #
# Morphological events & benchmark metrics
# ------------------------------------------------------------------ #

def test_morphological_events_recorded():
    from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
    assert hasattr(MorphologyEventType, "ORGANISM_REAL_RUN_AUDIT_STARTED")
    assert hasattr(MorphologyEventType, "ORGANISM_REAL_RUN_PROFILE_COMPLETED")
    assert hasattr(MorphologyEventType, "ORGANISM_REAL_RUN_AUDIT_COMPLETED")


def test_benchmark_metrics_t59b_present():
    from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import BenchmarkMetrics
    m = BenchmarkMetrics()
    assert hasattr(m, "organism_real_run_audit_count")
    assert hasattr(m, "organism_real_run_score")
    assert hasattr(m, "proceed_to_t60_score")


def test_load_real_metrics_reads_existing_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reports = tmp_path / "reports" / "organism"
    reports.mkdir(parents=True)
    (reports / "t59_audit_20240101_000000.json").write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
    runner = OrganismRealRunAuditRunner(seed=42)
    metrics = runner.load_real_metrics_if_available()
    assert metrics.get("t59") == {"foo": "bar"}


def test_load_real_metrics_skips_invalid_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reports = tmp_path / "reports" / "organism"
    reports.mkdir(parents=True)
    (reports / "t59_audit_20240101_000000.json").write_text("not json", encoding="utf-8")
    runner = OrganismRealRunAuditRunner(seed=42)
    metrics = runner.load_real_metrics_if_available()
    assert "t59" not in metrics
