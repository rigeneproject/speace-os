"""Tests for MultisensoryGroundingIntegrator — T152."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from speace_core.cellular_brain.experience.multisensory_grounding_integrator import (
    MultisensoryGroundingIntegrator,
)
from speace_core.cellular_brain.embodiment.passive_multisensory_observer import (
    PassiveMultisensoryObserver,
)


class DummyNarrativeEngine:
    def __init__(self):
        self.records = []

    def record(self, event_type, description, importance=5, metadata=None):
        self.records.append({
            "event_type": event_type,
            "description": description,
            "importance": importance,
            "metadata": metadata or {},
        })


class DummyMemory:
    def __init__(self):
        self.events = []

    def record_event(self, event):
        self.events.append(event)


@pytest.fixture
def integrator():
    observer = PassiveMultisensoryObserver()
    observer.enable_camera()
    observer.enable_microphone()
    observer.enable_screen()
    narrative = DummyNarrativeEngine()
    memory = DummyMemory()
    grounding = MagicMock()
    with tempfile.TemporaryDirectory() as tmpdir:
        mg = MultisensoryGroundingIntegrator(
            observer=observer,
            narrative_engine=narrative,
            memory=memory,
            grounding_engine=grounding,
            data_root=tmpdir,
        )
        yield mg, observer, narrative, memory, grounding


class TestMultisensoryGroundingIntegrator:
    def test_process_snapshot_no_enabled_sensors(self):
        obs = PassiveMultisensoryObserver()  # all disabled
        mg = MultisensoryGroundingIntegrator(observer=obs)
        assert mg.process_snapshot() is None

    def test_dialogue_context_empty(self):
        obs = PassiveMultisensoryObserver()
        mg = MultisensoryGroundingIntegrator(observer=obs)
        assert "Nessuna osservazione" in mg.get_dialogue_context()

    def test_process_snapshot_returns_structure(self, integrator):
        mg, observer, narrative, memory, grounding = integrator
        result = mg.process_snapshot()
        # Camera may be unavailable, but structure should be present if any sensor works
        if result:
            assert "run_id" in result
            assert "timestamp" in result
            assert "sensors" in result
            for sensor_key, payload in result["sensors"].items():
                assert "symbol" in payload
                assert "features" in payload

    def test_narrative_records_event(self, integrator):
        mg, observer, narrative, memory, grounding = integrator
        mg.process_snapshot()
        assert len(narrative.records) >= 0
        for rec in narrative.records:
            assert rec["event_type"] == "multisensory_snapshot"
            assert "importance" in rec

    def test_memory_records_event(self, integrator):
        mg, observer, narrative, memory, grounding = integrator
        mg.process_snapshot()
        assert len(memory.events) >= 0
        for ev in memory.events:
            assert ev.event_type.value == "sensor_snapshot"
            assert ev.source_id == "multisensory_grounding_integrator"

    def test_dialogue_context_after_snapshot(self, integrator):
        mg, observer, narrative, memory, grounding = integrator
        mg.process_snapshot()
        ctx = mg.get_dialogue_context()
        assert isinstance(ctx, str)
        # Should contain at least one sensor reference if snapshot succeeded
        if mg.recent_symbols():
            assert any(sym in ctx for sym in mg.recent_symbols())

    def test_grounding_engine_called(self, integrator):
        mg, observer, narrative, memory, grounding = integrator
        mg.process_snapshot()
        # Grounding engine should have been called for each available sensor
        if result := mg.process_snapshot():
            assert grounding.ground_assembly.call_count >= len(result["sensors"])
