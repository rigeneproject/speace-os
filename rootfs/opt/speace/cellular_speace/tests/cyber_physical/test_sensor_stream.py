import pytest
from speace_core.cellular_brain.cyber_physical.sensor_stream import SensorStreamManager
from speace_core.cellular_brain.cyber_physical.cyber_physical_models import (
    CyberPhysicalMode,
    ExternalSignal,
)


class TestSensorStream:
    def test_create_stream(self):
        mgr = SensorStreamManager()
        stream = mgr.create_stream(
            stream_id="test_stream",
            source_id="simulated_sensor",
            signal_type="environmental",
        )
        assert stream.stream_id == "test_stream"
        assert stream.active is True

    def test_list_streams(self):
        mgr = SensorStreamManager()
        mgr.create_stream("s1", "src1", "environmental")
        mgr.create_stream("s2", "src2", "energy")
        streams = mgr.list_streams()
        assert len(streams) == 2

    def test_get_stream_snapshot(self):
        mgr = SensorStreamManager()
        mgr.create_stream("s1", "src1", "environmental")
        snapshot = mgr.get_stream_snapshot("s1")
        assert snapshot is not None
        assert snapshot["stream"]["stream_id"] == "s1"

    def test_get_stream_snapshot_missing(self):
        mgr = SensorStreamManager()
        snapshot = mgr.get_stream_snapshot("missing")
        assert snapshot is None

    def test_deactivate_stream(self):
        mgr = SensorStreamManager()
        mgr.create_stream("s1", "src1", "environmental")
        mgr.deactivate_stream("s1")
        stream = mgr.list_streams()[0]
        assert stream.active is False

    def test_ingest_signal(self):
        mgr = SensorStreamManager()
        mgr.create_stream("s1", "src1", "environmental")
        signal = ExternalSignal(
            signal_id="sig_1",
            source_id="src1",
            signal_type="environmental",
            value=0.5,
            confidence=0.8,
        )
        result = mgr.ingest_signal("s1", signal)
        assert result is True
        stream = mgr.list_streams()[0]
        assert stream.sample_count == 1

    def test_ingest_signal_missing_stream(self):
        mgr = SensorStreamManager()
        signal = ExternalSignal(
            signal_id="sig_1",
            source_id="src1",
            signal_type="environmental",
            value=0.5,
        )
        result = mgr.ingest_signal("missing", signal)
        assert result is False

    def test_validate_signal_valid(self):
        mgr = SensorStreamManager()
        signal = ExternalSignal(
            signal_id="sig_1",
            source_id="src1",
            signal_type="environmental",
            value=0.5,
            confidence=0.8,
            noise_score=0.1,
        )
        assert mgr.validate_signal(signal) is True

    def test_validate_signal_invalid_confidence_low(self):
        mgr = SensorStreamManager()
        signal = ExternalSignal(
            signal_id="sig_1",
            source_id="src1",
            signal_type="environmental",
            value=0.5,
            confidence=-0.1,
            noise_score=0.1,
        )
        assert mgr.validate_signal(signal) is False

    def test_validate_signal_invalid_noise_high(self):
        mgr = SensorStreamManager()
        signal = ExternalSignal(
            signal_id="sig_1",
            source_id="src1",
            signal_type="environmental",
            value=0.5,
            confidence=0.8,
            noise_score=0.81,
        )
        assert mgr.validate_signal(signal) is False

    def test_validate_signal_invalid_confidence_range(self):
        mgr = SensorStreamManager()
        signal = ExternalSignal(
            signal_id="sig_1",
            source_id="src1",
            signal_type="environmental",
            value=0.5,
            confidence=1.5,
            noise_score=0.1,
        )
        assert mgr.validate_signal(signal) is False

    def test_stream_default_mode_read_only(self):
        mgr = SensorStreamManager()
        stream = mgr.create_stream("s1", "src1", "environmental")
        assert stream.mode == CyberPhysicalMode.SIMULATED_READ_ONLY.value

    def test_reject_real_mode_stream(self):
        mgr = SensorStreamManager()
        stream = mgr.create_stream(
            "s1", "src1", "environmental", mode="active_control"
        )
        # Invalid mode gets blocked
        assert stream.mode == CyberPhysicalMode.BLOCKED.value
        assert stream.active is False

    def test_ingest_signal_increases_sample_count(self):
        mgr = SensorStreamManager()
        mgr.create_stream("s1", "src1", "environmental")
        for i in range(5):
            signal = ExternalSignal(
                signal_id=f"sig_{i}",
                source_id="src1",
                signal_type="environmental",
                value=0.1 * i,
                confidence=0.8,
            )
            mgr.ingest_signal("s1", signal)
        stream = mgr.list_streams()[0]
        assert stream.sample_count == 5

    def test_multiple_streams_isolated(self):
        mgr = SensorStreamManager()
        mgr.create_stream("s1", "src1", "environmental")
        mgr.create_stream("s2", "src2", "energy")
        signal = ExternalSignal(
            signal_id="sig_1",
            source_id="src1",
            signal_type="environmental",
            value=0.5,
        )
        mgr.ingest_signal("s1", signal)
        s1 = mgr.get_stream_snapshot("s1")
        s2 = mgr.get_stream_snapshot("s2")
        assert s1["signal_count"] == 1
        assert s2["signal_count"] == 0

    def test_ingest_blocked_stream_returns_false(self):
        mgr = SensorStreamManager()
        mgr.create_stream("s1", "src1", "environmental", mode=CyberPhysicalMode.BLOCKED.value)
        signal = ExternalSignal(
            signal_id="sig_1",
            source_id="src1",
            signal_type="environmental",
            value=0.5,
            confidence=0.8,
        )
        assert mgr.ingest_signal("s1", signal) is False

    def test_deactivate_stream_prevents_ingest(self):
        mgr = SensorStreamManager()
        mgr.create_stream("s1", "src1", "environmental")
        mgr.deactivate_stream("s1")
        signal = ExternalSignal(
            signal_id="sig_1",
            source_id="src1",
            signal_type="environmental",
            value=0.5,
            confidence=0.8,
        )
        assert mgr.ingest_signal("s1", signal) is False

    def test_validate_signal_safety_relevance_too_high(self):
        mgr = SensorStreamManager()
        signal = ExternalSignal(
            signal_id="sig_1",
            source_id="src1",
            signal_type="environmental",
            value=0.5,
            confidence=0.8,
            noise_score=0.1,
            safety_relevance=1.5,
        )
        assert mgr.validate_signal(signal) is False
