"""BodyRegistry — maintains a registry of physical bodies available to SPEACE."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class BodyRegistry:
    """Registry of bodies (robot, iot, edge, cloud_clone, host) that SPEACE can inhabit.

    Each body entry tracks its capabilities, health, and last activity.
    The registry persists to ``data/embodiment/body_registry.jsonl``.
    """

    def __init__(self, storage_path: Optional[str] = None) -> None:
        self._storage_path = Path(storage_path or "data/embodiment/body_registry.jsonl")
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._bodies: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _load(self) -> None:
        if not self._storage_path.exists():
            return
        with open(self._storage_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    body_id = record.get("body_id")
                    if body_id:
                        self._bodies[body_id] = record
                except json.JSONDecodeError:
                    continue

    def _save(self) -> None:
        with open(self._storage_path, "w", encoding="utf-8") as f:
            for body in self._bodies.values():
                f.write(json.dumps(body, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def register_body(
        self,
        body_id: str,
        body_type: str,
        connection_string: str,
        capabilities: Dict[str, List[str]],
    ) -> None:
        """Register a new body or update an existing one."""
        record: Dict[str, Any] = {
            "body_id": body_id,
            "body_type": body_type,
            "connection_string": connection_string,
            "capabilities": capabilities,
            "health_score": 1.0,
            "last_active": datetime.now(timezone.utc).isoformat(),
        }
        self._bodies[body_id] = record
        self._save()

    def unregister_body(self, body_id: str) -> bool:
        """Remove a body from the registry. Returns True if it existed."""
        if body_id in self._bodies:
            del self._bodies[body_id]
            self._save()
            return True
        return False

    def get_body(self, body_id: str) -> Optional[Dict[str, Any]]:
        """Return the full record for a body, or None."""
        return self._bodies.get(body_id)

    def get_bodies_by_type(self, body_type: str) -> List[Dict[str, Any]]:
        """Return all bodies of a given type."""
        return [b for b in self._bodies.values() if b["body_type"] == body_type]

    def list_all(self) -> List[Dict[str, Any]]:
        """Return every registered body."""
        return list(self._bodies.values())

    def update_health(self, body_id: str, health_score: float) -> bool:
        """Set health_score in [0, 1]. Returns True if body existed."""
        body = self._bodies.get(body_id)
        if body is None:
            return False
        body["health_score"] = max(0.0, min(1.0, float(health_score)))
        body["last_active"] = datetime.now(timezone.utc).isoformat()
        self._save()
        return True

    def get_best_body_for_task(
        self,
        required_sensors: List[str],
        required_actuators: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Return the body with the highest health score that satisfies requirements.

        Returns ``None`` if no body matches.
        """
        candidates: List[Dict[str, Any]] = []
        for body in self._bodies.values():
            caps = body.get("capabilities", {})
            sensors = set(caps.get("sensors", []))
            actuators = set(caps.get("actuators", []))
            if sensors.issuperset(required_sensors) and actuators.issuperset(required_actuators):
                candidates.append(body)
        if not candidates:
            return None
        return max(candidates, key=lambda b: b["health_score"])
