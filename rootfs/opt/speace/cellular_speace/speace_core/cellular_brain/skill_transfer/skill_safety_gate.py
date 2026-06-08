from typing import Any, Dict, List

from speace_core.cellular_brain.skill_transfer.skill_transfer_models import (
    SkillTransferCandidate,
    SkillTransferResult,
)


class SkillSafetyGate:
    """Blocks unsafe skill transfers."""

    def evaluate(self, candidate: SkillTransferCandidate, result: SkillTransferResult) -> Dict[str, Any]:
        violations: List[str] = []
        if candidate.real_world_enabled:
            violations.append("real_world_enabled")
        if not candidate.sandbox_only:
            violations.append("not_sandbox_only")
        if result.transfer_success_score < 0.3 and result.safety_score < 1.0:
            violations.append("low_transfer_and_safety")
        blocked = len(violations) > 0
        return {
            "allowed": not blocked,
            "blocked": blocked,
            "violations": violations,
        }

    def should_block(self, candidate: SkillTransferCandidate) -> bool:
        return candidate.real_world_enabled or not candidate.sandbox_only
