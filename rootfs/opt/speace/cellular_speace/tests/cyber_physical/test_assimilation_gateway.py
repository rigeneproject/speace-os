import pytest
from speace_core.cellular_brain.cyber_physical.assimilation_gateway import (
    AssimilationGateway,
)
from speace_core.cellular_brain.cyber_physical.cyber_physical_models import ExternalSignal


class TestAssimilationGateway:
    def test_assimilate_safe_signal(self):
        gateway = AssimilationGateway()
        signal = ExternalSignal(
            signal_id="safe_1",
            source_id="src",
            signal_type="environmental",
            value=0.5,
            confidence=0.8,
            noise_score=0.1,
            safety_relevance=0.2,
        )
        decision = gateway.assimilate_signal(signal)
        assert decision.accepted is True
        assert decision.quarantined is False
        assert decision.action == "accept"

    def test_assimilate_noisy_signal(self):
        gateway = AssimilationGateway()
        signal = ExternalSignal(
            signal_id="noisy_1",
            source_id="src",
            signal_type="environmental",
            value=0.5,
            confidence=0.8,
            noise_score=0.7,
            safety_relevance=0.2,
        )
        decision = gateway.assimilate_signal(signal)
        assert decision.accepted is False
        assert decision.quarantined is True
        assert decision.action == "quarantine"

    def test_assimilate_invalid_confidence(self):
        gateway = AssimilationGateway()
        signal = ExternalSignal(
            signal_id="inv_1",
            source_id="src",
            signal_type="environmental",
            value=0.5,
            confidence=1.5,
            noise_score=0.1,
        )
        decision = gateway.assimilate_signal(signal)
        assert decision.accepted is False
        assert decision.quarantined is False
        assert decision.reason == "invalid_confidence_range"

    def test_assimilate_conflicting_signals(self):
        gateway = AssimilationGateway()
        signal1 = ExternalSignal(
            signal_id="env_1",
            source_id="src",
            signal_type="environmental",
            value=0.1,
            confidence=0.8,
            noise_score=0.1,
            safety_relevance=0.2,
        )
        signal2 = ExternalSignal(
            signal_id="env_2",
            source_id="src",
            signal_type="environmental",
            value=0.9,
            confidence=0.8,
            noise_score=0.1,
            safety_relevance=0.2,
        )
        gateway.assimilate_signal(signal1)
        decision = gateway.assimilate_signal(signal2)
        assert decision.quarantined is True
        assert "world_state_conflict" in decision.reason

    def test_quarantine_signal_manual(self):
        gateway = AssimilationGateway()
        signal = ExternalSignal(
            signal_id="man_1",
            source_id="src",
            signal_type="environmental",
            value=0.5,
        )
        decision = gateway.quarantine_signal(signal, reason="manual_test")
        assert decision.quarantined is True
        assert decision.reason == "manual_test"

    def test_assimilate_batch(self):
        gateway = AssimilationGateway()
        signals = [
            ExternalSignal(
                signal_id=f"sig_{i}",
                source_id="src",
                signal_type="environmental",
                value=0.5,
                confidence=0.8,
                noise_score=0.1,
            )
            for i in range(3)
        ]
        decisions = gateway.assimilate_batch(signals)
        assert len(decisions) == 3
        assert all(d.accepted for d in decisions)

    def test_publish_world_state_to_bus(self):
        gateway = AssimilationGateway()
        signal = ExternalSignal(
            signal_id="safe_1",
            source_id="src",
            signal_type="environmental",
            value=0.5,
            confidence=0.8,
            noise_score=0.1,
        )
        gateway.assimilate_signal(signal)
        msg = gateway.publish_world_state_to_bus()
        assert msg is not None
        assert msg["type"] == "world_state_update"
        assert msg["read_only"] is True

    def test_publish_world_state_empty(self):
        gateway = AssimilationGateway()
        msg = gateway.publish_world_state_to_bus()
        assert msg is None

    def test_generate_assimilation_report(self):
        gateway = AssimilationGateway()
        signal = ExternalSignal(
            signal_id="safe_1",
            source_id="src",
            signal_type="environmental",
            value=0.5,
            confidence=0.8,
            noise_score=0.1,
        )
        gateway.assimilate_signal(signal)
        report = gateway.generate_assimilation_report()
        assert report["accepted_count"] == 1
        assert report["quarantined_count"] == 0

    def test_safety_relevant_signal_accepted(self):
        gateway = AssimilationGateway()
        signal = ExternalSignal(
            signal_id="safe_high",
            source_id="src",
            signal_type="environmental",
            value=0.5,
            confidence=0.8,
            noise_score=0.1,
            safety_relevance=0.8,
        )
        decision = gateway.assimilate_signal(signal)
        assert decision.accepted is True
        assert decision.safety_relevant is True

    def test_assimilate_signal_with_negative_confidence(self):
        gateway = AssimilationGateway()
        signal = ExternalSignal(
            signal_id="neg_conf",
            source_id="src",
            signal_type="environmental",
            value=0.5,
            confidence=-0.1,
            noise_score=0.1,
        )
        decision = gateway.assimilate_signal(signal)
        assert decision.accepted is False
        assert decision.reason == "invalid_confidence_range"
