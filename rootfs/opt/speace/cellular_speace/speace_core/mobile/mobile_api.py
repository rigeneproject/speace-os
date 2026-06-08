"""MobileAPI — FastAPI router for SPEACE Mobile Companion Node (T120 + T125)."""

import json
import time
from typing import Any, Dict, Set

from speace_core.mobile.mobile_bridge import MobilePairingManager
from speace_core.mobile.mobile_sensor_store import MobileSensorStore

try:
    from fastapi import APIRouter, Header, HTTPException
except Exception:  # pragma: no cover
    APIRouter = Any  # type: ignore[misc,assignment]
    HTTPException = Any  # type: ignore[misc,assignment]

# ------------------------------------------------------------------ #
# Shared state
# ------------------------------------------------------------------ #
_pairing_manager = MobilePairingManager()
_sensor_store = MobileSensorStore()
# T120-D: lightweight notification queue per device
_notification_queue: Dict[str, list] = {}

router = APIRouter(prefix="/api/mobile", tags=["mobile"])

# ------------------------------------------------------------------ #
# RBAC helper
# ------------------------------------------------------------------ #

def _require_device(device_id: str) -> Any:
    """Validate device session exists and is not expired."""
    device = _pairing_manager.get_device(device_id)
    if device is None:
        raise HTTPException(status_code=403, detail="device not paired or expired")
    return device


def _require_role(device_id: str, allowed_roles: Set[str]) -> Any:
    """Validate device session and role membership."""
    device = _require_device(device_id)
    if device.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="insufficient privileges")
    return device


# ------------------------------------------------------------------ #
# Pairing (public)
# ------------------------------------------------------------------ #

@router.post("/pair")
async def mobile_pair() -> Dict[str, Any]:
    """Generate a temporary pairing token."""
    token = _pairing_manager.generate_token()
    return {
        "token": token,
        "expires_in_seconds": MobilePairingManager.TOKEN_TTL_SECONDS,
    }


@router.post("/verify")
async def mobile_verify(body: Dict[str, Any]) -> Dict[str, Any]:
    """Verify a token and establish a device session."""
    token = body.get("token", "")
    device_id = body.get("device_id", "")
    role = body.get("role", "observer")
    if not token or not device_id:
        raise HTTPException(status_code=400, detail="token and device_id required")
    device = _pairing_manager.verify_token(token, device_id, role=role)
    if device is None:
        raise HTTPException(status_code=403, detail="invalid or expired token")
    return {
        "status": "paired",
        "device_id": device.device_id,
        "role": device.role,
        "permissions": list(device.permissions),
    }


@router.post("/heartbeat")
async def mobile_heartbeat(
    body: Dict[str, Any],
    x_device_id: str = Header(default=""),
) -> Dict[str, Any]:
    """Keep a device session alive."""
    device_id = x_device_id or body.get("device_id", "")
    device = _require_device(device_id)
    return {"status": "ok", "last_seen": device.last_seen}


# ------------------------------------------------------------------ #
# Dashboard (read-only) — observer+
# ------------------------------------------------------------------ #

@router.get("/dashboard")
async def mobile_dashboard(
    x_device_id: str = Header(default=""),
) -> Dict[str, Any]:
    """Return a compact dashboard payload for the mobile app."""
    _require_role(x_device_id, {"observer", "operator", "reviewer", "admin"})

    from speace_core.monitoring.dashboard_api import (
        _alert_engine,
        _metrics_bus,
        _multi_node_aggregator,
        _runtime_engine,
    )

    health = {"status": "not_running"}
    runtime = {"status": "not_running"}
    if _runtime_engine is not None:
        try:
            snap = _runtime_engine.snapshot()
            health = _runtime_engine.health_monitor.snapshot()
            runtime = {
                "state": snap.get("state"),
                "tick_count": snap.get("tick_count"),
                "uptime_seconds": snap.get("uptime_seconds"),
                "circadian_phase": snap.get("circadian", {}).get("phase"),
            }
        except Exception:
            pass

    state = _metrics_bus.latest()
    if not state:
        from speace_core.monitoring.organism_state_collector import OrganismStateCollector
        state = OrganismStateCollector(data_root="data").collect_all()
        state["timestamp"] = time.time()

    alerts = _alert_engine.evaluate(state)
    nodes = _multi_node_aggregator.aggregate()

    # T120-D: enqueue critical alerts as notifications
    for a in alerts:
        if a.get("severity") in ("critical", "warning"):
            _enqueue_notification(x_device_id, {
                "title": f"SPEACE Alert: {a.get('severity', 'info')}",
                "body": a.get("message", ""),
                "timestamp": time.time(),
                "read": False,
            })

    return {
        "health": health,
        "runtime": runtime,
        "alerts": alerts[:5],
        "alert_count": len(alerts),
        "nodes": nodes,
        "timestamp": time.time(),
    }


