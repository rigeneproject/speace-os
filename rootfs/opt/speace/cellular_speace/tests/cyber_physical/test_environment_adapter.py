import pytest
from speace_core.cellular_brain.cyber_physical.environment_adapter import EnvironmentAdapter
from speace_core.cellular_brain.cyber_physical.cyber_physical_models import ExternalSignal


class TestEnvironmentAdapter:
    def test_normalize_signal(self):
        adapter = EnvironmentAdapter()
        raw = {
            "signal_id": "sig_1",
            "source_id": "sensor_1",
            "type": "temp",
            "value": 25.0,
            "confidence": 0.9,
            "noise_score": 0.1,
        }
        signal = adapter.normalize_signal(raw)
        assert signal.signal_type == "environmental"
        assert signal.value == 25.0
        assert signal.confidence == 0.9

    def test_normalize_signal_defaults(self):
        adapter = EnvironmentAdapter()
        raw = {
            "signal_id": "sig_1",
            "source_id": "sensor_1",
            "type": "temp",
            "value": 25.0,
        }
        signal = adapter.normalize_signal(raw)
        assert signal.confidence == 1.0
        assert signal.noise_score == 0.0
        assert signal.safety_relevance == 0.0

    def test_normalize_batch(self):
        adapter = EnvironmentAdapter()
        batch = [
            {"signal_id": "s1", "source_id": "src1", "type": "temp", "value": 20.0},
            {"signal_id": "s2", "source_id": "src2", "type": "voltage", "value": 220.0},
        ]
        signals = adapter.normalize_batch(batch)
        assert len(signals) == 2
        assert signals[0].signal_type == "environmental"
        assert signals[1].signal_type == "energy"

    def test_detect_noise_high(self):
        adapter = EnvironmentAdapter()
        signal = ExternalSignal(
            signal_id="a", source_id="s", signal_type="temp", value=20.0, noise_score=0.7
        )
        assert adapter.detect_noise(signal) is True

    def test_detect_noise_low_confidence(self):
        adapter = EnvironmentAdapter()
        signal = ExternalSignal(
            signal_id="a", source_id="s", signal_type="temp", value=20.0, confidence=0.1
        )
        assert adapter.detect_noise(signal) is True

    def test_detect_noise_safe(self):
        adapter = EnvironmentAdapter()
        signal = ExternalSignal(
            signal_id="a", source_id="s", signal_type="temp", value=20.0, noise_score=0.2, confidence=0.9
        )
        assert adapter.detect_noise(signal) is False

    def test_classify_signal_type_environmental(self):
        adapter = EnvironmentAdapter()
        assert adapter.classify_signal_type("temp") == "environmental"
        assert adapter.classify_signal_type("humidity") == "environmental"

    def test_classify_signal_type_energy(self):
        adapter = EnvironmentAdapter()
        assert adapter.classify_signal_type("voltage") == "energy"
        assert adapter.classify_signal_type("current") == "energy"

    def test_classify_signal_type_infrastructure(self):
        adapter = EnvironmentAdapter()
        assert adapter.classify_signal_type("cpu") == "infrastructure"
        assert adapter.classify_signal_type("memory") == "infrastructure"

    def test_classify_signal_type_sensor(self):
        adapter = EnvironmentAdapter()
        assert adapter.classify_signal_type("sensor") == "sensor"

    def test_classify_signal_type_unknown(self):
        adapter = EnvironmentAdapter()
        assert adapter.classify_signal_type("foobar") == "unknown"

    def test_quarantine_invalid_signal(self):
        adapter = EnvironmentAdapter()
        signal = ExternalSignal(
            signal_id="a", source_id="s", signal_type="temp", value=20.0
        )
        decision = adapter.quarantine_invalid_signal(signal)
        assert decision.quarantined is True
        assert decision.accepted is False
        assert decision.reason == "invalid_or_noisy_signal"

    def test_normalize_signal_clamps_confidence(self):
        adapter = EnvironmentAdapter()
        raw = {
            "signal_id": "s1",
            "source_id": "src",
            "type": "temp",
            "value": 20.0,
            "confidence": 1.5,
            "noise_score": -0.1,
        }
        signal = adapter.normalize_signal(raw)
        assert signal.confidence == 1.0
        assert signal.noise_score == 0.0

    def test_normalize_signal_unknown_type(self):
        adapter = EnvironmentAdapter()
        raw = {
            "signal_id": "s1",
            "source_id": "src",
            "type": "weird_type",
            "value": 20.0,
        }
        signal = adapter.normalize_signal(raw)
        assert signal.signal_type == "unknown"
