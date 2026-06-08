"""AdapterRegistry — T131-D: manages ecosystem protocol adapters.

Maps source types to appropriate adapters with automatic fallback.
"""

from typing import Any, Dict, Optional

from speace_core.ecosystem.adapters.base_adapter import AdapterResult, BaseAdapter
from speace_core.ecosystem.adapters.blockchain_adapter import BlockchainAdapter
from speace_core.ecosystem.adapters.file_adapter import FileAdapter
from speace_core.ecosystem.adapters.http_adapter import HTTPAdapter
from speace_core.ecosystem.adapters.llm_adapter import LLMAdapter
from speace_core.ecosystem.adapters.mqtt_adapter import MQTTAdapter


class AdapterRegistry:
    """Registry of protocol adapters for ecosystem observation."""

    def __init__(self) -> None:
        self._adapters: Dict[str, BaseAdapter] = {
            "rest_api": HTTPAdapter(),
            "api_gateway": HTTPAdapter(),
            "file": FileAdapter(),
            "sensor": FileAdapter(),
            "iot_sensor": FileAdapter(),
            "mqtt_broker": MQTTAdapter(),
            "llm_agent": LLMAdapter(),
            "ai_agent": LLMAdapter(),
            "blockchain": BlockchainAdapter(),
            "ledger": BlockchainAdapter(),
        }

    def register_adapter(self, source_type: str, adapter: BaseAdapter) -> None:
        """Register or override an adapter for a source type."""
        self._adapters[source_type] = adapter

    def get_adapter(self, source_type: str) -> Optional[BaseAdapter]:
        return self._adapters.get(source_type)

    async def fetch(
        self,
        source_type: str,
        uri: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AdapterResult:
        """Fetch from a source type using its registered adapter."""
        adapter = self.get_adapter(source_type)
        if adapter is None:
            return AdapterResult(
                status="unsupported",
                payload={"_error": f"no_adapter_for_{source_type}"},
            )
        return await adapter.fetch(uri, metadata or {})

    def list_supported_types(self) -> list[str]:
        """Return all source types with registered adapters."""
        return list(self._adapters.keys())
