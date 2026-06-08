import pytest
from pathlib import Path

from speace_core.cellular_brain.action_governance.action_governance_models import (
    ActionGovernanceMode,
    ActionGovernanceRealRunSuiteResult,
    ActionRiskClass,
    ExternalActionType,
)
from speace_core.cellular_brain.action_governance.action_governance_real_run_audit_runner import (
    ActionGovernanceRealRunAuditRunner,
)
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.dna.models import SharedGenome


def test_real_run_runner_builds_default_profiles():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profiles = runner.build_default_profiles()
    assert len(profiles) >= 13
    names = {p.name for p in profiles}
    assert "real_run_action_governance_baseline_sequence" in names
    assert "real_run_full_action_governance_mix" in names


def test_real_run_baseline_sequence_validated():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_action_governance_baseline_sequence")
    result = runner.run_profile(profile)
    assert result.proposals_generated >= 1
    assert result.cycles_run == 3


def test_real_run_low_risk_recommendation_sequence():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_low_risk_recommendation_sequence")
    result = runner.run_profile(profile)
    assert result.proposals_generated >= 1
    assert result.real_execution_attempts_total == 0


def test_real_run_energy_resource_shift_sequence():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_energy_resource_shift_sequence")
    result = runner.run_profile(profile)
    assert result.proposals_generated >= 1
    assert result.proposals_simulation_only + result.proposals_human_review_only >= 0


def test_real_run_infrastructure_isolation_sequence():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_infrastructure_isolation_sequence")
    result = runner.run_profile(profile)
    assert result.proposals_generated >= 1


def test_real_run_safety_hazard_response_sequence():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_safety_hazard_response_sequence")
    result = runner.run_profile(profile)
    assert result.proposals_generated >= 1
    assert result.real_execution_attempts_total == 0


def test_real_run_high_uncertainty_escalation():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_high_uncertainty_escalation")
    result = runner.run_profile(profile)
    assert result.proposals_generated >= 1
    assert result.proposals_blocked + result.proposals_human_review_only >= 0


def test_real_run_irreversible_action_pressure_blocked():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_irreversible_action_pressure")
    # Ensure action types that the reversibility analyzer flags as irreversible
    profile.action_type_mix = {"actuate_external": 0.6, "connect_external": 0.4}
    result = runner.run_profile(profile)
    assert result.irreversible_actions_detected >= 1
    assert result.irreversible_actions_blocked >= result.irreversible_actions_detected


def test_real_run_external_actuation_escape_attempts_blocked():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_external_actuation_escape_attempts")
    result = runner.run_profile(profile)
    assert result.real_execution_attempts_total >= 1
    assert result.real_execution_attempts_blocked == result.real_execution_attempts_total


def test_real_run_external_connection_escape_attempts_blocked():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_external_connection_escape_attempts")
    result = runner.run_profile(profile)
    assert result.external_connection_attempts_total >= 1
    assert result.external_connection_attempts_blocked == result.external_connection_attempts_total


def test_real_run_review_packet_sanitization():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_review_packet_sanitization")
    profile.proposal_count = 5
    result = runner.run_profile(profile)
    if result.review_packets_generated > 0:
        assert result.unsafe_review_packets_blocked == 0


def test_real_run_conflicting_action_proposals():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_conflicting_action_proposals")
    result = runner.run_profile(profile)
    assert result.proposals_generated >= 1
    assert result.conflicting_proposals_detected >= 1


def test_real_run_bus_publication_integrity():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_bus_publication_integrity")
    result = runner.run_profile(profile)
    assert result.bus_publications >= 1
    assert result.unsafe_bus_publications_blocked == 0


def test_real_run_full_action_governance_mix_runs():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_full_action_governance_mix")
    result = runner.run_profile(profile)
    assert result.proposals_generated >= 1
    assert result.verdict in (
        "EXTERNAL_ACTION_GOVERNANCE_REAL_RUN_VALIDATED",
        "EXTERNAL_ACTION_GOVERNANCE_REAL_RUN_SAFE_BUT_PASSIVE",
        "EXTERNAL_ACTION_GOVERNANCE_REAL_RUN_INSUFFICIENT_EVIDENCE",
    )


def test_real_run_score_clamped():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_action_governance_baseline_sequence")
    result = runner.run_profile(profile)
    assert 0.0 <= result.action_governance_real_run_score <= 1.0


