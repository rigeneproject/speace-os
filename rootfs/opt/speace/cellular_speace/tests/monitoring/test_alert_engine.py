"""Tests for T102 — AlertEngine."""

import json
import pathlib
import tempfile

import pytest

from speace_core.monitoring.alert_engine import AlertEngine


@pytest.fixture
def engine(tmp_path):
    p = tmp_path / "alerts.jsonl"
    return AlertEngine(alerts_path=str(p))


class TestAlertEngineEvaluate:
    def test_no_alerts_when_all_normal(self, engine):
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.1, "rigidity_score": 0.1, "drift": 0.01, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 1.0},
        }
        alerts = engine.evaluate(state)
        assert alerts == []

    def test_chaos_warning(self, engine):
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.5, "rigidity_score": 0.1, "drift": 0.01, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 1.0},
        }
        alerts = engine.evaluate(state)
        assert any(a["alert_type"] == "chaos_warning" for a in alerts)

    def test_chaos_critical(self, engine):
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.9, "rigidity_score": 0.1, "drift": 0.01, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 1.0},
        }
        alerts = engine.evaluate(state)
        assert any(a["alert_type"] == "chaos_critical" and a["severity"] == "critical" for a in alerts)

    def test_rigidity_warning(self, engine):
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.1, "rigidity_score": 0.5, "drift": 0.01, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 1.0},
        }
        alerts = engine.evaluate(state)
        assert any(a["alert_type"] == "rigidity_warning" for a in alerts)

    def test_drift_critical(self, engine):
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.1, "rigidity_score": 0.1, "drift": 0.6, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 1.0},
        }
        alerts = engine.evaluate(state)
        assert any(a["alert_type"] == "drift_critical" for a in alerts)

    def test_prediction_error_critical(self, engine):
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.1, "rigidity_score": 0.1, "drift": 0.01, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 25.0},
        }
        alerts = engine.evaluate(state)
        assert any(a["alert_type"] == "prediction_error_critical" for a in alerts)

    def test_coherence_phi_critical(self, engine):
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.05}},
            "dynamics": {"chaos_score": 0.1, "rigidity_score": 0.1, "drift": 0.01, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 1.0},
        }
        alerts = engine.evaluate(state)
        assert any(a["alert_type"] == "coherence_phi_critical" for a in alerts)

    def test_branching_deviation_warning(self, engine):
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.1, "rigidity_score": 0.1, "drift": 0.01, "criticality": {"branching_ratio": 1.3}},
            "embodiment": {"prediction_error": 1.0},
        }
        alerts = engine.evaluate(state)
        assert any(a["alert_type"] == "branching_warning" for a in alerts)

    def test_multiple_alerts(self, engine):
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.05}},
            "dynamics": {"chaos_score": 0.9, "rigidity_score": 0.8, "drift": 0.6, "criticality": {"branching_ratio": 1.5}},
            "embodiment": {"prediction_error": 25.0},
        }
        alerts = engine.evaluate(state)
        types = {a["alert_type"] for a in alerts}
        assert "chaos_critical" in types
        assert "rigidity_critical" in types
        assert "drift_critical" in types
        assert "prediction_error_critical" in types
        assert "coherence_phi_critical" in types
        assert "branching_critical" in types

    def test_alert_contains_read_only_flag(self, engine):
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.9, "rigidity_score": 0.1, "drift": 0.01, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 1.0},
        }
        alerts = engine.evaluate(state)
        assert all(a.get("read_only") is True for a in alerts)

    def test_alert_contains_source_state(self, engine):
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.9, "rigidity_score": 0.1, "drift": 0.01, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 1.0},
        }
        alerts = engine.evaluate(state)
        assert all("source_state" in a for a in alerts)
        assert all(a["source_state"]["chaos_score"] == 0.9 for a in alerts)


class TestAlertEngineHealthScore:
    def test_perfect_health(self, engine):
        state = {
            "cognition": {"self_model": {"coherence_phi": 1.0}},
            "dynamics": {"chaos_score": 0.0, "rigidity_score": 0.0, "drift": 0.0},
            "embodiment": {"prediction_error": 0.0},
        }
        score = engine.health_score(state)
        assert score == 1.0

    def test_zero_health(self, engine):
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.0}},
            "dynamics": {"chaos_score": 0.0, "rigidity_score": 0.0, "drift": 0.0},
            "embodiment": {"prediction_error": 0.0},
        }
        score = engine.health_score(state)
        assert score == 0.0

    def test_health_within_bounds(self, engine):
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.2, "rigidity_score": 0.3, "drift": 0.1},
            "embodiment": {"prediction_error": 10.0},
        }
        score = engine.health_score(state)
        assert 0.0 <= score <= 1.0

    def test_health_penalizes_chaos(self, engine):
        base = {
            "cognition": {"self_model": {"coherence_phi": 1.0}},
            "dynamics": {"chaos_score": 0.0, "rigidity_score": 0.0, "drift": 0.0},
            "embodiment": {"prediction_error": 0.0},
        }
        base["dynamics"]["chaos_score"] = 0.5
        score = engine.health_score(base)
        assert score == pytest.approx(0.5, abs=0.01)

    def test_health_penalizes_safety_risk(self, engine):
        base = {
            "cognition": {"self_model": {"coherence_phi": 1.0}},
            "dynamics": {"chaos_score": 0.0, "rigidity_score": 0.0, "drift": 0.0},
            "embodiment": {"prediction_error": 0.0},
            "safety": {"risk_level": "critical"},
        }
        score = engine.health_score(base)
        assert score == pytest.approx(0.0, abs=0.01)

    def test_health_penalizes_identity_divergence(self, engine):
        base = {
            "cognition": {"self_model": {"coherence_phi": 1.0}},
            "dynamics": {"chaos_score": 0.0, "rigidity_score": 0.0, "drift": 0.0},
            "embodiment": {"prediction_error": 0.0},
            "identity": {"divergence_detected": True},
        }
        score = engine.health_score(base)
        assert score == pytest.approx(0.7, abs=0.01)

    def test_health_penalizes_drive_instability(self, engine):
        base = {
            "cognition": {"self_model": {"coherence_phi": 1.0}},
            "dynamics": {"chaos_score": 0.0, "rigidity_score": 0.0, "drift": 0.0},
            "embodiment": {"prediction_error": 0.0},
            "drives": {"drives": [{"urgency": 0.5}]},
        }
        score = engine.health_score(base)
        assert score == pytest.approx(0.5, abs=0.01)


