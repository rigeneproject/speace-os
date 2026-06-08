import json
import pathlib
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class SandboxConfig(BaseModel):
    timeout_seconds: float = 5.0
    max_output_chars: int = 10000
    allow_filesystem: bool = False
    allow_network: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ToolDescriptor(BaseModel):
    tool_id: str
    description: str
    capabilities: List[str] = []
    risk_level: str = "LOW"  # LOW, MODERATE, HIGH, CRITICAL
    sandbox_config: SandboxConfig = SandboxConfig()
    enabled: bool = True
    degraded: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ToolCapabilityRegistry:
    """Registry of external tools and their capabilities."""

    def __init__(self, storage_path: Optional[pathlib.Path] = None):
        self._tools: Dict[str, ToolDescriptor] = {}
        self._storage_path = storage_path or pathlib.Path("data/tool_registry/tools.jsonl")
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def register_tool(self, descriptor: ToolDescriptor) -> None:
        self._tools[descriptor.tool_id] = descriptor
        self._save()

    def get_tool(self, tool_id: str) -> Optional[ToolDescriptor]:
        return self._tools.get(tool_id)

    def list_tools(self) -> List[ToolDescriptor]:
        return list(self._tools.values())

    def list_tools_by_risk(self, risk_level: str) -> List[ToolDescriptor]:
        return [t for t in self._tools.values() if t.risk_level == risk_level]

    def mark_degraded(self, tool_id: str) -> None:
        tool = self._tools.get(tool_id)
        if tool is not None:
            tool.degraded = True
            self._save()

    def _save(self) -> None:
        with open(self._storage_path, "w", encoding="utf-8") as f:
            for tool in self._tools.values():
                f.write(tool.model_dump_json() + "\n")

    def _load(self) -> None:
        if not self._storage_path.exists():
            return
        with open(self._storage_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    tool = ToolDescriptor.model_validate_json(line)
                    self._tools[tool.tool_id] = tool
                except Exception:
                    continue
