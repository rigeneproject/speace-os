"""Ecosystem Adapters — T131-D: Adaptive Connectors.

Read-only adapters for external protocols. All adapters enforce:
- No code execution
- Payload size limits
- Timeout handling
- Trust validation before fetch
"""

from speace_core.ecosystem.adapters.base_adapter import BaseAdapter, AdapterResult
from speace_core.ecosystem.adapters.http_adapter import HTTPAdapter
from speace_core.ecosystem.adapters.file_adapter import FileAdapter

try:
    from speace_core.ecosystem.adapters.mqtt_adapter import MQTTAdapter
except Exception:  # pragma: no cover
    MQTTAdapter = None  # type: ignore[misc, assignment]

try:
    from speace_core.ecosystem.adapters.llm_adapter import LLMAdapter
except Exception:  # pragma: no cover
    LLMAdapter = None  # type: ignore[misc, assignment]

try:
    from speace_core.ecosystem.adapters.blockchain_adapter import BlockchainAdapter
except Exception:  # pragma: no cover
    BlockchainAdapter = None  # type: ignore[misc, assignment]

__all__ = [
    "BaseAdapter",
    "AdapterResult",
    "HTTPAdapter",
    "FileAdapter",
    "MQTTAdapter",
    "LLMAdapter",
    "BlockchainAdapter",
]
