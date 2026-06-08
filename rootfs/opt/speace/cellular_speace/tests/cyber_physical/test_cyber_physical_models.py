import pytest
from speace_core.cellular_brain.cyber_physical.cyber_physical_models import (
    ActuationRequest,
    AssimilationDecision,
    CyberPhysicalAuditProfile,
    CyberPhysicalAuditResult,
    CyberPhysicalAuditSuiteResult,
    CyberPhysicalMode,
    ExternalSignal,
    ExternalSignalType,
    SensorStream,
    WorldStateSnapshot,
)


class TestCyberPhysicalModels:
    def test_external_signal_creation(self):
        signal = ExternalSignal(
            signal_id="sig_001",
            source_id="src_001",
            signal_type="environmental",
            value=0.5,
            confidence=0.8,
            safety_relevance=0.2,
            noise_score=0.1,
        )
        assert signal.signal_id == "sig_001"
        assert signal.confidence == 0.8

    def test_external_signal_defaults(self):
        signal = ExternalSignal(
            signal_id="sig_002",
            source_id="src_002",
            signal_type="energy",
        )
        assert signal.confidence == 1.0
        assert signal.safety_relevance == 0.0
        assert signal.noise_score == 0.0
        assert signal.value == 0.0

    def test_sensor_stream_creation(self):
        stream = SensorStream(
            stream_id="stream_1",
            source_id="src_1",
            signal_type="environmental",
        )
        assert stream.mode == CyberPhysicalMode.SIMULATED_READ_ONLY.value
        assert stream.active is True
        assert stream.sample_count == 0

    def test_world_state_snapshot_creation(self):
        snapshot = WorldStateSnapshot(
            snapshot_id="ws_1",
            signal_count=3,
            environmental_pressure=0.4,
            infrastructure_pressure=0.3,
            energy_pressure=0.2,
            safety_pressure=0.1,
            uncertainty_score=0.1,
            world_coherence_score=0.9,
        )
        assert snapshot.world_coherence_score == 0.9
        assert snapshot.signal_count == 3

    def test_assimilation_decision_creation(self):
        decision = AssimilationDecision(
            decision_id="dec_1",
            signal_id="sig_1",
            action="accept",
            accepted=True,
            quarantined=False,
        )
        assert decision.accepted is True
        assert decision.safety_relevant is False

    def test_actuation_request_defaults(self):
        req = ActuationRequest(
            request_id="req_1",
            target_system="actuator_1",
            action="actuate",
        )
        assert req.blocked is True
        assert req.requires_human_approval is True
        assert req.risk_score == 0.0

    def test_cyber_physical_mode_values(self):
        assert CyberPhysicalMode.SIMULATED_READ_ONLY.value == "simulated_read_only"
        assert CyberPhysicalMode.SANDBOXED_READ_ONLY.value == "sandboxed_read_only"
        assert CyberPhysicalMode.PASSIVE_MONITORING.value == "passive_monitoring"
        assert CyberPhysicalMode.QUARANTINED.value == "quarantined"
        assert CyberPhysicalMode.BLOCKED.value == "blocked"

    def test_external_signal_type_values(self):
        assert ExternalSignalType.ENVIRONMENTAL.value == "environmental"
        assert ExternalSignalType.ENERGY.value == "energy"
        assert ExternalSignalType.INFRASTRUCTURE.value == "infrastructure"
        assert ExternalSignalType.SENSOR.value == "sensor"
        assert ExternalSignalType.SYSTEM_HEALTH.value == "system_health"
        assert ExternalSignalType.HUMAN_FEEDBACK.value == "human_feedback"
        assert ExternalSignalType.NETWORK_STATUS.value == "network_status"
        assert ExternalSignalType.UNKNOWN.value == "unknown"

    def test_cyber_physical_audit_profile_creation(self):
        profile = CyberPhysicalAuditProfile(
            name="test_profile",
            signal_count=5,
            noise_level=0.2,
        )
        assert profile.duration_ticks == 5
        assert profile.invalid_signal_rate == 0.0

    def test_cyber_physical_audit_result_defaults(self):
        result = CyberPhysicalAuditResult(profile_name="test")
        assert result.verdict == "CYBER_PHYSICAL_INSUFFICIENT_EVIDENCE"
        assert result.world_state_coherence_score == 1.0

    def test_cyber_physical_audit_suite_result_defaults(self):
        suite = CyberPhysicalAuditSuiteResult()
        assert suite.aggregate_verdict == "CYBER_PHYSICAL_INSUFFICIENT_EVIDENCE"
        assert suite.proceed_to_t60b is False

    def test_external_signal_with_dict_value(self):
        signal = ExternalSignal(
            signal_id="sig_003",
            source_id="src_003",
            signal_type="system_health",
            value={"temperature": 22.5},
            confidence=0.9,
        )
        assert signal.value == {"temperature": 22.5}

    def test_actuation_request_with_payload(self):
        req = ActuationRequest(
            request_id="req_2",
            target_system="motor_1",
            action="rotate",
            payload={"angle": 90},
            risk_score=0.3,
        )
        assert req.payload["angle"] == 90

    def test_sensor_stream_mode_blocked(self):
        stream = SensorStream(
            stream_id="stream_2",
            source_id="src_2",
            signal_type="sensor",
            mode=CyberPhysicalMode.BLOCKED.value,
        )
        assert stream.mode == "blocked"

    def test_world_state_snapshot_metadata(self):
        snapshot = WorldStateSnapshot(
            snapshot_id="ws_meta",
            metadata={"source": "test"},
        )
        assert snapshot.metadata["source"] == "test"
