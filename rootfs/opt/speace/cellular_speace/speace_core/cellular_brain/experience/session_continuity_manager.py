"""SessionContinuityManager — restores context after restart (T108).

Saves and reloads: last known state, active human, last topic,
current alert severity, pending proposals, dialogue state.
"""

import json
import pathlib
import time
from typing import Any, Dict, Optional


class SessionContinuityManager:
    """Serializes and restores session context."""

    def __init__(
        self,
        continuity_path: str = "data/experience/session_continuity.json",
    ) -> None:
        self.continuity_path = pathlib.Path(continuity_path)
        self.continuity_path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, context: Dict[str, Any]) -> None:
        payload = {
            "saved_at": time.time(),
            **context,
        }
        try:
            with self.continuity_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def load(self) -> Dict[str, Any]:
        if not self.continuity_path.exists():
            return {}
        try:
            data = json.loads(self.continuity_path.read_text(encoding="utf-8"))
            # Check staleness (older than 30 days = stale)
            age_days = (time.time() - data.get("saved_at", 0)) / 86400
            data["_stale_days"] = age_days
            return data
        except (OSError, json.JSONDecodeError):
            return {}

    def is_stale(self, max_days: float = 30.0) -> bool:
        data = self.load()
        return data.get("_stale_days", float("inf")) > max_days

    def build_resume_narrative(self) -> str:
        data = self.load()
        if not data:
            return "Nessuna sessione precedente trovata. Sono appena nato per te."
        human = data.get("active_human", "unknown")
        last_topic = data.get("last_topic", "unknown")
        health = data.get("last_health_score", "unknown")
        age = data.get("_stale_days", 0)
        if age < 1:
            time_str = "pochi momenti fa"
        elif age < 2:
            time_str = "ieri"
        else:
            time_str = f"{int(age)} giorni fa"
        return (
            f"Bentornato, {human}. L'ultima volta ci siamo parlati {time_str}. "
            f"Stavamo discutendo di {last_topic}. Il mio health score era {health}. "
            f"Sono pronto a riprendere."
        )
