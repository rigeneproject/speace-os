"""BlockchainAdapter — T131-D: read-only adapter for blockchain RPC endpoints.

Falls back gracefully if httpx is unavailable.
"""

import time
from typing import Any, Dict

from speace_core.ecosystem.adapters.base_adapter import AdapterResult, BaseAdapter

try:
    import httpx

    _HAS_HTTPX = True
except Exception:  # pragma: no cover
    _HAS_HTTPX = False
    httpx = None  # type: ignore[assignment]


class BlockchainAdapter(BaseAdapter):
    """Read-only adapter for blockchain RPC endpoints.

    Only reads block height or chain status — never writes or signs.
    """

    PROTOCOL = "blockchain"

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    async def fetch(self, uri: str, metadata: Dict[str, Any] | None = None) -> AdapterResult:
        if not _HAS_HTTPX:
            return AdapterResult(status="unsupported", payload={"_error": "httpx_not_available"})
        start = time.time()
        # T131-D: read-only status check
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
