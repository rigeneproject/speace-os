"""MobileBridge — T120-A + T125: secure pairing, RBAC, and read-only dashboard API for SPEACE Mobile Companion.

Security rules:
- Pairing is manual (token-based)
- Tokens expire after 5 minutes
- No auto-replica
- Sensors are opt-in
- Microphone disabled in v1
- Notifications are read-only
- RBAC: observer, operator, reviewer, admin (reviewer currently unused on mobile)
"""

import secrets
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


# Role → permission mapping for mobile
_ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    "observer": {"dashboard"},
    "operator": {"dashboard", "dialogue_text", "sensor_consent"},
    "reviewer": {"dashboard", "dialogue_text", "sensor_consent"},
    "admin": {"dashboard", "dialogue_text", "admin", "sensor_consent"},
}


@dataclass
class PairedDevice:
    device_id: str
    token: str
    paired_at: float
    last_seen: float
    role: str = field(default="observer")
    permissions: Set[str] = field(default_factory=lambda: {"dashboard"})
    sensor_consent: Dict[str, bool] = field(default_factory=dict)


class MobilePairingManager:
    """Manages temporary pairing tokens and active device sessions."""

    TOKEN_TTL_SECONDS: float = 300.0  # 5 minutes
    SESSION_TTL_SECONDS: float = 3600.0  # 1 hour inactivity

    def __init__(self) -> None:
        self._pending_tokens: Dict[str, float] = {}  # token -> created_at
        self._devices: Dict[str, PairedDevice] = {}  # device_id -> PairedDevice

    # ------------------------------------------------------------------ #
    # Token lifecycle
    # ------------------------------------------------------------------ #

    def generate_token(self) -> str:
        """Generate a short numeric token for manual entry."""
        token = str(secrets.randbelow(1_000_000)).zfill(6)
        self._pending_tokens[token] = time.time()
        return token

    def verify_token(self, token: str, device_id: str, role: str = "observer") -> Optional[PairedDevice]:
        """Verify a pending token and promote it to a full device session."""
        created_at = self._pending_tokens.pop(token, None)
        if created_at is None:
            return None
        if time.time() - created_at > self.TOKEN_TTL_SECONDS:
            return None
        if role not in _ROLE_PERMISSIONS:
            role = "observer"
        device = PairedDevice(
            device_id=device_id,
            token=token,
            paired_at=time.time(),
            last_seen=time.time(),
            role=role,
            permissions=set(_ROLE_PERMISSIONS[role]),
            sensor_consent={},
        )
        self._devices[device_id] = device
        return device

    def revoke_device(self, device_id: str) -> bool:
        """Revoke a paired device."""
        return self._devices.pop(device_id, None) is not None

    def get_device(self, device_id: str) -> Optional[PairedDevice]:
        """Return device info if still valid."""
        device = self._devices.get(device_id)
        if device is None:
            return None
        if time.time() - device.last_seen > self.SESSION_TTL_SECONDS:
            self._devices.pop(device_id, None)
            return None
        device.last_seen = time.time()
        return device

    def get_role(self, device_id: str) -> Optional[str]:
        device = self.get_device(device_id)
        return device.role if device else None

    def has_role(self, device_id: str, role: str) -> bool:
        device = self.get_device(device_id)
        if device is None:
            return False
        return device.role == role

    def list_devices(self) -> List[Dict[str, Any]]:
        """List all active paired devices."""
        now = time.time()
        active = []
        stale = []
        for did, dev in self._devices.items():
            if now - dev.last_seen > self.SESSION_TTL_SECONDS:
                stale.append(did)
            else:
                active.append({
                    "device_id": dev.device_id,
                    "role": dev.role,
                    "paired_at": dev.paired_at,
                    "last_seen": dev.last_seen,
                    "permissions": list(dev.permissions),
                })
        for did in stale:
            self._devices.pop(did, None)
        return active

    def update_sensor_consent(self, device_id: str, consent: Dict[str, bool]) -> bool:
        """Update sensor opt-in consent for a device."""
        device = self._devices.get(device_id)
        if device is None:
            return False
        # Only allow known sensors; microphone is always False in v1
        allowed = {"battery", "location", "accelerometer", "network"}
        for k, v in consent.items():
            if k in allowed:
                device.sensor_consent[k] = bool(v)
        device.sensor_consent["microphone"] = False
        return True

    def is_authorized(self, device_id: str, permission: str) -> bool:
        device = self.get_device(device_id)
        if device is None:
            return False
        return permission in device.permissions

    def is_authorized_role(self, device_id: str, allowed_roles: Set[str]) -> bool:
        device = self.get_device(device_id)
        if device is None:
            return False
        return device.role in allowed_roles
