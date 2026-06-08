import pytest

from speace_core.cellular_brain.organism import OrganismBus, OrganismBusMessage


def test_organism_bus_publish_and_poll():
    bus = OrganismBus()
    msg = OrganismBusMessage(message_id="m1", source="a", target="b", message_type="state_update")
    assert bus.publish(msg) is True
    polled = bus.poll("b")
    assert len(polled) == 1
    assert polled[0].message_id == "m1"


def test_organism_bus_publish_no_target_broadcasts():
    bus = OrganismBus()
    msg = OrganismBusMessage(message_id="m1", source="a", target=None, message_type="state_update")
    bus.publish(msg)
    polled_a = bus.poll("b")
    assert len(polled_a) == 1  # broadcast matches any target != source


def test_organism_bus_broadcast():
    bus = OrganismBus()
    msg = OrganismBusMessage(message_id="m1", source="a", message_type="state_update")
    bus.broadcast(msg)
    assert msg.target is None
    polled = bus.poll("b")
    assert len(polled) == 1


def test_organism_bus_acknowledgement():
    bus = OrganismBus()
    assert bus.acknowledge("m1", "safety") is True
    assert bus.acknowledge("m1", "safety") is False
    assert "m1" in bus._acks


def test_organism_bus_ttl_expiry():
    bus = OrganismBus()
    msg = OrganismBusMessage(message_id="m1", source="a", message_type="state_update", ttl_ticks=0, safety_relevant=False)
    bus.publish(msg)
    dropped = bus.drop_expired_messages(current_tick=0)
    assert dropped == 1
    assert bus.get_queue_depth() == 0


def test_organism_bus_ttl_expiry_preserves_safety():
    bus = OrganismBus()
    msg = OrganismBusMessage(message_id="m1", source="a", message_type="risk_alert", ttl_ticks=0, safety_relevant=True)
    bus.publish(msg)
    dropped = bus.drop_expired_messages(current_tick=0)
    assert dropped == 0
    assert bus.get_queue_depth() == 1


def test_organism_bus_overload_drops_non_safety():
    bus = OrganismBus(max_queue_depth=2)
    bus.publish(OrganismBusMessage(message_id="m1", source="a", message_type="state_update", priority=0.1))
    bus.publish(OrganismBusMessage(message_id="m2", source="a", message_type="state_update", priority=0.2))
    # Queue full; non-safety publish should fail
    result = bus.publish(OrganismBusMessage(message_id="m3", source="a", message_type="state_update", priority=0.1))
    assert result is False
    assert bus._dropped_count >= 1


def test_organism_bus_overload_keeps_safety():
    bus = OrganismBus(max_queue_depth=2)
    bus.publish(OrganismBusMessage(message_id="m1", source="a", message_type="state_update", priority=0.1))
    bus.publish(OrganismBusMessage(message_id="m2", source="a", message_type="state_update", priority=0.2))
    # Safety-relevant should be published by dropping lowest-priority non-safety
    result = bus.publish(OrganismBusMessage(message_id="m3", source="a", message_type="risk_alert", priority=0.95, safety_relevant=True))
    assert result is True
    assert bus.get_queue_depth() == 2


def test_organism_bus_queue_depth():
    bus = OrganismBus()
    assert bus.get_queue_depth() == 0
    bus.publish(OrganismBusMessage(message_id="m1", source="a", message_type="state_update"))
    assert bus.get_queue_depth() == 1


def test_organism_bus_snapshot():
    bus = OrganismBus()
    bus.publish(OrganismBusMessage(message_id="m1", source="a", message_type="state_update"))
    snap = bus.snapshot()
    assert snap["queue_depth"] == 1
    assert snap["processed_count"] == 1


def test_organism_bus_poll_filters_correctly():
    bus = OrganismBus()
    bus.publish(OrganismBusMessage(message_id="m1", source="a", target="b", message_type="state_update"))
    bus.publish(OrganismBusMessage(message_id="m2", source="a", target="c", message_type="state_update"))
    polled_b = bus.poll("b")
    assert len(polled_b) == 1
    assert polled_b[0].message_id == "m1"
    assert bus.get_queue_depth() == 1  # m2 remains
