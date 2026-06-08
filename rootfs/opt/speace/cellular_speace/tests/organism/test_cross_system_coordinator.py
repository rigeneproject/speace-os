import pytest

from speace_core.cellular_brain.organism import (
    CrossSystemCoordinator,
    OrganismBusMessage,
    OrganismMessageType,
    OrganismState,
    OrganismBus,
    SubsystemRegistry,
)


def test_cross_system_coordinator_routes_resource_requests():
    coord = CrossSystemCoordinator()
    requests = [
        OrganismBusMessage(message_id="r1", source="evo", message_type=OrganismMessageType.RESOURCE_REQUEST.value),
    ]
    decisions = coord.route_resource_requests(requests)
    assert len(decisions) == 1
    assert decisions[0].action == "grant"


def test_cross_system_coordinator_throttles_evolution():
    coord = CrossSystemCoordinator()
    state = OrganismState(metabolic_mode="critical", evolutionary_pressure=0.5)
    decision = coord.throttle_evolution_if_needed(state)
    assert decision is not None
    assert decision.action == "throttle"
    assert decision.target_subsystem == "evolutionary_kernel"


def test_cross_system_coordinator_protect_safety():
    coord = CrossSystemCoordinator()
    state = OrganismState(safety_risk_score=0.4)
    decision = coord.protect_safety(state)
    assert decision is not None
    assert decision.action == "protect"


def test_cross_system_coordinator_generate_decisions():
    coord = CrossSystemCoordinator()
    state = OrganismState(metabolic_mode="critical", evolutionary_pressure=0.5, safety_risk_score=0.4)
    decisions = coord.generate_decisions(state)
    actions = {d.action for d in decisions}
    assert "throttle" in actions
    assert "protect" in actions


def test_cross_system_coordinator_prioritize_recovery():
    coord = CrossSystemCoordinator()
    msgs = [
        OrganismBusMessage(message_id="m1", source="a", message_type=OrganismMessageType.STATE_UPDATE.value),
        OrganismBusMessage(message_id="m2", source="a", message_type=OrganismMessageType.RECOVERY_REQUEST.value),
    ]
    ordered = coord.prioritize_recovery(msgs)
    assert ordered[0].message_id == "m2"


def test_coordinate_cycle_blocks_evolution_under_critical():
    coord = CrossSystemCoordinator()
    state = OrganismState(metabolic_mode="critical", evolutionary_pressure=0.5)
    msg = OrganismBusMessage(message_id="m1", source="evolutionary_kernel", message_type="evolutionary_request")
    decisions = coord.coordinate_cycle(state, [msg])
    assert any(d.action == "throttle" and d.target_subsystem == "evolutionary_kernel" for d in decisions)


def test_coordinate_cycle_protects_safety():
    coord = CrossSystemCoordinator()
    state = OrganismState(safety_risk_score=0.6)
    decisions = coord.coordinate_cycle(state, [])
    assert any(d.action == "protect" and d.target_subsystem == "safety" for d in decisions)