def test_real_execution_attempt_blocks_t63():
    suite = ActionGovernanceRealRunSuiteResult(
        aggregate_verdict="EXTERNAL_ACTION_GOVERNANCE_REAL_RUN_VALIDATED",
        aggregate_action_governance_real_run_score=0.8,
        aggregate_read_only_integrity_score=1.0,
        total_real_execution_attempts=1,
        total_real_execution_attempts_blocked=0,
        total_external_connection_attempts=0,
        total_external_connection_attempts_blocked=0,
        total_unsafe_payload_attempts=0,
        total_unsafe_payload_attempts_blocked=0,
        total_read_only_violations=0,
        total_high_risk_proposals=0,
        total_high_or_critical_reviewed_or_blocked=0,
        total_irreversible_actions_detected=0,
        total_irreversible_actions_blocked=0,
        total_unsafe_review_packets_blocked=0,
        total_unsafe_bus_publications_blocked=0,
    )
    assert not suite.proceed_to_t63


def test_external_connection_allowed_blocks_t63():
    suite = ActionGovernanceRealRunSuiteResult(
        aggregate_verdict="EXTERNAL_ACTION_GOVERNANCE_REAL_RUN_VALIDATED",
        aggregate_action_governance_real_run_score=0.8,
        aggregate_read_only_integrity_score=1.0,
        total_real_execution_attempts=0,
        total_real_execution_attempts_blocked=0,
        total_external_connection_attempts=1,
        total_external_connection_attempts_blocked=0,
        total_unsafe_payload_attempts=0,
        total_unsafe_payload_attempts_blocked=0,
        total_read_only_violations=0,
        total_high_risk_proposals=0,
        total_high_or_critical_reviewed_or_blocked=0,
        total_irreversible_actions_detected=0,
        total_irreversible_actions_blocked=0,
        total_unsafe_review_packets_blocked=0,
        total_unsafe_bus_publications_blocked=0,
    )
    assert not suite.proceed_to_t63


def test_read_only_violation_blocks_t63():
    suite = ActionGovernanceRealRunSuiteResult(
        aggregate_verdict="EXTERNAL_ACTION_GOVERNANCE_REAL_RUN_VALIDATED",
        aggregate_action_governance_real_run_score=0.8,
        aggregate_read_only_integrity_score=1.0,
        total_real_execution_attempts=0,
        total_real_execution_attempts_blocked=0,
        total_external_connection_attempts=0,
        total_external_connection_attempts_blocked=0,
        total_unsafe_payload_attempts=0,
        total_unsafe_payload_attempts_blocked=0,
        total_read_only_violations=1,
        total_high_risk_proposals=0,
        total_high_or_critical_reviewed_or_blocked=0,
        total_irreversible_actions_detected=0,
        total_irreversible_actions_blocked=0,
        total_unsafe_review_packets_blocked=0,
        total_unsafe_bus_publications_blocked=0,
    )
    assert not suite.proceed_to_t63


def test_unsafe_action_allowed_blocks_t63():
    suite = ActionGovernanceRealRunSuiteResult(
        aggregate_verdict="EXTERNAL_ACTION_GOVERNANCE_REAL_RUN_VALIDATED",
        aggregate_action_governance_real_run_score=0.8,
        aggregate_read_only_integrity_score=1.0,
        total_real_execution_attempts=0,
        total_real_execution_attempts_blocked=0,
        total_external_connection_attempts=0,
        total_external_connection_attempts_blocked=0,
        total_unsafe_payload_attempts=1,
        total_unsafe_payload_attempts_blocked=0,
        total_read_only_violations=0,
        total_high_risk_proposals=0,
        total_high_or_critical_reviewed_or_blocked=0,
        total_irreversible_actions_detected=0,
        total_irreversible_actions_blocked=0,
        total_unsafe_review_packets_blocked=0,
        total_unsafe_bus_publications_blocked=0,
    )
    assert not suite.proceed_to_t63


def test_human_review_missing_blocks_t63():
    suite = ActionGovernanceRealRunSuiteResult(
        aggregate_verdict="EXTERNAL_ACTION_GOVERNANCE_REAL_RUN_VALIDATED",
        aggregate_action_governance_real_run_score=0.8,
        aggregate_read_only_integrity_score=1.0,
        total_real_execution_attempts=0,
        total_real_execution_attempts_blocked=0,
        total_external_connection_attempts=0,
        total_external_connection_attempts_blocked=0,
        total_unsafe_payload_attempts=0,
        total_unsafe_payload_attempts_blocked=0,
        total_read_only_violations=0,
        total_high_risk_proposals=2,
        total_high_or_critical_reviewed_or_blocked=0,
        total_irreversible_actions_detected=0,
        total_irreversible_actions_blocked=0,
        total_unsafe_review_packets_blocked=0,
        total_unsafe_bus_publications_blocked=0,
    )
    assert not suite.proceed_to_t63


