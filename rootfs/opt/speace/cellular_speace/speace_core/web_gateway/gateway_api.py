"""GatewayAPI — T121 + T122 + T123 + T125: SPEACE Secure Web Gateway.

Exposes:
- Health check (public)
- Dashboard state (read-only, auth + RBAC)
- Dialogue (text only, auth + RBAC)
- Alert history (read-only, auth + RBAC)
- Runtime control proposals (auth + RBAC, human approval required)
- Node registry (read-only, auth + RBAC)
- Admin key management (auth + admin role)

Does NOT expose:
- Actuator commands
- Shell execution
- Auto-replication
- Direct runtime control (all actions go through human approval gate)
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Set

from speace_core.web_gateway.auth_engine import AuthEngine

try:
    from fastapi import FastAPI, Header, HTTPException, Request
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import JSONResponse
    _HAS_FASTAPI = True
except Exception:  # pragma: no cover
    _HAS_FASTAPI = False
    FastAPI = Any  # type: ignore[misc,assignment]
    Header = Any  # type: ignore[misc,assignment]
    HTTPException = Any  # type: ignore[misc,assignment]
    Request = Any  # type: ignore[misc,assignment]
    StaticFiles = Any  # type: ignore[misc,assignment]
    JSONResponse = Any  # type: ignore[misc,assignment]

if not _HAS_FASTAPI:
    raise ImportError(
        "FastAPI is not installed.\n"
        "Install with: pip install \"speace-core[web_gateway]\"\n"
        "or:          pip install fastapi uvicorn"
    )

# ------------------------------------------------------------------ #
# Auth
# ------------------------------------------------------------------ #
_auth_engine = AuthEngine()

# Bootstrap: generate an admin key if none exist, so the first user can log in
if not _auth_engine._keys:
    _bootstrap_key = _auth_engine.generate_key(role="admin")
    _bootstrap_path = Path(_auth_engine.data_root) / "bootstrap_key.txt"
    _bootstrap_path.write_text(
        f"SPEACE Bootstrap API Key (generated {datetime.now().isoformat()})\n"
        f"Key: {_bootstrap_key}\n"
        f"Role: admin\n"
        f"Keep this secret. Generate a new key via /api/admin/keys once logged in.\n",
        encoding="utf-8",
    )
    logging.getLogger(__name__).warning(
        "[BOOTSTRAP] No API keys found. Generated admin key: %s... (saved to %s)",
        _bootstrap_key[:12],
        _bootstrap_path,
    )
    print(f"\n{'='*70}")
    print("[BOOTSTRAP] SPEACE Web Gateway — First-time setup")
    print(f"Admin API Key: {_bootstrap_key}")
    print(f"Also saved to: {_bootstrap_path}")
    print("Use this key in the dashboard login field.")
    print(f"{'='*70}\n")

# ------------------------------------------------------------------ #
# FastAPI app
# ------------------------------------------------------------------ #
app = FastAPI(
    title="SPEACE Secure Web Gateway",
    description="T121/T122/T123/T125 — Secure web access to SPEACE",
    version="0.2.0",
)


# ------------------------------------------------------------------ #
# RBAC helpers
# ------------------------------------------------------------------ #

def _authenticate(request: Request, x_api_key: str = Header(default="")) -> tuple[str, str]:
    """Validate API key and rate limit; return (client_ip, role)."""
    client_ip = request.client.host if request.client else "unknown"
    if not x_api_key:
        _auth_engine.audit("missing", request.url.path, request.method, 401, client_ip)
        raise HTTPException(status_code=401, detail="X-API-Key header required")
    if not _auth_engine.is_valid(x_api_key):
        _auth_engine.audit(x_api_key, request.url.path, request.method, 403, client_ip)
        raise HTTPException(status_code=403, detail="invalid API key")
    if not _auth_engine.check_rate_limit(x_api_key):
        _auth_engine.audit(x_api_key, request.url.path, request.method, 429, client_ip)
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    role = _auth_engine.get_role(x_api_key) or "observer"
    return client_ip, role


def _require_role(
    request: Request,
    x_api_key: str = Header(default=""),
    allowed_roles: Optional[Set[str]] = None,
) -> tuple[str, str]:
    """Authenticate then verify role membership. Returns (client_ip, role)."""
    client_ip, role = _authenticate(request, x_api_key)
    if allowed_roles and role not in allowed_roles:
        _auth_engine.audit(
            x_api_key, request.url.path, request.method, 403, client_ip, role=role
        )
        raise HTTPException(status_code=403, detail="insufficient privileges")
    return client_ip, role


@app.middleware("http")
async def audit_middleware(request: Request, call_next: Any) -> Any:
    """Log every request after it completes."""
    response = await call_next(request)
    key = request.headers.get("x-api-key", "missing")
    client_ip = request.client.host if request.client else "unknown"
    role = _auth_engine.get_role(key) if _auth_engine.is_valid(key) else "unknown"
    _auth_engine.audit(
        key, request.url.path, request.method, response.status_code, client_ip, role=role
    )
    return response


# ------------------------------------------------------------------ #
# Public health
# ------------------------------------------------------------------ #

@app.get("/api/health")
async def api_health() -> Dict[str, Any]:
    return {"status": "ok", "timestamp": time.time()}


# ------------------------------------------------------------------ #
# Dashboard (read-only) — observer+
# ------------------------------------------------------------------ #

@app.get("/api/state")
async def api_state(
    request: Request, x_api_key: str = Header(default="")
) -> Dict[str, Any]:
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import (
        _alert_engine,
        _metrics_bus,
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
            logging.getLogger(__name__).warning("Gateway API operation failed", exc_info=True)
    else:
        # Cross-process fallback: read latest snapshot / checkpoint written by runtime
        try:
            snap_path = Path("data/runtime/latest_snapshot.json")
            if snap_path.exists():
                snap = json.loads(snap_path.read_text(encoding="utf-8"))
                runtime = {
                    "state": snap.get("state", "unknown"),
                    "tick_count": snap.get("tick_count", 0),
                    "uptime_seconds": snap.get("uptime_seconds", 0),
                    "circadian_phase": snap.get("circadian", {}).get("phase", "unknown"),
                }
                hm = snap.get("health", {})
                health = {
                    "status": snap.get("state", "unknown"),
                    "health_score": hm.get("health_score", 0.5),
                }
            else:
                from speace_core.runtime.checkpoint_manager import CheckpointManager
                cm = CheckpointManager()
                ckpt = cm.latest()
                if ckpt:
                    runtime_state = ckpt.get("runtime_state", "unknown")
                    runtime = {
                        "state": runtime_state,
                        "tick_count": ckpt.get("orchestrator", {}).get("current_tick", 0),
                        "uptime_seconds": time.time() - ckpt.get("timestamp", time.time()),
                        "circadian_phase": ckpt.get("circadian_phase", "unknown"),
                    }
                    health_score = {
                        "running": 1.0,
                        "paused": 0.8,
                        "sleeping": 0.6,
                        "halting": 0.3,
                        "halted": 0.0,
                        "initializing": 0.9,
                    }.get(runtime_state, 0.5)
                    health = {"status": runtime_state, "health_score": health_score}
        except Exception:
            logging.getLogger(__name__).warning("Gateway runtime fallback failed", exc_info=True)

    state = _metrics_bus.latest()
    if not state:
        from speace_core.monitoring.organism_state_collector import OrganismStateCollector
        state = OrganismStateCollector(data_root="data").collect_all()
        state["timestamp"] = time.time()

    alerts = _alert_engine.evaluate(state)
    return {
        "health": health,
        "runtime": runtime,
        "alerts": alerts[:10],
        "alert_count": len(alerts),
        "timestamp": time.time(),
    }


# ------------------------------------------------------------------ #
# Dialogue
# ------------------------------------------------------------------ #

@app.post("/api/dialogue/message")
async def api_dialogue_message(
    request: Request,
    body: Dict[str, Any],
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    _require_role(request, x_api_key, {"operator", "reviewer", "admin"})
    msg = body.get("message", "")
    if not msg:
        raise HTTPException(status_code=400, detail="message required")
    from speace_core.monitoring.dashboard_api import _dialogue_manager
    response = _dialogue_manager.receive(msg)
    return response


@app.get("/api/dialogue/history")
async def api_dialogue_history(
    request: Request,
    limit: int = 20,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _dialogue_manager
    turns = _dialogue_manager.history(limit=limit)
    return {"turns": turns, "state": _dialogue_manager.state}


# ------------------------------------------------------------------ #
# Alerts (read-only) — observer+
# ------------------------------------------------------------------ #

@app.get("/api/alerts")
async def api_alerts(
    request: Request,
    limit: int = 20,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import (
        _alert_engine,
        _metrics_bus,
    )
    state = _metrics_bus.latest()
    if not state:
        from speace_core.monitoring.organism_state_collector import OrganismStateCollector
        state = OrganismStateCollector(data_root="data").collect_all()
        state["timestamp"] = time.time()
    alerts = _alert_engine.evaluate(state)
    return {
        "alerts": alerts[:limit],
        "health_score": _alert_engine.health_score(state),
        "timestamp": time.time(),
    }


# ------------------------------------------------------------------ #
# T122 — Runtime Control Proposals (human approval required)
# ------------------------------------------------------------------ #

_RUNTIME_ACTIONS = {"pause", "resume", "halt", "checkpoint"}


@app.post("/api/runtime/propose")
async def api_runtime_propose(
    request: Request,
    body: Dict[str, Any],
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """Propose a runtime action. Returns a proposal_id for human approval."""
    _require_role(request, x_api_key, {"operator", "reviewer", "admin"})
    action = body.get("action", "")
    if action not in _RUNTIME_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"invalid action. allowed: {list(_RUNTIME_ACTIONS)}",
        )

    from speace_core.monitoring.dashboard_api import (
        _approval_gate,
        _metrics_bus,
    )
    state = _metrics_bus.latest()
    if not state:
        from speace_core.monitoring.organism_state_collector import OrganismStateCollector
        state = OrganismStateCollector(data_root="data").collect_all()
        state["timestamp"] = time.time()

    proposal = _approval_gate.builder.create_manual_proposal(
        proposed_action=f"runtime_{action}",
        current_state=state,
        alert_type="runtime_control",
        severity="warning",
        message=f"Web user requested runtime action: {action}",
    )
    return {
        "status": "pending",
        "proposal_id": proposal["proposal_id"],
        "action": action,
        "risk_score": proposal.get("risk_score"),
    }


@app.get("/api/runtime/proposals")
async def api_runtime_proposals(
    request: Request,
    status: str = "pending",
    limit: int = 50,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """List runtime control proposals."""
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _approval_gate
    proposals = _approval_gate.list_pending(limit=limit) if status == "pending" else _approval_gate.list_all(limit=limit)
    # Filter to runtime-related proposals only
    runtime_proposals = [p for p in proposals if p.get("alert", {}).get("alert_type") == "runtime_control"]
    return {
        "status": status,
        "count": len(runtime_proposals),
        "proposals": runtime_proposals,
    }


@app.post("/api/runtime/approve/{proposal_id}")
async def api_runtime_approve(
    request: Request,
    proposal_id: str,
    body: Dict[str, Any],
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """Approve a runtime proposal and execute the action."""
    client_ip, role = _require_role(request, x_api_key, {"reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import (
        _approval_gate,
        _runtime_engine,
    )
    if _runtime_engine is None:
        raise HTTPException(status_code=503, detail="runtime not running")

    reviewer = body.get("reviewer", role)
    health = _runtime_engine.health_monitor.health_score()
    result = _approval_gate.approve(proposal_id, reviewer=reviewer, current_health=health)

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    # Execute the runtime action
    proposal = _approval_gate.builder.get_proposal(proposal_id)
    action = proposal.get("proposed_action", "") if proposal else ""
    exec_outcome: Dict[str, Any] = {}
    try:
        if action == "runtime_pause":
            await _runtime_engine.pause()
            exec_outcome = {"action": "pause", "state": _runtime_engine.snapshot().get("state")}
        elif action == "runtime_resume":
            await _runtime_engine.resume()
            exec_outcome = {"action": "resume", "state": _runtime_engine.snapshot().get("state")}
        elif action == "runtime_halt":
            await _runtime_engine.halt()
            exec_outcome = {"action": "halt", "state": _runtime_engine.snapshot().get("state")}
        elif action == "runtime_checkpoint":
            cp = await _runtime_engine.force_checkpoint()
            exec_outcome = {"action": "checkpoint", "checkpoint": cp}
    except Exception as e:
        exec_outcome = {"action": action, "error": str(e)}

    result["runtime_execution"] = exec_outcome
    return result


@app.post("/api/runtime/reject/{proposal_id}")
async def api_runtime_reject(
    request: Request,
    proposal_id: str,
    body: Dict[str, Any],
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """Reject a runtime proposal."""
    client_ip, role = _require_role(request, x_api_key, {"reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _approval_gate
    reviewer = body.get("reviewer", role)
    result = _approval_gate.reject(proposal_id, reviewer=reviewer)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


# ------------------------------------------------------------------ #
# T123 — Node Registry (read-only) — observer+
# ------------------------------------------------------------------ #

@app.get("/api/nodes")
async def api_nodes(
    request: Request,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """List all registered SPEACE nodes."""
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _multi_node_aggregator
    agg = _multi_node_aggregator.aggregate()
    return {
        "nodes": agg,
        "timestamp": time.time(),
    }


@app.get("/api/nodes/{node_id}")
async def api_node_detail(
    request: Request,
    node_id: str,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """Detail view for a single node."""
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _multi_node_aggregator
    node_state = _multi_node_aggregator._states.get(node_id)
    if node_state is None:
        raise HTTPException(status_code=404, detail="node not found")
    drift = _multi_node_aggregator._compute_personality_drift()
    return {
        "node_id": node_id,
        "state": node_state,
        "personality_drift": drift.get(node_id),
        "timestamp": time.time(),
    }


# ------------------------------------------------------------------ #
# Admin: key management — admin only
# ------------------------------------------------------------------ #

@app.post("/api/admin/keys")
async def api_admin_generate_key(
    request: Request,
    body: Dict[str, Any],
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    _require_role(request, x_api_key, {"admin"})
    role = body.get("role", "observer")
    if role not in _auth_engine.VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"invalid role. allowed: {list(_auth_engine.VALID_ROLES)}")
    new_key = _auth_engine.generate_key(role=role)
    return {"key": new_key, "role": role, "status": "created"}


@app.get("/api/admin/keys")
async def api_admin_list_keys(
    request: Request,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    _require_role(request, x_api_key, {"admin"})
    return {"keys": _auth_engine.list_keys()}


@app.delete("/api/admin/keys/{key}")
async def api_admin_revoke_key(
    request: Request,
    key: str,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    _require_role(request, x_api_key, {"admin"})
    revoked = _auth_engine.revoke_key(key)
    if not revoked:
        raise HTTPException(status_code=404, detail="key not found")
    return {"status": "revoked", "key_preview": f"{key[:8]}..."}


@app.get("/api/admin/audit")
async def api_admin_audit(
    request: Request,
    limit: int = 100,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    _require_role(request, x_api_key, {"admin"})
    entries = []
    if _auth_engine._audit_path.exists():
        try:
            with open(_auth_engine._audit_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
                for line in lines[-limit:]:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        except OSError:
            pass
    return {"entries": entries}


# ------------------------------------------------------------------ #
# T124 — Web-based Regulation Proposal Management
# ------------------------------------------------------------------ #

@app.get("/api/regulation/proposals")
async def api_regulation_proposals(
    request: Request,
    status: str = "pending",
    severity: Optional[str] = None,
    module: Optional[str] = None,
    limit: int = 50,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """List regulation proposals with optional filters."""
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _approval_gate

    proposals = _approval_gate.list_pending(limit=limit) if status == "pending" else _approval_gate.list_all(limit=limit)

    if severity:
        proposals = [p for p in proposals if p.get("alert", {}).get("severity") == severity]
    if module:
        proposals = [p for p in proposals if module in p.get("alert", {}).get("alert_type", "")]

    return {
        "status": status,
        "count": len(proposals),
        "proposals": proposals,
        "timestamp": time.time(),
    }


@app.get("/api/regulation/proposals/{proposal_id}")
async def api_regulation_proposal_detail(
    request: Request,
    proposal_id: str,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """Detail view for a single regulation proposal, including rollback snapshot."""
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _approval_gate

    proposal = _approval_gate.builder.get_proposal(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="proposal not found")

    return {
        "proposal": proposal,
        "rollback_available": proposal.get("snapshot_pre") is not None,
        "confidence": proposal.get("confidence"),
        "timestamp": time.time(),
    }


@app.post("/api/regulation/approve/{proposal_id}")
async def api_regulation_approve(
    request: Request,
    proposal_id: str,
    body: Dict[str, Any],
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """Approve a regulation proposal and execute it safely."""
    client_ip, role = _require_role(request, x_api_key, {"reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _approval_gate, _alert_engine, _metrics_bus

    state = _metrics_bus.latest() or {}
    health = _alert_engine.health_score(state)
    reviewer = body.get("reviewer", role)
    result = _approval_gate.approve(proposal_id, reviewer=reviewer, current_health=health)

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/regulation/reject/{proposal_id}")
async def api_regulation_reject(
    request: Request,
    proposal_id: str,
    body: Dict[str, Any],
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """Reject a regulation proposal."""
    client_ip, role = _require_role(request, x_api_key, {"reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _approval_gate

    reviewer = body.get("reviewer", role)
    result = _approval_gate.reject(proposal_id, reviewer=reviewer)

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/api/regulation/audit")
async def api_regulation_audit(
    request: Request,
    limit: int = 100,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """Audit trail for regulation approvals/rejections/executions."""
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _approval_gate

    entries: List[Dict[str, Any]] = []
    log_path = _approval_gate.log_path
    if log_path.exists():
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
                for line in lines[-limit:]:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        except OSError:
            pass
    return {"entries": entries, "timestamp": time.time()}


# ------------------------------------------------------------------ #
# T127 — Metacognitive Monitoring Layer
# ------------------------------------------------------------------ #

@app.get("/api/metacognition/state")
async def api_metacognition_state(
    request: Request,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """Metacognitive state snapshot (observer+)."""
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _metacognitive_monitor, _metrics_bus, _collector

    state = _metrics_bus.latest()
    if not state:
        from speace_core.monitoring.organism_state_collector import OrganismStateCollector
        state = OrganismStateCollector(data_root="data").collect_all()
        state["timestamp"] = time.time()
    meta = _metacognitive_monitor.generate_meta_state(state)
    return meta.model_dump(mode="json")


@app.get("/api/metacognition/report")
async def api_metacognition_report(
    request: Request,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """Reflective narrative report (observer+)."""
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _metacognitive_monitor, _metrics_bus, _collector

    state = _metrics_bus.latest()
    if not state:
        from speace_core.monitoring.organism_state_collector import OrganismStateCollector
        state = OrganismStateCollector(data_root="data").collect_all()
        state["timestamp"] = time.time()
    meta = _metacognitive_monitor.generate_meta_state(state)
    return {
        "reflective_narrative": meta.reflective_narrative,
        "meta_state_label": meta.meta_state_label,
        "timestamp": time.time(),
    }


# ------------------------------------------------------------------ #
# T128 — Epistemic Confidence Engine
# ------------------------------------------------------------------ #

@app.get("/api/metacognition/proposal/{proposal_id}/confidence")
async def api_proposal_confidence(
    request: Request,
    proposal_id: str,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """Epistemic confidence for a regulation proposal (observer+)."""
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _metacognitive_monitor, _approval_gate, _metrics_bus

    state = _metrics_bus.latest()
    if not state:
        from speace_core.monitoring.organism_state_collector import OrganismStateCollector
        state = OrganismStateCollector(data_root="data").collect_all()
        state["timestamp"] = time.time()

    proposal = _approval_gate.builder.get_proposal(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="proposal not found")

    confidence = _metacognitive_monitor.confidence_for_proposal(proposal, state)
    return confidence.model_dump(mode="json")


@app.get("/api/metacognition/dialogue/confidence")
async def api_dialogue_confidence(
    request: Request,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """Epistemic confidence for the latest dialogue context (observer+)."""
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _metacognitive_monitor, _dialogue_manager, _metrics_bus

    state = _metrics_bus.latest()
    if not state:
        from speace_core.monitoring.organism_state_collector import OrganismStateCollector
        state = OrganismStateCollector(data_root="data").collect_all()
        state["timestamp"] = time.time()

    dialogue_state = {"turn_count": _dialogue_manager._turn_count, "state": _dialogue_manager.state}
    confidence = _metacognitive_monitor.confidence_for_dialogue(dialogue_state, state)
    return confidence.model_dump(mode="json")


# ------------------------------------------------------------------ #
# T130 — Cognitive Strategy Evaluator
# ------------------------------------------------------------------ #

@app.get("/api/metacognition/strategies")
async def api_metacognition_strategies(
    request: Request,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """List evaluated strategies and their efficacy (observer+)."""
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _metacognitive_monitor
    return _metacognitive_monitor.evaluate_all_strategies()


@app.get("/api/metacognition/strategies/best")
async def api_metacognition_best_strategy(
    request: Request,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """Return the best-performing strategy (observer+)."""
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _metacognitive_monitor
    best = _metacognitive_monitor.best_strategy()
    return {"best_strategy": best, "timestamp": time.time()}


# ------------------------------------------------------------------ #
# T131-A — Ecosystem Observation Layer
# ------------------------------------------------------------------ #

@app.get("/api/ecosystem/status")
async def api_ecosystem_status(
    request: Request,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """Ecosystem health summary (observer+)."""
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _ecosystem_layer
    return _ecosystem_layer.health().model_dump(mode="json")


@app.get("/api/ecosystem/sources")
async def api_ecosystem_sources(
    request: Request,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """List ecosystem sources (observer+)."""
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _ecosystem_layer
    sources = _ecosystem_layer.list_sources()
    return {
        "sources": [s.model_dump(mode="json") for s in sources],
        "count": len(sources),
        "timestamp": time.time(),
    }


@app.get("/api/ecosystem/sources/{source_id}")
async def api_ecosystem_source_detail(
    request: Request,
    source_id: str,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """Detail for a single ecosystem source (observer+)."""
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _ecosystem_layer
    detail = _ecosystem_layer.describe_source(source_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="source not found")
    return detail


@app.get("/api/ecosystem/graph")
async def api_ecosystem_graph(
    request: Request,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """T131-B: ecosystem relational graph (observer+)."""
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _ecosystem_layer
    summary = _ecosystem_layer.graph_summary()
    if summary is None:
        raise HTTPException(status_code=503, detail="graph unavailable")
    return summary


@app.get("/api/ecosystem/graph/narrative")
async def api_ecosystem_graph_narrative(
    request: Request,
    x_api_key: str = Header(default=""),
) -> Dict[str, str]:
    """T131-B: ecosystem graph narrative (observer+)."""
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _ecosystem_layer
    return {"narrative": _ecosystem_layer.describe_graph()}


# ------------------------------------------------------------------ #
# T131-E — Controlled Ecosystem Interaction (stubbed)
# ------------------------------------------------------------------ #

@app.post("/api/ecosystem/actions/propose")
async def api_gateway_ecosystem_action_propose(
    request: Request,
    body: Dict[str, Any],
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """Propose an ecosystem action (operator+)."""
    _require_role(request, x_api_key, {"operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _ecosystem_actuator
    proposal = _ecosystem_actuator.propose(
        source_id=body.get("source_id", ""),
        action_type=body.get("action_type", ""),
        payload=body.get("payload", {}),
        requested_by=x_api_key[:8],
    )
    return proposal.model_dump(mode="json")


@app.get("/api/ecosystem/actions")
async def api_gateway_ecosystem_actions_list(
    request: Request,
    x_api_key: str = Header(default=""),
    status: Optional[str] = None,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    """List ecosystem action proposals (observer+)."""
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _ecosystem_actuator
    proposals = _ecosystem_actuator.list_proposals(status_filter=status, source_filter=source)
    return {
        "proposals": [p.model_dump(mode="json") for p in proposals],
        "count": len(proposals),
    }


@app.get("/api/ecosystem/actions/{proposal_id}")
async def api_gateway_ecosystem_action_detail(
    request: Request,
    proposal_id: str,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """Detail of a single action proposal (observer+)."""
    _require_role(request, x_api_key, {"observer", "operator", "reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _ecosystem_actuator
    proposal = _ecosystem_actuator.get(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="proposal not found")
    return proposal.model_dump(mode="json")


@app.post("/api/ecosystem/actions/{proposal_id}/approve")
async def api_gateway_ecosystem_action_approve(
    request: Request,
    proposal_id: str,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """Approve a pending ecosystem action proposal (reviewer+)."""
    _require_role(request, x_api_key, {"reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _ecosystem_actuator
    proposal = _ecosystem_actuator.approve(proposal_id, approver=x_api_key[:8])
    if proposal is None:
        raise HTTPException(status_code=404, detail="proposal not found or not pending")
    return proposal.model_dump(mode="json")


@app.post("/api/ecosystem/actions/{proposal_id}/reject")
async def api_gateway_ecosystem_action_reject(
    request: Request,
    proposal_id: str,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """Reject a pending ecosystem action proposal (reviewer+)."""
    _require_role(request, x_api_key, {"reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _ecosystem_actuator
    proposal = _ecosystem_actuator.reject(proposal_id, approver=x_api_key[:8])
    if proposal is None:
        raise HTTPException(status_code=404, detail="proposal not found or not pending")
    return proposal.model_dump(mode="json")


@app.post("/api/ecosystem/actions/{proposal_id}/execute")
async def api_gateway_ecosystem_action_execute(
    request: Request,
    proposal_id: str,
    x_api_key: str = Header(default=""),
) -> Dict[str, Any]:
    """Execute an approved ecosystem action proposal (reviewer+)."""
    _require_role(request, x_api_key, {"reviewer", "admin"})
    from speace_core.monitoring.dashboard_api import _ecosystem_actuator
    proposal = _ecosystem_actuator.execute(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail="proposal not found or not approved")
    return proposal.model_dump(mode="json")


# ------------------------------------------------------------------ #
# Static frontend
# ------------------------------------------------------------------ #
import os
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="web_gateway")
