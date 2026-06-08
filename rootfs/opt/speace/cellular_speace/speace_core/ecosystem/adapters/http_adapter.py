"""HTTPAdapter — T131-D: read-only HTTP GET adapter."""

import time
from typing import Any, Dict

from speace_core.ecosystem.adapters.base_adapter import AdapterResult, BaseAdapter

try:
    import httpx

    _HAS_HTTPX = True
except Exception:  # pragma: no cover
    _HAS_HTTPX = False
    httpx = None  # type: ignore[assignment]


class HTTPAdapter(BaseAdapter):
    """Read-only HTTP adapter using httpx."""

    PROTOCOL = "http"

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    async def fetch(self, uri: str, metadata: Dict[str, Any] | None = None) -> AdapterResult:
        if not _HAS_HTTPX:
            return AdapterResult(status="unsupported", payload={"_error": "httpx_not_available"})
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(uri)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            return AdapterResult(
                status="error",
                payload={"_error": str(exc)},
                latency_ms=(time.time() - start) * 1000,
            )
        payload = self.sanitize(payload)
        return AdapterResult(
            payload=payload,
            status="ok",
            latency_ms=(time.time() - start) * 1000,
        )
