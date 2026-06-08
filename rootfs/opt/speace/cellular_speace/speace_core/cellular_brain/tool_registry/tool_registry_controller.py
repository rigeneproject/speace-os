from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.tool_registry.tool_capability_registry import (
    ToolCapabilityRegistry,
    ToolDescriptor,
)
from speace_core.cellular_brain.tool_registry.sandboxed_tool_executor import (
    SandboxedToolExecutor,
    ToolExecutionResult,
)
from speace_core.cellular_brain.tool_registry.graduated_authorization import (
    GraduatedAuthorizationEngine,
    AuthorizationDecision,
    AuthorizationLevel,
)


class ToolRegistryController:
    """Coordinates tool registration, authorization, and sandboxed execution."""

    def __init__(
        self,
        registry: Optional[ToolCapabilityRegistry] = None,
        executor: Optional[SandboxedToolExecutor] = None,
        authorization: Optional[GraduatedAuthorizationEngine] = None,
    ):
        self.registry = registry or ToolCapabilityRegistry()
        self.executor = executor or SandboxedToolExecutor(self.registry)
        self.authorization = authorization or GraduatedAuthorizationEngine()

    def register_tool(self, descriptor: ToolDescriptor) -> None:
        self.registry.register_tool(descriptor)

    def authorize_execution(self, tool_id: str, caller_id: str) -> AuthorizationDecision:
        tool = self.registry.get_tool(tool_id)
        if tool is None:
            return AuthorizationDecision(
                tool_id=tool_id,
                level=AuthorizationLevel.DENIED,
                reason="tool_not_found",
            )
        return self.authorization.authorize(tool, caller_id)

    def execute_tool(
        self,
        tool_id: str,
        caller_id: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        decision = self.authorize_execution(tool_id, caller_id)
        if decision.level in (AuthorizationLevel.DENIED, AuthorizationLevel.SIMULATION_ONLY):
            return ToolExecutionResult(
                success=False,
                blocked=True,
                block_reason=f"authorization_level:{decision.level.value}",
            )
        return self.executor.execute(tool_id, arguments)

    def audit_execution(self, tool_id: str, result: ToolExecutionResult) -> Dict[str, Any]:
        return {
            "tool_id": tool_id,
            "success": result.success,
            "blocked": result.blocked,
            "block_reason": result.block_reason,
            "return_code": result.return_code,
        }
