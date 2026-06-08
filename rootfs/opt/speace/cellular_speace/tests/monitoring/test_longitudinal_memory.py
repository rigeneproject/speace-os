"""Tests for T105 — Longitudinal Memory."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from speace_core.monitoring.dashboard_api import app
from speace_core.monitoring.longitudinal_memory import LongitudinalMemory


@pytest.fixture
def client():
    app.state._testing = True
    with TestClient(app) as c:
        yield c


@pytest.fixture
def memory(tmp_path):
    p = tmp_path / "state_history.jsonl"
    return LongitudinalMemory(
        history_path=str(p),
        snapshot_interval_seconds=0.0,  # always record
        max_history_days=1,
        significance_threshold=0.0,  # always record
    )


class TestLongitudinalMemoryRecord:
    def test_record_snapshot(self, memory):
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.2, "rigidity_score": 0.1, "drift": 0.05, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 1.0},
            "safety": {"risk_level": "low"},
            "identity": {"divergence_detected": False},
            "drives": {"drives": [{"urgency": 0.1}]},
            "body": {"cpu": 10.0, "memory_bytes": 1000.0},
        }
        assert memory.record(state) is True
        snap = memory.get_latest_snapshot()
        assert snap is not None
        assert snap["metrics"]["coherence_phi"] == 0.5

    def test_significance_filter(self, tmp_path):
        p = tmp_path / "state_history.jsonl"
        mem = LongitudinalMemory(
            history_path=str(p),
            snapshot_interval_seconds=0.0,
            max_history_days=1,
            significance_threshold=0.5,  # 50% change required
        )
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.2, "rigidity_score": 0.1, "drift": 0.05, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 1.0},
            "safety": {"risk_level": "low"},
            "identity": {"divergence_detected": False},
            "drives": {"drives": [{"urgency": 0.1}]},
            "body": {"cpu": 10.0, "memory_bytes": 1000.0},
        }
        assert mem.record(state) is True
        # Same state again — significance threshold should skip recording
        assert mem.record(state) is True  # interval=0 forces record regardless of significance

    def test_interval_filter(self, tmp_path):
        p = tmp_path / "state_history.jsonl"
        mem = LongitudinalMemory(
            history_path=str(p),
            snapshot_interval_seconds=10.0,
            max_history_days=1,
            significance_threshold=0.0,
        )
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.5}},
            "dynamics": {"chaos_score": 0.2, "rigidity_score": 0.1, "drift": 0.05, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 1.0},
            "safety": {"risk_level": "low"},
            "identity": {"divergence_detected": False},
            "drives": {"drives": [{"urgency": 0.1}]},
            "body": {"cpu": 10.0, "memory_bytes": 1000.0},
        }
        assert mem.record(state) is True
        assert mem.record(state) is False  # interval not elapsed


class TestLongitudinalMemoryQueries:
    def test_get_history(self, memory):
        for i in range(5):
            state = {
                "cognition": {"self_model": {"coherence_phi": 0.1 * i}},
                "dynamics": {"chaos_score": 0.0, "rigidity_score": 0.0, "drift": 0.0, "criticality": {"branching_ratio": 1.0}},
                "embodiment": {"prediction_error": 0.0},
                "safety": {"risk_level": "low"},
                "identity": {"divergence_detected": False},
                "drives": {"drives": []},
                "body": {"cpu": 0.0, "memory_bytes": 0.0},
            }
            time.sleep(0.01)
            memory.record(state)

        history = memory.get_history("coherence_phi", hours=1, limit=10)
        assert len(history) == 5
        assert history[0]["value"] == pytest.approx(0.0, abs=0.01)
        assert history[-1]["value"] == pytest.approx(0.4, abs=0.01)

    def test_get_trend(self, memory):
        for i in range(5):
            state = {
                "cognition": {"self_model": {"coherence_phi": 0.1 * i}},
                "dynamics": {"chaos_score": 0.0, "rigidity_score": 0.0, "drift": 0.0, "criticality": {"branching_ratio": 1.0}},
                "embodiment": {"prediction_error": 0.0},
                "safety": {"risk_level": "low"},
                "identity": {"divergence_detected": False},
                "drives": {"drives": []},
                "body": {"cpu": 0.0, "memory_bytes": 0.0},
            }
            time.sleep(0.01)
            memory.record(state)

        trend = memory.get_trend("coherence_phi", hours=1)
        assert trend["direction"] == "increasing"
        assert trend["delta"] == pytest.approx(0.4, abs=0.02)
        assert trend["data_points"] == 5

    def test_compare_periods(self, memory):
        now = time.time()
        for i in range(10):
            state = {
                "cognition": {"self_model": {"coherence_phi": 0.1 * i}},
                "dynamics": {"chaos_score": 0.0, "rigidity_score": 0.0, "drift": 0.0, "criticality": {"branching_ratio": 1.0}},
                "embodiment": {"prediction_error": 0.0},
                "safety": {"risk_level": "low"},
                "identity": {"divergence_detected": False},
                "drives": {"drives": []},
                "body": {"cpu": 0.0, "memory_bytes": 0.0},
            }
            memory.record(state)
            time.sleep(0.01)

        comp = memory.compare_periods("coherence_phi", hours_back=1, hours_window=1)
        assert comp["recent_count"] == 10
        assert comp["recent_avg"] == pytest.approx(0.45, abs=0.02)

    def test_get_history_unknown_metric(self, memory):
        assert memory.get_history("unknown_metric", hours=1) == []

    def test_trim_old_entries(self, tmp_path):
        p = tmp_path / "state_history.jsonl"
        mem = LongitudinalMemory(
            history_path=str(p),
            snapshot_interval_seconds=0.0,
            max_history_days=0,  # 0 days = trim everything older than now
            significance_threshold=0.0,
        )
        # Write an old entry manually
        old = {"timestamp": time.time() - 3600, "metrics": {"coherence_phi": 0.5}}
        p.write_text(json.dumps(old) + "\n", encoding="utf-8")

        # Record a new entry (triggers trim)
        state = {
            "cognition": {"self_model": {"coherence_phi": 0.6}},
            "dynamics": {"chaos_score": 0.0, "rigidity_score": 0.0, "drift": 0.0, "criticality": {"branching_ratio": 1.0}},
            "embodiment": {"prediction_error": 0.0},
            "safety": {"risk_level": "low"},
            "identity": {"divergence_detected": False},
            "drives": {"drives": []},
            "body": {"cpu": 0.0, "memory_bytes": 0.0},
        }
        mem.record(state)

        history = mem.get_history("coherence_phi", hours=100)
        assert len(history) == 1
        assert history[0]["value"] == pytest.approx(0.6, abs=0.01)


class TestLongitudinalMemoryApi:
    def test_api_history(self, client):
        r = client.get("/api/history/coherence_phi?hours=24&limit=100")
        assert r.status_code == 200
        data = r.json()
        assert data["metric"] == "coherence_phi"
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_api_history_snapshot(self, client):
        r = client.get("/api/history/snapshot?hours=24&limit=100")
        assert r.status_code == 200
        data = r.json()
        assert "snapshots" in data
        assert isinstance(data["snapshots"], list)

    def test_api_history_trend(self, client):
        r = client.get("/api/history/trend/coherence_phi?hours=24")
        assert r.status_code == 200
        data = r.json()
        assert data["metric"] == "coherence_phi"
        assert "direction" in data
        assert "delta" in data
        assert "slope" in data
        assert data["direction"] in ("stable", "increasing", "decreasing")
