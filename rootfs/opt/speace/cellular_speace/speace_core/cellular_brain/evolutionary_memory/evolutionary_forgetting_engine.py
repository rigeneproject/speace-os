from typing import List

from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_models import (
    ConsolidationDecision,
    EvolutionaryMemoryRecord,
    EvolutionaryMemoryStatus,
)


class EvolutionaryForgettingEngine:
    """T57 — Logical forgetting engine for evolutionary memory."""

    def apply_forgetting_policy(self, records: List[EvolutionaryMemoryRecord]) -> List[ConsolidationDecision]:
        decisions: List[ConsolidationDecision] = []
        for record in records:
            decision = self._evaluate_record(record)
            if decision is not None:
                decisions.append(decision)
                record.status = decision.new_status
        return decisions

    def _evaluate_record(self, record: EvolutionaryMemoryRecord) -> ConsolidationDecision | None:
        # Never forget reused records aggressively
        if record.reuse_count >= 2 and record.safety_score >= 0.5:
            return None

        # Forget low-quality noise
        if record.fitness_delta < -0.3 and record.reuse_count == 0 and record.confidence < 0.2:
            return self._forget(record, "Low fitness, never reused, low confidence.")

        # Forget deprecated or quarantined records that have not improved
        if record.status in (EvolutionaryMemoryStatus.DEPRECATED.value, EvolutionaryMemoryStatus.QUARANTINED.value):
            if record.reuse_count == 0:
                return self._forget(record, f"Status {record.status} with no reuse.")

        # Forget old volatile records that never graduated
        if record.status == EvolutionaryMemoryStatus.VOLATILE.value and record.reuse_count == 0 and record.confidence < 0.3:
            return self._forget(record, "Volatile, never reused, low confidence.")

        return None

    def _forget(self, record: EvolutionaryMemoryRecord, reason: str) -> ConsolidationDecision:
        return ConsolidationDecision(
            record_id=record.record_id,
            previous_status=record.status,
            new_status=EvolutionaryMemoryStatus.FORGOTTEN.value,
            reason=reason,
            confidence_delta=-record.confidence,
            governance_verdict="forgotten_by_policy",
            requires_human_review=False,
        )

    def compute_forgetting_score(self, records: List[EvolutionaryMemoryRecord]) -> float:
        """Higher score means better forgetting (more noise removed, less useful lost)."""
        if not records:
            return 0.0
        forgotten = [r for r in records if r.status == EvolutionaryMemoryStatus.FORGOTTEN.value]
        useful_forgotten = sum(1 for r in forgotten if r.reuse_count > 0)
        noise_forgotten = len(forgotten) - useful_forgotten
        if len(forgotten) == 0:
            return 0.0
        return max(0.0, noise_forgotten / len(forgotten))
