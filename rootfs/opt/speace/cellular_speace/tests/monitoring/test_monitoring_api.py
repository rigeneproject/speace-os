"""Tests for T101 — SPEACE Local Organism Monitor API and WebSocket."""

import pytest
from fastapi.testclient import TestClient

from speace_core.monitoring.dashboard_api import app


@pytest.fixture
def client():
    app.state._testing = True
    with TestClient(app) as c:
        yield c


class TestHttpEndpoints:
    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "uptime_seconds" in data
        assert "speace_version" in data

    def test_state(self, client):
        r = client.get("/api/state")
        assert r.status_code == 200
        data = r.json()
        assert "body" in data
        assert "cognition" in data
        assert "dynamics" in data
        assert "identity" in data
        assert "drives" in data
        assert "safety" in data
        assert "embodiment" in data
        assert "anomaly_panel" in data

    def test_state_includes_alert_engine(self, client):
        r = client.get("/api/state")
        assert r.status_code == 200
        data = r.json()
        assert "alert_engine" in data
        assert "alerts" in data["alert_engine"]
        assert "recent_alerts" in data["alert_engine"]
        assert "health_score" in data["alert_engine"]
        assert isinstance(data["alert_engine"]["alerts"], list)
        assert 0.0 <= data["alert_engine"]["health_score"] <= 1.0

    def test_body(self, client):
        r = client.get("/api/body")
        assert r.status_code == 200
        data = r.json()
        assert "cpu" in data
        assert "memory_bytes" in data

    def test_cognition(self, client):
        r = client.get("/api/cognition")
        assert r.status_code == 200
        data = r.json()
        assert "global_workspace" in data
        assert "self_model" in data

    def test_dynamics(self, client):
        r = client.get("/api/dynamics")
        assert r.status_code == 200
        data = r.json()
        assert "chaos_score" in data
        assert "criticality" in data

    def test_identity(self, client):
        r = client.get("/api/identity")
        assert r.status_code == 200
        data = r.json()
        assert "node_count" in data
        assert "distributed_nodes" in data

    def test_drives(self, client):
        r = client.get("/api/drives")
        assert r.status_code == 200
        data = r.json()
        assert "drives" in data
        assert "action_tendency" in data

    def test_safety(self, client):
        r = client.get("/api/safety")
        assert r.status_code == 200
        data = r.json()
        assert "risk_level" in data
        assert "governance_mode" in data
        assert data.get("governance_mode") == "observation_only"
        assert data.get("allow_actuator_commands") is False

    def test_static_index(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert b"SPEACE Local Organism Monitor" in r.content

    def test_static_css(self, client):
        r = client.get("/style.css")
        assert r.status_code == 200
        assert b"--bg-primary" in r.content

    def test_static_js(self, client):
        r = client.get("/app.js")
        assert r.status_code == 200
        assert b"WebSocket" in r.content

    def test_alerts(self, client):
        r = client.get("/api/alerts")
        assert r.status_code == 200
        data = r.json()
        assert "alerts" in data
        assert "health_score" in data
        assert "recent_alerts" in data
        assert isinstance(data["alerts"], list)
        assert 0.0 <= data["health_score"] <= 1.0

    def test_health_score(self, client):
        r = client.get("/api/health_score")
        assert r.status_code == 200
        data = r.json()
        assert "health_score" in data
        assert 0.0 <= data["health_score"] <= 1.0
        assert "timestamp" in data


class TestWebSocket:
    def test_ws_state(self, client):
        with client.websocket_connect("/ws/state") as ws:
            data = ws.receive_json()
            assert isinstance(data, dict)
            assert "body" in data
            assert "timestamp" in data

    def test_ws_includes_alert_engine(self, client):
        with client.websocket_connect("/ws/state") as ws:
            data = ws.receive_json()
            assert "alert_engine" in data
            assert "alerts" in data["alert_engine"]
            assert "health_score" in data["alert_engine"]
            assert isinstance(data["alert_engine"]["alerts"], list)
