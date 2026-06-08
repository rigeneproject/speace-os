"""EpigeneticController — manages an in-memory epigenetic mark table.

Lightweight wrapper around a per-cycle state, persisting to
``data/evolution_daemon/epigenetic_state.json``. Read-only from the
runtime's perspective: SPEACE's cellular epigenetic adapter can opt-in
to read the table, but this controller never injects writes into the
orchestrator.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


class EpigeneticController:
    """Maintains a small table of epigenetic marks."""

    def __init__(self, data_root: str | Path = "data") -> None:
        self.data_root = Path(data_root)
        self.path = self.data_root / "evolution_daemon" / "epigenetic_state.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def set(self, key: str, value: Any) -> None:
        state = self._read()
        state[key] = {"value": value, "ts": time.time()}
        self._write(state)

    def get(self, key: str, default: Any = None) -> Any:
        state = self._read()
        return state.get(key, {}).get("value", default)

    def all(self) -> Dict[str, Any]:
        return self._read()

    def apply_cycle(self, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Read a runtime snapshot, derive new marks, return changes."""
        changes: List[Dict[str, Any]] = []
        ns = snapshot.get("neuron_synapse", {}) or {}
        if ns.get("activation_mean", 0.0) > 0.7:
            self.set("high_activation_regime", True)
            changes.append({"key": "high_activation_regime", "value": True})
        diag = (snapshot.get("diagnostics") or {}).get("compartments") or {}
        alert_count = sum(1 for c in diag.values() if c.get("status") == "alert")
        self.set("alert_count", alert_count)
        changes.append({"key": "alert_count", "value": alert_count})
        return changes

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _read(self) -> Dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8")) or {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _write(self, state: Dict[str, Any]) -> None:
        try:
            self.path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except OSError as exc:  # pragma: no cover
            logger.warning("write epigenetic_state: %s", exc)
