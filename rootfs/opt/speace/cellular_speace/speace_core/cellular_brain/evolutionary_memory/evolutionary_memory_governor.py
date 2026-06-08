from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.evolutionary_kernel.evolutionary_cycle_models import (
    EvolutionCycleResult,
)
from speace_core.cellular_brain.evolutionary_kernel.multi_cycle_evolution_audit import (
    T56BAggregateVerdict,
)
from speace_core.cellular_brain.evolutionary_memory.consolidation_policy_engine import (
    ConsolidationPolicyEngine,
)
from speace_core.cellular_brain.evolutionary_memory.evolutionary_forgetting_engine import (
    EvolutionaryForgettingEngine,
)
from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_models import (
    ConsolidationDecision,
    EvolutionaryMemoryRecord,
    EvolutionaryMemoryStatus,
)
from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_store import (
    EvolutionaryMemoryStore,
)
from speace_core.cellular_brain.evolutionary_memory.memory_conflict_resolver import (
    MemoryConflictResolver,
)
from speace_core.cellular_brain.memory.morphology_events import MorphologyEvent, MorphologyEventType


class EvolutionaryMemoryGovernor:
    """T57 — Orchestrator for evolutionary memory governance."""

    def __init__(
        self,
        store: Optional[EvolutionaryMemoryStore] = None,
        consolidation: Optional[ConsolidationPolicyEngine] = None,
        conflict_resolver: Optional[MemoryConflictResolver] = None,
        forgetting_engine: Optional[EvolutionaryForgettingEngine] = None,
        report_dir: str = "reports/evolutionary_memory",
    ):
        self.store = store or EvolutionaryMemoryStore(report_dir=report_dir)
        self.consolidation = consolidation or ConsolidationPolicyEngine()
        self.conflict_resolver = conflict_resolver or MemoryConflictResolver()
        self.forgetting_engine = forgetting_engine or EvolutionaryForgettingEngine()
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Ingest
    # ------------------------------------------------------------------ #

    def ingest_cycle_result(self, result: EvolutionaryMemoryRecord) -> ConsolidationDecision:
        self.store.add_record(result)
        # T-Phase 8E — MM-APR integration: if the cycle was
        # hard_blocked by the MM-APR veto router, the record is
        # forcibly demoted to ``probationary`` regardless of the
        # consolidation policy's verdict. The veto info is mirrored
        # into the record's metadata so it survives subsequent
        # governance cycles.
        mmapr_hard_blocked = False
        try:
            veto = (result.metadata or {}).get("mmapr_veto_verdict")
            if isinstance(veto, dict) and veto.get("final_status") == "hard_blocked":
                # Hard-blocked records are kept for audit but cannot
                # be promoted to STABLE.
                result.metadata = dict(result.metadata or {})
                result.metadata["mmapr_hard_blocked"] = True
                result.metadata["mmapr_hard_blocked_by"] = veto.get("hard_blocked_by", [])
                mmapr_hard_blocked = True
        except Exception as exc:  # pragma: no cover - defensive
            import logging
            logging.getLogger(__name__).debug(
                "MMAPR veto integration failed on %s: %s",
                getattr(result, "record_id", "?"), exc,
            )

        decision = self.consolidation.evaluate(result)
        # MM-APR override: a hard-blocked record cannot reach STABLE
        if mmapr_hard_blocked and decision.new_status == EvolutionaryMemoryStatus.STABLE.value:
            self.store.update_status(
                result.record_id,
                EvolutionaryMemoryStatus.PROBATIONARY.value,
                "mmapr_hard_blocked: demoted to probationary by MM-APR veto",
            )
            return ConsolidationDecision(
                record_id=result.record_id,
                previous_status=EvolutionaryMemoryStatus.VOLATILE.value,
                new_status=EvolutionaryMemoryStatus.PROBATIONARY.value,
                reason="mmapr_hard_blocked: demoted to probationary by MM-APR veto",
                confidence_delta=decision.confidence_delta,
                governance_verdict="mmapr_veto_override",
                requires_human_review=True,
            )
        if decision.previous_status != decision.new_status:
            self.store.update_status(result.record_id, decision.new_status, decision.reason)
        self._log_event(MorphologyEventType.EVOLUTIONARY_MEMORY_RECORD_INGESTED, result.record_id, decision.new_status)
        return decision

    def adopt_self_modification(
        self,
        cycle_result: Any,
        source_cycle_id: str = "self_modification_cycle",
    ) -> ConsolidationDecision:
        """T169 — Promote a ``SelfModificationCycleResult`` into the
        evolutionary memory store.

        Builds a valid ``EvolutionaryMemoryRecord`` from the cycle's
        observed scores and post-patch deltas, then runs the standard
        consolidation policy to decide its status.
        """
        observed = getattr(cycle_result, "observed", {}) or {}
        # Build record from cycle result
        record = EvolutionaryMemoryRecord(
            record_id=getattr(cycle_result, "cycle_id", f"smc-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"),
            source_cycle_id=source_cycle_id,
            source_task="self_modification",
            source_profile="t169_phase3",
            fitness_delta=float(getattr(cycle_result, "delta_score", 0.0) or 0.0),
            phi_delta=float(observed.get("coherence_phi", 0.0) or 0.0),
            energy_delta=float(observed.get("mean_energy", 0.0) or 0.0),
            cognitive_delta=float(getattr(cycle_result, "delta_score", 0.0) or 0.0),
            regression_score=float(getattr(cycle_result, "regression_score", 0.0) or 0.0),
            safety_score=float(getattr(cycle_result, "safety_score", 0.5) or 0.5),
            confidence=float(getattr(cycle_result, "confidence", 0.0) or 0.0),
            reuse_count=1,  # adopted via closed loop
            status=EvolutionaryMemoryStatus.VOLATILE.value,
            metadata={
                "passed_steps": list(getattr(cycle_result, "passed_steps", []) or []),
                "adoption": getattr(cycle_result, "adoption", None),
                "limitations": list(getattr(cycle_result, "limitations", []) or []),
                "mutations": list(getattr(cycle_result, "mutations", []) or []),
            },
        )
        return self.ingest_cycle_result(record)

    def ingest_multi_cycle_audit_result(self, verdict: T56BAggregateVerdict) -> List[ConsolidationDecision]:
        decisions: List[ConsolidationDecision] = []
        for profile in verdict.profile_results:
            if profile.mce_result is None:
                continue
            record = EvolutionaryMemoryRecord(
                record_id=f"audit_{profile.profile_name}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                source_cycle_id="t56b",
                source_task="multi_cycle_audit",
                source_profile=profile.profile_name,
                fitness_delta=profile.cumulative_learning_score,
                drift_score=profile.drift_score,
                regression_score=profile.regression_pattern_count / max(1, profile.mce_result.consolidated.total_cycles),
                safety_score=1.0 - (profile.unsafe_cycle_count / max(1, profile.mce_result.consolidated.total_cycles)),
                confidence=profile.multi_cycle_validation_score,
                status=EvolutionaryMemoryStatus.VOLATILE.value,
            )
            decision = self.ingest_cycle_result(record)
            decisions.append(decision)
        return decisions

    # ------------------------------------------------------------------ #
    # Governance cycle
    # ------------------------------------------------------------------ #

    def run_governance_cycle(self) -> Dict[str, Any]:
        self._log_event(MorphologyEventType.EVOLUTIONARY_MEMORY_GOVERNANCE_STARTED, "governor", "cycle_started")
        records = self.store.list_records()

        # 1. Consolidation
        consolidation_decisions = self._consolidate_memory(records)
        for d in consolidation_decisions:
            if d.previous_status != d.new_status:
                self._log_event(
                    MorphologyEventType.EVOLUTIONARY_MEMORY_RECORD_PROMOTED if d.new_status in (EvolutionaryMemoryStatus.STABLE.value, EvolutionaryMemoryStatus.PROBATIONARY.value)
                    else MorphologyEventType.EVOLUTIONARY_MEMORY_RECORD_DEGRADED if d.new_status in (EvolutionaryMemoryStatus.DEPRECATED.value, EvolutionaryMemoryStatus.FORGOTTEN.value)
                    else MorphologyEventType.EVOLUTIONARY_MEMORY_RECORD_QUARANTINED,
                    d.record_id,
                    d.new_status,
                )

        # 2. Conflict resolution
        conflicts = self.conflict_resolver.detect_conflicts(records)
        resolved = 0
        for conflict in conflicts:
            winner_id = self.conflict_resolver.resolve_conflict(conflict, self.store._records)
            if winner_id:
                resolved += 1
                self.store.increment_reuse(winner_id)
            self._log_event(MorphologyEventType.EVOLUTIONARY_MEMORY_CONFLICT_DETECTED, conflict.conflict_id, conflict.conflict_type)

        # 3. Forgetting
        forgetting_decisions = self.forgetting_engine.apply_forgetting_policy(records)
        for d in forgetting_decisions:
            self._log_event(MorphologyEventType.EVOLUTIONARY_MEMORY_RECORD_FORGOTTEN, d.record_id, d.reason)

        self._log_event(MorphologyEventType.EVOLUTIONARY_MEMORY_GOVERNANCE_COMPLETED, "governor", "cycle_completed")
        return {
            "consolidation_decisions": len(consolidation_decisions),
            "conflicts_detected": len(conflicts),
            "conflicts_resolved": resolved,
            "forgotten_records": len(forgetting_decisions),
        }

    def _consolidate_memory(self, records: List[EvolutionaryMemoryRecord]) -> List[ConsolidationDecision]:
        decisions: List[ConsolidationDecision] = []
        for record in records:
            # Skip frozen and forgotten
            if record.status in (EvolutionaryMemoryStatus.FROZEN_POLICY.value, EvolutionaryMemoryStatus.FORGOTTEN.value):
                continue
            decision = self.consolidation.evaluate(record)
            if decision.previous_status != decision.new_status:
                self.store.update_status(record.record_id, decision.new_status, decision.reason)
                decisions.append(decision)
        return decisions

    # ------------------------------------------------------------------ #
    # Reports
    # ------------------------------------------------------------------ #

    def generate_governance_report(self) -> Path:
        return self.store.export_markdown()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _log_event(self, event_type: MorphologyEventType, source_id: str, detail: str) -> None:
        pass  # Events are logged externally via orchestrator memory when available
