"""TemporalCausalReasoningLayer — T160.

Builds persistent temporal causal sequences from observations and concept graph
nodes, enabling next-step prediction purely in read-only mode.

Pipeline:
    causal observations (action → effect + timestamp)
    → temporal event sequences
    → chain merging by shared prefix
    → next-step prediction with confidence
    → read-only query API

Constraints:
- read-only, suggestive, never autonomous action
- confidence always probabilistic
- sequences can be deprecated but never hard-deleted
"""

from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional


class TemporalCausalReasoningLayer:
    """Learns temporal causal chains and predicts likely next events."""

    def __init__(
        self,
        causal_world_model: Optional[Any] = None,
        concept_graph: Optional[Any] = None,
        data_root: str = "data/cognition/temporal_reasoning",
        min_support: int = 2,
    ) -> None:
        self._causal = causal_world_model
        self._graph = concept_graph
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._sequences_path = self._data_root / "temporal_sequences.jsonl"
        self._deprecated_path = self._data_root / "deprecated_sequences.jsonl"

        self._min_support = min_support
        self._sequences: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ------------------------------------------------------------------ #
    # Ingestion
    # ------------------------------------------------------------------ #

    def ingest_observations(self, hours: float = 168) -> List[Dict[str, Any]]:
        """Pull recent causal observations and extend/update sequences."""
        observations = []
        if self._causal is not None:
            try:
                observations = self._causal.recent_observations(limit=500)
            except Exception:
                observations = []

        updated: List[Dict[str, Any]] = []
        for obs in observations:
            cause = self._resolve_label(obs.get("action_name", ""))
            effect = self._resolve_label(obs.get("effect", ""))
            ts = obs.get("timestamp", time.time())
            conf = obs.get("confidence", 0.5)
            if not cause or not effect:
                continue

            # Try extending an existing active sequence whose last event == cause
            extended = self._try_extend_sequence(cause, effect, ts, obs, conf)
            if extended:
                updated.append(extended)
            else:
                # Start a new 2-event sequence
                new_seq = self._create_sequence(cause, effect, ts, obs, conf)
                self._sequences[new_seq["sequence_id"]] = new_seq
                self._persist_sequence(new_seq)
                updated.append(new_seq)
        return updated

    # ------------------------------------------------------------------ #
    # Prediction
    # ------------------------------------------------------------------ #

    def predict_next(
        self,
        prefix_labels: List[str],
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """Given a list of event labels, predict the most likely next labels."""
        if not prefix_labels:
            return []

        candidates: Dict[str, List[float]] = defaultdict(list)
        for seq in self._active_sequences():
            events = seq.get("events", [])
            labels = [e["label"] for e in events]
            # Look for exact consecutive match of prefix at the end
            if len(labels) <= len(prefix_labels):
                continue
            # Check if the sequence contains the prefix consecutively
            for i in range(len(labels) - len(prefix_labels)):
                if labels[i : i + len(prefix_labels)] == prefix_labels:
                    next_idx = i + len(prefix_labels)
                    if next_idx < len(labels):
                        candidates[labels[next_idx]].append(seq.get("confidence", 0.5))

        # Aggregate by weighted average confidence
        scored = []
        for label, confidences in candidates.items():
            avg_conf = sum(confidences) / len(confidences)
            scored.append({
                "label": label,
                "confidence": round(avg_conf, 4),
                "support": len(confidences),
            })

        scored.sort(key=lambda x: (-x["confidence"], -x["support"]))
        return scored[:top_k]

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get_sequence(self, sequence_id: str) -> Optional[Dict[str, Any]]:
        seq = self._sequences.get(sequence_id)
        if seq and seq.get("status") != "deprecated":
            return seq
        return None

    def list_sequences(self, limit: int = 100) -> List[Dict[str, Any]]:
        items = self._active_sequences()
        items.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
        return items[:limit]

    def deprecate_sequence(self, sequence_id: str, reviewer: str) -> Optional[Dict[str, Any]]:
        seq = self._sequences.get(sequence_id)
        if not seq:
            return None
        seq["status"] = "deprecated"
        seq["reviewer"] = reviewer
        seq["deprecated_at"] = time.time()
        self._persist_sequence(seq)
        self._persist_deprecated(seq)
        return seq

    def summary(self) -> Dict[str, Any]:
        active = self._active_sequences()
        lengths = [len(s.get("events", [])) for s in active]
        return {
            "total_sequences": len(self._sequences),
            "active_sequences": len(active),
            "deprecated_sequences": sum(
                1 for s in self._sequences.values() if s.get("status") == "deprecated"
            ),
            "average_length": round(sum(lengths) / max(len(lengths), 1), 2),
            "max_length": max(lengths) if lengths else 0,
        }

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _resolve_label(self, raw: str) -> Optional[str]:
        """Map raw action/effect string to a concept graph label if possible."""
        if not raw:
            return None
        if self._graph is not None:
            try:
                node = self._graph.get_node_by_label(raw)
                if node:
                    return node.get("label", raw)
            except Exception:
                pass
        return raw

    def _try_extend_sequence(
        self,
        cause: str,
        effect: str,
        ts: float,
        obs: Dict[str, Any],
        confidence: float,
    ) -> Optional[Dict[str, Any]]:
        for seq in self._active_sequences():
            events = seq.get("events", [])
            if events and events[-1]["label"] == cause:
                # Prevent duplicate immediate effect
                if len(events) >= 2 and events[-2]["label"] == effect and events[-1]["label"] == cause:
                    continue
                events.append({
                    "label": effect,
                    "timestamp": ts,
                    "observation_id": obs.get("timestamp", ""),
                })
                seq["length"] = len(events)
                seq["updated_at"] = time.time()
                # Update confidence with moving average
                old_conf = seq.get("confidence", 0.5)
                old_len = seq.get("length", 1)
                new_conf = (old_conf * (old_len - 1) + confidence) / old_len
                seq["confidence"] = round(new_conf, 4)
                self._persist_sequence(seq)
                return seq
        return None

    def _create_sequence(
        self,
        cause: str,
        effect: str,
        ts: float,
        obs: Dict[str, Any],
        confidence: float,
    ) -> Dict[str, Any]:
        sid = f"seq_{uuid.uuid4().hex[:8]}"
        return {
            "sequence_id": sid,
            "events": [
                {"label": cause, "timestamp": ts, "observation_id": obs.get("timestamp", "")},
                {"label": effect, "timestamp": ts, "observation_id": obs.get("timestamp", "")},
            ],
            "length": 2,
            "confidence": round(confidence, 4),
            "support": 1,
            "status": "active",
            "created_at": time.time(),
            "updated_at": time.time(),
        }

    def _active_sequences(self) -> List[Dict[str, Any]]:
        return [s for s in self._sequences.values() if s.get("status") != "deprecated"]

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _persist_sequence(self, seq: Dict[str, Any]) -> None:
        try:
            with self._sequences_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(seq, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _persist_deprecated(self, seq: Dict[str, Any]) -> None:
        try:
            with self._deprecated_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(seq, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _load(self) -> None:
        if not self._sequences_path.exists():
            return
        lines = self._sequences_path.read_text(encoding="utf-8").strip().split("\n")
        for line in lines:
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
                sid = obj.get("sequence_id")
                if sid:
                    self._sequences[sid] = obj
            except json.JSONDecodeError:
                continue
