"""RelationalMemory — remembers humans and their interactions (T108).

Tracks per-human: first_seen, last_seen, interaction_count,
preferred_language, mood_history, topics_discussed.
"""

import json
import pathlib
import time
from typing import Any, Dict, List, Optional


class RelationalMemory:
    """Stores relational data about known humans."""

    def __init__(
        self,
        store_path: str = "data/experience/relational_memory.json",
    ) -> None:
        self.store_path = pathlib.Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, Dict[str, Any]] = self._load()

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _load(self) -> Dict[str, Dict[str, Any]]:
        if self.store_path.exists():
            try:
                return json.loads(self.store_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        return {}

    def _save(self) -> None:
        try:
            with self.store_path.open("w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    # ------------------------------------------------------------------ #
    # Human record
    # ------------------------------------------------------------------ #

    def touch(
        self,
        human_id: str,
        name: Optional[str] = None,
        language: Optional[str] = None,
        topic: Optional[str] = None,
        mood: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = time.time()
        record = self._data.setdefault(human_id, {
            "human_id": human_id,
            "name": name or human_id,
            "first_seen": now,
            "last_seen": now,
            "interaction_count": 0,
            "preferred_language": language,
            "mood_history": [],
            "topics_discussed": [],
            "notes": [],
        })
        record["last_seen"] = now
        record["interaction_count"] += 1
        if language and not record.get("preferred_language"):
            record["preferred_language"] = language
        if topic and topic not in record["topics_discussed"]:
            record["topics_discussed"].append(topic)
        if mood:
            record["mood_history"].append({"mood": mood, "timestamp": now})
            # trim mood history
            if len(record["mood_history"]) > 100:
                record["mood_history"] = record["mood_history"][-100:]
        self._save()
        return record

    def get(self, human_id: str) -> Optional[Dict[str, Any]]:
        return self._data.get(human_id)

    def list_humans(self) -> List[Dict[str, Any]]:
        return sorted(self._data.values(), key=lambda h: h.get("last_seen", 0), reverse=True)

    def add_note(self, human_id: str, note: str) -> None:
        record = self._data.get(human_id)
        if record is None:
            return
        record["notes"].append({"text": note, "timestamp": time.time()})
        self._save()
