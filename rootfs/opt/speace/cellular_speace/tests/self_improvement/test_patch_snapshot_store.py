import json
import pytest
from pathlib import Path

from speace_core.cellular_brain.self_improvement.patch_snapshot_store import (
    PatchSnapshot,
    PatchSnapshotStore,
)


class TestPatchSnapshotStore:
    def test_save_and_load_snapshot(self, tmp_path):
        store = PatchSnapshotStore(data_dir=str(tmp_path))
        snapshot = PatchSnapshot(
            snapshot_id="snap-001",
            patch_id="patch-001",
            timestamp="2024-01-01T00:00:00Z",
            genome_snapshot={"gene_a": 1.0},
            orchestrator_flags={"flag_a": True},
            region_state={"region_1": {"phi": 0.5}},
            energy_state={"mean": 0.7},
            benchmark_baseline={"accuracy": 0.8},
        )
        path = store.save_snapshot(snapshot)
        assert path.exists()

        loaded = store.load_snapshot("patch-001")
        assert loaded is not None
        assert loaded.snapshot_id == "snap-001"
        assert loaded.orchestrator_flags["flag_a"] is True
        assert loaded.benchmark_baseline["accuracy"] == 0.8

    def test_load_snapshot_not_found(self, tmp_path):
        store = PatchSnapshotStore(data_dir=str(tmp_path))
        loaded = store.load_snapshot("patch-nonexistent")
        assert loaded is None

    def test_list_snapshots(self, tmp_path):
        store = PatchSnapshotStore(data_dir=str(tmp_path))
        for i in range(3):
            snapshot = PatchSnapshot(
                snapshot_id=f"snap-{i}",
                patch_id=f"patch-{i}",
                timestamp=f"2024-01-0{i+1}T00:00:00Z",
                )
            store.save_snapshot(snapshot)
        ids = store.list_snapshots()
        assert ids == ["patch-0", "patch-1", "patch-2"]

    def test_delete_snapshot(self, tmp_path):
        store = PatchSnapshotStore(data_dir=str(tmp_path))
        snapshot = PatchSnapshot(
            snapshot_id="snap-del",
            patch_id="patch-del",
            timestamp="2024-01-01T00:00:00Z",
        )
        store.save_snapshot(snapshot)
        assert store.delete_snapshot("patch-del") is True
        assert store.load_snapshot("patch-del") is None
        assert store.delete_snapshot("patch-del") is False

    def test_load_latest(self, tmp_path):
        store = PatchSnapshotStore(data_dir=str(tmp_path))
        for i in range(3):
            snapshot = PatchSnapshot(
                snapshot_id=f"snap-{i}",
                patch_id=f"patch-{i}",
                timestamp=f"2024-01-0{i+1}T00:00:00Z",
                )
            store.save_snapshot(snapshot)
        latest = store.load_latest()
        assert latest is not None
        assert latest.patch_id == "patch-2"

    def test_load_latest_empty(self, tmp_path):
        store = PatchSnapshotStore(data_dir=str(tmp_path))
        latest = store.load_latest()
        assert latest is None

    def test_snapshot_json_roundtrip(self, tmp_path):
        store = PatchSnapshotStore(data_dir=str(tmp_path))
        snapshot = PatchSnapshot(
            snapshot_id="snap-json",
            patch_id="patch-json",
            timestamp="2024-01-01T00:00:00Z",
            genome_snapshot={"a": 1},
            orchestrator_flags={"b": True},
            region_state={"c": 0.5},
            energy_state={"d": 0.3},
            benchmark_baseline={"e": 0.9},
        )
        store.save_snapshot(snapshot)
        path = tmp_path / "snapshot_patch-json.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw["snapshot_id"] == "snap-json"
        assert raw["patch_id"] == "patch-json"

    def test_default_data_dir(self):
        store = PatchSnapshotStore()
        assert store.data_dir.name == "architecture_patches"
