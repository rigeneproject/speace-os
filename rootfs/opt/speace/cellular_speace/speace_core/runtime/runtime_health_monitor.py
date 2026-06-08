"""RuntimeHealthMonitor — observes the runtime itself (T109).

Tracks tick jitter, latency, process memory, and consecutive exceptions.
All read-only; informs SafeDegradationHandler but never acts alone.
"""

import time
from typing import Any, Dict, Optional


class RuntimeHealthMonitor:
    """Monitors the health of the runtime process."""

    def __init__(
        self,
        target_tick_interval: float = 1.0,
        max_tick_jitter_ms: float = 2000.0,
        max_tick_latency_ms: float = 5000.0,
        max_memory_rss_mb: float = 2048.0,
        max_consecutive_exceptions: int = 3,
    ) -> None:
        self.target_tick_interval = target_tick_interval
        self.max_tick_jitter_ms = max_tick_jitter_ms
        self.max_tick_latency_ms = max_tick_latency_ms
        self.max_memory_rss_mb = max_memory_rss_mb
        self.max_consecutive_exceptions = max_consecutive_exceptions

        self._last_tick_time: Optional[float] = None
        self._tick_latency_ms: float = 0.0
        self._tick_jitter_ms: float = 0.0
        self._consecutive_exceptions: int = 0
        self._total_exceptions: int = 0
        self._peak_memory_rss_mb: float = 0.0

    def record_tick(self, latency_ms: float) -> None:
        now = time.time()
        if self._last_tick_time is not None:
            actual_interval_ms = (now - self._last_tick_time) * 1000.0
            self._tick_jitter_ms = abs(actual_interval_ms - (self.target_tick_interval * 1000.0))
        self._last_tick_time = now
        self._tick_latency_ms = latency_ms
        self._consecutive_exceptions = 0

    def record_exception(self) -> None:
        self._consecutive_exceptions += 1
        self._total_exceptions += 1

    def update_memory(self, rss_mb: float) -> None:
        self._peak_memory_rss_mb = max(self._peak_memory_rss_mb, rss_mb)

    def health_score(self) -> float:
        """Return a [0,1] score. 1.0 = perfect health."""
        score = 1.0
        if self._tick_jitter_ms > self.max_tick_jitter_ms:
            score -= 0.25
        if self._tick_latency_ms > self.max_tick_latency_ms:
            score -= 0.30
        if self._peak_memory_rss_mb > self.max_memory_rss_mb:
            score -= 0.25
        if self._consecutive_exceptions >= self.max_consecutive_exceptions:
            score -= 0.40
        return max(0.0, score)

    def is_degraded(self) -> bool:
        return self.health_score() < 0.7

    def is_critical(self) -> bool:
        return self.health_score() < 0.3

    def snapshot(self) -> Dict[str, Any]:
        return {
            "health_score": self.health_score(),
            "tick_jitter_ms": self._tick_jitter_ms,
            "tick_latency_ms": self._tick_latency_ms,
            "consecutive_exceptions": self._consecutive_exceptions,
            "total_exceptions": self._total_exceptions,
            "peak_memory_rss_mb": self._peak_memory_rss_mb,
            "thresholds": {
                "max_tick_jitter_ms": self.max_tick_jitter_ms,
                "max_tick_latency_ms": self.max_tick_latency_ms,
                "max_memory_rss_mb": self.max_memory_rss_mb,
                "max_consecutive_exceptions": self.max_consecutive_exceptions,
            },
        }