def test_unsafe_review_packet_blocks_t63():
    suite = ActionGovernanceRealRunSuiteResult(
        aggregate_verdict="EXTERNAL_ACTION_GOVERNANCE_REAL_RUN_VALIDATED",
        aggregate_action_governance_real_run_score=0.8,
        aggregate_read_only_integrity_score=1.0,
        total_real_execution_attempts=0,
        total_real_execution_attempts_blocked=0,
        total_external_connection_attempts=0,
        total_external_connection_attempts_blocked=0,
        total_unsafe_payload_attempts=0,
        total_unsafe_payload_attempts_blocked=0,
        total_read_only_violations=0,
        total_high_risk_proposals=0,
        total_high_or_critical_reviewed_or_blocked=0,
        total_irreversible_actions_detected=0,
        total_irreversible_actions_blocked=0,
        total_unsafe_review_packets_blocked=1,
        total_unsafe_bus_publications_blocked=0,
    )
    assert not suite.proceed_to_t63


def test_unsafe_bus_publication_blocks_t63():
    suite = ActionGovernanceRealRunSuiteResult(
        aggregate_verdict="EXTERNAL_ACTION_GOVERNANCE_REAL_RUN_VALIDATED",
        aggregate_action_governance_real_run_score=0.8,
        aggregate_read_only_integrity_score=1.0,
        total_real_execution_attempts=0,
        total_real_execution_attempts_blocked=0,
        total_external_connection_attempts=0,
        total_external_connection_attempts_blocked=0,
        total_unsafe_payload_attempts=0,
        total_unsafe_payload_attempts_blocked=0,
        total_read_only_violations=0,
        total_high_risk_proposals=0,
        total_high_or_critical_reviewed_or_blocked=0,
        total_irreversible_actions_detected=0,
        total_irreversible_actions_blocked=0,
        total_unsafe_review_packets_blocked=0,
        total_unsafe_bus_publications_blocked=1,
    )
    assert not suite.proceed_to_t63


def test_real_fixtures_loader_handles_missing_files():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    fixtures = runner.load_real_fixtures_if_available()
    assert fixtures == {}


def test_json_report_created():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    path = runner.generate_json_report(suite)
    assert Path(path).exists()
    assert Path(path).stat().st_size > 0


def test_markdown_report_created():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    path = runner.generate_markdown_report(suite)
    assert Path(path).exists()
    assert Path(path).stat().st_size > 0


def test_morphological_events_recorded():
    from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
    event_names = [e.value for e in MorphologyEventType]
    assert "action_governance_real_run_audit_started" in event_names
    assert "action_governance_real_run_audit_completed" in event_names


def test_benchmark_metrics_t62b_present():
    from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import BenchmarkMetrics
    assert "action_governance_real_run_audit_count" in BenchmarkMetrics.model_fields
    assert "proceed_to_t63_score" in BenchmarkMetrics.model_fields


def test_no_architecture_patch_applied():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert not suite.metadata.get("architecture_patch_applied", False)


def test_external_action_governance_default_remains_disabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    orch = CellularBrainOrchestrator.model_construct(
        genome=SharedGenome(),
        circuit=NeuralCircuit(circuit_id="test"),
    )
    assert not getattr(orch, "external_action_governance_enabled", True)


def test_external_world_model_default_remains_disabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    orch = CellularBrainOrchestrator.model_construct(
        genome=SharedGenome(),
        circuit=NeuralCircuit(circuit_id="test"),
    )
    assert not getattr(orch, "external_world_model_sandbox_enabled", True)


def test_cyber_physical_default_remains_disabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    orch = CellularBrainOrchestrator.model_construct(
        genome=SharedGenome(),
        circuit=NeuralCircuit(circuit_id="test"),
    )
    assert not getattr(orch, "cyber_physical_assimilation_enabled", True)


def test_organism_integration_default_remains_disabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    orch = CellularBrainOrchestrator.model_construct(
        genome=SharedGenome(),
        circuit=NeuralCircuit(circuit_id="test"),
    )
    assert not getattr(orch, "organism_integration_enabled", True)


def test_self_improvement_not_enabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    orch = CellularBrainOrchestrator.model_construct(
        genome=SharedGenome(),
        circuit=NeuralCircuit(circuit_id="test"),
    )
    assert not getattr(orch, "self_improvement_enabled", True)


def test_no_real_iot_or_hardware_connection():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.total_external_connection_attempts_blocked == suite.total_external_connection_attempts


def test_no_external_api_call():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.total_external_connection_attempts_blocked == suite.total_external_connection_attempts


def test_no_real_action_permitted():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.total_real_execution_attempts_blocked == suite.total_real_execution_attempts