# ------------------------------------------------------------------ #
# Sensor consent (opt-in) — operator+
# ------------------------------------------------------------------ #

@router.post("/sensor_consent")
async def mobile_sensor_consent(
    body: Dict[str, Any],
    x_device_id: str = Header(default=""),
) -> Dict[str, Any]:
    """Update sensor opt-in consent for this device."""
    device = _require_role(x_device_id, {"operator", "reviewer", "admin"})
    consent = body.get("consent", {})
    ok = _pairing_manager.update_sensor_consent(x_device_id, consent)
    if not ok:
        raise HTTPException(status_code=500, detail="failed to update consent")
    return {
        "status": "ok",
        "consent": device.sensor_consent,
    }


# ------------------------------------------------------------------ #
# Sensor ingestion (opt-in) — operator+
# ------------------------------------------------------------------ #

@router.post("/sensors")
async def mobile_sensors(
    body: Dict[str, Any],
    x_device_id: str = Header(default=""),
) -> Dict[str, Any]:
    """Receive sensor data from the mobile device."""
    device = _require_role(x_device_id, {"operator", "reviewer", "admin"})

    allowed = {k for k, v in device.sensor_consent.items() if v}
    payload = body.get("sensors", {})
    filtered = {k: v for k, v in payload.items() if k in allowed}
    accepted = _sensor_store.store(x_device_id, filtered)

    return {
        "status": "received",
        "accepted_sensors": accepted,
        "timestamp": time.time(),
    }


# ------------------------------------------------------------------ #
# Notifications (T120-D) — observer+
# ------------------------------------------------------------------ #

def _enqueue_notification(device_id: str, notification: Dict[str, Any]) -> None:
    if device_id not in _notification_queue:
        _notification_queue[device_id] = []
    _notification_queue[device_id].append(notification)
    # Keep only latest 100
    _notification_queue[device_id] = _notification_queue[device_id][-100:]


@router.get("/notifications")
async def mobile_notifications(
    x_device_id: str = Header(default=""),
    unread_only: bool = False,
) -> Dict[str, Any]:
    """Return queued notifications for this device."""
    _require_role(x_device_id, {"observer", "operator", "reviewer", "admin"})
    queue = _notification_queue.get(x_device_id, [])
    if unread_only:
        queue = [n for n in queue if not n.get("read", False)]
    return {
        "notifications": queue,
        "unread_count": len([n for n in queue if not n.get("read", False)]),
    }


@router.post("/notifications/read")
async def mobile_notifications_read(
    body: Dict[str, Any],
    x_device_id: str = Header(default=""),
) -> Dict[str, Any]:
    """Mark notifications as read."""
    _require_role(x_device_id, {"observer", "operator", "reviewer", "admin"})
    indices = body.get("indices", [])
    queue = _notification_queue.get(x_device_id, [])
    for idx in indices:
        if 0 <= idx < len(queue):
            queue[idx]["read"] = True
    return {"status": "ok"}


# ------------------------------------------------------------------ #
# Multi-node registry (T120-E) — observer+
# ------------------------------------------------------------------ #

@router.get("/nodes")
async def mobile_nodes(
    x_device_id: str = Header(default=""),
) -> Dict[str, Any]:
    """Return multi-node registry for mobile view."""
    _require_role(x_device_id, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _multi_node_aggregator
    agg = _multi_node_aggregator.aggregate()
    return {
        "nodes": agg,
        "timestamp": time.time(),
    }


# ------------------------------------------------------------------ #
# QR Code pairing (T120-F) — public
# ------------------------------------------------------------------ #

@router.get("/qr")
async def mobile_qr() -> Dict[str, Any]:
    """Return a pairing payload suitable for QR encoding."""
    token = _pairing_manager.generate_token()
    payload = {
        "token": token,
        "expires_in_seconds": MobilePairingManager.TOKEN_TTL_SECONDS,
    }
    return {
        "qr_payload": json.dumps(payload),
        "token": token,
        "expires_in_seconds": MobilePairingManager.TOKEN_TTL_SECONDS,
    }


# ------------------------------------------------------------------ #
# Device management (admin view) — admin only
# ------------------------------------------------------------------ #

@router.get("/devices")
async def mobile_devices(
    x_device_id: str = Header(default=""),
) -> Dict[str, Any]:
    """List all paired devices (admin)."""
    _require_role(x_device_id, {"admin"})
    return {"devices": _pairing_manager.list_devices()}
