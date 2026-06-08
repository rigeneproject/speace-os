import pathlib
from speace_core.cellular_brain.tool_registry.tool_capability_registry import (
    ToolCapabilityRegistry,
    ToolDescriptor,
)


def test_register_and_get_tool(tmp_path):
    registry = ToolCapabilityRegistry(storage_path=tmp_path / "tools.jsonl")
    tool = ToolDescriptor(tool_id="t1", description="test tool", risk_level="LOW")
    registry.register_tool(tool)
    fetched = registry.get_tool("t1")
    assert fetched is not None
    assert fetched.tool_id == "t1"


def test_list_tools_by_risk(tmp_path):
    registry = ToolCapabilityRegistry(storage_path=tmp_path / "tools.jsonl")
    registry.register_tool(ToolDescriptor(tool_id="t1", description="a", risk_level="LOW"))
    registry.register_tool(ToolDescriptor(tool_id="t2", description="b", risk_level="HIGH"))
    low = registry.list_tools_by_risk("LOW")
    assert len(low) == 1
    assert low[0].tool_id == "t1"


def test_mark_degraded(tmp_path):
    registry = ToolCapabilityRegistry(storage_path=tmp_path / "tools.jsonl")
    registry.register_tool(ToolDescriptor(tool_id="t1", description="a", risk_level="LOW"))
    registry.mark_degraded("t1")
    assert registry.get_tool("t1").degraded is True
