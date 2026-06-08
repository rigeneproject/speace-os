"""BaseAdapter — T131-D: abstract base for ecosystem protocol adapters."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class AdapterResult:
    """Result of an adapter fetch operation."""

    payload: Dict[str, Any] = field(default_factory=dict)
    status: str = "ok"  # ok | timeout | error | blocked | unsupported
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_ok(self) -> bool:
        return self.status == "ok"


class BaseAdapter(ABC):
    """Abstract base for ecosystem protocol adapters.

    All adapters are read-only by default.
    """

    PROTOCOL: str = ""
    MAX_PAYLOAD_BYTES: int = 1_048_576  # 1 MB

    @abstractmethod
    async def fetch(self, uri: str, metadata: Dict[str, Any] | None = None) -> AdapterResult:
        """Fetch data from source. Must be read-only."""

    def sanitize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Truncate payload if it exceeds size limit."""
        import json

        text = json.dumps(payload)
        if len(text.encode("utf-8")) > self.MAX_PAYLOAD_BYTES:
            return {
                "_truncated": True,
                "_original_length": len(text),
            }
        return payload
