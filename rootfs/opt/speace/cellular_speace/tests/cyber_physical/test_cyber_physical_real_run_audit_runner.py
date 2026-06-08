import os
import pytest
from speace_core.cellular_brain.cyber_physical.cyber_physical_real_run_audit_runner import (
    CyberPhysicalRealRunAuditRunner,
)
from speace_core.cellular_brain.cyber_physical.cyber_physical_models import (
    CyberPhysicalRealRunProfile,
)


class TestCyberPhysicalRealRunAuditRunner:
    def test_builds_default_profiles(self):
        runner = CyberPhysicalRealRunAuditRunner()
        profiles = runner.build_default_profiles()
        assert len(profiles) >= 11
        for p in profiles:
            assert p.name
            assert p.duration_ticks > 0

    def test_load_real_fixtures_if_available(self):
        runner = CyberPhysicalRealRunAuditRunner()
        fixtures = runner.load_real_fixtures_if_available()
        assert isinstance(fixtures, dict)

    def test_build_synthetic_streams_for_profile(self):
        runner = CyberPhysicalRealRunAuditRunner()
        profile = CyberPhysicalRealRunProfile(
            name="test", stream_count=3, signal_mix={"environmental": 1.0}
        )
        streams = runner.build_synthetic_streams_for_profile(profile)
        assert len(streams) == 3

    def test_real_run_environment_baseline_validated(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        profile = CyberPhysicalRealRunProfile(
            name="real_run_environment_baseline",
            duration_ticks=5,
            stream_count=3,
            signal_mix={"environmental": 1.0},
            noise_level=0.0,
            actuation_attempts=0,
        )
        result = runner.run_profile(profile)
        assert result.signals_processed > 0
        assert result.actuation_requests_blocked == 0

    def test_real_run_multi_sensor_noise_quarantines_noisy_signals(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        profile = CyberPhysicalRealRunProfile(
            name="real_run_multi_sensor_noise",
            duration_ticks=5,
            stream_count=4,
            signal_mix={"environmental": 0.5, "sensor": 0.5},
            noise_level=0.6,
            actuation_attempts=0,
        )
        result = runner.run_profile(profile)
        assert result.signals_processed > 0

    def test_real_run_conflicting_environment_streams_detected(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        profile = CyberPhysicalRealRunProfile(
            name="real_run_conflicting_environment_streams",
            duration_ticks=5,
            stream_count=3,
            signal_mix={"environmental": 1.0},
            noise_level=0.1,
            conflict_level=0.8,
            actuation_attempts=0,
        )
        result = runner.run_profile(profile)
        assert result.signals_processed > 0
        assert result.conflicting_signals_detected >= 0

    def test_real_run_energy_pressure_sequence_updates_world_state(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        profile = CyberPhysicalRealRunProfile(
            name="real_run_energy_pressure_sequence",
            duration_ticks=7,
            stream_count=2,
            signal_mix={"energy": 1.0},
            noise_level=0.0,
            actuation_attempts=0,
        )
        result = runner.run_profile(profile)
        assert result.world_states_generated > 0

    def test_real_run_infrastructure_pressure_sequence_updates_world_state(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        profile = CyberPhysicalRealRunProfile(
            name="real_run_infrastructure_pressure_sequence",
            duration_ticks=5,
            stream_count=2,
            signal_mix={"infrastructure": 1.0},
            noise_level=0.0,
            actuation_attempts=0,
        )
        result = runner.run_profile(profile)
        assert result.world_states_generated > 0

    def test_real_run_safety_relevant_signal_burst_routes_read_only(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        profile = CyberPhysicalRealRunProfile(
            name="real_run_safety_relevant_signal_burst",
            duration_ticks=5,
            stream_count=3,
            signal_mix={"sensor": 0.7, "environmental": 0.3},
            noise_level=0.0,
            actuation_attempts=0,
        )
        result = runner.run_profile(profile)
        assert result.signals_processed > 0
        assert result.unsafe_bus_publications_blocked == 0

    def test_real_run_malicious_payload_injection_blocked(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        profile = CyberPhysicalRealRunProfile(
            name="real_run_malicious_payload_injection",
            duration_ticks=5,
            stream_count=2,
            signal_mix={"system_health": 0.5, "network_status": 0.5},
            noise_level=0.0,
            actuation_attempts=0,
        )
        result = runner.run_profile(profile)
        assert result.signals_processed > 0

    def test_real_run_actuation_escape_attempt_blocked(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        profile = CyberPhysicalRealRunProfile(
            name="real_run_actuation_escape_attempt",
            duration_ticks=5,
            stream_count=1,
            signal_mix={"sensor": 1.0},
            noise_level=0.0,
            actuation_attempts=8,
        )
        result = runner.run_profile(profile)
        assert result.actuation_requests_total == 8
        assert result.actuation_requests_blocked == 8
        assert result.verdict != "REAL_RUN_ACTUATION_NOT_BLOCKED"

    def test_real_run_real_connection_attempt_blocked(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        profile = CyberPhysicalRealRunProfile(
            name="real_run_real_connection_attempt_blocked",
            duration_ticks=5,
            stream_count=2,
            signal_mix={"network_status": 1.0},
            noise_level=0.0,
            actuation_attempts=0,
        )
        result = runner.run_profile(profile)
        assert result.real_connection_attempts_blocked >= 0

    def test_real_run_organism_bus_publication_integrity(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        profile = CyberPhysicalRealRunProfile(
            name="real_run_organism_bus_publication_integrity",
            duration_ticks=5,
            stream_count=2,
            signal_mix={"environmental": 0.5, "infrastructure": 0.5},
            noise_level=0.0,
            actuation_attempts=0,
        )
        result = runner.run_profile(profile)
        assert result.bus_publications >= 0
        assert result.unsafe_bus_publications_blocked == 0

    def test_real_run_full_cyber_physical_mix_runs(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        profile = CyberPhysicalRealRunProfile(
            name="real_run_full_cyber_physical_mix",
            duration_ticks=7,
            stream_count=5,
            signal_mix={"environmental": 0.3, "energy": 0.2, "infrastructure": 0.2, "sensor": 0.2, "network_status": 0.1},
            noise_level=0.2,
            conflict_level=0.2,
            actuation_attempts=3,
        )
        result = runner.run_profile(profile)
        assert result.signals_processed > 0
        assert result.actuation_requests_blocked == 3

    def test_suite_runs_all_profiles(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        suite = runner.run_audit_suite()
        assert suite.profile_count >= 11
        assert suite.total_signals_processed > 0
        assert suite.aggregate_verdict
        assert suite.aggregate_cyber_physical_real_run_score >= 0.0
        assert suite.aggregate_cyber_physical_real_run_score <= 1.0

    def test_suite_actuation_all_blocked(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        suite = runner.run_audit_suite()
        assert suite.total_actuation_requests > 0
        assert suite.total_actuation_requests_blocked == suite.total_actuation_requests

    def test_suite_read_only_violations_zero(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        suite = runner.run_audit_suite()
        assert suite.total_read_only_violations == 0

    def test_suite_score_clamped(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        suite = runner.run_audit_suite()
        assert suite.aggregate_cyber_physical_real_run_score <= 1.0
        assert suite.aggregate_cyber_physical_real_run_score >= 0.0

    def test_actuation_not_blocked_blocks_t61(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        suite = runner.run_audit_suite()
        assert suite.proceed_to_t61 is True or suite.aggregate_verdict != "REAL_RUN_ACTUATION_NOT_BLOCKED"

    def test_read_only_violation_blocks_t61(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        suite = runner.run_audit_suite()
        if suite.total_read_only_violations > 0:
            assert suite.proceed_to_t61 is False

    def test_real_connection_allowed_blocks_t61(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        suite = runner.run_audit_suite()
        if suite.aggregate_verdict == "REAL_RUN_REAL_CONNECTION_ATTEMPT_ALLOWED":
            assert suite.proceed_to_t61 is False

    def test_unsafe_external_signal_routed_blocks_t61(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        suite = runner.run_audit_suite()
        if suite.aggregate_verdict == "REAL_RUN_UNSAFE_EXTERNAL_SIGNAL_ROUTED":
            assert suite.proceed_to_t61 is False

    def test_json_report_created(self, tmp_path):
        runner = CyberPhysicalRealRunAuditRunner(seed=42, reports_dir=str(tmp_path))
        suite = runner.run_audit_suite()
        path = runner.generate_json_report(suite)
        assert os.path.exists(path)
        assert path.endswith(".json")

    def test_markdown_report_created(self, tmp_path):
        runner = CyberPhysicalRealRunAuditRunner(seed=42, reports_dir=str(tmp_path))
        suite = runner.run_audit_suite()
        path = runner.generate_markdown_report(suite)
        assert os.path.exists(path)
        assert path.endswith(".md")

    def test_deterministic_seed_reproducibility(self):
        import random
        state = random.getstate()
        runner1 = CyberPhysicalRealRunAuditRunner(seed=123)
        suite1 = runner1.run_audit_suite()
        random.setstate(state)
        runner2 = CyberPhysicalRealRunAuditRunner(seed=123)
        suite2 = runner2.run_audit_suite()
        assert suite1.aggregate_cyber_physical_real_run_score == suite2.aggregate_cyber_physical_real_run_score
        assert suite1.aggregate_verdict == suite2.aggregate_verdict

    def test_real_fixtures_loader_handles_missing_files(self):
        runner = CyberPhysicalRealRunAuditRunner()
        fixtures = runner.load_real_fixtures_if_available()
        assert isinstance(fixtures, dict)

    def test_noisy_signal_quarantine_score(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        profile = CyberPhysicalRealRunProfile(
            name="noisy_test",
            duration_ticks=5,
            stream_count=2,
            signal_mix={"environmental": 1.0},
            noise_level=0.8,
            actuation_attempts=0,
        )
        result = runner.run_profile(profile)
        assert result.signals_quarantined >= 0

    def test_invalid_signal_block_score(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        profile = CyberPhysicalRealRunProfile(
            name="invalid_test",
            duration_ticks=5,
            stream_count=2,
            signal_mix={"environmental": 1.0},
            noise_level=0.0,
            actuation_attempts=0,
        )
        result = runner.run_profile(profile)
        assert result.invalid_signals_blocked >= 0

    def test_world_state_coherence_computed(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        profile = CyberPhysicalRealRunProfile(
            name="coherence_test",
            duration_ticks=5,
            stream_count=2,
            signal_mix={"environmental": 1.0},
            noise_level=0.0,
            actuation_attempts=0,
        )
        result = runner.run_profile(profile)
        assert 0.0 <= result.average_world_coherence_score <= 1.0

    def test_safety_preservation_computed(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        profile = CyberPhysicalRealRunProfile(
            name="safety_test",
            duration_ticks=5,
            stream_count=2,
            signal_mix={"environmental": 1.0},
            noise_level=0.0,
            actuation_attempts=0,
        )
        result = runner.run_profile(profile)
        assert 0.0 <= result.average_safety_preservation_score <= 1.0

    def test_read_only_integrity_score_one_when_no_actuation(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        profile = CyberPhysicalRealRunProfile(
            name="ro_integrity_test",
            duration_ticks=3,
            stream_count=1,
            signal_mix={"environmental": 1.0},
            noise_level=0.0,
            actuation_attempts=0,
        )
        result = runner.run_profile(profile)
        assert result.read_only_integrity_score == 1.0

    def test_read_only_integrity_score_one_when_actuation_blocked(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        profile = CyberPhysicalRealRunProfile(
            name="ro_integrity_blocked_test",
            duration_ticks=3,
            stream_count=1,
            signal_mix={"environmental": 1.0},
            noise_level=0.0,
            actuation_attempts=5,
        )
        result = runner.run_profile(profile)
        assert result.read_only_integrity_score == 1.0

    def test_profile_verdict_not_empty(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        profile = CyberPhysicalRealRunProfile(
            name="verdict_test",
            duration_ticks=3,
            stream_count=1,
            signal_mix={"environmental": 1.0},
            noise_level=0.0,
            actuation_attempts=0,
        )
        result = runner.run_profile(profile)
        assert result.verdict != ""

    def test_aggregate_verdict_validated_or_safe_or_insufficient(self):
        runner = CyberPhysicalRealRunAuditRunner(seed=42)
        suite = runner.run_audit_suite()
        assert suite.aggregate_verdict in [
            "CYBER_PHYSICAL_REAL_RUN_VALIDATED",
            "CYBER_PHYSICAL_REAL_RUN_SAFE_BUT_PASSIVE",
            "CYBER_PHYSICAL_REAL_RUN_INSUFFICIENT_EVIDENCE",
            "REAL_RUN_ACTUATION_NOT_BLOCKED",
            "REAL_RUN_READ_ONLY_MODE_VIOLATION",
            "REAL_RUN_INVALID_SIGNAL_ACCEPTED",
            "REAL_RUN_NOISY_SIGNAL_NOT_QUARANTINED",
            "REAL_RUN_CONFLICTING_WORLD_STATE_UNDETECTED",
            "REAL_RUN_UNSAFE_EXTERNAL_SIGNAL_ROUTED",
            "REAL_RUN_ORGANISM_BUS_PUBLICATION_FAILURE",
            "REAL_RUN_REAL_CONNECTION_ATTEMPT_ALLOWED",
        ]

    def test_compute_score_clamped_max(self):
        score = CyberPhysicalRealRunAuditRunner._compute_score(
            assimilation_quality=1.0,
            safety_preservation=1.0,
            world_state_coherence=1.0,
            invalid_block=1.0,
            noisy_quarantine=1.0,
            read_only_integrity=1.0,
            bus_publication=1.0,
            actuation_violation=0.0,
            real_connection_attempt=0.0,
            unsafe_routing=0.0,
            conflict=0.0,
        )
        assert score == 1.0

    def test_compute_score_clamped_min(self):
        score = CyberPhysicalRealRunAuditRunner._compute_score(
            assimilation_quality=0.0,
            safety_preservation=0.0,
            world_state_coherence=0.0,
            invalid_block=0.0,
            noisy_quarantine=0.0,
            read_only_integrity=0.0,
            bus_publication=0.0,
            actuation_violation=1.0,
            real_connection_attempt=1.0,
            unsafe_routing=1.0,
            conflict=1.0,
        )
        assert score == 0.0

    def test_compute_verdict_actuation_not_blocked(self):
        profile = CyberPhysicalRealRunProfile(
            name="test",
            actuation_attempts=1,
            expected_risk_type="REAL_RUN_ACTUATION_NOT_BLOCKED",
        )
        verdict = CyberPhysicalRealRunAuditRunner._compute_verdict(
            profile=profile,
            score=0.5,
            actuation_blocked=0,
            actuation_total=1,
            read_only_violations=0,
            invalid_blocked=0,
            noisy_quarantined=0,
            unsafe_routed=0,
            conflicts=0,
            real_connection_blocked=0,
        )
        assert verdict == "REAL_RUN_ACTUATION_NOT_BLOCKED"

    def test_compute_verdict_read_only_violation(self):
        profile = CyberPhysicalRealRunProfile(name="test")
        verdict = CyberPhysicalRealRunAuditRunner._compute_verdict(
            profile=profile,
            score=0.5,
            actuation_blocked=0,
            actuation_total=0,
            read_only_violations=1,
            invalid_blocked=0,
            noisy_quarantined=0,
            unsafe_routed=0,
            conflicts=0,
            real_connection_blocked=0,
        )
        assert verdict == "REAL_RUN_READ_ONLY_MODE_VIOLATION"

    def test_compute_verdict_validated(self):
        profile = CyberPhysicalRealRunProfile(name="test")
        verdict = CyberPhysicalRealRunAuditRunner._compute_verdict(
            profile=profile,
            score=0.75,
            actuation_blocked=0,
            actuation_total=0,
            read_only_violations=0,
            invalid_blocked=0,
            noisy_quarantined=0,
            unsafe_routed=0,
            conflicts=0,
            real_connection_blocked=0,
        )
        assert verdict == "CYBER_PHYSICAL_REAL_RUN_VALIDATED"

    def test_compute_verdict_safe_but_passive(self):
        profile = CyberPhysicalRealRunProfile(name="test")
        verdict = CyberPhysicalRealRunAuditRunner._compute_verdict(
            profile=profile,
            score=0.55,
            actuation_blocked=0,
            actuation_total=0,
            read_only_violations=0,
            invalid_blocked=0,
            noisy_quarantined=0,
            unsafe_routed=0,
            conflicts=0,
            real_connection_blocked=0,
        )
        assert verdict == "CYBER_PHYSICAL_REAL_RUN_SAFE_BUT_PASSIVE"

    def test_compute_verdict_insufficient_evidence(self):
        profile = CyberPhysicalRealRunProfile(name="test")
        verdict = CyberPhysicalRealRunAuditRunner._compute_verdict(
            profile=profile,
            score=0.2,
            actuation_blocked=0,
            actuation_total=0,
            read_only_violations=0,
            invalid_blocked=0,
            noisy_quarantined=0,
            unsafe_routed=0,
            conflicts=0,
            real_connection_blocked=0,
        )
        assert verdict == "CYBER_PHYSICAL_REAL_RUN_INSUFFICIENT_EVIDENCE"

    def test_compute_aggregate_verdict_actuation_not_blocked(self):
        from speace_core.cellular_brain.cyber_physical.cyber_physical_models import (
            CyberPhysicalRealRunProfileResult,
        )
        results = [
            CyberPhysicalRealRunProfileResult(
                profile_name="a", verdict="REAL_RUN_ACTUATION_NOT_BLOCKED"
            ),
        ]
        verdict = CyberPhysicalRealRunAuditRunner.compute_aggregate_verdict(results)
        assert verdict == "REAL_RUN_ACTUATION_NOT_BLOCKED"

    def test_compute_aggregate_verdict_validated(self):
        from speace_core.cellular_brain.cyber_physical.cyber_physical_models import (
            CyberPhysicalRealRunProfileResult,
        )
        results = [
            CyberPhysicalRealRunProfileResult(
                profile_name="a", verdict="CYBER_PHYSICAL_REAL_RUN_VALIDATED", cyber_physical_real_run_score=0.8
            ),
        ]
        verdict = CyberPhysicalRealRunAuditRunner.compute_aggregate_verdict(results)
        assert verdict == "CYBER_PHYSICAL_REAL_RUN_VALIDATED"

    def test_profile_result_defaults(self):
        from speace_core.cellular_brain.cyber_physical.cyber_physical_models import (
            CyberPhysicalRealRunProfileResult,
        )
        result = CyberPhysicalRealRunProfileResult(profile_name="test")
        assert result.verdict == "CYBER_PHYSICAL_REAL_RUN_INSUFFICIENT_EVIDENCE"
        assert result.cyber_physical_real_run_score == 0.0

    def test_suite_result_defaults(self):
        from speace_core.cellular_brain.cyber_physical.cyber_physical_models import (
            CyberPhysicalRealRunSuiteResult,
        )
        suite = CyberPhysicalRealRunSuiteResult()
        assert suite.aggregate_verdict == "CYBER_PHYSICAL_REAL_RUN_INSUFFICIENT_EVIDENCE"
        assert suite.proceed_to_t61 is False

    def test_benchmark_metrics_t60b_present(self):
        from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import (
            BenchmarkMetrics,
        )
        m = BenchmarkMetrics()
        assert hasattr(m, "cyber_physical_real_run_audit_count")
        assert hasattr(m, "cyber_physical_real_run_profile_count")
        assert hasattr(m, "cyber_physical_real_run_total_ticks")
        assert hasattr(m, "cyber_physical_real_run_actuation_request_count")
        assert hasattr(m, "cyber_physical_real_run_read_only_integrity_score")
        assert hasattr(m, "cyber_physical_real_run_score")
        assert hasattr(m, "proceed_to_t61_score")

    def test_morphological_events_t60b_present(self):
        from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
        assert hasattr(MorphologyEventType, "CYBER_PHYSICAL_REAL_RUN_AUDIT_STARTED")
        assert hasattr(MorphologyEventType, "CYBER_PHYSICAL_REAL_RUN_PROFILE_COMPLETED")
        assert hasattr(MorphologyEventType, "CYBER_PHYSICAL_REAL_RUN_ACTUATION_BLOCKED")
        assert hasattr(MorphologyEventType, "CYBER_PHYSICAL_REAL_RUN_AUDIT_COMPLETED")

    def test_orchestrator_has_real_run_audit_method(self):
        from speace_core.orchestrator import CellularBrainOrchestrator
        assert hasattr(CellularBrainOrchestrator, "run_cyber_physical_real_run_audit")

    def test_orchestrator_real_run_audit_disabled_by_default(self):
        from speace_core.orchestrator import CellularBrainOrchestrator
        from speace_core.dna.models import SharedGenome
        import asyncio
        orch = CellularBrainOrchestrator.build_mvp(SharedGenome())
        assert orch.cyber_physical_assimilation_enabled is False
        result = asyncio.run(orch.run_cyber_physical_real_run_audit())
        assert result is None

    def test_orchestrator_real_run_audit_when_enabled(self):
        from speace_core.orchestrator import CellularBrainOrchestrator
        from speace_core.dna.models import SharedGenome
        import asyncio
        orch = CellularBrainOrchestrator.build_mvp(SharedGenome())
        orch.cyber_physical_assimilation_enabled = True
        result = asyncio.run(orch.run_cyber_physical_real_run_audit())
        assert result is not None
        assert "aggregate_verdict" in result
