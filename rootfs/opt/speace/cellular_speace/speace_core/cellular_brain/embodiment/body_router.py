"""BodyRouter — routes sensorimotor commands to the appropriate physical body."""

import time
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.embodiment.body_registry import BodyRegistry


class BodyRouter:
    """Routes sensor and action commands to bodies using a simulated dict-based protocol.

    Future transports (MQTT, WebSocket, HTTP) will replace the internal
    ``_connections`` simulation with real network calls.
    """

    def __init__(self, registry: Optional[BodyRegistry] = None) -> None:
        self._registry = registry or BodyRegistry()
        # Simulated connection state per body_id.
        self._connections: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------ #
    # Simulated connection protocol
    # ------------------------------------------------------------------ #

    def _ensure_connection(self, body_id: str) -> bool:
        """Simulate establishing a connection. Returns True on success."""
        body = self._registry.get_body(body_id)
        if body is None:
            return False
        self._connections[body_id] = {
            "connected": True,
            "last_ping": time.time(),
        }
        return True

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def route_sensor_command(
        self, body_id: str, sensor_type: str
    ) -> Dict[str, Any]:
        """Request a sensor reading from a body.

        Returns a dict with ``status``, ``body_id``, ``sensor_type`` and
        ``reading`` (or ``error``).
        """
        if not self._ensure_connection(body_id):
            return {
                "status": "error",
                "body_id": body_id,
                "sensor_type": sensor_type,
                "error": f"Body {body_id} not found",
            }

        body = self._registry.get_body(body_id)
        assert body is not None
        caps = body.get("capabilities", {})
        sensors = caps.get("sensors", [])
        if sensor_type not in sensors:
            return {
                "status": "error",
                "body_id": body_id,
                "sensor_type": sensor_type,
                "error": f"Sensor {sensor_type} not available on body {body_id}",
            }

        # Simulated reading
        return {
            "status": "ok",
            "body_id": body_id,
            "sensor_type": sensor_type,
            "reading": {
                "value": 0.0,
                "timestamp": time.time(),
                "unit": "simulated",
            },
        }

    def route_action_command(
        self, body_id: str, action_type: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send an action command to a body.

        Returns a dict with ``status``, ``body_id``, ``action_type`` and
        ``result`` (or ``error``).
        """
        if not self._ensure_connection(body_id):
            return {
                "status": "error",
                "body_id": body_id,
                "action_type": action_type,
                "error": f"Body {body_id} not found",
            }

        body = self._registry.get_body(body_id)
        assert body is not None
        caps = body.get("capabilities", {})
        actuators = caps.get("actuators", [])
        if action_type not in actuators:
            return {
                "status": "error",
                "body_id": body_id,
                "action_type": action_type,
                "error": f"Action {action_type} not available on body {body_id}",
            }

        # Simulated action outcome
        return {
            "status": "ok",
            "body_id": body_id,
            "action_type": action_type,
            "result": {
                "executed": True,
                "timestamp": time.time(),
                "params": params or {},
            },
        }

    def broadcast_to_all(self, sensor_type: str) -> Dict[str, Any]:
        """Read *sensor_type* from every registered body and return an aggregated view.

        The returned dict contains ``status``, ``aggregate`` (mean value), and
        ``readings`` (list of per-body results).
        """
        bodies = self._registry.list_all()
        readings: List[Dict[str, Any]] = []
        values: List[float] = []

        for body in bodies:
            body_id = body["body_id"]
            result = self.route_sensor_command(body_id, sensor_type)
            readings.append(result)
            if result["status"] == "ok":
                values.append(result["reading"]["value"])

        aggregate = sum(values) / len(values) if values else 0.0
        return {
            "status": "ok",
            "sensor_type": sensor_type,
            "bodies_queried": len(bodies),
            "successful": len(values),
            "aggregate": aggregate,
            "readings": readings,
        }

    def select_body_for_task(self, task_description: str) -> Optional[Dict[str, Any]]:
        """Heuristic body selection based on a natural-language task description.

        For now this parses the description for keywords (sensor / actuator
        names) and delegates to ``BodyRegistry.get_best_body_for_task``.
        """
        task_lower = task_description.lower()

        # Simple keyword extraction heuristics
        sensor_keywords = {
            "camera": "camera",
            "image": "camera",
            "video": "camera",
            "temperature": "temperature_sensor",
            "thermometer": "temperature_sensor",
            "cpu": "cpu_sensor",
            "memory": "memory_sensor",
            "disk": "disk_sensor",
            "network": "network_sensor",
            "motion": "motion_sensor",
            "light": "light_sensor",
            "pressure": "pressure_sensor",
        }
        actuator_keywords = {
            "move": "motor",
            "motor": "motor",
            "drive": "motor",
            "speak": "speaker",
            "say": "speaker",
            "write": "file_writer",
            "delete": "file_writer",
            "execute": "executor",
            "run": "executor",
            "display": "display",
            "show": "display",
        }

        required_sensors: List[str] = []
        required_actuators: List[str] = []

        for keyword, sensor in sensor_keywords.items():
            if keyword in task_lower:
                required_sensors.append(sensor)
        for keyword, actuator in actuator_keywords.items():
            if keyword in task_lower:
                required_actuators.append(actuator)

        if not required_sensors and not required_actuators:
            return None

        return self._registry.get_best_body_for_task(required_sensors, required_actuators)
