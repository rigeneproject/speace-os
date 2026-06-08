"""Tests for T108 — Persistent Experiential Continuity."""

import json
import time
from pathlib import Path

from speace_core.cellular_brain.experience.relational_memory import RelationalMemory
from speace_core.cellular_brain.experience.temporal_narrative_engine import TemporalNarrativeEngine
from speace_core.cellular_brain.experience.session_continuity_manager import SessionContinuityManager
from speace_core.cellular_brain.experience.adaptive_preference_model import AdaptivePreferenceModel
from speace_core.cellular_brain.experience.experiential_snapshot_store import ExperientialSnapshotStore


# --------------------------------------------------------------------------- #
# RelationalMemory
# --------------------------------------------------------------------------- #

def test_relational_memory_touch(tmp_path):
    store = RelationalMemory(store_path=str(tmp_path / "rel.json"))
    record = store.touch("Roberto", name="Roberto", language="it", topic="health", mood="calm")
    assert record["human_id"] == "Roberto"
    assert record["interaction_count"] == 1
    assert record["preferred_language"] == "it"
    assert "health" in record["topics_discussed"]

    # second touch increments count
    store.touch("Roberto", topic="alerts")
    r2 = store.get("Roberto")
    assert r2["interaction_count"] == 2
    assert "alerts" in r2["topics_discussed"]


def test_relational_memory_add_note(tmp_path):
    store = RelationalMemory(store_path=str(tmp_path / "rel.json"))
    store.touch("Roberto")
    store.add_note("Roberto", "prefers Italian")
    r = store.get("Roberto")
    assert len(r["notes"]) == 1
    assert r["notes"][0]["text"] == "prefers Italian"


def test_relational_memory_persistence(tmp_path):
    path = str(tmp_path / "rel.json")
    s1 = RelationalMemory(store_path=path)
    s1.touch("Roberto", name="Roberto")
    s2 = RelationalMemory(store_path=path)
    assert s2.get("Roberto")["name"] == "Roberto"


# --------------------------------------------------------------------------- #
# TemporalNarrativeEngine
# --------------------------------------------------------------------------- #

def test_narrative_record_and_recent(tmp_path):
    engine = TemporalNarrativeEngine(timeline_path=str(tmp_path / "timeline.jsonl"))
    engine.record("test_event", "first event", importance=7)
    time.sleep(0.05)
    engine.record("test_event", "second event", importance=3)
    recent = engine.recent(hours=1, limit=10)
    assert len(recent) == 2
    assert recent[-1]["description"] == "second event"


def test_narrative_by_type(tmp_path):
    engine = TemporalNarrativeEngine(timeline_path=str(tmp_path / "timeline.jsonl"))
    engine.record("alpha", "alpha one")
    engine.record("beta", "beta one")
    alpha = engine.by_type("alpha")
    assert len(alpha) == 1
    assert alpha[0]["description"] == "alpha one"


def test_narrative_summary(tmp_path):
    engine = TemporalNarrativeEngine(timeline_path=str(tmp_path / "timeline.jsonl"))
    engine.record("boot", "system started")
    summary = engine.get_narrative_summary(hours=1)
    assert "system started" in summary


# --------------------------------------------------------------------------- #
# SessionContinuityManager
# --------------------------------------------------------------------------- #

def test_session_save_and_load(tmp_path):
    mgr = SessionContinuityManager(continuity_path=str(tmp_path / "session.json"))
    mgr.save({"active_human": "Roberto", "last_topic": "health", "last_health_score": 0.95})
    data = mgr.load()
    assert data["active_human"] == "Roberto"
    assert "_stale_days" in data


def test_session_staleness(tmp_path):
    mgr = SessionContinuityManager(continuity_path=str(tmp_path / "session.json"))
    assert mgr.is_stale(max_days=1.0) is True  # no file
    mgr.save({"active_human": "Roberto"})
    assert mgr.is_stale(max_days=1.0) is False


def test_session_resume_narrative(tmp_path):
    mgr = SessionContinuityManager(continuity_path=str(tmp_path / "session.json"))
    assert "Nessuna sessione precedente" in mgr.build_resume_narrative()
    mgr.save({"active_human": "Roberto", "last_topic": "health", "last_health_score": 0.95})
    narrative = mgr.build_resume_narrative()
    assert "Bentornato" in narrative
    assert "Roberto" in narrative
    assert "health" in narrative


# --------------------------------------------------------------------------- #
# AdaptivePreferenceModel
# --------------------------------------------------------------------------- #

def test_preference_set_and_get(tmp_path):
    model = AdaptivePreferenceModel(preferences_path=str(tmp_path / "prefs.json"))
    model.set_language("it")
    assert model.get("language") == "it"
    model.set_monitor_host("127.0.0.1:8787")
    assert model.get("monitor_host") == "127.0.0.1:8787"


def test_preference_drive_bias(tmp_path):
    model = AdaptivePreferenceModel(preferences_path=str(tmp_path / "prefs.json"))
    model.reinforce_drive_bias("exploration", 0.3)
    model.reinforce_drive_bias("exploration", 0.4)
    assert model.get("drive_biases")["exploration"] == 0.7
    model.reinforce_drive_bias("exploration", 0.5)
    assert model.get("drive_biases")["exploration"] == 1.0  # clamped


def test_preference_persistence(tmp_path):
    path = str(tmp_path / "prefs.json")
    m1 = AdaptivePreferenceModel(preferences_path=path)
    m1.set_language("it")
    m2 = AdaptivePreferenceModel(preferences_path=path)
    assert m2.get("language") == "it"


# --------------------------------------------------------------------------- #
# ExperientialSnapshotStore
# --------------------------------------------------------------------------- #

def test_snapshot_save_and_latest(tmp_path):
    store = ExperientialSnapshotStore(snapshot_dir=str(tmp_path / "snapshots"))
    snapshot = store.save(state={"health": 0.9}, human_id="Roberto", narrative_position="dialogue_turn")
    assert snapshot["human_id"] == "Roberto"
    latest = store.latest()
    assert latest["state"]["health"] == 0.9


def test_snapshot_list(tmp_path):
    store = ExperientialSnapshotStore(snapshot_dir=str(tmp_path / "snapshots"))
    store.save(state={"n": 1})
    time.sleep(0.05)
    store.save(state={"n": 2})
    snaps = store.list_snapshots(limit=5)
    assert len(snaps) == 2
    assert snaps[0]["state"]["n"] == 2  # latest first


def test_snapshot_trim(tmp_path):
    store = ExperientialSnapshotStore(snapshot_dir=str(tmp_path / "snapshots"), max_snapshots=2)
    store.save(state={"n": 1})
    store.save(state={"n": 2})
    store.save(state={"n": 3})
    snaps = store.list_snapshots(limit=10)
    assert len(snaps) == 2
