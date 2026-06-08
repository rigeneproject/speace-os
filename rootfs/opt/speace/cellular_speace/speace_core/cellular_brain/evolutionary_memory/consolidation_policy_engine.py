from typing import List, Optional

from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_models import (
    ConsolidationDecision,
    EvolutionaryMemoryRecord,
    EvolutionaryMemoryStatus,
)


class ConsolidationPolicyEngine:
    """T57 — Decide if an evolutionary learning should be promoted, maintained, degraded, or quarantined."""

    def evaluate(self, record: EvolutionaryMemoryRecord) -> ConsolidationDecision:
        previous = record.status
        new_status = self._compute_status(record)
        reason = self._reason(record, new_status)
        return ConsolidationDecision(
            record_id=record.record_id,
            previous_status=previous,
            new_status=new_status.value,
            reason=reason,
            confidence_delta=record.confidence,
            governance_verdict="consolidation_evaluated",
            requires_human_review=new_status == EvolutionaryMemoryStatus.PROBATIONARY,
        )

    @staticmethod
    def _compute_status(record: EvolutionaryMemoryRecord) -> EvolutionaryMemoryStatus:
        # QUARANTINED if unsafe or high drift/regression
        if record.safety_score < 0.4 or record.drift_score > 0.5 or record.regression_score > 0.5:
            return EvolutionaryMemoryStatus.QUARANTINED

        # FORGOTTEN if noise or harmful
        if record.fitness_delta < -0.2 and record.reuse_count == 0 and record.confidence < 0.2:
            return EvolutionaryMemoryStatus.FORGOTTEN

        # DEPRECATED if fitness negative and no reuse
        if record.fitness_delta < 0 and record.reuse_count == 0:
            return EvolutionaryMemoryStatus.DEPRECATED

        # STABLE if fitness positive, phi not decreased, low regression, high safety, reused
        if (
            record.fitness_delta > 0
            and record.phi_delta >= 0
            and record.regression_score < 0.2
            and record.safety_score >= 0.7
            and record.confidence >= 0.5
            and record.reuse_count > 0
        ):
            return EvolutionaryMemoryStatus.STABLE

        # PROBATIONARY if promising but not yet reused
        if record.fitness_delta > 0 and record.safety_score >= 0.6 and record.confidence >= 0.3:
            return EvolutionaryMemoryStatus.PROBATIONARY

        # EXPERIMENTAL if positive but low confidence
        if record.fitness_delta > 0 and record.confidence < 0.3:
            return EvolutionaryMemoryStatus.EXPERIMENTAL

        # Default: VOLATILE
        return EvolutionaryMemoryStatus.VOLATILE

    @staticmethod
    def _reason(record: EvolutionaryMemoryRecord, status: EvolutionaryMemoryStatus) -> str:
        return (
            f"fitness_delta={record.fitness_delta:.3f} phi_delta={record.phi_delta:.3f} "
            f"drift={record.drift_score:.3f} regression={record.regression_score:.3f} "
            f"safety={record.safety_score:.3f} confidence={record.confidence:.3f} "
            f"reuse={record.reuse_count} -> {status.value}"
        )