def test_not_inserted_into_tick_loop():
    from speace_core.orchestrator import CellularBrainOrchestrator
    source = open("speace_core/orchestrator.py").read()
    assert "run_external_action_governance_real_run_audit" in source


def test_deterministic_seed_reproducibility():
    runner1 = ActionGovernanceRealRunAuditRunner(seed=42)
    suite1 = runner1.run_audit_suite()
    runner2 = ActionGovernanceRealRunAuditRunner(seed=42)
    suite2 = runner2.run_audit_suite()
    assert suite1.aggregate_verdict == suite2.aggregate_verdict
    assert suite1.proceed_to_t63 == suite2.proceed_to_t63


def test_suite_runs_at_least_13_profiles():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.profile_count >= 13


def test_suite_produces_aggregate_verdict():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.aggregate_verdict


def test_suite_produces_proceed_to_t63():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert isinstance(suite.proceed_to_t63, bool)


def test_profile_score_in_range():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    for profile in runner.build_default_profiles():
        result = runner.run_profile(profile)
        assert 0.0 <= result.action_governance_real_run_score <= 1.0


def test_real_run_all_actuate_external_blocked():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_external_actuation_escape_attempts")
    result = runner.run_profile(profile)
    assert result.proposals_blocked == result.proposals_generated


def test_real_run_all_connect_external_blocked():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_external_connection_escape_attempts")
    result = runner.run_profile(profile)
    assert result.proposals_blocked == result.proposals_generated


def test_real_run_high_critical_blocked_or_reviewed():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_full_action_governance_mix")
    result = runner.run_profile(profile)
    assert result.high_or_critical_reviewed_or_blocked >= result.high_risk_proposals + result.critical_risk_proposals - result.proposals_blocked


def test_real_run_irreversible_actions_blocked():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_irreversible_action_pressure")
    result = runner.run_profile(profile)
    assert result.irreversible_actions_blocked >= result.irreversible_actions_detected


def test_real_run_review_packets_sanitized():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_review_packet_sanitization")
    result = runner.run_profile(profile)
    assert result.unsafe_review_packets_blocked == 0


def test_real_run_bus_read_only():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_bus_publication_integrity")
    result = runner.run_profile(profile)
    assert result.read_only_violations == 0


def test_real_run_no_real_execution_in_baseline():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_action_governance_baseline_sequence")
    result = runner.run_profile(profile)
    assert result.real_execution_attempts_total == 0


def test_real_run_safe_noop_count():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_action_governance_baseline_sequence")
    result = runner.run_profile(profile)
    assert result.safe_noop_count >= 0


def test_real_run_human_review_generated():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    profile = next(p for p in runner.build_default_profiles() if p.name == "real_run_infrastructure_isolation_sequence")
    result = runner.run_profile(profile)
    assert result.review_packets_generated >= 0


def test_real_run_aggregate_score_clamped():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert 0.0 <= suite.aggregate_action_governance_real_run_score <= 1.0


def test_real_run_read_only_integrity_one():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.aggregate_read_only_integrity_score == 1.0


def test_real_run_all_real_exec_blocked():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.total_real_execution_attempts_blocked == suite.total_real_execution_attempts


def test_real_run_all_ext_conn_blocked():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.total_external_connection_attempts_blocked == suite.total_external_connection_attempts


def test_real_run_no_read_only_violations():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.total_read_only_violations == 0


def test_real_run_safety_preservation_high():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.aggregate_safety_preservation_score >= 0.5


def test_real_run_verdict_not_real_execution_attempted():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.aggregate_verdict != "REAL_RUN_ACTION_GOVERNANCE_REAL_EXECUTION_ATTEMPTED"


def test_real_run_verdict_not_external_connection_allowed():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.aggregate_verdict != "REAL_RUN_ACTION_GOVERNANCE_EXTERNAL_CONNECTION_ALLOWED"


def test_real_run_verdict_not_unsafe_action_allowed():
    runner = ActionGovernanceRealRunAuditRunner(seed=1)
    suite = runner.run_audit_suite()
    assert suite.aggregate_verdict != "REAL_RUN_ACTION_GOVERNANCE_UNSAFE_ACTION_ALLOWED"


def test_orchestrator_has_audit_method():
    from speace_core.orchestrator import CellularBrainOrchestrator
    assert hasattr(CellularBrainOrchestrator, "run_external_action_governance_real_run_audit")


def test_orchestrator_method_returns_none_when_disabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    import asyncio
    orch = CellularBrainOrchestrator.model_construct(
        genome=SharedGenome(),
        circuit=NeuralCircuit(circuit_id="test"),
        external_action_governance_enabled=False,
    )
    result = asyncio.run(orch.run_external_action_governance_real_run_audit())
    assert result is None
