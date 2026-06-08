from typing import Any, Dict, Optional, Tuple


class WorldModelPolicyEngine:
    """Prevents escalation from sandbox to real control. Blocks dangerous simulated actions and real connections."""

    def __init__(self):
        self._dangerous_keywords = {
            "actuate", "command", "write", "control", "patch", "deploy",
            "execute", "enable", "disable", "reset", "delete", "drop",
            "format", "wipe", "shutdown", "reboot", "override",
        }
        self._real_connection_keywords = {
            "api_endpoint", "iot_device_id", "hardware_channel", "serial_port",
            "tcp_connect", "udp_send", "mqtt_publish", "ble_pair",
        }

    def is_simulated_action_allowed(self, action: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        action_type = action.get("type", "")
        if action_type in self._dangerous_keywords:
            return False, f"dangerous_action_type:{action_type}"
        for key in self._real_connection_keywords:
            if action.get(key):
                return False, f"real_connection_reference:{key}"
        if action.get("target_real", False):
            return False, "target_real_flag"
        return True, None

    def is_bus_message_safe(self, message: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        msg_type = message.get("type", "")
        if msg_type in ("actuate", "command", "control", "patch", "deploy"):
            return False, f"unsafe_bus_type:{msg_type}"
        if message.get("read_only") is False:
            return False, "read_only_false"
        if message.get("requires_ack", False):
            return False, "requires_ack_true"
        return True, None

    def block_real_action_attempt(self, action: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        allowed, reason = self.is_simulated_action_allowed(action)
        if not allowed:
            return True, reason
        return False, None

    def check_escalation_prevention(self, snapshot, scenario) -> Tuple[bool, Optional[str]]:
        for action in getattr(scenario, "simulated_actions", []) or []:
            allowed, reason = self.is_simulated_action_allowed(action)
            if not allowed:
                return False, reason
        return True, None
