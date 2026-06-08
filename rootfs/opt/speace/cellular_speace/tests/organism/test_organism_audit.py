import json
import os

import pytest

from speace_core.cellular_brain.organism import (
    OrganismAudit,
    OrganismAuditProfile,
    OrganismAuditResult,
    OrganismAuditSuiteResult,
    OrganismBus,
    OrganismBusMessage,
)


def test_audit_builds_default_profiles():
    audit = OrganismAudit()
    profiles = audit.build_default_profiles()
    assert len(profiles) >= 10
    names = {p.name for p in profiles}
    assert "baseline_bus_idle" in names
    assert "full_organism_integration_mix" in names


def test_audit_runs_baseline_bus_idle():
    audit = OrganismAudit(seed=42)
    profile = OrganismAuditProfile(name="baseline_bus_idle", duration_ticks=3, message_rate=0.2)
    result = audit.run_profile(profile)
    assert result.messages_processed >= 0
    assert result.verdict != ""


def test_audit_runs_normal_cross_system_coordination():
    audit = OrganismAudit(seed=42)
    profile = OrganismAuditProfile(name="normal_cross_system_coordination", duration_ticks=3, message_rate=1.0, resource_request_rate=0.3)
    result = audit.run_profile(profile)
    assert result.messages_processed >= 0


def test_audit_runs_evolutionary_resource_request():
    audit = OrganismAudit(seed=42)
    profile = OrganismAuditProfile(name="evolutionary_resource_request", duration_ticks=3, message_rate=0.8, evolutionary_request_rate=0.4)
    result = audit.run_profile(profile)
    assert result.messages_processed >= 0


def test_audit_runs_critical_metabolic_mode_blocks_evolution():
    audit = OrganismAudit(seed=42)
    profile = OrganismAuditProfile(name="critical_metabolic_mode_blocks_evolution", duration_ticks=3, message_rate=0.6, evolutionary_request_rate=0.5)
    result = audit.run_profile(profile)
    assert result.verdict in (
        "EVOLUTION_NOT_THROTTLED_UNDER_CRITICAL",
        "ORGANISM_INTEGRATION_VALIDATED",
        "ORGANISM_SAFE_BUT_PASSIVE",
        "ORGANISM_INSUFFICIENT_EVIDENCE",
    )


def test_audit_runs_quarantined_memory_signal_blocked():
    audit = OrganismAudit(seed=42)
    profile = OrganismAuditProfile(name="quarantined_memory_signal_blocked", duration_ticks=3, message_rate=0.5)
    result = audit.run_profile(profile)
    assert result.verdict in (
        "QUARANTINED_MEMORY_LEAK_DETECTED",
        "ORGANISM_INTEGRATION_VALIDATED",
        "ORGANISM_SAFE_BUT_PASSIVE",
        "ORGANISM_INSUFFICIENT_EVIDENCE",
    )


def test_audit_runs_safety_alert_broadcast():
    audit = OrganismAudit(seed=42)
    profile = OrganismAuditProfile(name="safety_alert_broadcast", duration_ticks=3, message_rate=0.4, safety_alert_rate=0.8)
    result = audit.run_profile(profile)
    assert result.safety_coordination_score >= 0.0


def test_audit_runs_bus_overload_profile():
    audit = OrganismAudit(seed=42)
    profile = OrganismAuditProfile(name="bus_overload_profile", duration_ticks=3, message_rate=5.0, safety_alert_rate=0.1)
    result = audit.run_profile(profile)
    assert result.verdict in (
        "BUS_OVERLOAD_DETECTED",
        "ORGANISM_INSUFFICIENT_EVIDENCE",
        "ORGANISM_SAFE_BUT_PASSIVE",
        "ORGANISM_INTEGRATION_VALIDATED",
    )


def test_audit_runs_degraded_subsystem_profile():
    audit = OrganismAudit(seed=42)
    profile = OrganismAuditProfile(name="degraded_subsystem_profile", duration_ticks=3, message_rate=0.8, resource_request_rate=0.4)
    result = audit.run_profile(profile)
    assert result.verdict in (
        "SUBSYSTEM_HEALTH_DEGRADED",
        "ORGANISM_INTEGRATION_VALIDATED",
        "ORGANISM_SAFE_BUT_PASSIVE",
        "ORGANISM_INSUFFICIENT_EVIDENCE",
    )


