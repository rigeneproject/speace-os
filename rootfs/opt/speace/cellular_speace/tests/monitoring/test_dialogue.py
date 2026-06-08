"""Tests for T107 — Vocal Interface & Dialog Organ."""

import pytest
from fastapi.testclient import TestClient

from speace_core.cellular_brain.language.conversation_memory import ConversationMemory
from speace_core.cellular_brain.language.dialogue_manager import DialogueManager
from speace_core.cellular_brain.language.speech_output_organ import SpeechOutputOrgan
from speace_core.monitoring.dashboard_api import app


@pytest.fixture
def client():
    app.state._testing = True
    with TestClient(app) as c:
        yield c


# ------------------------------------------------------------------ #
# ConversationMemory
# ------------------------------------------------------------------ #

class TestConversationMemory:
    def test_append_and_recent(self, tmp_path):
        p = tmp_path / "dialogue.jsonl"
        mem = ConversationMemory(history_path=str(p))
        t = mem.append("user", "hello")
        assert t["speaker"] == "user"
        assert t["message"] == "hello"
        recent = mem.recent(limit=1)
        assert len(recent) == 1
        assert recent[0]["message"] == "hello"

    def test_multiple_turns_order(self, tmp_path):
        p = tmp_path / "dialogue.jsonl"
        mem = ConversationMemory(history_path=str(p))
        mem.append("user", "a")
        mem.append("speace", "b")
        mem.append("user", "c")
        recent = mem.recent(limit=2)
        assert recent[0]["message"] == "b"
        assert recent[1]["message"] == "c"


# ------------------------------------------------------------------ #
# SpeechOutputOrgan
# ------------------------------------------------------------------ #

class TestSpeechOutputOrgan:
    def test_muted_returns_muted(self, tmp_path):
        log = tmp_path / "speech_log.jsonl"
        organ = SpeechOutputOrgan(muted=True, log_path=str(log))
        result = organ.speak("hello")
        assert result["mode"] == "muted"

    def test_volume_clamping(self):
        organ = SpeechOutputOrgan(volume=2.0)
        assert organ.volume == 1.0
        organ.set_volume(-1.0)
        assert organ.volume == 0.0

    def test_set_mute(self):
        organ = SpeechOutputOrgan(muted=False)
        organ.set_mute(True)
        assert organ.muted is True


# ------------------------------------------------------------------ #
# DialogueManager
# ------------------------------------------------------------------ #

class TestDialogueManager:
    def test_receive_returns_response(self):
        dm = DialogueManager()
        r = dm.receive("hello")
        assert r["speaker"] == "speace"
        assert "message" in r
        assert r["state"] == "active"

    def test_paused_blocks(self):
        dm = DialogueManager()
        dm.set_state("paused")
        r = dm.receive("hello")
        assert r["state"] == "paused"
        assert "Dialogue is paused" in r["message"]

    def test_history_accumulates(self):
        dm = DialogueManager()
        dm.receive("hello")
        hist = dm.history(limit=10)
        assert len(hist) >= 2  # user + speace

    def test_speak_last_no_turn(self, tmp_path):
        p = tmp_path / "dialogue.jsonl"
        mem = ConversationMemory(history_path=str(p))
        dm = DialogueManager(memory=mem)
        r = dm.speak_last_response()
        assert r["mode"] == "none"

    def test_grounded_response_health(self):
        dm = DialogueManager()
        r = dm.receive("What is my health?")
        assert "health" in r["message"].lower()

    def test_grounded_response_identity(self):
        dm = DialogueManager()
        r = dm.receive("Who are you?")
        assert "SPEACE" in r["message"]


# ------------------------------------------------------------------ #
# Dashboard API
# ------------------------------------------------------------------ #

class TestDialogueApi:
    def test_api_message(self, client):
        r = client.post("/api/dialogue/message", json={"message": "hello"})
        assert r.status_code == 200
        data = r.json()
        assert data["speaker"] == "speace"
        assert "message" in data

    def test_api_message_empty(self, client):
        r = client.post("/api/dialogue/message", json={"message": ""})
        assert r.status_code == 200
        assert r.json()["error"] == "empty_message"

    def test_api_history(self, client):
        client.post("/api/dialogue/message", json={"message": "hi"})
        r = client.get("/api/dialogue/history?limit=10")
        assert r.status_code == 200
        data = r.json()
        assert "turns" in data
        assert isinstance(data["turns"], list)
        assert data["state"] in ("idle", "active", "paused")

    def test_api_speak(self, client):
        r = client.post("/api/dialogue/speak")
        assert r.status_code == 200
        # Either none or printed depending on whether a turn exists
        assert "mode" in r.json()
