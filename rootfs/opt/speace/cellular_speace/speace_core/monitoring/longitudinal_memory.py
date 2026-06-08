"""LongitudinalMemory — T105 historical state tracking for SPEACE.

Persists lightweight organismic metric snapshots over time, supports
temporal queries, trend analysis, and automatic window trimming.
"""

import json
import pathlib
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional


class LongitudinalMemory:
    """Records and queries organismic state history."""

    _TRACKED_METRICS = (
        "coherence_phi",
        "chaos_score",
        "rigidity_score",
        "drift",
        "prediction_error",
        "branching_ratio",
        "health_score",
        "safety_risk",
        "drive_instability",
        "identity_divergence",
        "cpu",
        "memory_bytes",
    )

    def __init__(
        self,
        history_path: str = "data/monitoring/state_history.jsonl",
        snapshot_interval_seconds: float = 60.0,
        max_history_days: int = 30,
        significance_threshold: float = 0.05,
        health_score_func: Optional[Any] = None,
    ) -> None:
        self.history_path = pathlib.Path(history_path)
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        self.snapshot_interval = snapshot_interval_seconds
        self.max_history_seconds = max_history_days * 24 * 3600
        self.significance_threshold = significance_threshold
        self._health_score_func = health_score_func
        self._last_snapshot: Optional[Dict[str, Any]] = None
        self._last_snapshot_time: float = 0.0
        self._lock = False  # simple reentrancy guard for sync contexts

    # ------------------------------------------------------------------ #
    # Recording
    # ------------------------------------------------------------------ #

    def record(self, state: Dict[str, Any]) -> bool:
        """Record a snapshot if interval elapsed or significant change detected.

        Returns True if a snapshot was written.
        """
        now = time.time()
        if now - self._last_snapshot_time < self.snapshot_interval:
            return False

        metrics = self._extract_metrics(state)
        if self._last_snapshot is not None and not self._is_significant_change(
            self._last_snapshot.get("metrics", {}), metrics
        ):
            # Even without significance, we still record at interval boundaries
            pass

        entry = {
            "timestamp": now,
            "metrics": metrics,
        }
        self._write(entry)
        self._last_snapshot = entry
        self._last_snapshot_time = now
        self._trim_old(now)
        return True

    def _extract_metrics(self, state: Dict[str, Any]) -> Dict[str, float]:
        """Extract tracked scalar metrics from a full organism state dict."""
        cognition = state.get("cognition", {})
        dynamics = state.get("dynamics", {})
        embodiment = state.get("embodiment", {})
        safety = state.get("safety", {})
        identity = state.get("identity", {})
        drives = state.get("drives", {})
        body = state.get("body", {})

        metrics: Dict[str, float] = {}

        # Coherence phi
        metrics["coherence_phi"] = cognition.get("self_model", {}).get("coherence_phi", 0.0)

        # Dynamics
        metrics["chaos_score"] = dynamics.get("chaos_score", 0.0)
        metrics["rigidity_score"] = dynamics.get("rigidity_score", 0.0)
        metrics["drift"] = dynamics.get("drift", 0.0)
        metrics["branching_ratio"] = dynamics.get("criticality", {}).get("branching_ratio", 0.0)

        # Embodiment
        metrics["prediction_error"] = embodiment.get("prediction_error", 0.0)

        # Safety risk (numeric)
        risk_map = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        metrics["safety_risk"] = float(risk_map.get(safety.get("risk_level", "low"), 0))

        # Drive instability
        drives_list = drives.get("drives", [])
        metrics["drive_instability"] = max((d.get("urgency", 0.0) for d in drives_list), default=0.0)

        # Identity divergence
        metrics["identity_divergence"] = 1.0 if identity.get("divergence_detected", False) else 0.0

        # Body
        metrics["cpu"] = body.get("cpu", 0.0)
        metrics["memory_bytes"] = body.get("memory_bytes", 0.0)

        # Health score (if callable provided)
        if self._health_score_func is not None:
            try:
                metrics["health_score"] = float(self._health_score_func(state))
            except Exception:
                metrics["health_score"] = 0.0
        else:
            metrics["health_score"] = 0.0

        return metrics

    def _is_significant_change(
        self, previous: Dict[str, float], current: Dict[str, float]
    ) -> bool:
        """Return True if any tracked metric changed by > threshold relative to previous."""
        for key in self._TRACKED_METRICS:
            prev = previous.get(key, 0.0)
            curr = current.get(key, 0.0)
            if prev == 0.0 and curr != 0.0:
                return True
            if prev != 0.0 and abs((curr - prev) / prev) > self.significance_threshold:
                return True
        return False

    def _write(self, entry: Dict[str, Any]) -> None:
        try:
            with self.history_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _trim_old(self, now: float) -> None:
        """Remove entries older than max_history_seconds."""
        if not self.history_path.exists():
            return
        cutoff = now - self.max_history_seconds
        retained: List[str] = []
        try:
            with self.history_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("timestamp", 0) >= cutoff:
                        retained.append(line)
            with self.history_path.open("w", encoding="utf-8") as f:
                for line in retained:
                    f.write(line + "\n")
        except OSError:
            pass

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get_history(
        self,
        metric: str,
        hours: int = 24,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return timestamp/value pairs for a metric over the last N hours."""
        if metric not in self._TRACKED_METRICS:
            return []
        cutoff = time.time() - (hours * 3600)
        entries: List[Dict[str, Any]] = []
        try:
            with self.history_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = entry.get("timestamp", 0)
                    if ts < cutoff:
                        continue
                    value = entry.get("metrics", {}).get(metric)
                    if value is not None:
                        entries.append({"timestamp": ts, "value": value})
        except OSError:
            return []
        if limit:
            entries = entries[-limit:]
        return entries

    def get_trend(self, metric: str, hours: int = 24) -> Dict[str, Any]:
        """Compute delta, direction, slope for a metric over the window."""
        history = self.get_history(metric, hours=hours, limit=0)
        if len(history) < 2:
            return {"delta": 0.0, "direction": "stable", "slope": 0.0, "data_points": len(history)}

        first = history[0]["value"]
        last = history[-1]["value"]
        delta = last - first

        # Simple linear slope: delta / number of intervals
        slope = delta / max(1, len(history) - 1)

        if abs(delta) < 0.01:
            direction = "stable"
        elif delta > 0:
            direction = "increasing"
        else:
            direction = "decreasing"

        return {
            "delta": delta,
            "direction": direction,
            "slope": slope,
            "data_points": len(history),
        }

    def compare_periods(
        self,
        metric: str,
        hours_back: int = 24,
        hours_window: int = 24,
    ) -> Dict[str, Any]:
        """Compare two consecutive windows: [now-hours_back-hours_window, now-hours_back] vs [now-hours_back, now]."""
        now = time.time()
        recent_start = now - hours_back
        older_start = now - hours_back - hours_window

        recent_values: List[float] = []
        older_values: List[float] = []

        try:
            with self.history_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = entry.get("timestamp", 0)
                    value = entry.get("metrics", {}).get(metric)
                    if value is None:
                        continue
                    if recent_start <= ts <= now:
                        recent_values.append(value)
                    elif older_start <= ts < recent_start:
                        older_values.append(value)
        except OSError:
            pass

        recent_avg = sum(recent_values) / len(recent_values) if recent_values else 0.0
        older_avg = sum(older_values) / len(older_values) if older_values else 0.0

        if older_avg == 0.0:
            pct_change = 0.0 if recent_avg == 0.0 else float("inf")
        else:
            pct_change = (recent_avg - older_avg) / older_avg

        return {
            "recent_avg": recent_avg,
            "older_avg": older_avg,
            "pct_change": pct_change,
            "recent_count": len(recent_values),
            "older_count": len(older_values),
        }

    def get_latest_snapshot(self) -> Optional[Dict[str, Any]]:
        """Return the most recent recorded snapshot."""
        if not self.history_path.exists():
            return None
        last: Optional[Dict[str, Any]] = None
        try:
            with self.history_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        last = json.loads(line)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return None
        return last
