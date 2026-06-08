"""WebSocket server for live organismic state updates.

Provides /ws/state endpoint that pushes JSON state snapshots
via the MetricsBus.
"""

import logging
from typing import Any, Dict

from speace_core.monitoring.metrics_bus import MetricsBus

try:
    from fastapi import APIRouter, WebSocket, WebSocketDisconnect

    _HAS_FASTAPI = True
except Exception:  # pragma: no cover
    _HAS_FASTAPI = False
    APIRouter = Any  # type: ignore[misc,assignment]
    WebSocket = Any  # type: ignore[misc,assignment]
    WebSocketDisconnect = Exception  # type: ignore[misc,assignment]


def create_websocket_router(metrics_bus: MetricsBus) -> APIRouter:
    """Return a FastAPI router with the /ws/state WebSocket endpoint."""
    if not _HAS_FASTAPI:
        raise ImportError("fastapi is required for WebSocket support")

    router = APIRouter()

    @router.websocket("/ws/state")
    async def ws_state(websocket: WebSocket) -> None:
        await websocket.accept()
        queue = metrics_bus.subscribe()
        if queue is None:
            # Subscriber cap reached — close gracefully
            await websocket.close(code=1013, reason="subscriber cap reached")
            return
        try:
            while True:
                state: Dict[str, Any] = await queue.get()
                await websocket.send_json(state)
        except WebSocketDisconnect:
            pass
        except Exception:
            logging.getLogger(__name__).warning("WebSocket task failed", exc_info=True)
        finally:
            metrics_bus.unsubscribe(queue)

    return router
