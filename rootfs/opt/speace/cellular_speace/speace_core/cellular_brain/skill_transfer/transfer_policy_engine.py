from typing import Any, Dict

from speace_core.cellular_brain.skill_transfer.skill_transfer_models import (
    SkillTransferCandidate,
    SkillTransferResult,
    SkillTransferState,
)


class TransferPolicyEngine:
    """Policy engine for skill transfer decisions."""

    def evaluate_policy(
        self, candidate: SkillTransferCandidate, result: SkillTransferResult
    ) -> Dict[str, Any]:
        can_advance = (
            candidate.source_maturity_score >= 0.72
            and candidate.source_confidence_score >= 0.70
            and candidate.source_safety_score >= 0.90
            and result.transfer_success_score >= 0.70
            and result.generalization_score >= 0.68
            and result.overfitting_score <= 0.25
            and result.negative_transfer_score <= 0.20
            and candidate.sandbox_only
            and not candidate.real_world_enabled
            and result.read_only_integrity_score == 1.0
        )
        requires_review = result.safety_score < 1.0 or result.overfitting_score > 0.15
        return {
            "can_advance": can_advance,
            "requires_human_review": requires_review,
            "recommendation": self._recommendation(candidate, result, can_advance),
            "allowed": candidate.sandbox_only and not candidate.real_world_enabled,
        }

    def _recommendation(self, candidate: SkillTransferCandidate, result: SkillTransferResult, can_advance: bool) -> str:
        if candidate.real_world_enabled or result.real_world_enabled:
            return "BLOCK: real_world_enabled must be False"
        if not candidate.sandbox_only or not result.sandbox_only:
            return "BLOCK: sandbox_only must be True"
        if result.overfitting_score > 0.25:
            return "HOLD: overfitting detected"
        if result.negative_transfer_score > 0.20:
            return "HOLD: negative transfer detected"
        if can_advance:
            return "ADVANCE: skill generalizes safely in sandbox"
        if result.transfer_success_score >= 0.55:
            return "MONITOR: partial transfer, needs more evidence"
        return "OBSERVE: insufficient transfer evidence"
