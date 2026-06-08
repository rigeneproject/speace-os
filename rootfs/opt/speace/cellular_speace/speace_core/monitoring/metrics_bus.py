"""MetricsBus — async pub/sub bus for live organismic state updates.

Publishes state snapshots to all WebSocket subscribers.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from speace_core.monitoring.organism_state_collector import OrganismStateCollector


class MetricsBus:
    """Async metrics bus that polls the collector and broadcasts state."""

    # Cap concurrent WebSocket subscribers to prevent unbounded growth
    # (e.g. clients that never send close frame, zombie connections).
    _MAX_SUBSCRIBERS = 64
    # Track consecutive failed publishes per subscriber — when a queue is
    # repeatedly full, drop it (slow consumer protection).
    _MAX_CONSECUTIVE_FULL = 5

    def __init__(
        self,
        collector: OrganismStateCollector,
        interval_ms: float = 1000.0,
        post_process: Optional[Any] = None,
    ) -> None:
        self.collector = collector
        self.interval_ms = interval_ms
        self.post_process = post_process
        self._subscribers: List[asyncio.Queue] = []
        self._subscribers_full_count: Dict[int, int] = {}
        self._latest_state: Dict[str, Any] = {}
        self._task: Optional[asyncio.Task] = None
        self._stop_event: Optional[asyncio.Event] = None

    # ------------------------------------------------------------------ #
    # Subscriptions
    # ------------------------------------------------------------------ #

    def subscribe(self) -> Optional[asyncio.Queue]:
        if len(self._subscribers) >= self._MAX_SUBSCRIBERS:
            logging.getLogger(__name__).warning(
                "MetricsBus subscriber cap reached (%d) — rejecting new subscriber",
                self._MAX_SUBSCRIBERS,
            )
            return None
        q: asyncio.Queue = asyncio.Queue(maxsize=2)
        self._subscribers.append(q)
        self._subscribers_full_count[id(q)] = 0
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)
        self._subscribers_full_count.pop(id(q), None)

    def latest(self) -> Dict[str, Any]:
        return dict(self._latest_state)

    # ------------------------------------------------------------------ #
    # Broadcasting
    # ------------------------------------------------------------------ #

    def _publish(self, state: Dict[str, Any]) -> None:
        self._latest_state = state
        dead: List[asyncio.Queue] = []
        for q in list(self._subscribers):
            qid = id(q)
            try:
                q.put_nowait(state)
                self._subscribers_full_count[qid] = 0
            except asyncio.QueueFull:
                # Slow consumer: track consecutive failures and drop if persistent
                self._subscribers_full_count[qid] = self._subscribers_full_count.get(qid, 0) + 1
                if self._subscribers_full_count[qid] >= self._MAX_CONSECUTIVE_FULL:
                    dead.append(q)
            except Exception:
                dead.append(q)
        for q in dead:
            self.unsubscribe(q)

    # ------------------------------------------------------------------ #
    # Background loop
    # ------------------------------------------------------------------ #

    async def _loop(self) -> None:
        interval = self.interval_ms / 1000.0
        stop_event = self._stop_event
        assert stop_event is not None
        while not stop_event.is_set():
            try:
                state = self.collector.collect_all()
                state["timestamp"] = time.time()
                if self.post_process is not None:
                    try:
                        state = self.post_process(state)
                    except Exception:
                        pass
                self._publish(state)
            except Exception:
                # Never crash the bus — degrade silently
                pass
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop_event = asyncio.Event()
            self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._task and not self._task.done():
            self._task.cancel()
