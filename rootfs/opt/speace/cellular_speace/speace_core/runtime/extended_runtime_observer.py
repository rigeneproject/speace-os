"""ExtendedRuntimeObserver — longitudinal observation for T111.

Tracks memory growth, narrative stability, checkpoint churn, regulation
density, and dialogue continuity over multi-hour runs. All read-only;
produces periodic observation reports.
"""

import json
import pathlib
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional


class ExtendedRuntimeObserver:
    """Observes runtime behaviour over extended durations (2–6 h)."""

    def __init__(
        self,
        history_window_seconds: float = 3600.0,
        report_interval_seconds: float = 600.0,
        narrative_engine: Any = None,
    ) -> None:
        self.history_window_seconds = history_window_seconds
        self.report_interval_seconds = report_interval_seconds
        self.narrative_engine = narrative_engine

        # Time-series stores (timestamp, value)
        self._memory_samples: Deque[tuple[float, float]] = deque()
        self._health_samples: Deque[tuple[float, float]] = deque()
        self._tick_latency_samples: Deque[tuple[float, float]] = deque()
        self._narrative_event_counts: Deque[tuple[float, int]] = deque()
        self._regulation_proposal_counts: Deque[tuple[float, int]] = deque()
        self._dialogue_event_counts: Deque[tuple[float, int]] = deque()
        self._checkpoint_timestamps: Deque[float] = deque()

        self._last_report_at: float = time.time()
        self._reports: List[Dict[str, Any]] = []
        self._started_at: float = time.time()

    # ------------------------------------------------------------------ #
    # Sampling hooks (called from the runtime loop)
    # ------------------------------------------------------------------ #

    def sample(
        self,
        memory_rss_mb: float,
        health_score: float,
        tick_latency_ms: float,
        orchestrator: Any,
    ) -> None:
        now = time.time()
        self._memory_samples.append((now, memory_rss_mb))
        self._health_samples.append((now, health_score))
        self._tick_latency_samples.append((now, tick_latency_ms))
        self._trim_all(now)

        # Narrative drift proxy: count events in window
        narrative = getattr(orchestrator, "_narrative_engine", None)
        if narrative is not None:
            events = getattr(narrative, "_events", None)
            if events is not None:
                self._narrative_event_counts.append((now, len(events)))

        # Regulation proposal density
        reg = getattr(orchestrator, "_regulation_proposal_builder", None)
        if reg is not None:
            proposals = getattr(reg, "_proposals", None)
            if proposals is not None:
                self._regulation_proposal_counts.append((now, len(proposals)))

        # Dialogue continuity
        dialogue = getattr(orchestrator, "_dialogue_history", None)
        if dialogue is not None:
            turns = getattr(dialogue, "_turns", None)
            if turns is not None:
                self._dialogue_event_counts.append((now, len(turns)))

        # Periodic report
        if (now - self._last_report_at) >= self.report_interval_seconds:
            self._emit_report(now)

    def record_checkpoint(self) -> None:
        self._checkpoint_timestamps.append(time.time())

    # ------------------------------------------------------------------ #
    # Analysis
    # ------------------------------------------------------------------ #

    def _emit_report(self, now: float) -> None:
        report = self._build_report(now)
        self._reports.append(report)
        self._last_report_at = now
        if self.narrative_engine is not None:
            try:
                self.narrative_engine.record(
                    event_type="extended_runtime_report",
                    description=f"T111 report: health_trend={report['health_trend']:.3f}, memory_growth_mb={report['memory_growth_mb']:.1f}",
                    importance=4,
                    metadata=report,
                )
            except Exception:
                pass

    def _build_report(self, now: float) -> Dict[str, Any]:
        mem_growth = self._linear_slope(self._memory_samples)
        health_trend = self._linear_slope(self._health_samples)
        latency_trend = self._linear_slope(self._tick_latency_samples)

        # Narrative drift: event count delta per minute
        narrative_rate = self._rate_per_minute(self._narrative_event_counts, now)
        regulation_rate = self._rate_per_minute(self._regulation_proposal_counts, now)
        dialogue_rate = self._rate_per_minute(self._dialogue_event_counts, now)

        # Checkpoint churn: checkpoints per hour
        recent_cps = [ts for ts in self._checkpoint_timestamps if (now - ts) <= self.history_window_seconds]
        checkpoint_churn = len(recent_cps) / (self.history_window_seconds / 3600.0)

        return {
            "timestamp": now,
            "uptime_seconds": now - self._started_at,
            "memory_growth_mb": mem_growth,
            "health_trend": health_trend,
            "latency_trend_ms": latency_trend,
            "narrative_events_per_minute": narrative_rate,
            "regulation_proposals_per_minute": regulation_rate,
            "dialogue_turns_per_minute": dialogue_rate,
            "checkpoint_churn_per_hour": checkpoint_churn,
            "is_degraded": health_trend < -0.01 or mem_growth > 10.0,
            "window_seconds": self.history_window_seconds,
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _trim_all(self, now: float) -> None:
        cutoff = now - self.history_window_seconds
        for q in (
            self._memory_samples,
            self._health_samples,
            self._tick_latency_samples,
            self._narrative_event_counts,
            self._regulation_proposal_counts,
            self._dialogue_event_counts,
        ):
            while q and q[0][0] < cutoff:
                q.popleft()
        while self._checkpoint_timestamps and self._checkpoint_timestamps[0] < cutoff:
            self._checkpoint_timestamps.popleft()

    @staticmethod
    def _linear_slope(samples: Deque[tuple[float, float]]) -> float:
        """Least-squares slope over the samples (value vs time)."""
        if len(samples) < 2:
            return 0.0
        n = len(samples)
        sum_x = sum(t for t, _ in samples)
        sum_y = sum(v for _, v in samples)
        sum_xy = sum(t * v for t, v in samples)
        sum_x2 = sum(t * t for t, _ in samples)
        denom = n * sum_x2 - sum_x * sum_x
        if denom == 0:
            return 0.0
        return (n * sum_xy - sum_x * sum_y) / denom

    @staticmethod
    def _rate_per_minute(samples: Deque[tuple[float, int]], now: float) -> float:
        if len(samples) < 2:
            return 0.0
        first_count = samples[0][1]
        last_count = samples[-1][1]
        dt_minutes = (now - samples[0][0]) / 60.0
        if dt_minutes <= 0:
            return 0.0
        return (last_count - first_count) / dt_minutes

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def latest_report(self) -> Optional[Dict[str, Any]]:
        return self._reports[-1] if self._reports else None

    def save_reports(self, path: str = "data/runtime/extended_observation.jsonl") -> None:
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            for report in self._reports:
                f.write(json.dumps(report, ensure_ascii=False) + "\n")
        self._reports.clear()

    def summary(self) -> Dict[str, Any]:
        report = self.latest_report()
        return {
            "latest_report": report,
            "total_reports": len(self._reports),
            "uptime_seconds": time.time() - self._started_at,
        }
