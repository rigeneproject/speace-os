"""Tests for T147 Embodied Sensory Stream dashboard endpoints."""

import pytest

try:
    from fastapi.testclient import TestClient
    from speace_core.monitoring.dashboard_api import app

    _HAS_FASTAPI = True
except Exception:  # pragma: no cover
    _HAS_FASTAPI = False
    TestClient = None  # type: ignore[misc,assignment]
    app = None  # type: ignore[misc,assignment]


@pytest.mark.skipif(not _HAS_FASTAPI, reason="FastAPI not installed")
class TestEmbodimentDashboard:
    @pytest.fixture(autouse=True)
    def client(self):
        app.state._testing = True  # type: ignore[union-attr]
        return TestClient(app)

    def test_get_sensors(self, client):
        r = client.get("/api/embodiment/sensors")
        assert r.status_code == 200
        data = r.json()
        assert "runtime_running" in data
        assert "embodiment_enabled" in data
        assert "snapshot" in data
