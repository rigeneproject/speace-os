from speace_core.cellular_brain.tool_registry.tool_capability_registry import ToolDescriptor
from speace_core.cellular_brain.tool_registry.graduated_authorization import (
    GraduatedAuthorizationEngine,
    AuthorizationLevel,
)


def test_authorize_critical_always_denied():
    engine = GraduatedAuthorizationEngine()
    tool = ToolDescriptor(tool_id="t1", description="a", risk_level="CRITICAL")
    decision = engine.authorize(tool, "caller1")
    assert decision.level == AuthorizationLevel.DENIED


def test_authorize_high_trusted():
    engine = GraduatedAuthorizationEngine()
    engine.set_trust("caller1", 0.9)
    tool = ToolDescriptor(tool_id="t1", description="a", risk_level="HIGH")
    decision = engine.authorize(tool, "caller1")
    assert decision.level == AuthorizationLevel.ALLOWED_WITH_REVIEW


def test_authorize_low_untrusted():
    engine = GraduatedAuthorizationEngine()
    tool = ToolDescriptor(tool_id="t1", description="a", risk_level="LOW")
    decision = engine.authorize(tool, "caller1")
    assert decision.level == AuthorizationLevel.SIMULATION_ONLY


def test_authorize_low_trusted():
    engine = GraduatedAuthorizationEngine()
    engine.set_trust("caller1", 0.5)
    tool = ToolDescriptor(tool_id="t1", description="a", risk_level="LOW")
    decision = engine.authorize(tool, "caller1")
    assert decision.level == AuthorizationLevel.ALLOWED
