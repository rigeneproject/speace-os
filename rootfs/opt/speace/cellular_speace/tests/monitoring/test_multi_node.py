"""Tests for T106 — Multi-node Monitoring Readiness."""

import pytest
from fastapi.testclient import TestClient

from speace_core.cellular_brain.distributed.node_client import NodeClient
from speace_core.monitoring.dashboard_api import app
from speace_core.monitoring.multi_node_aggregator import MultiNodeAggregator


@pytest.fixture
def client():
    app.state._testing = True
    with TestClient(app) as c:
        yield c


@pytest.fixture
def aggregator():
    return MultiNodeAggregator()


# ------------------------------------------------------------------ #
# MultiNodeAggregator
# ------------------------------------------------------------------ #

class TestMultiNodeAggregator:
    def test_empty_aggregate(self, aggregator):
        agg = aggregator.aggregate()
        assert agg["node_count"] == 0
        assert agg["consensus_health_score"] is None

    def test_aggregate_computes_health(self, aggregator):
        aggregator.ingest("node-a", {
            "alert_engine": {"health_score": 0.8},
            "identity": {"consensus_identity_hash": "abc"},
            "drives": {"drives": [{"name": "explore", "urgency": 0.5}]},
            "cognition": {"self_model": {"coherence_phi": 0.6}, "narrative_trace": [{"title": "x"}]},
        })
        aggregator.ingest("node-b", {
            "alert_engine": {"health_score": 0.6},
            "identity": {"consensus_identity_hash": "abc"},
            "drives": {"drives": [{"name": "explore", "urgency": 0.5}]},
            "cognition": {"self_model": {"coherence_phi": 0.6}, "narrative_trace": [{"title": "x"}]},
        })
        agg = aggregator.aggregate()
        assert agg["node_count"] == 2
        assert agg["consensus_health_score"] == pytest.approx(0.7, abs=0.01)

    def test_personality_drift_no_nodes(self, aggregator):
        drift = aggregator._compute_personality_drift()
        assert drift["overall_drift"] == 0.0

    def test_personality_drift_single_node(self, aggregator):
        aggregator.ingest("node-a", {
            "drives": {"drives": [{"name": "explore", "urgency": 0.5}]},
            "cognition": {"self_model": {"coherence_phi": 0.6}, "narrative_trace": [{"title": "x"}]},
        })
        drift = aggregator._compute_personality_drift()
        assert drift["overall_drift"] == 0.0

    def test_drive_divergence(self, aggregator):
        aggregator.ingest("node-a", {
            "drives": {"drives": [{"name": "explore", "urgency": 0.9}, {"name": "rest", "urgency": 0.1}]},
            "cognition": {"self_model": {"coherence_phi": 0.6}, "narrative_trace": []},
        })
        aggregator.ingest("node-b", {
            "drives": {"drives": [{"name": "explore", "urgency": 0.1}, {"name": "rest", "urgency": 0.9}]},
            "cognition": {"self_model": {"coherence_phi": 0.6}, "narrative_trace": []},
        })
        drift = aggregator._compute_personality_drift()
        assert drift["drive_divergence"] > 0.0
        assert drift["overall_drift"] > 0.0

    def test_narrative_divergence(self, aggregator):
        aggregator.ingest("node-a", {
            "drives": {"drives": []},
            "cognition": {"self_model": {"coherence_phi": 0.6}, "narrative_trace": [{"title": "alpha"}]},
        })
        aggregator.ingest("node-b", {
            "drives": {"drives": []},
            "cognition": {"self_model": {"coherence_phi": 0.6}, "narrative_trace": [{"title": "beta"}]},
        })
        drift = aggregator._compute_personality_drift()
        assert drift["narrative_divergence"] == pytest.approx(1.0, abs=0.01)

    def test_decisional_divergence(self, aggregator):
        aggregator.ingest("node-a", {
            "drives": {"drives": [], "action_tendency": "explore"},
            "cognition": {"self_model": {"coherence_phi": 0.6}, "narrative_trace": []},
        })
        aggregator.ingest("node-b", {
            "drives": {"drives": [], "action_tendency": "rest"},
            "cognition": {"self_model": {"coherence_phi": 0.6}, "narrative_trace": []},
        })
        drift = aggregator._compute_personality_drift()
        assert drift["decisional_divergence"] > 0.0

    def test_max_hash_divergence(self, aggregator):
        aggregator.ingest("node-a", {"identity": {"consensus_identity_hash": "abc"}})
        aggregator.ingest("node-b", {"identity": {"consensus_identity_hash": "abc"}})
        aggregator.ingest("node-c", {"identity": {"consensus_identity_hash": "xyz"}})
        agg = aggregator.aggregate()
        assert agg["max_divergence"] == pytest.approx(1 / 3, abs=0.01)


# ------------------------------------------------------------------ #
# NodeClient
# ------------------------------------------------------------------ #

class TestNodeClient:
    def test_cache_miss_and_empty(self):
        client = NodeClient(cache_ttl_seconds=0.0)
        # No server running — should return error marker
        import asyncio
        result = asyncio.run(client.fetch_state("127.0.0.1", 9999))
        assert result is not None
        assert result.get("node_unreachable") is True

    def test_invalidate(self):
        client = NodeClient(cache_ttl_seconds=60.0)
        client._cache["127.0.0.1:9999"] = {"health_score": 1.0}
        client._cache_ts["127.0.0.1:9999"] = 0.0
        client.invalidate("127.0.0.1", 9999)
        assert "127.0.0.1:9999" not in client._cache


# ------------------------------------------------------------------ #
# Dashboard API
# ------------------------------------------------------------------ #

class TestMultiNodeApi:
    def test_api_nodes(self, client):
        r = client.get("/api/nodes")
        assert r.status_code == 200
        data = r.json()
        assert "node_count" in data
        assert "personality_drift" in data

    def test_api_distributed_divergence(self, client):
        r = client.get("/api/distributed/divergence")
        assert r.status_code == 200
        data = r.json()
        assert "personality_drift" in data
        assert "node_count" in data

    def test_api_node_state_not_found(self, client):
        r = client.get("/api/nodes/nonexistent/state")
        assert r.status_code == 200
        assert r.json().get("error") == "node_not_found"
