"""Tests for HierarchicalConceptAbstractionLayer — T159."""

import tempfile
from pathlib import Path

import pytest

from speace_core.cellular_brain.cognition.concept_graph import ConceptGraph
from speace_core.cellular_brain.cognition.hierarchical_concept_abstraction_layer import (
    HierarchicalConceptAbstractionLayer,
)


class DummyEpisodicLayer:
    """Mimics EpisodicConceptFormationLayer.list_concepts()."""

    def __init__(self, concepts):
        self._concepts = concepts

    def list_concepts(self, limit=100):
        return self._concepts[:limit]


class DummyCausalModel:
    """Mimics CausalWorldModel.recent_observations()."""

    def __init__(self, observations):
        self._obs = observations

    def recent_observations(self, limit=100):
        return self._obs[:limit]


@pytest.fixture
def layer():
    with tempfile.TemporaryDirectory() as tmpdir:
        g = ConceptGraph(data_root=Path(tmpdir) / "graph")
        l = HierarchicalConceptAbstractionLayer(
            concept_graph=g,
            data_root=tmpdir,
            category_similarity_threshold=0.3,
            schema_min_observations=2,
            schema_confidence_threshold=0.5,
        )
        yield l, tmpdir


class TestHierarchicalConceptAbstractionLayer:
    def test_empty_ingest(self, layer):
        l, _ = layer
        episodic = DummyEpisodicLayer([])
        causal = DummyCausalModel([])
        candidates = l.ingest(episodic, causal)
        assert candidates == []
        s = l.summary()
        assert s["pending_candidates"] == 0

    def test_level1_ingestion(self, layer):
        l, _ = layer
        concepts = [
            {
                "concept_label": "concept_beep_notifica",
                "symbolic_signature": ["beep", "notifica", "suono"],
                "confidence": 0.7,
            },
            {
                "concept_label": "concept_messaggio_voce",
                "symbolic_signature": ["messaggio", "voce", "testo"],
                "confidence": 0.6,
            },
        ]
        episodic = DummyEpisodicLayer(concepts)
        causal = DummyCausalModel([])
        l.ingest(episodic, causal)
        nodes = l._graph.list_nodes(level=1, status="approved")
        assert len(nodes) == 2

    def test_category_candidate_formation(self, layer):
        l, _ = layer
        # Two concepts with overlapping signature and shared causal target
        concepts = [
            {
                "concept_label": "concept_beep_notifica",
                "symbolic_signature": ["beep", "notifica", "suono"],
                "confidence": 0.7,
            },
            {
                "concept_label": "concept_messaggio_voce",
                "symbolic_signature": ["messaggio", "voce", "notifica", "suono"],
                "confidence": 0.6,
            },
            {
                "concept_label": "risposta_umana",
                "symbolic_signature": ["risposta", "umana", "interazione"],
                "confidence": 0.5,
            },
        ]
        # Causal observations creating shared target
        observations = [
            {"action_name": "concept_beep_notifica", "effect": "risposta_umana", "confidence": 0.8},
            {"action_name": "concept_messaggio_voce", "effect": "risposta_umana", "confidence": 0.75},
        ]
        episodic = DummyEpisodicLayer(concepts)
        causal = DummyCausalModel(observations)
        candidates = l.ingest(episodic, causal)
        # Should propose at least one category candidate
        cats = [c for c in candidates if c["level"] == 2]
        assert len(cats) >= 1
        assert cats[0]["status"] == "pending"
        assert "cat_" in cats[0]["label"]

    def test_schema_candidate_formation(self, layer):
        l, _ = layer
        # Seed graph with categories manually to bypass category detection dependency
        l._graph.add_node(
            label="cat_suono_notifica",
            level=2,
            symbolic_signature=["suono", "notifica"],
            confidence=0.7,
            status="approved",
        )
        l._graph.add_node(
            label="cat_risposta_interazione",
            level=2,
            symbolic_signature=["risposta", "interazione"],
            confidence=0.7,
            status="approved",
        )
        observations = [
            {"action_name": "cat_suono_notifica", "effect": "cat_risposta_interazione", "confidence": 0.8},
            {"action_name": "cat_suono_notifica", "effect": "cat_risposta_interazione", "confidence": 0.85},
        ]
        episodic = DummyEpisodicLayer([])
        causal = DummyCausalModel(observations)
        candidates = l.ingest(episodic, causal)
        schemas = [c for c in candidates if c["level"] == 3]
        assert len(schemas) >= 1
        assert schemas[0]["status"] == "pending"
        assert "schema_" in schemas[0]["label"]

    def test_approve_abstraction(self, layer):
        l, _ = layer
        concepts = [
            {
                "concept_label": "concept_a",
                "symbolic_signature": ["x", "y"],
                "confidence": 0.7,
            },
            {
                "concept_label": "concept_b",
                "symbolic_signature": ["x", "z"],
                "confidence": 0.6,
            },
            {
                "concept_label": "outcome",
                "symbolic_signature": ["result"],
                "confidence": 0.5,
            },
        ]
        observations = [
            {"action_name": "concept_a", "effect": "outcome", "confidence": 0.8},
            {"action_name": "concept_b", "effect": "outcome", "confidence": 0.75},
        ]
        episodic = DummyEpisodicLayer(concepts)
        causal = DummyCausalModel(observations)
        candidates = l.ingest(episodic, causal)
        cat_candidates = [c for c in candidates if c["level"] == 2]
        assert len(cat_candidates) > 0
        cid = cat_candidates[0]["candidate_id"]
        node = l.approve_abstraction(cid, reviewer="roberto")
        assert node is not None
        assert node["status"] == "approved"
        assert node["reviewer"] == "roberto"

    def test_reject_abstraction(self, layer):
        l, _ = layer
        concepts = [
            {
                "concept_label": "concept_a",
                "symbolic_signature": ["x", "y"],
                "confidence": 0.7,
            },
            {
                "concept_label": "concept_b",
                "symbolic_signature": ["x", "z"],
                "confidence": 0.6,
            },
            {
                "concept_label": "outcome",
                "symbolic_signature": ["result"],
                "confidence": 0.5,
            },
        ]
        observations = [
            {"action_name": "concept_a", "effect": "outcome", "confidence": 0.8},
            {"action_name": "concept_b", "effect": "outcome", "confidence": 0.75},
        ]
        episodic = DummyEpisodicLayer(concepts)
        causal = DummyCausalModel(observations)
        candidates = l.ingest(episodic, causal)
        cat_candidates = [c for c in candidates if c["level"] == 2]
        cid = cat_candidates[0]["candidate_id"]
        assert l.reject_abstraction(cid, reviewer="roberto") is True
        assert l.list_candidates(status="pending") == []

    def test_deprecation_rollback(self, layer):
        l, _ = layer
        concepts = [
            {
                "concept_label": "concept_a",
                "symbolic_signature": ["x", "y"],
                "confidence": 0.7,
            },
            {
                "concept_label": "concept_b",
                "symbolic_signature": ["x", "z"],
                "confidence": 0.6,
            },
            {
                "concept_label": "outcome",
                "symbolic_signature": ["result"],
                "confidence": 0.5,
            },
        ]
        observations = [
            {"action_name": "concept_a", "effect": "outcome", "confidence": 0.8},
            {"action_name": "concept_b", "effect": "outcome", "confidence": 0.75},
        ]
        episodic = DummyEpisodicLayer(concepts)
        causal = DummyCausalModel(observations)
        candidates = l.ingest(episodic, causal)
        cat_candidates = [c for c in candidates if c["level"] == 2]
        cid = cat_candidates[0]["candidate_id"]
        node = l.approve_abstraction(cid, reviewer="roberto")
        nid = node["node_id"]
        deprecated = l.deprecate_abstraction(nid, reviewer="roberto")
        assert deprecated is not None
        assert deprecated["status"] == "deprecated"
        # After deprecation, listing approved nodes should not include it
        active = l._graph.list_nodes(status="approved")
        assert nid not in [n["node_id"] for n in active]

    def test_get_hierarchy(self, layer):
        l, _ = layer
        # Build a small hierarchy manually
        l._graph.add_node(label="root", level=2, status="approved")
        root = l._graph.get_node_by_label("root")
        l._graph.add_node(
            label="child",
            level=1,
            parents=["root"],
            status="approved",
        )
        child = l._graph.get_node_by_label("child")
        root["children"] = [child["node_id"]]
        l._graph.update_node(root["node_id"], root)

        hier = l.get_hierarchy("root", depth=2)
        assert hier["label"] == "root"
        assert "descendants" in hier

    def test_get_schema(self, layer):
        l, _ = layer
        l._graph.add_node(
            label="cause",
            level=1,
            causal_links=[],
            status="approved",
        )
        l._graph.add_node(
            label="effect",
            level=1,
            causal_links=[],
            status="approved",
        )
        cause = l._graph.get_node_by_label("cause")
        effect = l._graph.get_node_by_label("effect")
        cause["causal_links"] = [
            {"target": effect["node_id"], "confidence": 0.8, "obs_count": 5}
        ]
        l._graph.update_node(cause["node_id"], cause)

        schemas = l.get_schema("cause")
        assert len(schemas) == 1
        assert schemas[0]["direction"] == "outgoing"
        assert schemas[0]["effect_label"] == "effect"

    def test_summary(self, layer):
        l, _ = layer
        l._graph.add_node(label="a", level=1, status="approved")
        l._graph.add_node(label="b", level=2, status="approved")
        s = l.summary()
        assert s["active_nodes"] == 2
        assert s["by_level"][1] == 1
        assert s["by_level"][2] == 1
