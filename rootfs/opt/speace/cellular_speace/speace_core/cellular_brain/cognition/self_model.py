import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class IdentitySnapshot(BaseModel):
    snapshot_id: str
    timestamp: str
    tick: int = 0
    identity_vector: List[float] = Field(default_factory=list)
    developmental_stage: str = "embryonic"
    coherence_phi: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SelfModel:
    """Persistent identity continuity engine.

    Tracks the organism's self-representation across ticks, maintaining
    an identity_vector (continuity signature), developmental_stage,
    coherence_history, and narrative_trace.
    """

    def __init__(
        self,
        base_path: str = "data/self_model",
        identity_vector: Optional[List[float]] = None,
        developmental_stage: str = "embryonic",
    ):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.snapshots_path = self.base_path / "snapshots.jsonl"
        self.narrative_path = self.base_path / "narrative_trace.jsonl"

        self.identity_vector: List[float] = identity_vector if identity_vector is not None else []
        self.developmental_stage: str = developmental_stage
        self.coherence_history: List[float] = []
        self.narrative_trace: List[Dict[str, Any]] = []
        self._tick: int = 0

        self._load()

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _load(self) -> None:
        if self.snapshots_path.exists():
            snapshots = [
                json.loads(line)
                for line in self.snapshots_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            if snapshots:
                latest = snapshots[-1]
                self.identity_vector = latest.get("identity_vector", self.identity_vector)
                self.developmental_stage = latest.get(
                    "developmental_stage", self.developmental_stage
                )
                self.coherence_history = [
                    s.get("coherence_phi", 0.0) for s in snapshots
                ]
                self._tick = latest.get("tick", 0)

        if self.narrative_path.exists():
            self.narrative_trace = [
                json.loads(line)
                for line in self.narrative_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

    def _save_snapshot(self, snapshot: IdentitySnapshot) -> None:
        with open(self.snapshots_path, "a", encoding="utf-8") as f:
            f.write(snapshot.model_dump_json() + "\n")

    def _save_narrative(self, entry: Dict[str, Any]) -> None:
        with open(self.narrative_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------ #
    # Core API
    # ------------------------------------------------------------------ #

    def update(self, state_snapshot: Dict[str, Any]) -> IdentitySnapshot:
        """Ingest a state snapshot and evolve the self-model."""
        self._tick += 1

        incoming_vector = state_snapshot.get("identity_vector")
        if incoming_vector is not None:
            self.identity_vector = self._merge_vector(self.identity_vector, incoming_vector)

        incoming_stage = state_snapshot.get("developmental_stage")
        if incoming_stage is not None:
            self.developmental_stage = incoming_stage

        coherence = state_snapshot.get("coherence_phi", 0.0)
        self.coherence_history.append(coherence)

        narrative_entry = {
            "tick": self._tick,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": self.developmental_stage,
            "coherence_phi": coherence,
            "event": state_snapshot.get("event", "tick_update"),
            "metadata": state_snapshot.get("metadata", {}),
        }
        self.narrative_trace.append(narrative_entry)
        self._save_narrative(narrative_entry)

        snapshot = IdentitySnapshot(
            snapshot_id=f"sm-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{self._tick:06d}",
            timestamp=narrative_entry["timestamp"],
            tick=self._tick,
            identity_vector=list(self.identity_vector),
            developmental_stage=self.developmental_stage,
            coherence_phi=coherence,
            metadata=dict(state_snapshot.get("metadata", {})),
        )
        self._save_snapshot(snapshot)
        return snapshot

    def get_identity_signature(self) -> List[float]:
        """Return the current continuity signature (identity_vector)."""
        return list(self.identity_vector)

    def get_developmental_stage(self) -> str:
        """Return the current developmental stage."""
        return self.developmental_stage

    def is_coherent(self, threshold: float = 0.5) -> bool:
        """Return True if the latest coherence is above the threshold."""
        if not self.coherence_history:
            return False
        return self.coherence_history[-1] >= threshold

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _merge_vector(current: List[float], incoming: List[float]) -> List[float]:
        """Exponential moving average merge of identity vectors."""
        if not current:
            return list(incoming)
        if not incoming:
            return list(current)
        alpha = 0.3
        max_len = max(len(current), len(incoming))
        padded_current = current + [0.0] * (max_len - len(current))
        padded_incoming = incoming + [0.0] * (max_len - len(incoming))
        merged = [
            alpha * inc + (1 - alpha) * cur
            for cur, inc in zip(padded_current, padded_incoming)
        ]
        return merged

    def summary(self) -> Dict[str, Any]:
        return {
            "tick": self._tick,
            "developmental_stage": self.developmental_stage,
            "identity_vector_length": len(self.identity_vector),
            "coherence_latest": self.coherence_history[-1] if self.coherence_history else None,
            "coherence_mean": sum(self.coherence_history) / len(self.coherence_history)
            if self.coherence_history
            else None,
            "narrative_entries": len(self.narrative_trace),
        }
