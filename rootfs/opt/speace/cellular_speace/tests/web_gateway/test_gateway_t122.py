"""Tests for T122 — Web Runtime Control with Human Approval."""

from unittest.mock import MagicMock, patch

import pytest

from speace_core.web_gateway.auth_engine import AuthEngine


def _valid_auth(role: str = "admin"):
    auth = AuthEngine(data_root="data/test_web_gateway_t122")
    key = auth.generate_key(role=role)
    # override generate_key so it doesn't collide in future calls
    auth.generate_key = lambda role="observer": key
    return auth, key


def _header(key):
    return {"X-API-Key": key}


def test_propose_runtime_action():
    from speace_core.web_gateway import gateway_api
    auth, key = _valid_auth(role="operator")
    gateway_api._auth_engine = auth

    mock_builder = MagicMock()
    mock_builder.create_manual_proposal.return_value = {
        "proposal_id": "RP-1234567890ab",
        "risk_score": 0.25,
    }
    mock_approval_gate = MagicMock()
    mock_approval_gate.builder = mock_builder

    with patch("speace_core.monitoring.dashboard_api._approval_gate", mock_approval_gate):
        from fastapi.testclient import TestClient
        client = TestClient(gateway_api.app)
        res = client.post("/api/runtime/propose", json={"action": "pause"}, headers=_header(key))

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "pending"
    assert data["proposal_id"] == "RP-1234567890ab"
    assert data["action"] == "pause"


def test_propose_invalid_action():
    from speace_core.web_gateway import gateway_api
    auth, key = _valid_auth(role="operator")
    gateway_api._auth_engine = auth

    from fastapi.testclient import TestClient
    client = TestClient(gateway_api.app)
    res = client.post("/api/runtime/propose", json={"action": "destroy"}, headers=_header(key))
    assert res.status_code == 400


def test_list_runtime_proposals():
    from speace_core.web_gateway import gateway_api
    auth, key = _valid_auth(role="observer")
    gateway_api._auth_engine = auth

    mock_builder = MagicMock()
    mock_builder.list_proposals.return_value = [
        {"proposal_id": "RP-1", "alert": {"alert_type": "runtime_control"}, "status": "pending"},
        {"proposal_id": "RP-2", "alert": {"alert_type": "other"}, "status": "pending"},
    ]
    mock_approval_gate = MagicMock()
    mock_approval_gate.builder = mock_builder
    mock_approval_gate.list_pending = mock_builder.list_proposals

    with patch("speace_core.monitoring.dashboard_api._approval_gate", mock_approval_gate):
        from fastapi.testclient import TestClient
        client = TestClient(gateway_api.app)
        res = client.get("/api/runtime/proposals?status=pending", headers=_header(key))

    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 1
    assert data["proposals"][0]["proposal_id"] == "RP-1"


def test_approve_runtime_proposal():
    from speace_core.web_gateway import gateway_api
    auth, key = _valid_auth(role="reviewer")
    gateway_api._auth_engine = auth

    mock_builder = MagicMock()
    mock_builder.get_proposal.return_value = {"proposed_action": "runtime_pause"}
    mock_approval_gate = MagicMock()
    mock_approval_gate.builder = mock_builder
    mock_approval_gate.approve.return_value = {"status": "executed", "proposal_id": "RP-1"}

    mock_runtime = MagicMock()
    mock_runtime.health_monitor.health_score.return_value = 0.9
    mock_runtime.snapshot.return_value = {"state": "paused"}

    with patch("speace_core.monitoring.dashboard_api._approval_gate", mock_approval_gate):
        with patch("speace_core.monitoring.dashboard_api._runtime_engine", mock_runtime):
            from fastapi.testclient import TestClient
            client = TestClient(gateway_api.app)
            res = client.post("/api/runtime/approve/RP-1", json={"reviewer": "web_test"}, headers=_header(key))

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "executed"
    mock_runtime.pause.assert_called_once()
