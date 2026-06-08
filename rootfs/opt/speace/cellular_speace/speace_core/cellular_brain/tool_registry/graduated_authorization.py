from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict

from speace_core.cellular_brain.tool_registry.tool_capability_registry import ToolDescriptor


class AuthorizationLevel(str, Enum):
    DENIED = "DENIED"
    SIMULATION_ONLY = "SIMULATION_ONLY"
    OBSERVE_ONLY = "OBSERVE_ONLY"
    ALLOWED_WITH_REVIEW = "ALLOWED_WITH_REVIEW"
    ALLOWED = "ALLOWED"


class AuthorizationDecision(BaseModel):
    tool_id: str
    level: AuthorizationLevel
    reason: str

    model_config = ConfigDict(arbitrary_types_allowed=True)


class GraduatedAuthorizationEngine:
    """Assigns graduated authorization levels based on tool risk and caller trust."""

    def __init__(self):
        self._trust_levels: dict[str, float] = {}

    def set_trust(self, caller_id: str, trust: float) -> None:
        self._trust_levels[caller_id] = trust

    def authorize(
        self,
        tool: ToolDescriptor,
        caller_id: str,
    ) -> AuthorizationDecision:
        trust = self._trust_levels.get(caller_id, 0.0)
        risk = tool.risk_level

        if risk == "CRITICAL":
            return AuthorizationDecision(
                tool_id=tool.tool_id,
                level=AuthorizationLevel.DENIED,
                reason="critical_risk_always_denied",
            )

        if risk == "HIGH":
            if trust >= 0.8:
                return AuthorizationDecision(
                    tool_id=tool.tool_id,
                    level=AuthorizationLevel.ALLOWED_WITH_REVIEW,
                    reason="high_risk_trusted_caller",
                )
            return AuthorizationDecision(
                tool_id=tool.tool_id,
                level=AuthorizationLevel.SIMULATION_ONLY,
                reason="high_risk_low_trust",
            )

        if risk == "MODERATE":
            if trust >= 0.5:
                return AuthorizationDecision(
                    tool_id=tool.tool_id,
                    level=AuthorizationLevel.OBSERVE_ONLY,
                    reason="moderate_risk_moderate_trust",
                )
            return AuthorizationDecision(
                tool_id=tool.tool_id,
                level=AuthorizationLevel.SIMULATION_ONLY,
                reason="moderate_risk_low_trust",
            )

        # LOW risk
        if trust >= 0.3:
            return AuthorizationDecision(
                tool_id=tool.tool_id,
                level=AuthorizationLevel.ALLOWED,
                reason="low_risk_sufficient_trust",
            )
        return AuthorizationDecision(
            tool_id=tool.tool_id,
            level=AuthorizationLevel.SIMULATION_ONLY,
            reason="low_risk_no_trust",
        )
