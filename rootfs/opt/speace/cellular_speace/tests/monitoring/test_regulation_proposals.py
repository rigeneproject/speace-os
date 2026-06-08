"""Tests for T104 — Safe Regulation Layer."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from speace_core.monitoring.dashboard_api import app
from speace_core.monitoring.human_approval_gate import HumanApprovalGate
from speace_core.monitoring.regulation_confidence_scorer import RegulationConfidenceScorer
from speace_core.monitoring.regulation_proposal_builder import RegulationProposalBuilder
from speace_core.monitoring.safe_regulation_executor import SafeRegulationExecutor


@pytest.fixture
def client():
    app.state._testing = True
    with TestClient(app) as c:
        yield c


@pytest.fixture
def builder(tmp_path):
    p = tmp_path / "proposals.jsonl"
    return RegulationProposalBuilder(proposals_path=str(p))


@pytest.fixture
def gate(builder):
    return HumanApprovalGate(builder=builder)


# ------------------------------------------------------------------ #
# RegulationConfidenceScorer
# ------------------------------------------------------------------ #

class TestRegulationConfidenceScorer:
    def test_empty_history(self, tmp_path):
        p = tmp_path / "outcomes.jsonl"
        scorer = RegulationConfidenceScorer(outcomes_path=str(p))
        result = scorer.score("increase stability bias", "chaos_warning", {})
        assert result["confidence"] == 0.5
        assert result["based_on_history"] is False

    def test_confidence_from_success(self, tmp_path):
        p = tmp_path / "outcomes.jsonl"
        scorer = RegulationConfidenceScorer(outcomes_path=str(p))
        scorer.record_outcome("p1", "chaos_warning", "increase stability bias", 0.5, 0.7, "success")
        result = scorer.score("increase stability bias", "chaos_warning", {})
        assert result["based_on_history"] is True
        assert result["confidence"] > 0.5
        assert result["success_rate"] == 1.0

    def test_confidence_from_rollback(self, tmp_path):
        p = tmp_path / "outcomes.jsonl"
        scorer = RegulationConfidenceScorer(outcomes_path=str(p))
        scorer.record_outcome("p1", "chaos_warning", "increase stability bias", 0.5, 0.3, "rollback")
        result = scorer.score("increase stability bias", "chaos_warning", {})
        assert result["confidence"] < 0.5
        assert result["success_rate"] == 0.0

    def test_similar_count_filters_by_alert_type(self, tmp_path):
        p = tmp_path / "outcomes.jsonl"
        scorer = RegulationConfidenceScorer(outcomes_path=str(p))
        scorer.record_outcome("p1", "chaos_warning", "increase stability bias", 0.5, 0.7, "success")
        scorer.record_outcome("p2", "rigidity_warning", "increase stability bias", 0.5, 0.7, "success")
        result = scorer.score("increase stability bias", "chaos_warning", {})
        assert result["similar_count"] == 1


# ------------------------------------------------------------------ #
# RegulationProposalBuilder
# ------------------------------------------------------------------ #

class TestRegulationProposalBuilder:
    def test_build_from_critical_alert(self, builder):
        alert = {
            "alert_type": "chaos_critical",
            "severity": "critical",
            "message": "chaos_score=0.85",
            "timestamp": time.time(),
        }
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.4}},
            "dynamics": {"chaos_score": 0.85, "rigidity_score": 0.1, "drift": 0.0, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 0.0},
            "safety": {"risk_level": "low"},
            "identity": {"divergence_detected": False},
            "drives": {"drives": []},
            "body": {"cpu": 0.0, "memory_bytes": 0.0},
        }
        proposals = builder.build_from_alerts([alert], state)
        assert len(proposals) > 0
        assert proposals[0]["status"] == "pending"
        assert proposals[0]["reversibility"] == "tunable_parameter"
        assert "snapshot_pre" in proposals[0]
        assert "confidence" in proposals[0]

    def test_build_ignores_info_alerts(self, builder):
        alert = {"alert_type": "something_info", "severity": "info", "message": "", "timestamp": time.time()}
        proposals = builder.build_from_alerts([alert], {})
        assert len(proposals) == 0

    def test_proposal_id_unique(self, builder):
        alert = {"alert_type": "chaos_warning", "severity": "warning", "message": "", "timestamp": time.time()}
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.4}},
            "dynamics": {"chaos_score": 0.5, "rigidity_score": 0.0, "drift": 0.0, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 0.0},
            "safety": {"risk_level": "low"},
            "identity": {"divergence_detected": False},
            "drives": {"drives": []},
            "body": {"cpu": 0.0, "memory_bytes": 0.0},
        }
        p1 = builder.build_from_alerts([alert], state)
        p2 = builder.build_from_alerts([alert], state)
        assert p1[0]["proposal_id"] != p2[0]["proposal_id"]


# ------------------------------------------------------------------ #
# HumanApprovalGate
# ------------------------------------------------------------------ #

class TestHumanApprovalGate:
    def test_approve_executes_and_logs(self, gate, builder):
        alert = {"alert_type": "chaos_warning", "severity": "warning", "message": "", "timestamp": time.time()}
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.4}},
            "dynamics": {"chaos_score": 0.5, "rigidity_score": 0.0, "drift": 0.0, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 0.0},
            "safety": {"risk_level": "low"},
            "identity": {"divergence_detected": False},
            "drives": {"drives": []},
            "body": {"cpu": 0.0, "memory_bytes": 0.0},
        }
        proposals = builder.build_from_alerts([alert], state)
        pid = proposals[0]["proposal_id"]
        result = gate.approve(pid, "Roberto", current_health=0.5)
        assert result["status"] == "executed"
        assert result["reviewer"] == "Roberto"
        assert "execution" in result

    def test_reject_sets_status(self, gate, builder):
        alert = {"alert_type": "chaos_warning", "severity": "warning", "message": "", "timestamp": time.time()}
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.4}},
            "dynamics": {"chaos_score": 0.5, "rigidity_score": 0.0, "drift": 0.0, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 0.0},
            "safety": {"risk_level": "low"},
            "identity": {"divergence_detected": False},
            "drives": {"drives": []},
            "body": {"cpu": 0.0, "memory_bytes": 0.0},
        }
        proposals = builder.build_from_alerts([alert], state)
        pid = proposals[0]["proposal_id"]
        result = gate.reject(pid, "Roberto")
        assert result["status"] == "rejected"
        assert result["reviewer"] == "Roberto"

    def test_approve_unknown_returns_error(self, gate):
        result = gate.approve("RP-doesnotexist", "Roberto", current_health=0.5)
        assert result["error"] == "proposal_not_found"


# ------------------------------------------------------------------ #
# SafeRegulationExecutor
# ------------------------------------------------------------------ #

class TestSafeRegulationExecutor:
    def test_blocks_structural_change(self):
        ex = SafeRegulationExecutor()
        proposal = {
            "proposal_id": "p1",
            "proposed_action": "global workspace reset",
            "alert": {"alert_type": "coherence_phi_critical"},
            "snapshot_pre": {},
            "estimated_risk": 0.5,
            "confidence": {"confidence": 0.5},
        }
        log = ex.execute(proposal, current_health=0.5)
        assert log["outcome"] == "blocked"

    def test_allows_tunable_parameter(self):
        ex = SafeRegulationExecutor()
        proposal = {
            "proposal_id": "p1",
            "proposed_action": "increase stability bias",
            "alert": {"alert_type": "chaos_warning"},
            "snapshot_pre": {},
            "estimated_risk": 0.3,
            "confidence": {"confidence": 0.5},
        }
        log = ex.execute(proposal, current_health=0.5)
        assert log["outcome"] in ("success", "rollback")


# ------------------------------------------------------------------ #
# Dashboard API
# ------------------------------------------------------------------ #

class TestRegulationApi:
    def test_api_list_pending(self, client):
        r = client.get("/api/regulation/proposals?status=pending")
        assert r.status_code == 200
        data = r.json()
        assert "proposals" in data
        assert isinstance(data["proposals"], list)

    def test_api_reject(self, client):
        # Seed a proposal by triggering an alert via /api/alerts
        r = client.get("/api/alerts")
        assert r.status_code == 200
        state = r.json()
        # Build a proposal manually via the underlying builder
        from speace_core.monitoring.dashboard_api import _regulation_builder
        alert = {"alert_type": "chaos_warning", "severity": "warning", "message": "x", "timestamp": time.time()}
        proposals = _regulation_builder.build_from_alerts([alert], state)
        if proposals:
            pid = proposals[0]["proposal_id"]
            r2 = client.post(f"/api/regulation/reject/{pid}", json={"reviewer": "Roberto"})
            assert r2.status_code == 200
            assert r2.json()["status"] == "rejected"
