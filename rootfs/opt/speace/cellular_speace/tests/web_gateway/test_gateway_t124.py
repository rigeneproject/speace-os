"""Tests for T124 — Web-based Regulation Proposal Management."""

import time
from unittest.mock import MagicMock, patch

import pytest

from speace_core.web_gateway.auth_engine import AuthEngine
from speace_core.web_gateway import gateway_api


def _setup_auth():
    auth = AuthEngine(data_root="data/test_web_gateway_t124")
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
    mock_builder.get_proposal.return_value = {
        "proposal_id": "RP-t124",
        "status": "pending",
        "alert": {"alert_type": "chaos_warning", "severity": "warning", "message": "x"},
        "proposed_action": "increase stability bias",
        "snapshot_pre": {"chaos_score": 0.5},
        "confidence": {"confidence": 0.7},
    }
    mock_gate = MagicMock()
    mock_gate.builder = mock_builder
    mock_gate.list_pending.return_value = [mock_builder.get_proposal.return_value]
    mock_gate.list_all.return_value = [mock_builder.get_proposal.return_value]
    mock_gate.approve.return_value = {"status": "executed", "proposal_id": "RP-t124"}
    mock_gate.reject.return_value = {"status": "rejected", "proposal_id": "RP-t124"}
    mock_gate.log_path = MagicMock()
    mock_gate.log_path.exists.return_value = False
    return mock_gate


# ------------------------------------------------------------------ #
# List proposals
# ------------------------------------------------------------------ #


def test_observer_can_list_regulation_proposals():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t124")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    mock_gate = _mock_approval_gate()
    with patch("speace_core.monitoring.dashboard_api._approval_gate", mock_gate):
        from fastapi.testclient import TestClient
        client = TestClient(gateway_api.app)
        res = client.get("/api/regulation/proposals", headers=_header(observer))
        assert res.status_code == 200
        data = res.json()
        assert "proposals" in data
        assert data["count"] == 1


def test_list_with_severity_filter():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t124")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    mock_gate = _mock_approval_gate()
    with patch("speace_core.monitoring.dashboard_api._approval_gate", mock_gate):
        from fastapi.testclient import TestClient
        client = TestClient(gateway_api.app)
        res = client.get("/api/regulation/proposals?severity=critical", headers=_header(observer))
        assert res.status_code == 200
        data = res.json()
        assert data["count"] == 0


def test_list_with_module_filter():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t124")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    mock_gate = _mock_approval_gate()
    with patch("speace_core.monitoring.dashboard_api._approval_gate", mock_gate):
        from fastapi.testclient import TestClient
        client = TestClient(gateway_api.app)
        res = client.get("/api/regulation/proposals?module=chaos", headers=_header(observer))
        assert res.status_code == 200
        data = res.json()
        assert data["count"] == 1


# ------------------------------------------------------------------ #
# Detail
# ------------------------------------------------------------------ #


def test_proposal_detail_includes_rollback_and_confidence():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t124")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    mock_gate = _mock_approval_gate()
    with patch("speace_core.monitoring.dashboard_api._approval_gate", mock_gate):
        from fastapi.testclient import TestClient
        client = TestClient(gateway_api.app)
        res = client.get("/api/regulation/proposals/RP-t124", headers=_header(observer))
        assert res.status_code == 200
        data = res.json()
        assert data["rollback_available"] is True
        assert data["confidence"]["confidence"] == 0.7


def test_proposal_detail_not_found():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t124")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    mock_gate = _mock_approval_gate()
    mock_gate.builder.get_proposal.return_value = None
    with patch("speace_core.monitoring.dashboard_api._approval_gate", mock_gate):
        from fastapi.testclient import TestClient
        client = TestClient(gateway_api.app)
        res = client.get("/api/regulation/proposals/RP-missing", headers=_header(observer))
        assert res.status_code == 404


# ------------------------------------------------------------------ #
# Approve / Reject
# ------------------------------------------------------------------ #


def test_reviewer_can_approve_regulation():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t124")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    mock_gate = _mock_approval_gate()
    with patch("speace_core.monitoring.dashboard_api._approval_gate", mock_gate):
        from fastapi.testclient import TestClient
        client = TestClient(gateway_api.app)
        res = client.post("/api/regulation/approve/RP-t124", json={}, headers=_header(reviewer))
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "executed"


def test_reviewer_can_reject_regulation():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t124")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    mock_gate = _mock_approval_gate()
    with patch("speace_core.monitoring.dashboard_api._approval_gate", mock_gate):
        from fastapi.testclient import TestClient
        client = TestClient(gateway_api.app)
        res = client.post("/api/regulation/reject/RP-t124", json={}, headers=_header(reviewer))
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "rejected"


def test_operator_cannot_approve_regulation():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t124")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    mock_gate = _mock_approval_gate()
    with patch("speace_core.monitoring.dashboard_api._approval_gate", mock_gate):
        from fastapi.testclient import TestClient
        client = TestClient(gateway_api.app)
        res = client.post("/api/regulation/approve/RP-t124", json={}, headers=_header(operator))
        assert res.status_code == 403


def test_approve_propagates_error():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t124")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    mock_gate = _mock_approval_gate()
    mock_gate.approve.return_value = {"error": "not_pending"}
    with patch("speace_core.monitoring.dashboard_api._approval_gate", mock_gate):
        from fastapi.testclient import TestClient
        client = TestClient(gateway_api.app)
        res = client.post("/api/regulation/approve/RP-t124", json={}, headers=_header(reviewer))
        assert res.status_code == 400
        assert res.json()["detail"] == "not_pending"


# ------------------------------------------------------------------ #
# Audit
# ------------------------------------------------------------------ #


def test_observer_can_read_regulation_audit():
    observer, operator, reviewer, admin = _setup_auth()
    gateway_api._auth_engine = AuthEngine(data_root="data/test_web_gateway_t124")
    gateway_api._auth_engine._keys = {}
    for role, k in [("observer", observer), ("operator", operator), ("reviewer", reviewer), ("admin", admin)]:
        gateway_api._auth_engine._keys[k] = role

    mock_gate = _mock_approval_gate()
    with patch("speace_core.monitoring.dashboard_api._approval_gate", mock_gate):
        from fastapi.testclient import TestClient
        client = TestClient(gateway_api.app)
        res = client.get("/api/regulation/audit", headers=_header(observer))
        assert res.status_code == 200
        data = res.json()
        assert "entries" in data
