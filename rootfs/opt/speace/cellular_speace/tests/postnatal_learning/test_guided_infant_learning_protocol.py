"""Tests for GuidedInfantLearningProtocol — T156."""

import tempfile
from pathlib import Path

import pytest

from speace_core.cellular_brain.postnatal_learning.guided_infant_learning_protocol import (
    GuidedInfantLearningProtocol,
)
from speace_core.cellular_brain.embodiment.passive_multisensory_observer import (
    PassiveMultisensoryObserver,
)
from speace_core.cellular_brain.experience.temporal_narrative_engine import (
    TemporalNarrativeEngine,
)
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.language.symbolic_grounding_engine import (
    SymbolicGroundingEngine,
)


@pytest.fixture
def protocol():
    with tempfile.TemporaryDirectory() as tmpdir:
        observer = PassiveMultisensoryObserver()
        observer.enable_camera()
        narrative = TemporalNarrativeEngine(timeline_path=f"{tmpdir}/narrative.jsonl")
        memory = MorphologicalMemory(storage_path=f"{tmpdir}/memory")
        grounding = SymbolicGroundingEngine(store_path=Path(tmpdir) / "grounding.json")
        p = GuidedInfantLearningProtocol(
            observer=observer,
            grounding_engine=grounding,
            narrative_engine=narrative,
            episodic_memory=memory,
            data_root=tmpdir,
        )
        yield p, observer, narrative, memory, grounding


class TestGuidedInfantLearningProtocol:
    def test_present_event(self, protocol):
        p, observer, narrative, memory, grounding = protocol
        record = p.present_event(
            event_label="red_ball",
            description="A red ball rolling on the floor",
            expected_sound="bounce",
        )
        assert record["event_label"] == "red_ball"
        assert record["description"] == "A red ball rolling on the floor"
        assert "session_id" in record
        assert "timestamp" in record

    def test_recall_event(self, protocol):
        p, observer, narrative, memory, grounding = protocol
        p.present_event("blue_cube", "A blue cube on the table")
        recalled = p.recall_event("blue_cube")
        assert recalled is not None
        assert recalled["event_label"] == "blue_cube"

    def test_recall_by_description(self, protocol):
        p, observer, narrative, memory, grounding = protocol
        p.present_event("red_ball", "A red ball rolling")
        p.present_event("green_car", "A green car moving")
        results = p.recall_by_description("red")
        assert len(results) == 1
        assert results[0]["event_label"] == "red_ball"

    def test_list_learned_events(self, protocol):
        p, observer, narrative, memory, grounding = protocol
        p.present_event("event_a", "Description A")
        p.present_event("event_b", "Description B")
        events = p.list_learned_events()
        assert len(events) == 2

    def test_narrative_recorded(self, protocol):
        p, observer, narrative, memory, grounding = protocol
        p.present_event("test_event", "Test description")
        events = narrative.by_type("infant_learning_event")
        assert len(events) == 1
        assert "Test description" in events[0]["description"]

    def test_memory_recorded(self, protocol):
        p, observer, narrative, memory, grounding = protocol
        p.present_event("mem_event", "Memory test")
        assert len(memory.events) == 1
        assert memory.events[0].target_id == "mem_event"

    def test_grounding_created(self, protocol):
        p, observer, narrative, memory, grounding = protocol
        p.present_event("ground_event", "Grounding test")
        assert grounding.get_assembly("ground_event") is not None
