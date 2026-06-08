"""Tests for the SPEACE dashboard API endpoints."""

import json
import urllib.request

import pytest

from speace_core.dashboard.server import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health_endpoint(client):
    rv = client.get("/api/health")
    assert rv.status_code == 200
    data = rv.get_json()
    assert data["status"] == "ok"
    assert "uptime_seconds" in data
    assert "speace_version" in data


def test_state_endpoint(client):
    rv = client.get("/api/state")
    assert rv.status_code == 200
    data = rv.get_json()
    assert "organismic_summary" in data
    assert "workspace" in data
    assert "self_model" in data
    assert "sensors" in data
    assert "drives" in data
    assert "embodiment" in data
    assert "stabilizer" in data
    assert "distributed" in data
    assert "social" in data
    assert "narrative" in data


def test_history_endpoint(client):
    rv = client.get("/api/history?metric=coherence_phi&limit=10")
    assert rv.status_code == 200
    data = rv.get_json()
    assert isinstance(data, list)


def test_logs_endpoint(client):
    rv = client.get("/api/logs")
    assert rv.status_code == 200
    data = rv.get_json()
    assert isinstance(data, list)


def test_static_files(client):
    rv = client.get("/")
    assert rv.status_code == 200
    assert b"SPEACE Organismic Monitor" in rv.data

    css = client.get("/static/css/dashboard.css")
    assert css.status_code == 200
    assert b"dark theme" in css.data or b"--bg-primary" in css.data

    js = client.get("/static/js/dashboard.js")
    assert js.status_code == 200
    assert b"fetchState" in js.data or b"fetch(" in js.data
