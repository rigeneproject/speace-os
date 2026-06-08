import asyncio

import pytest

from speace_core.cellular_brain.base.digital_signal import DigitalSignal
from speace_core.event_bus import EventBus


@pytest.mark.asyncio
async def test_publish_subscribe():
    bus = EventBus()
    received = []

    def handler(signal: DigitalSignal):
        received.append(signal)

    bus.subscribe("test", handler)
    sig = DigitalSignal(source="a", target="b", strength=0.5)
    await bus.publish("test", sig)
    await asyncio.sleep(0.01)
    assert len(received) == 1
    assert received[0].strength == 0.5


@pytest.mark.asyncio
async def test_unsubscribe():
    bus = EventBus()
    received = []

    def handler(signal: DigitalSignal):
        received.append(signal)

    bus.subscribe("test", handler)
    bus.unsubscribe("test", handler)
    await bus.publish("test", DigitalSignal(source="a"))
    await asyncio.sleep(0.01)
    assert len(received) == 0
