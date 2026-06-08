from typing import Any, Dict

from speace_core.cellular_brain.skill_transfer.skill_transfer_models import (
    SkillTransferCandidate,
    SkillTransferResult,
    SkillTransferState,
    TransferScenario,
)


class TransferEvaluator:
    """Evaluates transfer success between source and target scenario."""

    def evaluate(
        self,
        candidate: SkillTransferCandidate,
        scenario: TransferScenario,
        rng,
    ) -> SkillTransferResult:
        result = SkillTransferResult(
            skill_id=candidate.skill_id,
            scenario_id=scenario.scenario_id,
            sandbox_only=candidate.sandbox_only,
            real_world_enabled=candidate.real_world_enabled,
        )

        # Base transfer success depends on source maturity and scenario difficulty
        base_success = candidate.source_maturity_score * (1.0 - scenario.difficulty_score * 0.5)
        transfer_success = max(0.0, min(1.0, base_success + rng.uniform(-0.1, 0.1)))
        result.transfer_success_score = round(transfer_success, 4)

        # Generalization depends on novelty and transfer success
        generalization = transfer_success * (1.0 - scenario.novelty_score * 0.4)
        result.generalization_score = round(max(0.0, min(1.0, generalization)), 4)

        # Overfitting: high source score but low generalization
        overfitting = max(0.0, candidate.source_maturity_score - result.generalization_score)
        result.overfitting_score = round(min(1.0, overfitting), 4)

        # Negative transfer: transfer makes things worse
        negative_transfer = max(0.0, scenario.difficulty_score - transfer_success)
        result.negative_transfer_score = round(min(1.0, negative_transfer), 4)

        # Safety score
        result.safety_score = 1.0 if candidate.sandbox_only and not candidate.real_world_enabled else 0.0
        result.confidence_score = round(candidate.source_confidence_score * (0.8 + 0.2 * transfer_success), 4)
        result.read_only_integrity_score = 1.0

        return result
