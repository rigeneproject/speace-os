import asyncio
import time
from dataclasses import dataclass
from typing import Callable, Dict, List

import structlog

from speace_core.cellular_brain.base.digital_signal import DigitalSignal

logger = structlog.get_logger(__name__)


@dataclass
class EventDispatchResult:
    success: bool
    handler_name: str
    error: str | None
    duration_ms: float


class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable[[DigitalSignal], None]]] = {}

    def subscribe(self, channel: str, handler: Callable[[DigitalSignal], None]) -> None:
        self._subscribers.setdefault(channel, []).append(handler)

    def unsubscribe(self, channel: str, handler: Callable[[DigitalSignal], None]) -> None:
        if channel in self._subscribers:
            try:
                self._subscribers[channel].remove(handler)
            except ValueError:
                pass

    async def publish(self, channel: str, signal: DigitalSignal) -> List[EventDispatchResult]:
        handlers = self._subscribers.get(channel, [])
        if not handlers:
            return []
        results = await asyncio.gather(
            *(self._safe_dispatch(h, signal) for h in handlers),
            return_exceptions=True,
        )
        return [r if isinstance(r, EventDispatchResult) else r for r in results]

    async def _safe_dispatch(
        self, handler: Callable[[DigitalSignal], None], signal: DigitalSignal
    ) -> EventDispatchResult:
        handler_name = getattr(handler, "__name__", handler.__class__.__name__)
        start = time.perf_counter()
        try:
            result = handler(signal)
            if asyncio.isawaitable(result):
                await result
            duration_ms = (time.perf_counter() - start) * 1000
            return EventDispatchResult(
                success=True, handler_name=handler_name, error=None, duration_ms=duration_ms
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception("event_bus_dispatch_failed", handler=handler_name)
            return EventDispatchResult(
                success=False,
                handler_name=handler_name,
                error=str(exc),
                duration_ms=duration_ms,
            )
