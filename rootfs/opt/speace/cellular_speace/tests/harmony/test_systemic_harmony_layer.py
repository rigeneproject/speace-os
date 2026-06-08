"""Tests for SystemicHarmonyLayer — T162."""

import tempfile
import time

import pytest

from speace_core.cellular_brain.harmony.systemic_harmony_layer import SystemicHarmonyLayer


class DummyNarrativeEngine:
    def __init__(self, events=None):
        self._events = events or []

    def recent(self, hours=24, limit=100):
        cutoff = time.time() - (hours * 3600)
        return [e for e in self._events if e.get("timestamp", 0) >= cutoff][-limit:]

    def record(self, event_type, description, importance=5, metadata=None):
        self._events.append({
            "timestamp": time.time(),
            "event_type": event_type,
            "description": description,
            "importance": importance,
            "metadata": metadata or {},
        })


class DummyConceptGraph:
    def __init__(self, nodes=None):
        self._nodes = nodes or []

    def list_nodes(self, level=None, status=None, limit=100):
        items = self._nodes[:limit]
        if level is not None:
            items = [n for n in items if n.get("level") == level]
        if status is not None:
            items = [n for n in items if n.get("status") == status]
        return items


class DummyTemporalReasoning:
    def __init__(self, sequences=None):
        self._seqs = sequences or []

    def list_sequences(self, limit=100):
        return self._seqs[:limit]


class DummySelfModel:
    def __init__(self, coherence_history=None):
        self.coherence_history = coherence_history or []

    def get_developmental_stage(self):
        return "infantile"

    def is_coherent(self, threshold=0.5):
        return True


class DummyCuriosityLayer:
    def get_top_interesting(self, n=5):
        return [{"label": "concept_beep"}, {"label": "concept_luce"}]


@pytest.fixture
def layer():
    with tempfile.TemporaryDirectory() as tmpdir:
        narrative = DummyNarrativeEngine([
            {"timestamp": time.time(), "event_type": "sensor", "description": "un suono forte"},
        ])
        graph = DummyConceptGraph([
            {"node_id": "n1", "label": "concept_beep", "level": 1, "status": "approved", "symbolic_signature": ["beep", "suono"]},
            {"node_id": "n2", "label": "concept_luce", "level": 1, "status": "approved", "symbolic_signature": ["luce", "colore"]},
        ])
        temporal = DummyTemporalReasoning([
            {"sequence_id": "s1", "events": [{"label": "a"}, {"label": "b"}, {"label": "c"}], "length": 3},
        ])
        self_model = DummySelfModel(coherence_history=[0.6, 0.7, 0.65, 0.68, 0.72])
        curiosity = DummyCuriosityLayer()

        l = SystemicHarmonyLayer(
            narrative_engine=narrative,
            concept_graph=graph,
            temporal_reasoning=temporal,
            self_model=self_model,
            curiosity_layer=curiosity,
            data_root=tmpdir,
        )
        yield l, tmpdir


class TestSystemicHarmonyLayer:
    def test_tick_produces_report(self, layer):
        l, _ = layer
        report = l.tick()
        assert report is not None
        assert "aggregate_harmony" in report
        assert "metrics" in report
        assert report["fragment_generated"] is True
        assert 0.0 <= report["aggregate_harmony"] <= 1.0

    def test_metrics_present(self, layer):
        l, _ = layer
        report = l.tick()
        m = report["metrics"]
        expected_keys = [
            "narrative_concept_alignment",
            "prediction_narrative_consistency",
            "self_state_stability",
            "curiosity_concept_coverage",
            "temporal_chain_depth",
        ]
        for key in expected_keys:
            assert key in m
            assert 0.0 <= m[key] <= 1.0

    def test_latest_report(self, layer):
        l, _ = layer
        l.tick()
        l.tick()
        latest = l.latest_report()
        assert latest is not None
        assert latest == l._reports[-1]

    def test_to_state_dict(self, layer):
        l, _ = layer
        l.tick()
        state = l.to_state_dict()
        assert state["harmony_enabled"] is True
        assert state["latest_report"] is not None
        assert state["total_reports"] == 1
        assert state["narrative_stream_active"] is True
        assert state["concept_abstraction_active"] is True

    def test_summary(self, layer):
        l, _ = layer
        l.tick()
        l.tick()
        s = l.summary()
        assert s["total_reports"] == 2
        assert s["average_aggregate_harmony"] is not None
        assert s["latest_aggregate_harmony"] is not None

    def test_graceful_degradation_no_dependencies(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            l = SystemicHarmonyLayer(data_root=tmpdir)
            report = l.tick()
            assert report is not None
            # All metrics should fallback to 0.5, aggregate ~0.5
            assert report["aggregate_harmony"] == pytest.approx(0.5, abs=0.1)
            assert report["fragment_generated"] is False
            assert report["new_candidates_count"] == 0

    def test_persistence(self, layer):
        l, tmpdir = layer
        l.tick()
        l.tick()
        # Fresh instance should reload reports
        l2 = SystemicHarmonyLayer(
            narrative_engine=DummyNarrativeEngine([]),
            data_root=tmpdir,
        )
        assert len(l2._reports) == 2
