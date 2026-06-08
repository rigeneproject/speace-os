"""Tests for T128 — Epistemic Confidence Engine integration."""

from unittest.mock import MagicMock, patch

import pytest

from speace_core.cellular_brain.metacognition.metacognitive_monitor import MetacognitiveMonitor
from speace_core.cellular_brain.metacognition.meta_state import EpistemicConfidence


def _make_state(chaos_score=0.3, coherence_phi=0.7):
    return {
        "dynamics": {"chaos_score": chaos_score, "rigidity_score": 0.2, "drift": 0.1},
        "cognition": {"self_model": {"coherence_phi": coherence_phi}},
        "alert_engine": {"health_score": 0.8, "alerts": []},
        "timestamp": 1234567890.0,
    }


def test_confidence_for_proposal_with_high_risk():
    monitor = MetacognitiveMonitor()
    state = _make_state()
    proposal = {"risk_score": 0.9, "confidence": {"confidence": 0.3}}
    conf = monitor.confidence_for_proposal(proposal, state)
    assert isinstance(conf, EpistemicConfidence)
    assert conf.confidence_score < 0.5


def test_confidence_for_proposal_with_low_risk():
    monitor = MetacognitiveMonitor()
    state = _make_state()
    proposal = {"risk_score": 0.1, "confidence": {"confidence": 0.8}}
    conf = monitor.confidence_for_proposal(proposal, state)
    assert conf.confidence_score > 0.5


def test_confidence_for_dialogue_start():
    monitor = MetacognitiveMonitor()
    state = _make_state(coherence_phi=0.9)
    dialogue_state = {"turn_count": 0, "state": "idle"}
    conf = monitor.confidence_for_dialogue(dialogue_state, state)
    assert conf.novelty_score > 0.5  # high novelty at start


def test_confidence_for_dialogue_ongoing():
    monitor = MetacognitiveMonitor()
    state = _make_state(coherence_phi=0.9)
    dialogue_state = {"turn_count": 10, "state": "active"}
    conf = monitor.confidence_for_dialogue(dialogue_state, state)
    assert conf.confidence_score > 0.5


# ------------------------------------------------------------------ #
# API tests (gateway)
# ------------------------------------------------------------------ #


def test_gateway_proposal_confidence():
    from speace_core.web_gateway.auth_engine import AuthEngine
    from speace_core.web_gateway import gateway_api

    auth = AuthEngine(data_root="data/test_web_gateway_t128")
    for key in list(auth._keys.keys()):
        auth.revoke_key(key)
    observer = auth.generate_key(role="observer")
    gateway_api._auth_engine = auth

    mock_proposal = {"risk_score": 0.2, "confidence": {"confidence": 0.8}}
    with patch("speace_core.monitoring.dashboard_api._approval_gate") as mock_gate:
        mock_gate.builder.get_proposal.return_value = mock_proposal
        from fastapi.testclient import TestClient
        client = TestClient(gateway_api.app)
        res = client.get("/api/metacognition/proposal/RP-123/confidence", headers={"X-API-Key": observer})
        assert res.status_code == 200
        data = res.json()
        assert "confidence_score" in data


def test_gateway_dialogue_confidence():
    from speace_core.web_gateway.auth_engine import AuthEngine
    from speace_core.web_gateway import gateway_api

    auth = AuthEngine(data_root="data/test_web_gateway_t128")
    for key in list(auth._keys.keys()):
        auth.revoke_key(key)
    observer = auth.generate_key(role="observer")
    gateway_api._auth_engine = auth

    with patch("speace_core.monitoring.dashboard_api._dialogue_manager") as mock_dm:
        mock_dm._turn_count = 5
        mock_dm.state = "active"
        from fastapi.testclient import TestClient
        client = TestClient(gateway_api.app)
        res = client.get("/api/metacognition/dialogue/confidence", headers={"X-API-Key": observer})
        assert res.status_code == 200
        data = res.json()
        assert "confidence_score" in data
