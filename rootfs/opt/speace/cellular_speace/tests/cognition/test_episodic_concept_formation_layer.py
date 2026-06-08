"""Tests for EpisodicConceptFormationLayer — T157."""

import tempfile
import time
from pathlib import Path

import pytest

from speace_core.cellular_brain.cognition.episodic_concept_formation_layer import (
    EpisodicConceptFormationLayer,
)
from speace_core.cellular_brain.experience.temporal_narrative_engine import (
    TemporalNarrativeEngine,
)
from speace_core.cellular_brain.language.symbolic_grounding_engine import (
    SymbolicGroundingEngine,
)


class DummyNarrativeEngine:
    """Simple in-memory narrative engine for testing."""

    def __init__(self):
        self.events = []

    def record(self, event_type, description, importance=5, metadata=None):
        self.events.append({
            "timestamp": time.time(),
            "event_type": event_type,
            "description": description,
            "importance": importance,
            "metadata": metadata or {},
        })

    def recent(self, hours=24, limit=100):
        return self.events[-limit:]


@pytest.fixture
def layer():
    with tempfile.TemporaryDirectory() as tmpdir:
        narrative = DummyNarrativeEngine()
        grounding = SymbolicGroundingEngine(store_path=Path(tmpdir) / "grounding.json")
        l = EpisodicConceptFormationLayer(
            narrative_engine=narrative,
            grounding_engine=grounding,
            data_root=tmpdir,
            similarity_threshold=0.5,
            min_cluster_size=3,
        )
        yield l, narrative, grounding


class TestEpisodicConceptFormationLayer:
    def test_ingest_not_enough_episodes(self, layer):
        l, narrative, grounding = layer
        # Only 2 episodes below min_cluster_size=3
        narrative.record("test", "red ball rolling fast")
        narrative.record("test", "red ball moving slowly")
        candidates = l.ingest_recent_episodes()
        assert len(candidates) == 0

    def test_concept_candidate_formation(self, layer):
        l, narrative, grounding = layer
        for _ in range(3):
            narrative.record("test", "red ball rolling on the floor")
        for _ in range(3):
            narrative.record("test", "blue ball bouncing high")
        candidates = l.ingest_recent_episodes()
        assert len(candidates) > 0
        for c in candidates:
            assert c["status"] == "pending"
            assert c["episode_count"] >= 3
            assert "concept_" in c["concept_label"]

    def test_approve_candidate(self, layer):
        l, narrative, grounding = layer
        for _ in range(3):
            narrative.record("test", "red ball rolling")
        candidates = l.ingest_recent_episodes()
        cid = candidates[0]["candidate_id"]
        concept = l.approve_candidate(cid, reviewer="roberto")
        assert concept is not None
        assert concept["status"] == "consolidated"
        assert concept["reviewer"] == "roberto"
        # Grounding engine should know the label
        assert grounding.get_assembly(concept["concept_label"]) is not None

    def test_reject_candidate(self, layer):
        l, narrative, grounding = layer
        for _ in range(3):
            narrative.record("test", "red ball rolling")
        candidates = l.ingest_recent_episodes()
        cid = candidates[0]["candidate_id"]
        assert l.reject_candidate(cid, reviewer="roberto") is True
        assert l.list_candidates(status="pending") == []

    def test_list_candidates_and_concepts(self, layer):
        l, narrative, grounding = layer
        for _ in range(3):
            narrative.record("test", "red ball rolling")
        candidates = l.ingest_recent_episodes()
        assert len(l.list_candidates(status="pending")) > 0
        l.approve_candidate(candidates[0]["candidate_id"], "roberto")
        assert len(l.list_concepts()) == 1

    def test_summary(self, layer):
        l, narrative, grounding = layer
        for _ in range(3):
            narrative.record("test", "red ball rolling")
        l.ingest_recent_episodes()
        s = l.summary()
        assert s["pending_candidates"] == 1
        assert s["consolidated_concepts"] == 0
