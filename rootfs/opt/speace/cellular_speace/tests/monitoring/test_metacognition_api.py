"""Tests for T127 — Metacognition API endpoints in dashboard and gateway."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from speace_core.monitoring.dashboard_api import app as dashboard_app
from speace_core.web_gateway.auth_engine import AuthEngine
from speace_core.web_gateway import gateway_api


@pytest.fixture
def dashboard_client():
    dashboard_app.state._testing = True
    with TestClient(dashboard_app) as c:
        yield c


def _setup_gateway_auth():
    auth = AuthEngine(data_root="data/test_web_gateway_t127")
    for key in list(auth._keys.keys()):
        auth.revoke_key(key)
    observer = auth.generate_key(role="observer")
    return auth, observer


# ------------------------------------------------------------------ #
# Dashboard API
# ------------------------------------------------------------------ #


def test_dashboard_metacognition_state(dashboard_client):
    res = dashboard_client.get("/api/metacognition/state")
    assert res.status_code == 200
    data = res.json()
    assert "meta_state_label" in data
    assert "cognitive_observation" in data
    assert "error_detection" in data
    assert "epistemic_confidence" in data


def test_dashboard_metacognition_report(dashboard_client):
    res = dashboard_client.get("/api/metacognition/report")
    assert res.status_code == 200
    data = res.json()
    assert "reflective_narrative" in data
    assert "meta_state_label" in data


# ------------------------------------------------------------------ #
# Gateway API
# ------------------------------------------------------------------ #


def test_gateway_metacognition_state():
    auth, observer = _setup_gateway_auth()
    gateway_api._auth_engine = auth

    with patch("speace_core.monitoring.dashboard_api._metacognitive_monitor") as mock_monitor:
        from speace_core.cellular_brain.metacognition.meta_state import MetaState
        mock_monitor.generate_meta_state.return_value = MetaState(
            meta_state_label="stable",
            reflective_narrative="All good.",
        )
        client = TestClient(gateway_api.app)
        res = client.get("/api/metacognition/state", headers={"X-API-Key": observer})
        assert res.status_code == 200
        data = res.json()
        assert data["meta_state_label"] == "stable"


def test_gateway_metacognition_report():
    auth, observer = _setup_gateway_auth()
    gateway_api._auth_engine = auth

    with patch("speace_core.monitoring.dashboard_api._metacognitive_monitor") as mock_monitor:
        from speace_core.cellular_brain.metacognition.meta_state import MetaState
        mock_monitor.generate_meta_state.return_value = MetaState(
            meta_state_label="stable",
            reflective_narrative="All good.",
        )
        client = TestClient(gateway_api.app)
        res = client.get("/api/metacognition/report", headers={"X-API-Key": observer})
        assert res.status_code == 200
        data = res.json()
        assert data["reflective_narrative"] == "All good."


def test_gateway_metacognition_unauthorized():
    auth, _ = _setup_gateway_auth()
    gateway_api._auth_engine = auth

    client = TestClient(gateway_api.app)
    res = client.get("/api/metacognition/state")
    assert res.status_code == 401
