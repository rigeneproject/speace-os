from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.capability_maturation.capability_maturation_models import (
    CapabilityMaturityState,
    CapabilityRecord,
    CapabilityRiskClass,
)


class MaturityEvaluator:
    """Evaluates maturity state of capabilities based on scores and evidence."""

    def evaluate(self, record: CapabilityRecord) -> CapabilityMaturityState:
        if record.real_world_enabled:
            return CapabilityMaturityState.SAFETY_BLOCKED
        if record.safety_violation_count > 0:
            return CapabilityMaturityState.SAFETY_BLOCKED
        if record.regression_rate > 0.3:
            return CapabilityMaturityState.REGRESSIVE
        if record.maturity_score >= 0.72 and record.confidence_score >= 0.70 and record.safety_violation_count == 0:
            return CapabilityMaturityState.MATURE_SANDBOXED
        if record.maturity_score >= 0.55:
            return CapabilityMaturityState.MATURING
        if record.maturity_score >= 0.35:
            return CapabilityMaturityState.IMMATURE
        if record.maturity_score >= 0.15 or record.evidence_count > 0:
            return CapabilityMaturityState.EMERGING
        return CapabilityMaturityState.UNOBSERVED

    def compute_maturity_score(self, record: CapabilityRecord) -> float:
        if record.evidence_count == 0:
            return 0.0
        base = record.success_rate * 0.5 + record.confidence_score * 0.3
        penalty = record.regression_rate * 0.15 + (record.safety_violation_count / max(1, record.evidence_count)) * 0.05
        return max(0.0, min(1.0, base - penalty))

    def compute_confidence_score(self, record: CapabilityRecord) -> float:
        if record.evidence_count == 0:
            return 0.0
        base = min(1.0, record.evidence_count / 10.0)
        penalty = record.regression_rate * 0.2 + (record.safety_violation_count / max(1, record.evidence_count)) * 0.1
        return max(0.0, min(1.0, base - penalty))

    def compute_risk_class(self, record: CapabilityRecord) -> CapabilityRiskClass:
        if record.real_world_enabled or record.safety_violation_count > 0:
            return CapabilityRiskClass.CRITICAL
        if record.regression_rate > 0.3:
            return CapabilityRiskClass.HIGH
        if record.regression_rate > 0.15 or record.human_review_required_count > 0:
            return CapabilityRiskClass.MODERATE
        if record.maturity_state == CapabilityMaturityState.MATURE_SANDBOXED:
            return CapabilityRiskClass.LOW
        return CapabilityRiskClass.MODERATE
