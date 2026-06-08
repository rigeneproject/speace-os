"""Tests for T145 Dialogue Evolution Approval Dashboard endpoints."""

import pytest

from speace_core.cellular_brain.metacognition.cognitive_linguistic_coherence_monitor import (
    CognitiveLinguisticCoherenceReport,
)
from speace_core.cellular_brain.cognitive_evolution.cla_feedback_layer import CLAFeedbackLayer

try:
    from fastapi.testclient import TestClient
    from speace_core.monitoring.dashboard_api import app

    _HAS_FASTAPI = True
except Exception:  # pragma: no cover
    _HAS_FASTAPI = False
    TestClient = None  # type: ignore[misc,assignment]
    app = None  # type: ignore[misc,assignment]


@pytest.mark.skipif(not _HAS_FASTAPI, reason="FastAPI not installed")
class TestDialogueEvolutionDashboard:
    @pytest.fixture(autouse=True)
    def client(self):
        app.state._testing = True  # type: ignore[union-attr]
        return TestClient(app)

    def _seed_proposal(self, dialogue_manager):
        layer = dialogue_manager._cla_feedback
        report = CognitiveLinguisticCoherenceReport(
            overall_coherence_score=0.2,
            narrative_coherence=0.1,
            grounding_consistency=0.1,
            drive_language_alignment=0.1,
            confidence_language_alignment=0.1,
            memory_reference_consistency=0.1,
            self_model_consistency=0.1,
            contradiction_rate=0.8,
            repetitive_loop_density=0.8,
        )
        result = layer.process_coherence_report(report)
        proposals = result.get("proposals", [])
        return proposals[0]["proposal_id"] if proposals else None

    def test_get_proposals(self, client):
        r = client.get("/api/dialogue/evolution/proposals")
        assert r.status_code == 200
        data = r.json()
        assert "proposals" in data
        assert "count" in data

    def test_get_proposal_detail(self, client):
        from speace_core.monitoring.dashboard_api import _dialogue_manager

        pid = self._seed_proposal(_dialogue_manager)
        if pid is None:
            pytest.skip("No proposal generated")
        r = client.get(f"/api/dialogue/evolution/proposals/{pid}")
        assert r.status_code == 200
        data = r.json()
        assert data.get("proposal_id") == pid

    def test_approve_and_reject(self, client):
        from speace_core.monitoring.dashboard_api import _dialogue_manager

        pid = self._seed_proposal(_dialogue_manager)
        if pid is None:
            pytest.skip("No proposal generated")
        r = client.post(f"/api/dialogue/evolution/approve/{pid}", json={"reviewer": "tester"})
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") in ("applied", "error")

    def test_get_audit(self, client):
        r = client.get("/api/dialogue/evolution/audit?hours=1&limit=10")
        assert r.status_code == 200
        data = r.json()
        assert "events" in data
        assert "count" in data

    def test_get_summary(self, client):
        r = client.get("/api/dialogue/evolution/summary")
        assert r.status_code == 200
        data = r.json()
        assert "warning_threshold" in data
        assert "critical_threshold" in data
