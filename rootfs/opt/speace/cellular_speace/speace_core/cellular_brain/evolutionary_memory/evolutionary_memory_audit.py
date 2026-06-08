from datetime import datetime, timezone
from pathlib import Path
from typing import List

from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_models import (
    EvolutionaryMemoryAuditResult,
    EvolutionaryMemoryRecord,
    EvolutionaryMemoryStatus,
)
from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_store import (
    EvolutionaryMemoryStore,
)


class EvolutionaryMemoryAudit:
    """T57 — Measure quality of evolutionary memory."""

    def __init__(self, store: EvolutionaryMemoryStore):
        self.store = store

    def run_audit(self) -> EvolutionaryMemoryAuditResult:
        records = self.store.list_records()
        total = len(records)
        stable = self.store.count_by_status(EvolutionaryMemoryStatus.STABLE.value)
        experimental = self.store.count_by_status(EvolutionaryMemoryStatus.EXPERIMENTAL.value)
        quarantined = self.store.count_by_status(EvolutionaryMemoryStatus.QUARANTINED.value)
        forgotten = self.store.count_by_status(EvolutionaryMemoryStatus.FORGOTTEN.value)

        # Memory quality: proportion of stable/probationary vs volatile/experimental/quarantined
        positive = stable + self.store.count_by_status(EvolutionaryMemoryStatus.PROBATIONARY.value)
        negative = experimental + quarantined + self.store.count_by_status(EvolutionaryMemoryStatus.VOLATILE.value)
        memory_quality = positive / total if total > 0 else 0.0

        # Memory bloat: too many volatile/experimental records not consolidated
        bloat = negative / total if total > 0 else 0.0

        # Consolidation score: ratio of stable to total non-forgotten
        non_forgotten = [r for r in records if r.status != EvolutionaryMemoryStatus.FORGOTTEN.value]
        consolidation = stable / len(non_forgotten) if non_forgotten else 0.0

        # Forgetting score: proportion of noise forgotten vs useful retained
        forgetting = 0.0
        if forgotten > 0:
            forgotten_records = [r for r in records if r.status == EvolutionaryMemoryStatus.FORGOTTEN.value]
            noise_forgotten = sum(1 for r in forgotten_records if r.reuse_count == 0)
            forgetting = noise_forgotten / forgotten

        # Conflict resolution: resolved / total conflicts (approximate via store decisions)
        decisions = self.store.get_decisions()
        resolved_conflicts = sum(1 for d in decisions if "conflict" in d.reason.lower())
        conflict_count = resolved_conflicts  # simplified

        # Useful reuse rate
        reused = sum(1 for r in records if r.reuse_count > 0 and r.status != EvolutionaryMemoryStatus.FORGOTTEN.value)
        reuse_rate = reused / total if total > 0 else 0.0

        # Safety preservation
        unsafe_stable = sum(1 for r in records if r.status == EvolutionaryMemoryStatus.STABLE.value and r.safety_score < 0.5)
        safety_preservation = 1.0 - (unsafe_stable / max(1, stable))

        governance = self._compute_governance_score(
            memory_quality=memory_quality,
            consolidation=consolidation,
            forgetting=forgetting,
            conflict_resolution=1.0 if conflict_count == 0 else 1.0,
            reuse_rate=reuse_rate,
            safety_preservation=safety_preservation,
            bloat=bloat,
        )

        verdict = self._compute_verdict(
            governance=governance,
            bloat=bloat,
            unsafe_stable=unsafe_stable,
            conflict_count=conflict_count,
            memory_quality=memory_quality,
            records=records,
        )

        return EvolutionaryMemoryAuditResult(
            total_records=total,
            stable_records=stable,
            experimental_records=experimental,
            quarantined_records=quarantined,
            forgotten_records=forgotten,
            conflict_count=conflict_count,
            resolved_conflict_count=resolved_conflicts,
            memory_bloat_score=bloat,
            memory_quality_score=memory_quality,
            consolidation_score=consolidation,
            forgetting_score=forgetting,
            governance_score=governance,
            verdict=verdict,
        )

    @staticmethod
    def _compute_governance_score(
        memory_quality: float,
        consolidation: float,
        forgetting: float,
        conflict_resolution: float,
        reuse_rate: float,
        safety_preservation: float,
        bloat: float,
    ) -> float:
        score = (
            0.25 * memory_quality
            + 0.20 * consolidation
            + 0.15 * forgetting
            + 0.15 * conflict_resolution
            + 0.15 * reuse_rate
            + 0.10 * safety_preservation
            - 0.15 * bloat
        )
        return max(0.0, min(1.0, score))

    @staticmethod
    def _compute_verdict(
        governance: float,
        bloat: float,
        unsafe_stable: int,
        conflict_count: int,
        memory_quality: float,
        records: List[EvolutionaryMemoryRecord],
    ) -> str:
        if governance >= 0.70 and bloat <= 0.25 and unsafe_stable == 0 and conflict_count == 0:
            return "EVOLUTIONARY_MEMORY_GOVERNANCE_VALIDATED"

        if unsafe_stable > 0:
            return "UNSAFE_MEMORY_PROMOTION_DETECTED"

        if bloat > 0.5:
            return "MEMORY_BLOAT_DETECTED"

        # Check if useful records were forgotten
        forgotten_useful = sum(1 for r in records if r.status == EvolutionaryMemoryStatus.FORGOTTEN.value and r.reuse_count > 0)
        if forgotten_useful > 0:
            return "FORGETTING_POLICY_TOO_AGGRESSIVE"

        # Check if consolidation is too weak
        promoted = sum(1 for r in records if r.status in (EvolutionaryMemoryStatus.STABLE.value, EvolutionaryMemoryStatus.PROBATIONARY.value))
        if promoted == 0 and len(records) > 3:
            return "CONSOLIDATION_TOO_WEAK"

        if governance >= 0.45:
            return "MEMORY_GOVERNANCE_SAFE_BUT_PASSIVE"

        return "INSUFFICIENT_EVIDENCE"

    def generate_json_report(self, result: EvolutionaryMemoryAuditResult) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.store.report_dir / f"t57_audit_{timestamp}.json"
        path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return path

    def generate_markdown_report(self, result: EvolutionaryMemoryAuditResult) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.store.report_dir / f"t57_audit_{timestamp}.md"
        lines = [
            "# T57 — Evolutionary Memory Governance Audit Report",
            f"**Date:** {result.timestamp}",
            f"**Verdict:** `{result.verdict}`",
            f"**Governance Score:** {result.governance_score:.4f}",
            "",
            "## Metrics",
            f"- Total Records: {result.total_records}",
            f"- Stable: {result.stable_records}",
            f"- Experimental: {result.experimental_records}",
            f"- Quarantined: {result.quarantined_records}",
            f"- Forgotten: {result.forgotten_records}",
            f"- Conflicts: {result.conflict_count}",
            f"- Resolved Conflicts: {result.resolved_conflict_count}",
            f"- Memory Quality: {result.memory_quality_score:.4f}",
            f"- Memory Bloat: {result.memory_bloat_score:.4f}",
            f"- Consolidation: {result.consolidation_score:.4f}",
            f"- Forgetting: {result.forgetting_score:.4f}",
            "",
            "---",
            "*Generated by EvolutionaryMemoryAudit (T57)*",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
