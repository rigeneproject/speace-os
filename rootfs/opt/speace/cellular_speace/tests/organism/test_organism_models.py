import pytest

from speace_core.cellular_brain.organism import (
    IntegrationDecision,
    OrganismAuditProfile,
    OrganismAuditResult,
    OrganismAuditSuiteResult,
    OrganismBusMessage,
    OrganismLifecycleState,
    OrganismMessageType,
    OrganismState,
    OrganismSubsystem,
    SubsystemStatus,
)


def test_organism_message_creation():
    msg = OrganismBusMessage(
        message_id="m1",
        source="safety",
        target="metabolism",
        message_type=OrganismMessageType.RISK_ALERT.value,
        priority=0.95,
        safety_relevant=True,
    )
    assert msg.message_id == "m1"
    assert msg.safety_relevant is True


def test_organism_message_defaults():
    msg = OrganismBusMessage(message_id="m2", source="a", message_type="state_update")
    assert msg.priority == 0.5
    assert msg.ttl_ticks == 10
    assert msg.requires_ack is False


def test_subsystem_status_defaults():
    s = SubsystemStatus(subsystem_name="metabolism")
    assert s.enabled is True
    assert s.health_score == 1.0
    assert s.degraded is False


def test_organism_state_defaults():
    state = OrganismState()
    assert state.tick == 0
    assert state.global_health_score == 1.0
    assert state.metabolic_mode == "normal"


def test_integration_decision_defaults():
    d = IntegrationDecision(decision_id="d1", target_subsystem="evo", action="throttle")
    assert d.reversible is True
    assert d.priority == 0.5


def test_organism_audit_profile_defaults():
    p = OrganismAuditProfile(name="test")
    assert p.duration_ticks == 5
    assert p.message_rate == 1.0
    assert p.seed == 42


def test_organism_audit_result_defaults():
    r = OrganismAuditResult(profile_name="test")
    assert r.messages_processed == 0
    assert r.verdict == "ORGANISM_INSUFFICIENT_EVIDENCE"


def test_organism_audit_suite_defaults():
    s = OrganismAuditSuiteResult()
    assert s.profile_count == 0
    assert s.proceed_to_t60 is False


def test_organism_subsystem_enum_values():
    assert OrganismSubsystem.SAFETY.value == "safety"
    assert OrganismSubsystem.METABOLISM.value == "metabolism"


def test_organism_message_type_enum_values():
    assert OrganismMessageType.RISK_ALERT.value == "risk_alert"
    assert OrganismMessageType.RESOURCE_REQUEST.value == "resource_request"


def test_organism_lifecycle_state_enum_values():
    assert OrganismLifecycleState.ACTIVE.value == "active"
    assert OrganismLifecycleState.CRITICAL.value == "critical"
