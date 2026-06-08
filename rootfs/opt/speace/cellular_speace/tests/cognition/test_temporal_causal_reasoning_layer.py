"""Tests for TemporalCausalReasoningLayer — T160."""

import tempfile

import pytest

from speace_core.cellular_brain.cognition.temporal_causal_reasoning_layer import (
    TemporalCausalReasoningLayer,
)


class DummyCausalModel:
    """Mimics CausalWorldModel.recent_observations()."""

    def __init__(self, observations):
        self._obs = observations

    def recent_observations(self, limit=100):
        return self._obs[:limit]


class DummyConceptGraph:
    """Mimics ConceptGraph.get_node_by_label() for identity mapping."""

    def get_node_by_label(self, label):
        return {"label": label}


@pytest.fixture
def layer():
    with tempfile.TemporaryDirectory() as tmpdir:
        l = TemporalCausalReasoningLayer(
            causal_world_model=None,
            concept_graph=None,
            data_root=tmpdir,
            min_support=1,
        )
        yield l, tmpdir


class TestTemporalCausalReasoningLayer:
    def test_empty_ingest(self, layer):
        l, _ = layer
        causal = DummyCausalModel([])
        l._causal = causal
        updated = l.ingest_observations()
        assert updated == []
        s = l.summary()
        assert s["active_sequences"] == 0

    def test_sequence_creation(self, layer):
        l, _ = layer
        observations = [
            {"action_name": "beep", "effect": "notifica", "timestamp": 1000.0, "confidence": 0.8},
            {"action_name": "notifica", "effect": "risposta", "timestamp": 1010.0, "confidence": 0.7},
        ]
        l._causal = DummyCausalModel(observations)
        updated = l.ingest_observations()
        assert len(updated) == 2
        # First obs creates [beep, notifica]
        # Second obs extends it to [beep, notifica, risposta] because last event matches cause
        seqs = l.list_sequences()
        assert len(seqs) == 1
        assert seqs[0]["length"] == 3

    def test_sequence_extension(self, layer):
        l, _ = layer
        observations = [
            {"action_name": "beep", "effect": "notifica", "timestamp": 1000.0, "confidence": 0.8},
            {"action_name": "notifica", "effect": "risposta", "timestamp": 1010.0, "confidence": 0.7},
            {"action_name": "risposta", "effect": "fine", "timestamp": 1020.0, "confidence": 0.9},
        ]
        l._causal = DummyCausalModel(observations)
        l.ingest_observations()
        # Now create a chain beep → notifica → risposta by feeding another beep → notifica first
        observations2 = [
            {"action_name": "beep", "effect": "notifica", "timestamp": 2000.0, "confidence": 0.85},
            {"action_name": "notifica", "effect": "risposta", "timestamp": 2010.0, "confidence": 0.75},
            {"action_name": "risposta", "effect": "fine", "timestamp": 2020.0, "confidence": 0.9},
        ]
        l._causal = DummyCausalModel(observations2)
        l.ingest_observations()
        seqs = l.list_sequences()
        # We expect one long sequence [beep, notifica, risposta, fine] and some others
        lengths = [s["length"] for s in seqs]
        assert max(lengths) >= 3

    def test_predict_next(self, layer):
        l, _ = layer
        observations = [
            {"action_name": "beep", "effect": "notifica", "timestamp": 1000.0, "confidence": 0.8},
            {"action_name": "notifica", "effect": "risposta", "timestamp": 1010.0, "confidence": 0.7},
            {"action_name": "beep", "effect": "notifica", "timestamp": 2000.0, "confidence": 0.8},
            {"action_name": "notifica", "effect": "risposta", "timestamp": 2010.0, "confidence": 0.7},
            {"action_name": "beep", "effect": "notifica", "timestamp": 3000.0, "confidence": 0.8},
            {"action_name": "notifica", "effect": "risposta", "timestamp": 3010.0, "confidence": 0.7},
        ]
        l._causal = DummyCausalModel(observations)
        l.ingest_observations()
        preds = l.predict_next(["beep", "notifica"], top_k=3)
        assert len(preds) >= 1
        assert preds[0]["label"] == "risposta"

    def test_predict_next_empty(self, layer):
        l, _ = layer
        preds = l.predict_next(["unknown"], top_k=3)
        assert preds == []

    def test_deprecate_sequence(self, layer):
        l, _ = layer
        observations = [
            {"action_name": "a", "effect": "b", "timestamp": 1.0, "confidence": 0.8},
        ]
        l._causal = DummyCausalModel(observations)
        updated = l.ingest_observations()
        sid = updated[0]["sequence_id"]
        dep = l.deprecate_sequence(sid, reviewer="roberto")
        assert dep is not None
        assert dep["status"] == "deprecated"
        assert l.get_sequence(sid) is None

    def test_summary(self, layer):
        l, _ = layer
        observations = [
            {"action_name": "a", "effect": "b", "timestamp": 1.0, "confidence": 0.8},
            {"action_name": "b", "effect": "c", "timestamp": 2.0, "confidence": 0.7},
        ]
        l._causal = DummyCausalModel(observations)
        l.ingest_observations()
        s = l.summary()
        # Chains into single sequence [a, b, c]
        assert s["active_sequences"] == 1
        assert s["average_length"] == 3.0
