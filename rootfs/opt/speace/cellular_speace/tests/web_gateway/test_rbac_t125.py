"""Tests for T125 — RBAC on Web Gateway endpoints."""

from unittest.mock import MagicMock, patch

import pytest

from speace_core.web_gateway.auth_engine import AuthEngine
from speace_core.web_gateway import gateway_api


def _setup_auth():
    auth = AuthEngine(data_root="data/test_web_gateway_t125")
    # clear any previous keys for determinism
    for key in list(auth._keys.keys()):
        auth.revoke_key(key)
    observer = auth.generate_key(role="observer")
    operator = auth.generate_key(role="operator")
    reviewer = auth.generate_key(role="reviewer")
    admin = auth.generate_key(role="admin")
    return observer, operator, reviewer, admin


def _header(key):
    return {"X-API-Key": key}


def _mock_approval_gate():
    mock_builder = MagicMock()
    mock_builder.create_manual_proposal.return_value = {
        "proposal_id": "RP-1234567890ab",
        "risk_score": 0.25,
    }
    mock_builder.get_proposal.return_value = {"proposed_action": "runtime_pause"}
    mock_gate = MagicMock()
    mock_gate.builder = mock_builder
    mock_gate.approve.return_value = {"status": "executed", "proposal_id": "RP-1"}
    mock_gate.reject.return_value = {"status": "rejected", "proposal_id": "RP-1"}
    mock_gate.list_pending.return_value = [
        {"proposal_id": "RP-1", "alert": {"alert_type": "runtime_control"}, "status": "pending"},
    ]
    mock_gate.list_all.return_value = mock_gate.list_pending.return_value
    return mock_gate


def _mock_runtime():
    rt = MagicMock()
    rt.health_monitor.health_score.return_value = 0.9
    rt.snapshot.return_value = {"state": "paused"}
    return rt


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #


def test_authenticate_missing_key_returns_401():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t125")
    for key in list(gateway_api._auth_engine._keys.keys()):
        gateway_api._auth_engine.revoke_key(key)
    # re-add keys so they exist in this instance too
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    from fastapi.testclient import TestClient
    client = TestClient(gateway_api.app)
    res = client.get("/api/state")
    assert res.status_code == 401


def test_authenticate_invalid_key_returns_403():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t125")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    from fastapi.testclient import TestClient
    client = TestClient(gateway_api.app)
    res = client.get("/api/state", headers={"X-API-Key": "bad_key"})
    assert res.status_code == 403


# ------------------------------------------------------------------ #
# Observer permissions
# ------------------------------------------------------------------ #


def test_observer_can_read_dashboard():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t125")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    from fastapi.testclient import TestClient
    client = TestClient(gateway_api.app)
    res = client.get("/api/state", headers=_header(observer))
    assert res.status_code == 200


def test_observer_cannot_propose_runtime():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t125")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    from fastapi.testclient import TestClient
    client = TestClient(gateway_api.app)
    res = client.post("/api/runtime/propose", json={"action": "pause"}, headers=_header(observer))
    assert res.status_code == 403


def test_observer_cannot_approve_runtime():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t125")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    from fastapi.testclient import TestClient
    client = TestClient(gateway_api.app)
    res = client.post("/api/runtime/approve/RP-1", json={}, headers=_header(observer))
    assert res.status_code == 403


def test_observer_cannot_access_admin():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t125")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    from fastapi.testclient import TestClient
    client = TestClient(gateway_api.app)
    res = client.post("/api/admin/keys", json={}, headers=_header(observer))
    assert res.status_code == 403


# ------------------------------------------------------------------ #
# Operator permissions
# ------------------------------------------------------------------ #


def test_operator_can_propose_runtime():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t125")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    mock_gate = _mock_approval_gate()
    with patch("speace_core.monitoring.dashboard_api._approval_gate", mock_gate):
        from fastapi.testclient import TestClient
        client = TestClient(gateway_api.app)
        res = client.post("/api/runtime/propose", json={"action": "pause"}, headers=_header(operator))
        assert res.status_code == 200


