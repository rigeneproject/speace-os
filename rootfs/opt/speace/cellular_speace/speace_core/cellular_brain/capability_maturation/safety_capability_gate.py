from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.capability_maturation.capability_maturation_models import (
    CapabilityMaturityState,
    CapabilityRecord,
    CapabilityRiskClass,
)


class SafetyCapabilityGate:
    """Safety gate that blocks unsafe capabilities from advancing."""

    def evaluate(self, record: CapabilityRecord) -> Dict[str, Any]:
        violations: List[str] = []
        if record.real_world_enabled:
            violations.append("real_world_enabled")
        if record.safety_violation_count > 0:
            violations.append("safety_violations")
        if not record.sandbox_only:
            violations.append("not_sandbox_only")

        blocked = len(violations) > 0
        return {
            "allowed": not blocked,
            "blocked": blocked,
            "violations": violations,
            "requires_human_review": record.risk_class in (CapabilityRiskClass.HIGH, CapabilityRiskClass.CRITICAL),
        }

    def should_block(self, record: CapabilityRecord) -> bool:
        return record.real_world_enabled or record.safety_violation_count > 0 or not record.sandbox_only
