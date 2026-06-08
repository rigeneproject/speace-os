"""Tests for T123 — Web Node Registry View."""

from unittest.mock import MagicMock, patch

from speace_core.web_gateway.auth_engine import AuthEngine


def _valid_auth(role: str = "observer"):
    auth = AuthEngine(data_root="data/test_web_gateway_t123")
    key = auth.generate_key(role=role)
    auth.generate_key = lambda role="observer": key
    return auth, key


def _header(key):
    return {"X-API-Key": key}


def test_list_nodes():
    from speace_core.web_gateway import gateway_api
    auth, key = _valid_auth(role="observer")
    gateway_api._auth_engine = auth

    mock_aggregator = MagicMock()
    mock_aggregator.aggregate.return_value = {
        "node_a": {"trust_score": 0.9, "last_seen": 1716500000, "online": True},
        "node_b": {"trust_score": 0.5, "last_seen": 1716400000, "online": False},
    }

    with patch("speace_core.monitoring.dashboard_api._multi_node_aggregator", mock_aggregator):
        from fastapi.testclient import TestClient
        client = TestClient(gateway_api.app)
        res = client.get("/api/nodes", headers=_header(key))

    assert res.status_code == 200
    data = res.json()
    assert "nodes" in data
    assert data["nodes"]["node_a"]["online"] is True


def test_node_detail_found():
    from speace_core.web_gateway import gateway_api
    auth, key = _valid_auth(role="observer")
    gateway_api._auth_engine = auth

    mock_aggregator = MagicMock()
    mock_aggregator._states = {
        "node_a": {"trust_score": 0.9},
    }
    mock_aggregator._compute_personality_drift.return_value = {"node_a": 0.12}

    with patch("speace_core.monitoring.dashboard_api._multi_node_aggregator", mock_aggregator):
        from fastapi.testclient import TestClient
        client = TestClient(gateway_api.app)
        res = client.get("/api/nodes/node_a", headers=_header(key))

    assert res.status_code == 200
    data = res.json()
    assert data["node_id"] == "node_a"
    assert data["personality_drift"] == 0.12


def test_node_detail_not_found():
    from speace_core.web_gateway import gateway_api
    auth, key = _valid_auth(role="observer")
    gateway_api._auth_engine = auth

    mock_aggregator = MagicMock()
    mock_aggregator._states = {}
    mock_aggregator._compute_personality_drift.return_value = {}

    with patch("speace_core.monitoring.dashboard_api._multi_node_aggregator", mock_aggregator):
        from fastapi.testclient import TestClient
        client = TestClient(gateway_api.app)
        res = client.get("/api/nodes/unknown", headers=_header(key))

    assert res.status_code == 404
