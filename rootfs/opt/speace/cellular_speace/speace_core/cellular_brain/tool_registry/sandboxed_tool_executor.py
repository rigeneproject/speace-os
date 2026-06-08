import subprocess
import tempfile
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict

from speace_core.cellular_brain.tool_registry.tool_capability_registry import (
    ToolCapabilityRegistry,
    SandboxConfig,
)


class ToolExecutionResult(BaseModel):
    success: bool
    stdout: str = ""
    stderr: str = ""
    return_code: int | None = None
    blocked: bool = False
    block_reason: str = ""
    duration_ms: float = 0.0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class SandboxedToolExecutor:
    """Executes registered tools in a sandboxed environment."""

    def __init__(self, registry: ToolCapabilityRegistry):
        self.registry = registry

    def execute(
        self,
        tool_id: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> ToolExecutionResult:
        tool = self.registry.get_tool(tool_id)
        if tool is None:
            return ToolExecutionResult(
                success=False, blocked=True, block_reason="tool_not_registered"
            )
        if not tool.enabled or tool.degraded:
            return ToolExecutionResult(
                success=False, blocked=True, block_reason="tool_disabled_or_degraded"
            )

        config = tool.sandbox_config
        return self._run_sandboxed(tool_id, arguments or {}, config)

    def _run_sandboxed(
        self,
        tool_id: str,
        arguments: Dict[str, Any],
        config: SandboxConfig,
    ) -> ToolExecutionResult:
        # Simulated sandbox: run a restricted subprocess with timeout
        try:
            # Build a safe command placeholder
            cmd = ["python", "-c", f"print('tool:{tool_id} executed')"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config.timeout_seconds,
            )
            stdout = result.stdout[: config.max_output_chars]
            stderr = result.stderr[: config.max_output_chars]
            if result.returncode != 0:
                self.registry.mark_degraded(tool_id)
                return ToolExecutionResult(
                    success=False,
                    stdout=stdout,
                    stderr=stderr,
                    return_code=result.returncode,
                    block_reason="execution_failed",
                )
            return ToolExecutionResult(
                success=True,
                stdout=stdout,
                stderr=stderr,
                return_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            self.registry.mark_degraded(tool_id)
            return ToolExecutionResult(
                success=False, blocked=True, block_reason="timeout"
            )
        except Exception as exc:
            self.registry.mark_degraded(tool_id)
            return ToolExecutionResult(
                success=False, blocked=True, block_reason=str(exc)
            )