class TestAlertEngineNewMetrics:
    def test_safety_risk_warning(self, engine):
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.1, "rigidity_score": 0.1, "drift": 0.01, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 1.0},
            "safety": {"risk_level": "medium"},
        }
        alerts = engine.evaluate(state)
        assert any(a["alert_type"] == "safety_risk_warning" for a in alerts)

    def test_safety_risk_critical(self, engine):
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.1, "rigidity_score": 0.1, "drift": 0.01, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 1.0},
            "safety": {"risk_level": "critical"},
        }
        alerts = engine.evaluate(state)
        assert any(a["alert_type"] == "safety_risk_critical" and a["severity"] == "critical" for a in alerts)

    def test_identity_divergence_warning(self, engine):
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.1, "rigidity_score": 0.1, "drift": 0.01, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 1.0},
            "identity": {"divergence_detected": True},
        }
        alerts = engine.evaluate(state)
        assert any(a["alert_type"] == "identity_divergence_warning" for a in alerts)

    def test_drive_instability_warning(self, engine):
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.1, "rigidity_score": 0.1, "drift": 0.01, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 1.0},
            "drives": {"drives": [{"urgency": 0.6}]},
        }
        alerts = engine.evaluate(state)
        assert any(a["alert_type"] == "drive_instability_warning" for a in alerts)

    def test_drive_instability_critical(self, engine):
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.1, "rigidity_score": 0.1, "drift": 0.01, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 1.0},
            "drives": {"drives": [{"urgency": 0.9}]},
        }
        alerts = engine.evaluate(state)
        assert any(a["alert_type"] == "drive_instability_critical" and a["severity"] == "critical" for a in alerts)

    def test_new_alert_source_state(self, engine):
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.1, "rigidity_score": 0.1, "drift": 0.01, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 1.0},
            "safety": {"risk_level": "critical"},
            "identity": {"divergence_detected": True},
            "drives": {"drives": [{"urgency": 0.9}]},
        }
        alerts = engine.evaluate(state)
        assert all("source_state" in a for a in alerts)
        for a in alerts:
            if a["alert_type"].startswith("safety"):
                assert a["source_state"]["safety_risk"] == "critical"
            if a["alert_type"].startswith("identity"):
                assert a["source_state"]["divergence_detected"] is True
            if a["alert_type"].startswith("drive"):
                assert a["source_state"]["drive_instability"] == 0.9


class TestAlertEnginePersistence:
    def test_persist_and_read(self, tmp_path):
        p = tmp_path / "alerts.jsonl"
        engine = AlertEngine(alerts_path=str(p))
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.9, "rigidity_score": 0.1, "drift": 0.01, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 1.0},
        }
        alerts = engine.evaluate(state)
        assert len(alerts) > 0
        recent = engine.recent_alerts(limit=10)
        assert len(recent) >= len(alerts)
        assert all(a["alert_type"] for a in recent)

    def test_max_history_trimming(self, tmp_path):
        p = tmp_path / "alerts.jsonl"
        engine = AlertEngine(alerts_path=str(p), max_history=3)
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.9, "rigidity_score": 0.1, "drift": 0.01, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 1.0},
        }
        for _ in range(5):
            engine.evaluate(state)
        recent = engine.recent_alerts(limit=100)
        assert len(recent) <= 3

    def test_corrupt_line_skipped(self, tmp_path):
        p = tmp_path / "alerts.jsonl"
        p.write_text("not json\n", encoding="utf-8")
        engine = AlertEngine(alerts_path=str(p))
        recent = engine.recent_alerts(limit=10)
        assert recent == []


class TestAlertEngineCustomThresholds:
    def test_custom_thresholds(self):
        engine = AlertEngine(thresholds={"chaos_warning": 0.1, "chaos_critical": 0.5})
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.3, "rigidity_score": 0.0, "drift": 0.0, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 0.0},
        }
        alerts = engine.evaluate(state)
        assert any(a["severity"] == "warning" for a in alerts)
        assert not any(a["severity"] == "critical" for a in alerts)
