"""Tests for PassiveMultisensoryObserver — T151."""

import pytest

from speace_core.cellular_brain.embodiment.passive_multisensory_observer import (
    PassiveMultisensoryObserver,
)


class TestPassiveMultisensoryObserver:
    def test_default_all_disabled(self):
        obs = PassiveMultisensoryObserver()
        status = obs.status()
        assert status["camera_enabled"] is False
        assert status["microphone_enabled"] is False
        assert status["screen_enabled"] is False

    def test_opt_in_toggles(self):
        obs = PassiveMultisensoryObserver()
        obs.enable_camera()
        obs.enable_microphone()
        obs.enable_screen()
        status = obs.status()
        assert status["camera_enabled"] is True
        assert status["microphone_enabled"] is True
        assert status["screen_enabled"] is True

        obs.disable_camera()
        obs.disable_microphone()
        obs.disable_screen()
        status = obs.status()
        assert status["camera_enabled"] is False
        assert status["microphone_enabled"] is False
        assert status["screen_enabled"] is False

    def test_camera_disabled_returns_none(self):
        obs = PassiveMultisensoryObserver()
        result = obs.camera_snapshot()
        assert result is None

    def test_microphone_disabled_returns_none(self):
        obs = PassiveMultisensoryObserver()
        result = obs.microphone_snapshot()
        assert result is None

    def test_screen_disabled_returns_none(self):
        obs = PassiveMultisensoryObserver()
        result = obs.screen_snapshot()
        assert result is None

    def test_multisensory_snapshot_all_disabled(self):
        obs = PassiveMultisensoryObserver()
        snap = obs.multisensory_snapshot()
        assert "run_id" in snap
        assert snap["camera"]["enabled"] is False
        assert snap["microphone"]["enabled"] is False
        assert snap["screen"]["enabled"] is False

    def test_multisensory_snapshot_with_camera_enabled(self):
        obs = PassiveMultisensoryObserver()
        obs.enable_camera()
        snap = obs.multisensory_snapshot()
        # Camera may be unavailable (no cv2 or no hardware), but it should not be None
        assert "camera" in snap
        # If unavailable, error should be descriptive
        if not snap["camera"].get("available", False):
            assert "error" in snap["camera"]
