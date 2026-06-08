import pytest
from speace_core.cellular_brain.cyber_physical.cyber_physical_policy_engine import (
    CyberPhysicalPolicyEngine,
)
from speace_core.cellular_brain.cyber_physical.cyber_physical_models import (
    CyberPhysicalMode,
    ExternalSignal,
)


class TestCyberPhysicalPolicyEngine:
    def test_evaluate_signal_pass(self):
        engine = CyberPhysicalPolicyEngine()
        signal = ExternalSignal(
            signal_id="s1",
            source_id="src",
            signal_type="environmental",
            value=0.5,
            confidence=0.8,
            noise_score=0.1,
            safety_relevance=0.2,
        )
        assert engine.evaluate_signal(signal) is True

    def test_evaluate_signal_blocked_mode(self):
        engine = CyberPhysicalPolicyEngine()
        signal = ExternalSignal(
            signal_id="s1",
            source_id="src",
            signal_type="environmental",
            value=0.5,
            confidence=0.8,
            noise_score=0.1,
        )
        assert (
            engine.evaluate_signal(signal, mode=CyberPhysicalMode.BLOCKED.value)
            is False
        )

    def test_evaluate_signal_high_noise(self):
        engine = CyberPhysicalPolicyEngine()
        signal = ExternalSignal(
            signal_id="s1",
            source_id="src",
            signal_type="environmental",
            value=0.5,
            confidence=0.8,
            noise_score=0.8,
        )
        assert engine.evaluate_signal(signal) is False

    def test_evaluate_signal_low_confidence(self):
        engine = CyberPhysicalPolicyEngine()
        signal = ExternalSignal(
            signal_id="s1",
            source_id="src",
            signal_type="environmental",
            value=0.5,
            confidence=0.1,
            noise_score=0.1,
        )
        assert engine.evaluate_signal(signal) is False

    def test_evaluate_signal_safety_relevant_high_noise(self):
        engine = CyberPhysicalPolicyEngine()
        signal = ExternalSignal(
            signal_id="s1",
            source_id="src",
            signal_type="environmental",
            value=0.5,
            confidence=0.8,
            noise_score=0.5,
            safety_relevance=0.95,
        )
        assert engine.evaluate_signal(signal) is False

    def test_is_read_only_violation(self):
        engine = CyberPhysicalPolicyEngine()
        assert engine.is_read_only_violation("actuate") is True
        assert engine.is_read_only_violation("control") is True
        assert engine.is_read_only_violation("command") is True
        assert engine.is_read_only_violation("write") is True
        assert engine.is_read_only_violation("modify") is True
        assert engine.is_read_only_violation("execute") is True
        assert engine.is_read_only_violation("read") is False
        assert engine.is_read_only_violation("observe") is False

    def test_block_unsafe_signal_routing(self):
        engine = CyberPhysicalPolicyEngine()
        signal = ExternalSignal(
            signal_id="s1",
            source_id="src",
            signal_type="environmental",
            value=0.5,
            noise_score=0.7,
        )
        decision = engine.block_unsafe_signal_routing(signal)
        assert decision is not None
        assert decision.quarantined is True
        assert decision.action == "block_routing"

    def test_block_unsafe_signal_routing_safe(self):
        engine = CyberPhysicalPolicyEngine()
        signal = ExternalSignal(
            signal_id="s1",
            source_id="src",
            signal_type="environmental",
            value=0.5,
            noise_score=0.3,
        )
        decision = engine.block_unsafe_signal_routing(signal)
        assert decision is None

    def test_protect_safety_from_anomalous_signal(self):
        engine = CyberPhysicalPolicyEngine()
        signal = ExternalSignal(
            signal_id="s1",
            source_id="src",
            signal_type="environmental",
            value=0.5,
            safety_relevance=0.8,
            confidence=0.5,
        )
        assert engine.protect_safety_from_anomalous_signal(signal) is True

    def test_protect_safety_not_anomalous(self):
        engine = CyberPhysicalPolicyEngine()
        signal = ExternalSignal(
            signal_id="s1",
            source_id="src",
            signal_type="environmental",
            value=0.5,
            safety_relevance=0.3,
            confidence=0.5,
        )
        assert engine.protect_safety_from_anomalous_signal(signal) is False

    def test_prevent_escalation_read_only_to_active(self):
        engine = CyberPhysicalPolicyEngine()
        assert (
            engine.prevent_escalation(
                CyberPhysicalMode.SIMULATED_READ_ONLY.value,
                CyberPhysicalMode.SIMULATED_READ_ONLY.value,
            )
            is True
        )
        assert (
            engine.prevent_escalation(
                CyberPhysicalMode.SIMULATED_READ_ONLY.value,
                "active_control",
            )
            is False
        )

    def test_prevent_escalation_quarantined_allowed(self):
        engine = CyberPhysicalPolicyEngine()
        assert (
            engine.prevent_escalation(
                CyberPhysicalMode.SIMULATED_READ_ONLY.value,
                CyberPhysicalMode.QUARANTINED.value,
            )
            is True
        )

    def test_generate_policy_decision_accept(self):
        engine = CyberPhysicalPolicyEngine()
        signal = ExternalSignal(
            signal_id="s1",
            source_id="src",
            signal_type="environmental",
            value=0.5,
            confidence=0.8,
            noise_score=0.1,
        )
        decision = engine.generate_policy_decision(
            signal, CyberPhysicalMode.SIMULATED_READ_ONLY.value
        )
        assert decision.accepted is True
        assert decision.action == "accept"

    def test_generate_policy_decision_block(self):
        engine = CyberPhysicalPolicyEngine()
        signal = ExternalSignal(
            signal_id="s1",
            source_id="src",
            signal_type="environmental",
            value=0.5,
            confidence=0.1,
            noise_score=0.1,
        )
        decision = engine.generate_policy_decision(
            signal, CyberPhysicalMode.SIMULATED_READ_ONLY.value
        )
        assert decision.accepted is False
        assert decision.action == "block"
