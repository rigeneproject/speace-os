import pytest
from speace_core.cellular_brain.world_model.world_model_policy_engine import WorldModelPolicyEngine


def test_is_simulated_action_allowed_safe():
    pe = WorldModelPolicyEngine()
    ok, reason = pe.is_simulated_action_allowed({"type": "observe"})
    assert ok is True
    assert reason is None


def test_is_simulated_action_allowed_dangerous():
    pe = WorldModelPolicyEngine()
    ok, reason = pe.is_simulated_action_allowed({"type": "actuate"})
    assert ok is False
    assert "dangerous_action_type" in reason


def test_is_simulated_action_allowed_real_connection():
    pe = WorldModelPolicyEngine()
    ok, reason = pe.is_simulated_action_allowed({"type": "observe", "api_endpoint": "http://example.com"})
    assert ok is False
    assert "real_connection_reference" in reason


def test_is_simulated_action_allowed_target_real():
    pe = WorldModelPolicyEngine()
    ok, reason = pe.is_simulated_action_allowed({"type": "observe", "target_real": True})
    assert ok is False
    assert "target_real_flag" in reason


def test_is_bus_message_safe_read_only():
    pe = WorldModelPolicyEngine()
    ok, reason = pe.is_bus_message_safe({"type": "world_model_summary", "read_only": True})
    assert ok is True
    assert reason is None


def test_is_bus_message_safe_unsafe_type():
    pe = WorldModelPolicyEngine()
    ok, reason = pe.is_bus_message_safe({"type": "actuate"})
    assert ok is False
    assert "unsafe_bus_type" in reason


def test_is_bus_message_safe_read_only_false():
    pe = WorldModelPolicyEngine()
    ok, reason = pe.is_bus_message_safe({"type": "summary", "read_only": False})
    assert ok is False
    assert "read_only_false" in reason


def test_block_real_action_attempt():
    pe = WorldModelPolicyEngine()
    blocked, reason = pe.block_real_action_attempt({"type": "command"})
    assert blocked is True
    assert "dangerous_action_type" in reason


def test_check_escalation_prevention_safe():
    pe = WorldModelPolicyEngine()
    class FakeSnapshot:
        pass
    class FakeScenario:
        simulated_actions = [{"type": "observe"}]
    ok, reason = pe.check_escalation_prevention(FakeSnapshot(), FakeScenario())
    assert ok is True


def test_check_escalation_prevention_blocked():
    pe = WorldModelPolicyEngine()
    class FakeSnapshot:
        pass
    class FakeScenario:
        simulated_actions = [{"type": "actuate"}]
    ok, reason = pe.check_escalation_prevention(FakeSnapshot(), FakeScenario())
    assert ok is False