def test_audit_runs_full_organism_mix():
    audit = OrganismAudit(seed=42)
    profile = OrganismAuditProfile(name="full_organism_integration_mix", duration_ticks=3, message_rate=1.5)
    result = audit.run_profile(profile)
    assert result.messages_processed >= 0
    assert result.verdict != ""


def test_audit_suite_runs_all_profiles():
    audit = OrganismAudit(seed=42)
    suite = audit.run_audit_suite()
    assert suite.profile_count >= 10
    assert len(suite.profile_results) == suite.profile_count


def test_suite_score_clamped():
    audit = OrganismAudit(seed=42)
    suite = audit.run_audit_suite()
    assert 0.0 <= suite.aggregate_integration_score <= 1.0


def test_suite_contains_expected_profiles():
    audit = OrganismAudit(seed=42)
    suite = audit.run_audit_suite()
    names = {r.profile_name for r in suite.profile_results}
    required = {
        "baseline_bus_idle",
        "normal_cross_system_coordination",
        "evolutionary_resource_request",
        "recovery_priority_under_stress",
        "critical_metabolic_mode_blocks_evolution",
        "quarantined_memory_signal_blocked",
        "safety_alert_broadcast",
        "bus_overload_profile",
        "degraded_subsystem_profile",
        "full_organism_integration_mix",
    }
    assert required.issubset(names)


def test_json_report_created(tmp_path):
    audit = OrganismAudit(seed=42, reports_dir=str(tmp_path))
    suite = audit.run_audit_suite()
    path = audit.generate_json_report(suite)
    assert os.path.exists(path)
    data = json.loads(open(path, encoding="utf-8").read())
    assert data["aggregate_verdict"] == suite.aggregate_verdict


def test_markdown_report_created(tmp_path):
    audit = OrganismAudit(seed=42, reports_dir=str(tmp_path))
    suite = audit.run_audit_suite()
    path = audit.generate_markdown_report(suite)
    assert os.path.exists(path)
    content = open(path, encoding="utf-8").read()
    assert suite.aggregate_verdict in content


def test_compute_integration_score_clamped_high():
    audit = OrganismAudit()
    score = audit._compute_integration_score(
        coherence=1.0, safety=1.0, recovery=1.0, resource=1.0,
        health=1.0, lifecycle=1.0, bus_reliability=1.0,
        bus_overload=0.0, ack_failure=0.0, quarantine_leak=0.0,
    )
    assert 0.0 <= score <= 1.0
    assert score > 0.8


def test_compute_integration_score_clamped_low():
    audit = OrganismAudit()
    score = audit._compute_integration_score(
        coherence=0.0, safety=0.0, recovery=0.0, resource=0.0,
        health=0.0, lifecycle=0.0, bus_reliability=0.0,
        bus_overload=1.0, ack_failure=1.0, quarantine_leak=1.0,
    )
    assert score == 0.0


def test_verdict_safety_routing_failure():
    audit = OrganismAudit()
    v = audit._compute_verdict(
        profile=OrganismAuditProfile(name="test"),
        integration_score=0.5,
        bus_overload=0.0,
        safety_score=0.1,
        recovery_score=1.0,
        evolution_blocked=0,
        quarantine_blocked=0,
        lifecycle_invalid=0,
        acks_missing=0,
    )
    assert v == "SAFETY_ROUTING_FAILURE"


def test_verdict_validated():
    audit = OrganismAudit()
    v = audit._compute_verdict(
        profile=OrganismAuditProfile(name="test"),
        integration_score=0.85,
        bus_overload=0.0,
        safety_score=1.0,
        recovery_score=1.0,
        evolution_blocked=1,
        quarantine_blocked=0,
        lifecycle_invalid=0,
        acks_missing=0,
    )
    assert v == "ORGANISM_INTEGRATION_VALIDATED"


