"""LongitudinalEvolutionTracker — T136: monitors how cognitive skills evolve over time.

Tracks:
- fitness history per skill
- rollback counts
- approvals/rejections
- transfer success between nodes
- identity drift

All events are append-only JSONL for durability and auditability.
"""

import json
import pathlib
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional


class LongitudinalEvolutionTracker:
    """T136: records and queries skill evolution history."""

    def __init__(
        self,
        history_path: str = "data/cognitive_evolution/skill_evolution_history.jsonl",
    ) -> None:
        self.history_path = pathlib.Path(history_path)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: Optional[List[Dict[str, Any]]] = None

    # ------------------------------------------------------------------ #
    # Recording
    # ------------------------------------------------------------------ #

    def record_event(
        self,
        skill_id: str,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append an evolution event to the longitudinal log."""
        entry = {
            "timestamp": time.time(),
            "skill_id": skill_id,
            "event_type": event_type,
            "payload": payload or {},
        }
        with self.history_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._cache = None  # invalidate cache

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def _load_all(self) -> List[Dict[str, Any]]:
        if self._cache is not None:
            return self._cache
        events: List[Dict[str, Any]] = []
        if self.history_path.exists():
            with self.history_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        self._cache = events
        return events

    def _filter(
        self,
        skill_id: Optional[str] = None,
        event_type: Optional[str] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        events = self._load_all()
        result: List[Dict[str, Any]] = []
        for ev in events:
            if skill_id is not None and ev.get("skill_id") != skill_id:
                continue
            if event_type is not None and ev.get("event_type") != event_type:
                continue
            ts = ev.get("timestamp", 0.0)
            if since is not None and ts < since:
                continue
            if until is not None and ts > until:
                continue
            result.append(ev)
        return result

    def get_skill_timeline(
        self,
        skill_id: str,
        hours: float = 24.0,
    ) -> List[Dict[str, Any]]:
        """Return all events for a skill within the last N hours."""
        since = time.time() - hours * 3600.0
        return self._filter(skill_id=skill_id, since=since)

    def get_fitness_trend(
        self,
        skill_id: str,
        hours: float = 24.0,
    ) -> Dict[str, Any]:
        """Analyze fitness trend for a skill."""
        since = time.time() - hours * 3600.0
        events = self._filter(
            skill_id=skill_id,
            event_type="fitness_evaluated",
            since=since,
        )
        if len(events) < 2:
            return {
                "skill_id": skill_id,
                "slope": 0.0,
                "direction": "stable",
                "stability": 0.0,
                "samples": len(events),
            }

        values = []
        timestamps = []
        for ev in events:
            payload = ev.get("payload", {})
            fitness = payload.get("fitness")
            if fitness is not None:
                values.append(float(fitness))
                timestamps.append(ev["timestamp"])

        if len(values) < 2:
            return {
                "skill_id": skill_id,
                "slope": 0.0,
                "direction": "stable",
                "stability": 0.0,
                "samples": len(values),
            }

        # Simple linear regression (least squares)
        n = len(values)
        x_mean = sum(timestamps) / n
        y_mean = sum(values) / n
        num = sum((t - x_mean) * (v - y_mean) for t, v in zip(timestamps, values))
        den = sum((t - x_mean) ** 2 for t in timestamps)
        slope = num / den if den != 0 else 0.0

        # Stability = 1 - normalized std dev
        variance = sum((v - y_mean) ** 2 for v in values) / n
        std_dev = variance ** 0.5
        stability = max(0.0, 1.0 - std_dev)

        if slope > 0.01:
            direction = "improving"
        elif slope < -0.01:
            direction = "decaying"
        else:
            direction = "stable"

        return {
            "skill_id": skill_id,
            "slope": round(slope, 6),
            "direction": direction,
            "stability": round(stability, 4),
            "samples": n,
            "latest_fitness": round(values[-1], 4),
        }

    def get_rollback_prone_skills(
        self,
        min_rollbacks: int = 2,
        hours: float = 48.0,
    ) -> List[str]:
        """Return skill IDs with many rollbacks."""
        since = time.time() - hours * 3600.0
        events = self._filter(event_type="proposal_rolled_back", since=since)
        counts: Dict[str, int] = defaultdict(int)
        for ev in events:
            counts[ev.get("skill_id", "")] += 1
        return [sid for sid, cnt in counts.items() if cnt >= min_rollbacks]

    def get_decaying_skills(
        self,
        fitness_threshold: float = 0.3,
        window_hours: float = 48.0,
    ) -> List[str]:
        """Return skills whose latest fitness is below threshold."""
        since = time.time() - window_hours * 3600.0
        events = self._filter(event_type="fitness_evaluated", since=since)
        latest: Dict[str, float] = {}
        for ev in events:
            sid = ev.get("skill_id", "")
            fitness = ev.get("payload", {}).get("fitness")
            if fitness is not None:
                ts = ev.get("timestamp", 0.0)
                if sid not in latest or ts > latest.get(sid + "_ts", 0):
                    latest[sid] = float(fitness)
                    latest[sid + "_ts"] = ts
        return [sid for sid, fit in latest.items() if fit < fitness_threshold]

    def get_converging_skills(
        self,
        min_fitness: float = 0.7,
        window_hours: float = 48.0,
    ) -> List[str]:
        """Return skills with stable or improving fitness above threshold."""
        since = time.time() - window_hours * 3600.0
        events = self._filter(event_type="fitness_evaluated", since=since)
        by_skill: Dict[str, List[float]] = defaultdict(list)
        for ev in events:
            sid = ev.get("skill_id", "")
            fitness = ev.get("payload", {}).get("fitness")
            if fitness is not None:
                by_skill[sid].append(float(fitness))

        result: List[str] = []
        for sid, values in by_skill.items():
            if len(values) >= 2 and values[-1] >= min_fitness:
                # Check if improving or stable
                slope = values[-1] - values[0]
                if slope >= -0.05:  # not decaying significantly
                    result.append(sid)
        return result

    def generate_longitudinal_report(self) -> Dict[str, Any]:
        """Generate a full longitudinal evolution report."""
        events = self._load_all()
        if not events:
            return {
                "total_events": 0,
                "skills_tracked": [],
                "trends": {},
                "rollback_prone": [],
                "decaying": [],
                "converging": [],
                "timestamp": time.time(),
            }

        skill_ids = sorted(set(ev.get("skill_id", "") for ev in events if ev.get("skill_id")))
        trends = {}
        for sid in skill_ids:
            trends[sid] = self.get_fitness_trend(sid, hours=48.0)

        return {
            "total_events": len(events),
            "skills_tracked": skill_ids,
            "trends": trends,
            "rollback_prone": self.get_rollback_prone_skills(),
            "decaying": self.get_decaying_skills(),
            "converging": self.get_converging_skills(),
            "timestamp": time.time(),
        }

    # ------------------------------------------------------------------ #
    # Utility
    # ------------------------------------------------------------------ #

    def recent_events(
        self,
        hours: float = 24.0,
        event_types: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return recent events, optionally filtered by event type."""
        since = time.time() - hours * 3600.0
        events = self._filter(since=since)
        if event_types:
            events = [ev for ev in events if ev.get("event_type") in event_types]
        events = sorted(events, key=lambda ev: ev.get("timestamp", 0.0), reverse=True)
        return events[:limit]

    def clear_history(self) -> None:
        """Clear all history (mainly for testing)."""
        if self.history_path.exists():
            self.history_path.unlink()
        self._cache = None
