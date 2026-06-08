import random
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.skill_transfer.skill_transfer_models import (
    SkillTransferAuditResult,
    SkillTransferCandidate,
    SkillTransferResult,
    SkillTransferState,
)
from speace_core.cellular_brain.skill_transfer.skill_candidate_registry import (
    SkillCandidateRegistry,
)
from speace_core.cellular_brain.skill_transfer.transfer_scenario_builder import (
    TransferScenarioBuilder,
)
from speace_core.cellular_brain.skill_transfer.transfer_evaluator import (
    TransferEvaluator,
)
from speace_core.cellular_brain.skill_transfer.generalization_tracker import (
    GeneralizationTracker,
)
from speace_core.cellular_brain.skill_transfer.negative_transfer_detector import (
    NegativeTransferDetector,
)
from speace_core.cellular_brain.skill_transfer.skill_safety_gate import (
    SkillSafetyGate,
)
from speace_core.cellular_brain.skill_transfer.transfer_policy_engine import (
    TransferPolicyEngine,
)


class SkillTransferLayer:
    """T65 main layer. Evaluates sandboxed skill transfer and generalization."""

    def __init__(self, seed: int = 42):
        self._seed = seed
        self._rng = random.Random(seed)
        self._registry = SkillCandidateRegistry()
        self._scenario_builder = TransferScenarioBuilder(seed=seed)
        self._evaluator = TransferEvaluator()
        self._gen_tracker = GeneralizationTracker()
        self._neg_detector = NegativeTransferDetector()
        self._gate = SkillSafetyGate()
        self._policy = TransferPolicyEngine()

    def get_stages(self) -> List[str]:
        return ["candidate", "scenario", "evaluate", "gate", "policy", "report"]

    def register_candidates(self, candidates: List[SkillTransferCandidate]) -> None:
        for candidate in candidates:
            self._registry.add_candidate(candidate)

    def run_transfer(self) -> SkillTransferAuditResult:
        candidates = self._registry.get_all_candidates()
        scenarios = self._scenario_builder.build_default_scenarios()
        results: List[SkillTransferResult] = []

        for candidate in candidates:
            for scenario in scenarios:
                result = self._evaluator.evaluate(candidate, scenario, self._rng)
                result.sandbox_only = candidate.sandbox_only
                result.real_world_enabled = candidate.real_world_enabled
                result.read_only_integrity_score = 1.0

                # Safety gate
                if self._gate.should_block(candidate):
                    result.blocked = True
                    result.transfer_state = SkillTransferState.SAFETY_BLOCKED
                    result.safety_score = 0.0
                else:
                    result.safety_score = 1.0

                # Track generalization and negative transfer
                self._gen_tracker.record(candidate.skill_id, result.generalization_score)
                self._neg_detector.record(candidate.skill_id, result.negative_transfer_score)

                # Policy evaluation
                policy = self._policy.evaluate_policy(candidate, result)
                if result.blocked:
                    pass
                elif policy["can_advance"]:
                    if self._gen_tracker.generalizes(candidate.skill_id):
                        result.transfer_state = SkillTransferState.GENERALIZES_SANDBOXED
                    else:
                        result.transfer_state = SkillTransferState.TRANSFERRED_SANDBOXED
                elif result.overfitting_score > 0.25:
                    result.transfer_state = SkillTransferState.OVERFITTED
                elif result.negative_transfer_score > 0.20:
                    result.transfer_state = SkillTransferState.NEGATIVE_TRANSFER
                elif candidate.source_maturity_score >= 0.55:
                    result.transfer_state = SkillTransferState.TRANSFER_TESTED
                else:
                    result.transfer_state = SkillTransferState.INSUFFICIENT_EVIDENCE

                # Quarantine check: if candidate has real_world_enabled
                if candidate.real_world_enabled:
                    result.quarantined = True
                    result.transfer_state = SkillTransferState.QUARANTINED

                result.verdict = self._compute_result_verdict(result)
                results.append(result)

        return self._build_result(candidates, scenarios, results)

    def _compute_result_verdict(self, result: SkillTransferResult) -> str:
        if result.read_only_integrity_score < 1.0:
            return "SKILL_TRANSFER_READ_ONLY_VIOLATION"
        if result.real_world_enabled:
            return "REAL_WORLD_SKILL_ENABLED"
        if not result.sandbox_only:
            return "UNSAFE_SKILL_TRANSFER_ENABLED"
        if result.transfer_state == SkillTransferState.QUARANTINED:
            return "SKILL_TRANSFER_QUARANTINE_REQUIRED"
        if result.transfer_state == SkillTransferState.SAFETY_BLOCKED:
            return "SKILL_TRANSFER_SAFETY_BLOCK_REQUIRED"
        if result.transfer_state == SkillTransferState.OVERFITTED:
            return "SKILL_OVERFITTING_DETECTED"
        if result.transfer_state == SkillTransferState.NEGATIVE_TRANSFER:
            return "NEGATIVE_TRANSFER_DETECTED"
        if result.transfer_state == SkillTransferState.GENERALIZES_SANDBOXED:
            return "SKILL_TRANSFER_LAYER_VALIDATED"
        if result.transfer_state == SkillTransferState.TRANSFERRED_SANDBOXED:
            return "SKILL_TRANSFER_SAFE_BUT_LIMITED"
        return "SKILL_TRANSFER_INSUFFICIENT_EVIDENCE"

    def _build_result(
        self,
        candidates: List[SkillTransferCandidate],
        scenarios: List[Any],
        results: List[SkillTransferResult],
    ) -> SkillTransferAuditResult:
        audit = SkillTransferAuditResult(results=results)
        audit.candidate_count = len(candidates)
        audit.scenario_count = len(scenarios)
        audit.transfer_attempt_count = len(results)
        audit.transferred_sandboxed_count = sum(
            1 for r in results if r.transfer_state == SkillTransferState.TRANSFERRED_SANDBOXED
        )
        audit.generalized_sandboxed_count = sum(
            1 for r in results if r.transfer_state == SkillTransferState.GENERALIZES_SANDBOXED
        )
        audit.overfitted_count = sum(
            1 for r in results if r.transfer_state == SkillTransferState.OVERFITTED
        )
        audit.negative_transfer_count = sum(
            1 for r in results if r.transfer_state == SkillTransferState.NEGATIVE_TRANSFER
        )
        audit.safety_blocked_count = sum(
            1 for r in results if r.transfer_state == SkillTransferState.SAFETY_BLOCKED
        )
        audit.quarantined_count = sum(
            1 for r in results if r.transfer_state == SkillTransferState.QUARANTINED
        )
        audit.unsafe_transfer_enabled_count = sum(
            1 for r in results if not r.sandbox_only
        )
        audit.real_world_enabled_count = sum(
            1 for r in results if r.real_world_enabled
        )

        if results:
            audit.aggregate_transfer_score = round(
                sum(r.transfer_success_score for r in results) / len(results), 4
            )
            audit.aggregate_generalization_score = round(
                sum(r.generalization_score for r in results) / len(results), 4
            )
            audit.aggregate_safety_score = round(
                sum(r.safety_score for r in results) / len(results), 4
            )

        audit.read_only_integrity_score = 1.0
        audit.transfer_verdict = self._compute_audit_verdict(audit)
        audit.proceed_to_t65b = self._compute_proceed(audit)
        return audit

    def _compute_audit_verdict(self, audit: SkillTransferAuditResult) -> str:
        if audit.real_world_enabled_count > 0:
            return "REAL_WORLD_SKILL_ENABLED"
        if audit.unsafe_transfer_enabled_count > 0:
            return "UNSAFE_SKILL_TRANSFER_ENABLED"
        if audit.overfitted_count > 0:
            return "SKILL_OVERFITTING_DETECTED"
        if audit.negative_transfer_count > 0:
            return "NEGATIVE_TRANSFER_DETECTED"
        if audit.safety_blocked_count > 0:
            return "SKILL_TRANSFER_SAFETY_BLOCK_REQUIRED"
        if audit.quarantined_count > 0:
            return "SKILL_TRANSFER_QUARANTINE_REQUIRED"
        if audit.aggregate_transfer_score >= 0.70 and audit.aggregate_generalization_score >= 0.68:
            if audit.generalized_sandboxed_count > 0 and audit.overfitted_count == 0 and audit.negative_transfer_count == 0:
                return "SKILL_TRANSFER_LAYER_VALIDATED"
            return "SKILL_TRANSFER_SAFE_BUT_LIMITED"
        return "SKILL_TRANSFER_INSUFFICIENT_EVIDENCE"

    def _compute_proceed(self, audit: SkillTransferAuditResult) -> bool:
        if audit.aggregate_transfer_score < 0.70:
            return False
        if audit.aggregate_generalization_score < 0.68:
            return False
        if audit.read_only_integrity_score < 1.0:
            return False
        if audit.real_world_enabled_count > 0:
            return False
        if audit.unsafe_transfer_enabled_count > 0:
            return False
        if audit.overfitted_count > 0:
            return False
        if audit.negative_transfer_count > 0:
            return False
        if audit.quarantined_count > 0:
            return False
        return True

    def get_state(self) -> Dict[str, Any]:
        return {
            "candidate_count": self._registry.record_count(),
            "candidates": [c.model_dump() for c in self._registry.get_all_candidates()],
        }
