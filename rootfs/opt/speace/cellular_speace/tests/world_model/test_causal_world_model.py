"""Tests for CausalWorldModel — T153."""

import json
import tempfile
from pathlib import Path

import pytest

from speace_core.cellular_brain.world_model.causal_world_model import CausalWorldModel


@pytest.fixture
def model():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield CausalWorldModel(data_root=tmpdir)


class TestCausalWorldModel:
    def test_record_and_predict(self, model):
        model.record_observation("cpu_stress", {"load": 80}, "temperature_rise", 0.7)
        model.record_observation("cpu_stress", {"load": 80}, "fan_speed_up", 0.6)
        model.record_observation("cpu_stress", {"load": 90}, "temperature_rise", 0.8)

        preds = model.predict("cpu_stress", {"load": 80}, top_k=5)
        assert len(preds) == 2
        effects = {p["effect"] for p in preds}
        assert "temperature_rise" in effects
        assert "fan_speed_up" in effects

    def test_predict_confidence(self, model):
        model.record_observation("a", {}, "e", 0.5)
        model.record_observation("a", {}, "e", 0.7)
        assert model.predict_confidence("a", "e") == 0.6

    def test_predict_no_match(self, model):
        model.record_observation("a", {}, "e", 0.5)
        preds = model.predict("b", {})
        assert preds == []

    def test_ingest_report(self, model):
        report = {
            "action": {"name": "test_act", "params": {"x": 1}},
            "hypotheses": [
                {"cause": "c1", "effect": "e1", "confidence": 0.6},
                {"cause": "c2", "effect": "e2", "confidence": 0.4},
            ],
            "pre_state_summary": None,
            "post_state_summary": None,
        }
        entries = model.ingest_report(report)
        assert len(entries) == 2
        assert model.summary()["total_observations"] == 2

    def test_summary(self, model):
        model.record_observation("a", {}, "e1", 0.5)
        model.record_observation("a", {}, "e2", 0.7)
        s = model.summary()
        assert s["total_observations"] == 2
        assert s["unique_actions"] == 1
        assert s["unique_effects"] == 2
        assert s["average_confidence"] == 0.6

    def test_persistence(self, model):
        model.record_observation("a", {}, "e", 0.5)
        # Re-load from same directory
        model2 = CausalWorldModel(data_root=str(model._data_root))
        assert model2.summary()["total_observations"] == 1
