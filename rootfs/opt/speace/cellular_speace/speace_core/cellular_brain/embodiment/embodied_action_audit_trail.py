"""T-EAAT — Embodied Action Audit Trail.

Records every step of the active-inference embodiment loop so the
causality the system *claims* to learn is actually auditable.

Each audit entry captures:

* ``pre_state``     — flattened sensor reading before the action.
* ``prediction``    — the model-predicted post state.
* ``action``        — the action that was proposed.
* ``post_state``    — flattened sensor reading after the action.
* ``prediction_error`` — ``|post_state - prediction|``.
* ``surprise``      — Bayesian surprise passed to active inference.
* ``belief_after``  — post-update belief distribution.

The trail is persisted as JSONL. A summary helper computes aggregate
statistics (mean prediction error, action distribution, surprise
trend) that can be queried by the host orchestrator and exposed via
the dashboard API.
"""
from __future__ import annotations

import json
import logging
import math
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_logger = logging.getLogger(__name__)


@dataclass
class EmbodiedAuditEntry:
    """One step of the embodiment loop."""

    tick: int
    wall_time: float
    pre_state: Dict[str, float] = field(default_factory=dict)
    prediction: Optional[Dict[str, float]] = None
    action: Optional[str] = None
    post_state: Dict[str, float] = field(default_factory=dict)
    prediction_error: float = 0.0
    surprise: float = 0.0
    belief_after: Dict[str, float] = field(default_factory=dict)
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "wall_time": self.wall_time,
            "pre_state": dict(self.pre_state),
            "prediction": dict(self.prediction) if self.prediction is not None else None,
            "action": self.action,
            "post_state": dict(self.post_state),
            "prediction_error": float(self.prediction_error),
            "surprise": float(self.surprise),
            "belief_after": dict(self.belief_after),
            "note": self.note,
        }


class EmbodiedActionAuditTrail:
    """Append-only audit trail of the active inference embodiment loop."""

    def __init__(
        self,
        log_path: Optional[str] = None,
        max_entries: int = 10000,
        auto_flush: bool = True,
    ):
        self.log_path = log_path or os.path.join(
            "data", "embodiment_audit", "trail.jsonl"
        )
        self.max_entries = int(max_entries)
        self.auto_flush = bool(auto_flush)
        self._entries: List[EmbodiedAuditEntry] = []
        self._fh = None
        if self.auto_flush:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            self._fh = open(self.log_path, "a", encoding="utf-8")

    # ------------------------------------------------------------------ #
    # Recording
    # ------------------------------------------------------------------ #

    def record(
        self,
        tick: int,
        pre_state: Dict[str, float],
        post_state: Dict[str, float],
        action: Optional[str] = None,
        prediction: Optional[Dict[str, float]] = None,
        surprise: float = 0.0,
        belief_after: Optional[Dict[str, float]] = None,
        note: str = "",
    ) -> EmbodiedAuditEntry:
        """Append one audit entry and return it."""
        if prediction is None:
            prediction_error = 0.0
        else:
            prediction_error = _l1_distance(post_state, prediction)
        entry = EmbodiedAuditEntry(
            tick=int(tick),
            wall_time=time.time(),
            pre_state=dict(pre_state),
            prediction=dict(prediction) if prediction is not None else None,
            action=action,
            post_state=dict(post_state),
            prediction_error=float(prediction_error),
            surprise=float(max(0.0, surprise)),
            belief_after=dict(belief_after or {}),
            note=str(note),
        )
        self._entries.append(entry)
        if len(self._entries) > self.max_entries:
            # Keep only the most recent half in memory.
            self._entries = self._entries[-self.max_entries // 2 :]
        if self._fh is not None:
            try:
                self._fh.write(json.dumps(entry.to_dict()) + "\n")
                self._fh.flush()
            except Exception as exc:  # pragma: no cover
                _logger.debug("Audit write failed: %s", exc)
        return entry

    def close(self) -> None:
        if self._fh is not None:
            try:
                self._fh.close()
            finally:
                self._fh = None

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    @property
    def entries(self) -> List[EmbodiedAuditEntry]:
        return list(self._entries)

    def last(self) -> Optional[EmbodiedAuditEntry]:
        return self._entries[-1] if self._entries else None

    def summary(self) -> Dict[str, Any]:
        if not self._entries:
            return {
                "count": 0,
                "mean_prediction_error": 0.0,
                "mean_surprise": 0.0,
                "action_counts": {},
                "recent_prediction_error_trend": 0.0,
            }
        n = len(self._entries)
        mean_err = sum(e.prediction_error for e in self._entries) / n
        mean_surp = sum(e.surprise for e in self._entries) / n
        actions: Dict[str, int] = {}
        for e in self._entries:
            if e.action is not None:
                actions[e.action] = actions.get(e.action, 0) + 1
        recent = self._entries[-min(20, n) :]
        if len(recent) >= 2:
            first_half = recent[: len(recent) // 2]
            second_half = recent[len(recent) // 2 :]
            trend = (
                sum(e.prediction_error for e in second_half)
                / max(1, len(second_half))
            ) - (
                sum(e.prediction_error for e in first_half)
                / max(1, len(first_half))
            )
        else:
            trend = 0.0
        return {
            "count": n,
            "mean_prediction_error": mean_err,
            "mean_surprise": mean_surp,
            "action_counts": actions,
            "recent_prediction_error_trend": float(trend),
        }

    def export(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._entries]


def _l1_distance(a: Dict[str, float], b: Dict[str, float]) -> float:
    keys = set(a.keys()) | set(b.keys())
    return float(sum(abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))) for k in keys))
