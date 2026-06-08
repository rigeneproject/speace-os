from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.capability_maturation.capability_maturation_models import (
    CapabilityMaturityState,
    CapabilityRecord,
    CapabilityRiskClass,
)


class CapabilityQuarantineManager:
    """Quarantines critical-risk capabilities."""

    def evaluate_quarantine(self, record: CapabilityRecord) -> bool:
        if record.risk_class == CapabilityRiskClass.CRITICAL:
            return True
        if record.safety_violation_count >= 2:
            return True
        if record.real_world_enabled:
            return True
        return False

    def quarantine(self, record: CapabilityRecord) -> None:
        record.maturity_state = CapabilityMaturityState.QUARANTINED
        record.sandbox_only = True
        record.real_world_enabled = False

    def release(self, record: CapabilityRecord) -> None:
        if record.maturity_state == CapabilityMaturityState.QUARANTINED:
            record.maturity_state = CapabilityMaturityState.IMMATURE
