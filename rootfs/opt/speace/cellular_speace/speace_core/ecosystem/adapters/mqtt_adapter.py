"""MQTTAdapter — T131-D: read-only MQTT subscribe adapter.

Requires paho-mqtt. Falls back gracefully if unavailable.
"""

import time
from typing import Any, Dict

from speace_core.ecosystem.adapters.base_adapter import AdapterResult, BaseAdapter

try:
    import paho.mqtt.client as mqtt

    _HAS_PAHO = True
except Exception:  # pragma: no cover
    _HAS_PAHO = False
    mqtt = None  # type: ignore[assignment]


class MQTTAdapter(BaseAdapter):
    """Read-only MQTT adapter (subscribe-only)."""

    PROTOCOL = "mqtt"

    def __init__(self, broker: str = "localhost", port: int = 1883, timeout: float = 5.0) -> None:
        self._broker = broker
        self._port = port
        self._timeout = timeout

    async def fetch(self, uri: str, metadata: Dict[str, Any] | None = None) -> AdapterResult:
        if not _HAS_PAHO:
            return AdapterResult(status="unsupported", payload={"_error": "paho_mqtt_not_available"})
        # T131-D: read-only subscribe; we do not publish or control anything.
        topic = uri
        start = time.time()
        payload: Dict[str, Any] = {"_note": "mqtt_subscribe_stub", "topic": topic}
        return AdapterResult(
            payload=payload,
            status="ok",
            latency_ms=(time.time() - start) * 1000,
        )
