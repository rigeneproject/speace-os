"""ExperientialSnapshotStore — periodic organismic snapshots (T108).

Captures full state for experiential memory. Unlike longitudinal memory
(metrics), snapshots include relational context, narrative position,
and dialogue state.
"""

import json
import pathlib
import time
from typing import Any, Dict, List, Optional


class ExperientialSnapshotStore:
    """Stores periodic experiential snapshots."""

    def __init__(
        self,
        snapshot_dir: str = "data/experience/snapshots",
        max_snapshots: int = 100,
    ) -> None:
        self.snapshot_dir = pathlib.Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.max_snapshots = max_snapshots

    def save(
        self,
        state: Dict[str, Any],
        human_id: Optional[str] = None,
        narrative_position: Optional[str] = None,
    ) -> Dict[str, Any]:
        snapshot = {
            "timestamp": time.time(),
            "human_id": human_id,
            "narrative_position": narrative_position,
            "state": state,
        }
        filename = f"snapshot_{int(snapshot['timestamp'] * 1000)}.json"
        path = self.snapshot_dir / filename
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
        self._trim()
        return snapshot

    def _trim(self) -> None:
        files = sorted(self.snapshot_dir.glob("snapshot_*.json"), key=lambda p: p.stat().st_mtime)
        while len(files) > self.max_snapshots:
            try:
                files.pop(0).unlink()
            except OSError:
                break

    def latest(self) -> Optional[Dict[str, Any]]:
        files = sorted(self.snapshot_dir.glob("snapshot_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            return None
        try:
            return json.loads(files[0].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def list_snapshots(self, limit: int = 10) -> List[Dict[str, Any]]:
        files = sorted(self.snapshot_dir.glob("snapshot_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        snapshots: List[Dict[str, Any]] = []
        for f in files[:limit]:
            try:
                snapshots.append(json.loads(f.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return snapshots
