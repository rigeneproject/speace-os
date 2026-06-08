"""FileAdapter — T131-D: read-only local file adapter."""

import json
import time
from pathlib import Path
from typing import Any, Dict

from speace_core.ecosystem.adapters.base_adapter import AdapterResult, BaseAdapter


class FileAdapter(BaseAdapter):
    """Read-only file system adapter."""

    PROTOCOL = "file"

    async def fetch(self, uri: str, metadata: Dict[str, Any] | None = None) -> AdapterResult:
        start = time.time()
        path = Path(uri)
        if not path.exists():
            return AdapterResult(
                status="error",
                payload={"_error": "file_not_found"},
                latency_ms=(time.time() - start) * 1000,
            )
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:
            return AdapterResult(
                status="error",
                payload={"_error": str(exc)},
                latency_ms=(time.time() - start) * 1000,
            )
        if len(text.encode("utf-8")) > self.MAX_PAYLOAD_BYTES:
            return AdapterResult(
                status="error",
                payload={"_error": "file_too_large", "_truncated": True},
                latency_ms=(time.time() - start) * 1000,
            )
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {"_raw": text}
        return AdapterResult(
            payload=payload,
            status="ok",
            latency_ms=(time.time() - start) * 1000,
        )
