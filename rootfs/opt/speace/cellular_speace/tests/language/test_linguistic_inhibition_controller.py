"""Tests for LinguisticInhibitionController."""

import pytest

from speace_core.cellular_brain.language.linguistic_inhibition_controller import (
    LinguisticInhibitionController,
)


class TestLinguisticInhibitionController:
    def test_default_state_not_inhibited(self):
        ctrl = LinguisticInhibitionController()
        status = ctrl.inhibition_status()
        assert status["inhibited"] is False

    def test_record_production_tracks_token(self):
        ctrl = LinguisticInhibitionController()
        result = ctrl.record_production("hello")
        assert result["inhibited"] is False
        assert result["repeat_count"] == 0
        # After recording, the token count is 1
        assert ctrl._token_count["hello"] == 1

    def test_token_refractory_prevents_immediate_repeat(self):
        ctrl = LinguisticInhibitionController(token_refractory_ticks=10)
        ctrl.record_production("hello")
        result = ctrl.record_production("hello")
        assert result["inhibited"] is True
        assert result["reason"] == "ecolalia"

    def test_different_token_not_inhibited(self):
        ctrl = LinguisticInhibitionController(token_refractory_ticks=10)
        ctrl.record_production("hello")
        result = ctrl.record_production("world")
        assert result["inhibited"] is False

    def test_refractory_expires(self):
        ctrl = LinguisticInhibitionController(token_refractory_ticks=2)
        ctrl.record_production("hello")
        ctrl.record_production("world")
        ctrl.record_production("foo")
        result = ctrl.record_production("hello")
        assert result["inhibited"] is False

    def test_is_token_inhibited(self):
        ctrl = LinguisticInhibitionController(token_refractory_ticks=5)
        ctrl.record_production("hello")
        assert ctrl.is_token_inhibited("hello") is True
        assert ctrl.is_token_inhibited("world") is False

    def test_perseveration_detection(self):
        ctrl = LinguisticInhibitionController(
            token_refractory_ticks=1,
            max_token_repeat=1,
            perseveration_threshold=3,
        )
        ctrl.record_production("x")   # tick=1
        ctrl.record_production("y")   # tick=2
        ctrl.record_production("x")   # tick=3: count=1, 1>1=False → pass
        result = ctrl.record_production("x")   # tick=4: count=2>1, recent=["y","x","x"] sum=2≥2 → perseveration!
        assert result["inhibited"] is True
        assert result["reason"] == "perseveration"

    def test_loop_detection(self):
        ctrl = LinguisticInhibitionController(
            token_refractory_ticks=1,
            loop_detection_window=8,
            max_loop_cycles=2,
        )
        pattern = ["a", "b", "a", "b", "a", "b", "a", "b", "a"]
        for tok in pattern:
            result = ctrl.record_production(tok)
        assert result["inhibited"] is True
        assert result["reason"] == "production_loop"

    def test_is_production_inhibited_global_flag(self):
        ctrl = LinguisticInhibitionController(
            token_refractory_ticks=1,
            loop_detection_window=8,
            max_loop_cycles=2,
        )
        assert ctrl.is_production_inhibited() is False
        for tok in ["a", "b", "a", "b", "a", "b", "a", "b", "a"]:
            ctrl.record_production(tok)
        assert ctrl.is_production_inhibited() is True

    def test_reset_clears_state(self):
        ctrl = LinguisticInhibitionController(token_refractory_ticks=10)
        ctrl.record_production("hello")
        assert ctrl.is_token_inhibited("hello") is True
        ctrl.reset()
        assert ctrl.is_token_inhibited("hello") is False
        assert ctrl.is_production_inhibited() is False

    def test_inhibition_status_returns_metadata(self):
        ctrl = LinguisticInhibitionController()
        status = ctrl.inhibition_status()
        assert "inhibited" in status
        assert "reason" in status
        assert "tick" in status
        assert "production_count" in status
        assert "unique_tokens" in status

    def test_multiple_unique_tokens(self):
        ctrl = LinguisticInhibitionController(token_refractory_ticks=1)
        for tok in ["a", "b", "c", "d", "e"]:
            result = ctrl.record_production(tok)
            assert result["inhibited"] is False
        status = ctrl.inhibition_status()
        assert status["unique_tokens"] == 5
        assert status["production_count"] == 5

    def test_consecutive_different_tokens_no_inhibition(self):
        ctrl = LinguisticInhibitionController(token_refractory_ticks=20)
        for tok in ["a", "b", "c", "d", "e", "f", "g"]:
            result = ctrl.record_production(tok)
            assert result["inhibited"] is False

    def test_inhibition_history_records_events(self):
        ctrl = LinguisticInhibitionController(
            token_refractory_ticks=1,
            max_token_repeat=1,
            perseveration_threshold=3,
        )
        ctrl.record_production("x")   # tick=1
        ctrl.record_production("y")   # tick=2
        ctrl.record_production("x")   # tick=3: count=1, 1>1=False
        ctrl.record_production("x")   # tick=4: count=2>1, recent=["y","x","x"] → perseveration
        assert len(ctrl._inhibition_history) >= 1
        last = ctrl._inhibition_history[-1]
        assert "tick" in last
        assert "reason" in last
        assert "token" in last

    def test_no_false_positive_loop_on_short_history(self):
        ctrl = LinguisticInhibitionController(loop_detection_window=20)
        for tok in ["a", "b", "c"]:
            result = ctrl.record_production(tok)
            assert result["inhibited"] is False

    def test_no_false_positive_on_random_sequence(self):
        ctrl = LinguisticInhibitionController(
            token_refractory_ticks=1,
            loop_detection_window=10,
            max_loop_cycles=2,
        )
        for tok in ["a", "b", "a", "c", "b", "a", "d", "c", "b", "e"]:
            result = ctrl.record_production(tok)
            assert result["inhibited"] is False
