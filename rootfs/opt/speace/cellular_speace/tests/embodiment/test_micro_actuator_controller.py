"""Tests for MicroActuatorController — Phase 3 Limited Physical Embodiment."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from speace_core.cellular_brain.embodiment.micro_actuator_controller import (
    MicroActuatorController,
)


@pytest.fixture
def controller():
    with tempfile.TemporaryDirectory() as tmpdir:
        c = MicroActuatorController(data_root=tmpdir)
        yield c


class TestMicroActuatorController:
    def test_propose_and_approve_beep(self, controller):
        pid = controller.propose_action("speaker_beep", {"frequency": 440, "duration_ms": 100})
        assert pid.startswith("micro_")
        # Status is either proposed (governance allows) or blocked (governance rejects)
        status = controller._proposals[pid]["status"]
        assert status in ("proposed", "blocked")

    def test_propose_cursor_nudge_blocked_without_human_review(self, controller):
        pid = controller.propose_action("cursor_nudge", {"dx": 5, "dy": 0})
        # Even if proposed, execution without human_review should block
        result = controller.execute_action("cursor_nudge", {"dx": 5, "dy": 0})
        assert result["success"] is False
        assert "human_review" in result["error"]

    def test_propose_unknown_action(self, controller):
        # Unknown actions are not in DANGEROUS_ACTIONS, so they go through propose
        # but execute will raise ValueError
        result = controller.execute_action("unknown_action", {})
        assert result["success"] is False

    def test_tts_announce_fallback(self, controller):
        result = controller.execute_action("tts_announce", {"text": "hello"})
        assert result["success"] is True
        assert result["result"]["mode"] == "tts"

    def test_notification_empty_message(self, controller):
        result = controller.execute_action("notification", {"title": "T", "message": ""})
        assert result["success"] is True
        assert result["result"]["error"] == "empty_message"

    def test_notification_rate_limit(self, controller):
        # Fill rate limit window
        for _ in range(5):
            controller.execute_action("notification", {"title": "T", "message": "M"})
        # 6th should be rate limited
        result = controller.execute_action("notification", {"title": "T", "message": "M"})
        assert result["success"] is True
        assert result["result"]["error"] == "rate_limited"

    def test_light_pulse_invalid_led(self, controller):
        result = controller.execute_action("light_pulse", {"led": "scrolllock"})
        assert result["success"] is False
        assert "invalid_led_choice" in result["error"]

    def test_history_and_summary(self, controller):
        controller.execute_action("speaker_beep", {"frequency": 440, "duration_ms": 100})
        controller.execute_action("tts_announce", {"text": "test"})
        hist = controller.get_action_history()
        assert len(hist) == 2
        summary = controller.summary()
        assert summary["total_actions"] == 2
        assert summary["successes"] == 2
        assert "speaker_beep" in summary["by_type"]
        assert "tts_announce" in summary["by_type"]

    def test_beep_safety_limits(self, controller):
        # Frequency clamped
        result = controller.execute_action("speaker_beep", {"frequency": 5000, "duration_ms": 100})
        assert result["success"] is True
        assert result["result"]["frequency"] == 2000
        # Duration clamped
        result = controller.execute_action("speaker_beep", {"frequency": 440, "duration_ms": 5000})
        assert result["success"] is True
        assert result["result"]["duration_ms"] == 1000

    def test_cursor_nudge_exceeds_safety_limit(self, controller):
        result = controller.execute_action(
            "cursor_nudge",
            {"dx": 50, "dy": 0},
            approval_level="human_review",
        )
        assert result["success"] is False
        assert "safety_limit" in result["error"]

    def test_audit_log_written(self, controller):
        controller.execute_action("tts_announce", {"text": "audit"})
        audit_path = Path(controller._data_root) / "micro_actuator_audit.jsonl"
        assert audit_path.exists()
        lines = audit_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) >= 1
        record = json.loads(lines[0])
        assert "timestamp" in record
        assert "action_id" in record
