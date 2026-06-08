"""Tests for T103 — Observer Report Generator."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from speace_core.monitoring.dashboard_api import app
from speace_core.monitoring.observer_report import (
    AlertSummary,
    AnomalySummary,
    ObserverReport,
    Recommendation,
    ReportMeta,
    TrendAnalysis,
)
from speace_core.monitoring.observer_report_generator import ObserverReportGenerator


@pytest.fixture
def client():
    app.state._testing = True
    with TestClient(app) as c:
        yield c


class TestObserverReportModel:
    def test_report_creation(self):
        rep = ObserverReport(
            meta=ReportMeta(lookback_window_hours=24),
            alert_summary=AlertSummary(total_count=5, critical_count=1, warning_count=3),
            verdict="WATCH",
        )
        assert rep.meta.lookback_window_hours == 24
        assert rep.alert_summary.total_count == 5
        assert rep.verdict == "WATCH"

    def test_report_to_markdown(self):
        rep = ObserverReport(
            meta=ReportMeta(lookback_window_hours=24),
            alert_summary=AlertSummary(total_count=2, critical_count=0, warning_count=1),
            trend_analysis=TrendAnalysis(trend_direction="stable"),
            recommendations=[
                Recommendation(category="safety", message="Test rec", severity="warning", confidence=0.8)
            ],
            verdict="STABLE",
        )
        md = rep.to_markdown()
        assert "# SPEACE Observer Report" in md
        assert "STABLE" in md
        assert "Test rec" in md
        assert "stable" in md


class TestObserverReportGenerator:
    def test_generate_basic(self, tmp_path):
        gen = ObserverReportGenerator(data_root=str(tmp_path))
        rep = gen.generate(lookback_hours=1)
        assert isinstance(rep, ObserverReport)
        assert rep.meta.lookback_window_hours == 1
        assert rep.verdict in ("STABLE", "WATCH", "INTERVENTION_RECOMMENDED")
        assert 0.0 <= rep.alert_summary.health_score_current <= 1.0

    def test_alert_summary_from_file(self, tmp_path):
        alerts_file = tmp_path / "monitoring" / "alerts.jsonl"
        alerts_file.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        alerts_file.write_text(
            json.dumps({"severity": "critical", "timestamp": now, "alert_type": "chaos_critical", "message": "x"}) + "\n" +
            json.dumps({"severity": "warning", "timestamp": now - 100, "alert_type": "rigidity_warning", "message": "y"}) + "\n",
            encoding="utf-8",
        )
        gen = ObserverReportGenerator(data_root=str(tmp_path), alerts_path=str(alerts_file))
        rep = gen.generate(lookback_hours=1)
        assert rep.alert_summary.total_count == 2
        assert rep.alert_summary.critical_count == 1
        assert rep.alert_summary.warning_count == 1
        assert len(rep.alert_summary.recent_alerts) == 2

    def test_anomaly_summary_from_file(self, tmp_path):
        reg_file = tmp_path / "regulation" / "stabilizer_interventions.jsonl"
        reg_file.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        reg_file.write_text(
            json.dumps({"pattern_detected": "rigidity", "timestamp": now, "severity": 1.0}) + "\n" +
            json.dumps({"pattern_detected": "rigidity", "timestamp": now - 100, "severity": 2.0}) + "\n" +
            json.dumps({"pattern_detected": "chaos", "timestamp": now - 200, "severity": 1.5}) + "\n",
            encoding="utf-8",
        )
        gen = ObserverReportGenerator(data_root=str(tmp_path))
        rep = gen.generate(lookback_hours=1)
        assert rep.anomaly_summary.total_interventions == 3
        assert rep.anomaly_summary.pattern_counts.get("rigidity") == 2
        assert rep.anomaly_summary.pattern_counts.get("chaos") == 1

    def test_trend_analysis_from_snapshots(self, tmp_path):
        snap_file = tmp_path / "morphological_memory" / "snapshots.jsonl"
        snap_file.parent.mkdir(parents=True, exist_ok=True)
        now = time.time()
        snap_file.write_text(
            json.dumps({"coherence_phi": 0.3, "chaos_score": 0.8, "rigidity_score": 0.5, "drift": 0.1, "prediction_error": 5.0, "branching_ratio": 1.2, "timestamp": now - 4000}) + "\n" +
            json.dumps({"coherence_phi": 0.5, "chaos_score": 0.6, "rigidity_score": 0.4, "drift": 0.05, "prediction_error": 3.0, "branching_ratio": 1.05, "timestamp": now}) + "\n",
            encoding="utf-8",
        )
        gen = ObserverReportGenerator(data_root=str(tmp_path))
        rep = gen.generate(lookback_hours=2)
        assert rep.trend_analysis.coherence_phi_delta == pytest.approx(0.2, abs=0.01)
        assert rep.trend_analysis.chaos_score_delta == pytest.approx(-0.2, abs=0.01)
        assert rep.trend_analysis.trend_direction == "improving"

    def test_recommendations_safety_risk(self, tmp_path):
        gen = ObserverReportGenerator(data_root=str(tmp_path))
        # Simulate a state with high safety risk by overriding collector state
        # Since collect_all reads from files, we test recommendations indirectly
        # via the verdict computation with mocked alert_summary
        alert_summary = AlertSummary(critical_count=1, warning_count=0, health_score_current=0.3)
        trend = TrendAnalysis(trend_direction="stable")
        recs = [
            Recommendation(category="safety", message="x", severity="critical", confidence=0.9)
        ]
        verdict = gen._compute_verdict(alert_summary, trend, recs)
        assert verdict == "INTERVENTION_RECOMMENDED"

    def test_verdict_stable(self, tmp_path):
        gen = ObserverReportGenerator(data_root=str(tmp_path))
        alert_summary = AlertSummary(critical_count=0, warning_count=1, health_score_current=0.9)
        trend = TrendAnalysis(trend_direction="stable")
        verdict = gen._compute_verdict(alert_summary, trend, [])
        assert verdict == "STABLE"

    def test_verdict_watch(self, tmp_path):
        gen = ObserverReportGenerator(data_root=str(tmp_path))
        alert_summary = AlertSummary(critical_count=0, warning_count=5, health_score_current=0.7)
        trend = TrendAnalysis(trend_direction="degrading")
        verdict = gen._compute_verdict(alert_summary, trend, [])
        assert verdict == "WATCH"

    def test_read_jsonl_since_skips_old(self, tmp_path):
        p = tmp_path / "test.jsonl"
        now = time.time()
        p.write_text(
            json.dumps({"timestamp": now - 10000, "msg": "old"}) + "\n" +
            json.dumps({"timestamp": now - 100, "msg": "recent"}) + "\n",
            encoding="utf-8",
        )
        gen = ObserverReportGenerator(data_root=str(tmp_path))
        entries = gen._read_jsonl_since(p, now - 3600)
        assert len(entries) == 1
        assert entries[0]["msg"] == "recent"


class TestObserverReportApi:
    def test_api_report(self, client):
        r = client.get("/api/report")
        assert r.status_code == 200
        data = r.json()
        assert "meta" in data
        assert "organismic_summary" in data
        assert "alert_summary" in data
        assert "anomaly_summary" in data
        assert "trend_analysis" in data
        assert "recommendations" in data
        assert "verdict" in data
        assert data["meta"]["lookback_window_hours"] == 24

    def test_api_report_lookback_param(self, client):
        r = client.get("/api/report?lookback=1")
        assert r.status_code == 200
        data = r.json()
        assert data["meta"]["lookback_window_hours"] == 1

    def test_api_report_verdict_values(self, client):
        r = client.get("/api/report")
        assert r.status_code == 200
        data = r.json()
        assert data["verdict"] in ("STABLE", "WATCH", "INTERVENTION_RECOMMENDED")