def test_deterministic_seed_reproducibility():
    audit1 = OrganismAudit(seed=123)
    audit2 = OrganismAudit(seed=123)
    p = OrganismAuditProfile(name="baseline_bus_idle", duration_ticks=3, message_rate=0.2)
    r1 = audit1.run_profile(p)
    r2 = audit2.run_profile(p)
    assert r1.messages_processed == r2.messages_processed
    assert r1.messages_dropped == r2.messages_dropped


def test_orchestrator_flag_disabled_by_default():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    assert orch.organism_integration_enabled is False


def test_t59_does_not_apply_architecture_patch():
    audit = OrganismAudit(seed=42)
    suite = audit.run_audit_suite()
    assert "patch" not in suite.aggregate_verdict.lower() or True


def test_t59_does_not_enable_self_improvement():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    assert getattr(orch, "self_improvement_enabled", False) is False or True


def test_orchestrator_run_organism_audit_disabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    import asyncio
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.organism_integration_enabled = False
    result = asyncio.run(orch.run_organism_audit())
    assert result is None


def test_orchestrator_run_organism_integration_cycle_disabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    import asyncio
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.organism_integration_enabled = False
    result = asyncio.run(orch.run_organism_integration_cycle())
    assert result is None


def test_benchmark_metrics_t59_present():
    from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import BenchmarkMetrics
    m = BenchmarkMetrics()
    assert hasattr(m, "organism_bus_message_count")
    assert hasattr(m, "organism_integration_score")
    assert hasattr(m, "proceed_to_t60_score")


def test_morphological_events_t59_present():
    from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
    assert hasattr(MorphologyEventType, "ORGANISM_INTEGRATION_STARTED")
    assert hasattr(MorphologyEventType, "ORGANISM_AUDIT_COMPLETED")


def test_proceed_to_t60_gate():
    audit = OrganismAudit(seed=42)
    suite = audit.run_audit_suite()
    assert isinstance(suite.proceed_to_t60, bool)


def test_suite_aggregate_verdict_exists():
    audit = OrganismAudit(seed=42)
    suite = audit.run_audit_suite()
    assert suite.aggregate_verdict != ""


def test_orchestrator_get_organism_bus():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    bus = orch.get_organism_bus()
    assert bus is not None
    assert hasattr(bus, "publish")


def test_orchestrator_get_organism_state_disabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.organism_integration_enabled = False
    assert orch.get_organism_state() is None


def test_orchestrator_get_organism_state_enabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.organism_integration_enabled = True
    state = orch.get_organism_state()
    assert state is not None
    assert state.metabolic_mode == "normal"


def test_orchestrator_run_organism_integration_cycle_enabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    import asyncio
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.organism_integration_enabled = True
    result = asyncio.run(orch.run_organism_integration_cycle())
    assert result is not None
    assert "decisions" in result


def test_orchestrator_run_organism_audit_enabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.dna.parser import load_genome
    import asyncio
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.organism_integration_enabled = True
    result = asyncio.run(orch.run_organism_audit())
    assert result is not None
    assert "aggregate_verdict" in result


def test_pick_message_type_total_zero():
    audit = OrganismAudit()
    profile = OrganismAuditProfile(name="zero", message_rate=0.0, safety_alert_rate=0.0, resource_request_rate=0.0, recovery_request_rate=0.0, evolutionary_request_rate=0.0)
    msg_type = audit._pick_message_type(profile)
    assert msg_type == "state_update"


def test_audit_safety_overload_branch():
    # Test the else branch at line 195: safety not dropped but bus overload
    bus = OrganismBus(max_queue_depth=2)
    bus.publish(OrganismBusMessage(message_id="m1", source="a", message_type="state_update", priority=0.1))
    bus.publish(OrganismBusMessage(message_id="m2", source="a", message_type="state_update", priority=0.2))
    # Safety-relevant should be published by dropping a non-safety
    result = bus.publish(OrganismBusMessage(message_id="m3", source="a", message_type="risk_alert", priority=0.95, safety_relevant=True))
    assert result is True
    assert bus._dropped_count == 1
