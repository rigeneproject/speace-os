"""Tests for ReflectiveInnerNarrativeStream — T161."""

import tempfile
import time

import pytest

from speace_core.cellular_brain.experience.reflective_inner_narrative_stream import (
    ReflectiveInnerNarrativeStream,
)


class DummyNarrativeEngine:
    def __init__(self, events):
        self._events = events

    def recent(self, hours=24, limit=100):
        cutoff = time.time() - (hours * 3600)
        return [e for e in self._events if e.get("timestamp", 0) >= cutoff][-limit:]


class DummyConceptGraph:
    def list_nodes(self, level=None, status=None, limit=100):
        return [
            {"node_id": "n1", "label": "concept_beep", "level": 1, "status": "approved"},
            {"node_id": "n2", "label": "concept_luce", "level": 1, "status": "approved"},
        ][:limit]

    def get_node_by_label(self, label):
        return {"node_id": "n1", "label": label}


class DummyTemporalReasoning:
    def predict_next(self, prefix, top_k=3):
        if prefix:
            return [{"label": "risposta", "confidence": 0.75, "support": 3}]
        return []


class DummySelfModel:
    def get_developmental_stage(self):
        return "infantile"

    def is_coherent(self, threshold=0.5):
        return True


class DummyCuriosityLayer:
    def evaluate_experience(self, event):
        return 0.8


@pytest.fixture
def stream():
    with tempfile.TemporaryDirectory() as tmpdir:
        narrative = DummyNarrativeEngine([
            {"timestamp": time.time(), "event_type": "sensor", "description": "un suono forte"},
        ])
        s = ReflectiveInnerNarrativeStream(
            narrative_engine=narrative,
            concept_graph=DummyConceptGraph(),
            temporal_reasoning=DummyTemporalReasoning(),
            self_model=DummySelfModel(),
            curiosity_layer=DummyCuriosityLayer(),
            data_root=tmpdir,
        )
        yield s, tmpdir


class TestReflectiveInnerNarrativeStream:
    def test_generate_tick(self, stream):
        s, _ = stream
        frag = s.generate_tick()
        assert frag is not None
        assert "fragment_id" in frag
        assert frag["language"] == "it"
        assert "Ho osservato" in frag["content"]
        assert len(frag["sources"]) >= 2

    def test_generate_tick_empty_dependencies(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            s = ReflectiveInnerNarrativeStream(data_root=tmpdir)
            frag = s.generate_tick()
            assert frag is None

    def test_recent_fragments(self, stream):
        s, _ = stream
        s.generate_tick()
        s.generate_tick()
        frags = s.recent_fragments(hours=1, limit=10)
        assert len(frags) == 2

    def test_get_stream_summary(self, stream):
        s, _ = stream
        s.generate_tick()
        summary = s.get_stream_summary(hours=1)
        assert "Ho osservato" in summary
        assert "riflessivo" not in summary  # not the empty message

    def test_summary(self, stream):
        s, _ = stream
        s.generate_tick()
        s.generate_tick()
        s.generate_tick()
        summary = s.summary()
        assert summary["total_fragments"] == 3
        assert summary["latest_timestamp"] is not None

    def test_persistence(self, stream):
        s, tmpdir = stream
        s.generate_tick()
        # New instance should reload
        s2 = ReflectiveInnerNarrativeStream(
            narrative_engine=DummyNarrativeEngine([]),
            data_root=tmpdir,
        )
        assert len(s2._fragments) == 1
