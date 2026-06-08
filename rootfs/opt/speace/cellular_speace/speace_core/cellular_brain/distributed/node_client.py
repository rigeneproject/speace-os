"""NodeClient — async HTTP client for querying remote SPEACE nodes (T106).

Caches remote state in memory with configurable TTL.
"""

import asyncio
import logging
from typing import Any, Dict, Optional


class NodeClient:
    """Async client to fetch state from peer SPEACE nodes."""

    def __init__(
        self,
        timeout: float = 5.0,
        retries: int = 2,
        cache_ttl_seconds: float = 10.0,
    ) -> None:
        self.timeout = timeout
        self.retries = retries
        self.cache_ttl = cache_ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ts: Dict[str, float] = {}

    async def fetch_state(self, host: str, port: int) -> Optional[Dict[str, Any]]:
        """Fetch /api/state from a remote node."""
        key = f"{host}:{port}"
        now = asyncio.get_event_loop().time()

        # Check cache
        if key in self._cache and (now - self._cache_ts.get(key, 0)) < self.cache_ttl:
            return self._cache[key]

        url = f"http://{host}:{port}/api/state"
        last_error: Optional[Exception] = None

        for attempt in range(self.retries + 1):
            try:
                # Try httpx first, fallback to aiohttp
                data = await self._fetch_with_httpx(url)
                if data is None:
                    data = await self._fetch_with_aiohttp(url)
                if data is not None:
                    self._cache[key] = data
                    self._cache_ts[key] = now
                    return data
            except Exception as e:
                last_error = e
                if attempt < self.retries:
                    await asyncio.sleep(0.5 * (attempt + 1))

        # Cache miss with error — store stale marker
        self._cache[key] = {"error": str(last_error), "node_unreachable": True}
        self._cache_ts[key] = now
        return self._cache[key]

    async def _fetch_with_httpx(self, url: str) -> Optional[Dict[str, Any]]:
        try:
            import httpx  # type: ignore[import-untyped]
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.get(url)
                if r.status_code == 200:
                    return r.json()
        except Exception:
            logging.getLogger(__name__).warning("Node client operation failed for httpx fetch", exc_info=True)
        return None

    async def _fetch_with_aiohttp(self, url: str) -> Optional[Dict[str, Any]]:
        try:
            import aiohttp  # type: ignore[import-untyped]
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception:
            logging.getLogger(__name__).warning("Node client operation failed for aiohttp fetch", exc_info=True)
        return None

    def invalidate(self, host: str, port: int) -> None:
        key = f"{host}:{port}"
        self._cache.pop(key, None)
        self._cache_ts.pop(key, None)
