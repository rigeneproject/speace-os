"""TemporalNarrativeEngine — persistent storyline of organismic events (T108).

Appends narrative events with temporal anchors. Supports queries by
period, topic, and importance.
"""

import json
import pathlib
import time
from typing import Any, Dict, List, Optional


class TemporalNarrativeEngine:
    """Builds a persistent narrative timeline."""

    def __init__(
        self,
        timeline_path: str = "data/experience/narrative_timeline.jsonl",
    ) -> None:
        self.timeline_path = pathlib.Path(timeline_path)
        self.timeline_path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        event_type: str,
        description: str,
        importance: int = 5,  # 1–10
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        entry = {
            "timestamp": time.time(),
            "event_type": event_type,
            "description": description,
            "importance": max(1, min(10, importance)),
            "metadata": metadata or {},
        }
        try:
            with self.timeline_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass
        return entry

    def recent(self, hours: float = 24, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.timeline_path.exists():
            return []
        cutoff = time.time() - (hours * 3600)
        events: List[Dict[str, Any]] = []
        try:
            with self.timeline_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if ev.get("timestamp", 0) >= cutoff:
                        events.append(ev)
        except OSError:
            return []
        return events[-limit:]

    def by_type(self, event_type: str, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.timeline_path.exists():
            return []
        events: List[Dict[str, Any]] = []
        try:
            with self.timeline_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if ev.get("event_type") == event_type:
                        events.append(ev)
        except OSError:
            return []
        return events[-limit:]

    def get_narrative_summary(self, hours: float = 168) -> str:
        events = self.recent(hours=hours, limit=50)
        if not events:
            return "Nessun evento narrativo recente."
        lines = []
        for ev in events:
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(ev["timestamp"]))
            lines.append(f"[{ts}] {ev['event_type']}: {ev['description']}")
        return "\n".join(lines)
