"""Tests for InfantCuriosityLayer — T158."""

import tempfile

import pytest

from speace_core.cellular_brain.experience.infant_curiosity_layer import (
    InfantCuriosityLayer,
)


class DummyCausalWorldModel:
    def predict(self, action_name, params, top_k=3):
        if action_name == "known_action":
            return [{"effect": "expected_effect", "confidence": 0.9}]
        return []


class DummyNarrativeEngine:
    def by_type(self, event_type, limit=10):
        if event_type == "test":
            return [{"description": "d"} for _ in range(3)]
        return []


@pytest.fixture
def layer():
    with tempfile.TemporaryDirectory() as tmpdir:
        narrative = DummyNarrativeEngine()
        causal = DummyCausalWorldModel()
        l = InfantCuriosityLayer(
            narrative_engine=narrative,
            causal_world_model=causal,
            data_root=tmpdir,
        )
        yield l, narrative, causal


class TestInfantCuriosityLayer:
    def test_evaluate_returns_score_between_0_and_1(self, layer):
        l, narrative, causal = layer
        event = {"event_type": "test", "description": "A test event", "metadata": {}}
        score = l.evaluate_experience(event)
        assert 0.0 <= score <= 1.0

    def test_novelty_decreases_on_repeat(self, layer):
        l, narrative, causal = layer
        event = {"event_type": "test", "description": "same description", "metadata": {}}
        s1 = l.evaluate_experience(event)
        s2 = l.evaluate_experience(event)
        assert s2 < s1  # novelty drops

    def test_multisensory_consistency_multiple_sensors(self, layer):
        l, narrative, causal = layer
        event = {
            "event_type": "test",
            "description": "multi",
            "metadata": {"camera": True, "microphone": True},
        }
        score = l.evaluate_experience(event)
        assert score > 0.5

    def test_suggest_next_observation(self, layer):
        l, narrative, causal = layer
        for _ in range(5):
            l.evaluate_experience({
                "event_type": "multisensory_snapshot",
                "description": "snapshot",
                "metadata": {"camera": True},
            })
        suggestion = l.suggest_next_observation()
        assert suggestion is not None
        assert isinstance(suggestion, str)

    def test_get_top_interesting(self, layer):
        l, narrative, causal = layer
        scores = []
        for i in range(10):
            s = l.evaluate_experience({
                "event_type": "test",
                "description": f"event_{i}",
                "metadata": {},
            })
            scores.append(s)
        top = l.get_top_interesting(n=3)
        assert len(top) == 3
        assert top[0]["total"] >= top[1]["total"]

    def test_average_curiosity(self, layer):
        l, narrative, causal = layer
        for _ in range(5):
            l.evaluate_experience({
                "event_type": "test",
                "description": "x",
                "metadata": {},
            })
        avg = l.get_average_curiosity()
        assert 0.0 <= avg <= 1.0

    def test_causal_clarity_known_action(self, layer):
        l, narrative, causal = layer
        event = {
            "event_type": "known_action",
            "action_name": "known_action",
            "description": "known",
            "metadata": {},
        }
        score = l.evaluate_experience(event)
        assert score > 0.5