def test_operator_cannot_approve_runtime():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t125")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    from fastapi.testclient import TestClient
    client = TestClient(gateway_api.app)
    res = client.post("/api/runtime/approve/RP-1", json={}, headers=_header(operator))
    assert res.status_code == 403


def test_operator_can_send_dialogue():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t125")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    with patch("speace_core.monitoring.dashboard_api._dialogue_manager") as mock_dm:
        mock_dm.receive.return_value = {"response": "hello"}
        from fastapi.testclient import TestClient
        client = TestClient(gateway_api.app)
        res = client.post("/api/dialogue/message", json={"message": "hi"}, headers=_header(operator))
        assert res.status_code == 200


# ------------------------------------------------------------------ #
# Reviewer permissions
# ------------------------------------------------------------------ #


def test_reviewer_can_approve_and_reject():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t125")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    mock_gate = _mock_approval_gate()
    mock_rt = _mock_runtime()
    with patch("speace_core.monitoring.dashboard_api._approval_gate", mock_gate):
        with patch("speace_core.monitoring.dashboard_api._runtime_engine", mock_rt):
            from fastapi.testclient import TestClient
            client = TestClient(gateway_api.app)
            res_approve = client.post("/api/runtime/approve/RP-1", json={}, headers=_header(reviewer))
            assert res_approve.status_code == 200
            res_reject = client.post("/api/runtime/reject/RP-1", json={}, headers=_header(reviewer))
            assert res_reject.status_code == 200


def test_reviewer_cannot_access_admin():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t125")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    from fastapi.testclient import TestClient
    client = TestClient(gateway_api.app)
    res = client.get("/api/admin/keys", headers=_header(reviewer))
    assert res.status_code == 403


# ------------------------------------------------------------------ #
# Admin permissions
# ------------------------------------------------------------------ #


def test_admin_can_access_all_endpoints():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t125")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    from fastapi.testclient import TestClient
    client = TestClient(gateway_api.app)

    # observer endpoints
    assert client.get("/api/state", headers=_header(admin)).status_code == 200
    assert client.get("/api/alerts", headers=_header(admin)).status_code == 200
    assert client.get("/api/dialogue/history", headers=_header(admin)).status_code == 200
    assert client.get("/api/runtime/proposals", headers=_header(admin)).status_code == 200

    # operator endpoint
    with patch("speace_core.monitoring.dashboard_api._approval_gate") as mock_gate:
        mock_gate.builder.create_manual_proposal.return_value = {"proposal_id": "RP-x", "risk_score": 0.1}
        assert client.post("/api/runtime/propose", json={"action": "pause"}, headers=_header(admin)).status_code == 200

    # reviewer endpoints
    mock_gate = _mock_approval_gate()
    mock_rt = _mock_runtime()
    with patch("speace_core.monitoring.dashboard_api._approval_gate", mock_gate):
        with patch("speace_core.monitoring.dashboard_api._runtime_engine", mock_rt):
            assert client.post("/api/runtime/approve/RP-1", json={}, headers=_header(admin)).status_code == 200
            assert client.post("/api/runtime/reject/RP-1", json={}, headers=_header(admin)).status_code == 200

    # admin endpoints
    assert client.get("/api/admin/keys", headers=_header(admin)).status_code == 200
    assert client.post("/api/admin/keys", json={"role": "observer"}, headers=_header(admin)).status_code == 200
    # revoke a key (use observer key as victim)
    assert client.delete(f"/api/admin/keys/{observer}", headers=_header(admin)).status_code == 200
    assert client.get("/api/admin/audit", headers=_header(admin)).status_code == 200


def test_admin_generate_key_with_role():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t125")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    from fastapi.testclient import TestClient
    client = TestClient(gateway_api.app)
    res = client.post("/api/admin/keys", json={"role": "operator"}, headers=_header(admin))
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "operator"
    assert "key" in data


def test_admin_cannot_generate_key_with_invalid_role():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t125")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    from fastapi.testclient import TestClient
    client = TestClient(gateway_api.app)
    res = client.post("/api/admin/keys", json={"role": "superuser"}, headers=_header(admin))
    assert res.status_code == 400
