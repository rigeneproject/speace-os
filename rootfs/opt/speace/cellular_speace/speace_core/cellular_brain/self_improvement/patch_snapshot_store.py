import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PatchSnapshot(BaseModel):
    snapshot_id: str
    patch_id: str
    timestamp: str
    genome_snapshot: Dict[str, Any] = Field(default_factory=dict)
    orchestrator_flags: Dict[str, Any] = Field(default_factory=dict)
    region_state: Dict[str, Any] = Field(default_factory=dict)
    energy_state: Dict[str, Any] = Field(default_factory=dict)
    benchmark_baseline: Dict[str, Any] = Field(default_factory=dict)


class PatchSnapshotStore:
    """T50 — Persist and load pre-patch snapshots for safe rollback."""

    def __init__(self, data_dir: str = "data/architecture_patches"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def save_snapshot(self, snapshot: PatchSnapshot) -> Path:
        path = self.data_dir / f"snapshot_{snapshot.patch_id}.json"
        path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load_snapshot(self, patch_id: str) -> Optional[PatchSnapshot]:
        path = self.data_dir / f"snapshot_{patch_id}.json"
        if not path.exists():
            return None
        return PatchSnapshot.model_validate_json(path.read_text(encoding="utf-8"))

    def list_snapshots(self) -> List[str]:
        return sorted(
            [p.stem.replace("snapshot_", "") for p in self.data_dir.glob("snapshot_*.json")]
        )

    def delete_snapshot(self, patch_id: str) -> bool:
        path = self.data_dir / f"snapshot_{patch_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def load_latest(self) -> Optional[PatchSnapshot]:
        snapshots = sorted(self.data_dir.glob("snapshot_*.json"), key=lambda p: p.stat().st_mtime)
        if not snapshots:
            return None
        return PatchSnapshot.model_validate_json(snapshots[-1].read_text(encoding="utf-8"))
