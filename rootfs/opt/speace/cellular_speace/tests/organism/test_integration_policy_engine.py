import pytest

from speace_core.cellular_brain.organism import IntegrationPolicyEngine, OrganismBusMessage


def test_policy_engine_prioritizes_safety():
    engine = IntegrationPolicyEngine()
    msgs = [
        OrganismBusMessage(message_id="m1", source="a", message_type="state_update", priority=0.3, safety_relevant=False),
        OrganismBusMessage(message_id="m2", source="a", message_type="risk_alert", priority=0.5, safety_relevant=True),
    ]
    sorted_msgs = engine.prioritize_messages(msgs)
    assert sorted_msgs[0].message_id == "m2"


def test_policy_engine_prioritizes_recovery_under_stress():
    engine = IntegrationPolicyEngine()
    assert engine.is_recovery_priority_above_evolution("stress") is True
    assert engine.is_recovery_priority_above_evolution("critical") is True
    assert engine.is_recovery_priority_above_evolution("normal") is False


def test_policy_engine_blocks_evolution_under_critical():
    engine = IntegrationPolicyEngine()
    msg = OrganismBusMessage(
        message_id="m1",
        source="evolutionary_kernel",
        message_type="resource_request",
        priority=0.8,
    )
    assert engine.evaluate_message(msg, metabolic_mode="critical") is False


def test_policy_engine_allows_evolution_in_normal():
    engine = IntegrationPolicyEngine()
    msg = OrganismBusMessage(
        message_id="m1",
        source="evolutionary_kernel",
        message_type="resource_request",
        priority=0.8,
    )
    assert engine.evaluate_message(msg, metabolic_mode="normal") is True


def test_policy_engine_blocks_quarantined_memory():
    engine = IntegrationPolicyEngine()
    assert engine.block_quarantined_memory("quarantined") is True
    assert engine.block_quarantined_memory("normal") is False


def test_policy_engine_rejects_invalid_ttl():
    engine = IntegrationPolicyEngine()
    msg = OrganismBusMessage(message_id="m1", source="a", message_type="state_update", ttl_ticks=0)
    assert engine.evaluate_message(msg) is False


def test_policy_engine_is_safety_highest_priority():
    engine = IntegrationPolicyEngine()
    msgs = [
        OrganismBusMessage(message_id="m1", source="a", message_type="state_update", priority=0.9, safety_relevant=False),
        OrganismBusMessage(message_id="m2", source="a", message_type="risk_alert", priority=0.95, safety_relevant=True),
    ]
    assert engine.is_safety_highest_priority(msgs) is True


def test_policy_engine_generates_block_decision_for_critical():
    engine = IntegrationPolicyEngine()
    msg = OrganismBusMessage(message_id="m1", source="evolutionary_kernel", message_type="resource_request")
    decision = engine.generate_decision_from_policy(msg, metabolic_mode="critical", memory_status="normal")
    assert decision is not None
    assert decision.action == "block"


def test_policy_engine_generates_throttle_decision_for_evolution():
    engine = IntegrationPolicyEngine()
    msg = OrganismBusMessage(message_id="m1", source="evolutionary_kernel", message_type="evolutionary_request")
    decision = engine.generate_decision_from_policy(msg, metabolic_mode="critical", memory_status="normal")
    assert decision is not None
    assert decision.action in ("block", "throttle")


def test_policy_engine_generates_block_for_quarantine():
    engine = IntegrationPolicyEngine()
    msg = OrganismBusMessage(message_id="m1", source="memory", message_type="state_update")
    decision = engine.generate_decision_from_policy(msg, metabolic_mode="normal", memory_status="quarantined")
    assert decision is not None
    assert decision.action == "block"
