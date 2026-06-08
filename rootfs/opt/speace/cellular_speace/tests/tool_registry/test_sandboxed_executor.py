import pathlib
from speace_core.cellular_brain.tool_registry.tool_capability_registry import (
    ToolCapabilityRegistry,
    ToolDescriptor,
)
from speace_core.cellular_brain.tool_registry.sandboxed_tool_executor import (
    SandboxedToolExecutor,
)


def test_execute_registered_tool(tmp_path):
    registry = ToolCapabilityRegistry(storage_path=tmp_path / "tools.jsonl")
    registry.register_tool(ToolDescriptor(tool_id="t1", description="a", risk_level="LOW"))
    executor = SandboxedToolExecutor(registry)
    result = executor.execute("t1")
    assert result.success is True
    assert result.blocked is False


def test_execute_unknown_tool(tmp_path):
    registry = ToolCapabilityRegistry(storage_path=tmp_path / "tools.jsonl")
    executor = SandboxedToolExecutor(registry)
    result = executor.execute("unknown")
    assert result.blocked is True
    assert result.block_reason == "tool_not_registered"


def test_execute_disabled_tool(tmp_path):
    registry = ToolCapabilityRegistry(storage_path=tmp_path / "tools.jsonl")
    registry.register_tool(ToolDescriptor(tool_id="t1", description="a", risk_level="LOW", enabled=False))
    executor = SandboxedToolExecutor(registry)
    result = executor.execute("t1")
    assert result.blocked is True
    assert result.block_reason == "tool_disabled_or_degraded"
