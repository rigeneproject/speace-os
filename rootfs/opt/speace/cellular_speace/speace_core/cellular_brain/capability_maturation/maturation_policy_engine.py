from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.capability_maturation.capability_maturation_models import (
    CapabilityMaturityState,
    CapabilityRecord,
    CapabilityRiskClass,
)


class MaturationPolicyEngine:
    """Policy engine enforcing maturation rules and producing recommendations."""

    def evaluate_policy(self, record: CapabilityRecord) -> Dict[str, Any]:
        can_advance = (
            record.maturity_score >= 0.72
            and record.confidence_score >= 0.70
            and record.safety_violation_count == 0
            and record.regression_rate <= 0.3
            and record.sandbox_only
            and not record.real_world_enabled
        )
        requires_review = record.risk_class in (CapabilityRiskClass.HIGH, CapabilityRiskClass.CRITICAL)
        return {
            "can_advance": can_advance,
            "requires_human_review": requires_review,
            "recommendation": self._recommendation(record, can_advance),
            "allowed": record.sandbox_only and not record.real_world_enabled,
        }

    def _recommendation(self, record: CapabilityRecord, can_advance: bool) -> str:
        if record.real_world_enabled:
            return "BLOCK: real_world_enabled must be False"
        if record.safety_violation_count > 0:
            return "BLOCK: safety violations detected"
        if record.regression_rate > 0.3:
            return "HOLD: regression rate too high"
        if can_advance:
            return "ADVANCE: capability is mature and sandboxed"
        if record.maturity_score >= 0.55:
            return "MONITOR: maturing but not yet mature"
        return "OBSERVE: insufficient evidence"
