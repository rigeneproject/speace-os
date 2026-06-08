import json
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.evolutionary_memory.consolidation_policy_engine import (
    ConsolidationPolicyEngine,
)
from speace_core.cellular_brain.evolutionary_memory.evolutionary_forgetting_engine import (
    EvolutionaryForgettingEngine,
)
from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_audit import (
    EvolutionaryMemoryAudit,
)
from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_governor import (
    EvolutionaryMemoryGovernor,
)
from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_models import (
    EvolutionaryMemoryRecord,
    EvolutionaryMemoryStatus,
    GovernanceAuditProfile,
    GovernanceAuditProfileResult,
    GovernanceAuditSuiteResult,
)
from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_store import (
    EvolutionaryMemoryStore,
)
from speace_core.cellular_brain.evolutionary_memory.memory_conflict_resolver import (
    MemoryConflictResolver,
)
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType


class EvolutionaryMemoryGovernanceAuditRunner:
    """T57B — Real-run audit runner for evolutionary memory governance."""

    def __init__(
        self,
        governor: Optional[EvolutionaryMemoryGovernor] = None,
        seed: int = 42,
        reports_dir: str = "reports/evolutionary_memory",
    ):
        self.governor = governor or EvolutionaryMemoryGovernor(
            store=EvolutionaryMemoryStore(report_dir=reports_dir),
            consolidation=ConsolidationPolicyEngine(),
            conflict_resolver=MemoryConflictResolver(),
            forgetting_engine=EvolutionaryForgettingEngine(),
            report_dir=reports_dir,
        )
        self.seed = seed
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        random.seed(seed)

    # ------------------------------------------------------------------ #
    # Profiles
    # ------------------------------------------------------------------ #

    def build_default_profiles(self) -> List[GovernanceAuditProfile]:
        return [
            GovernanceAuditProfile(
                name="empty_memory_baseline",
                description="Store vuoto, deve produrre INSUFFICIENT_EVIDENCE o SAFE_BUT_PASSIVE",
                record_count=0,
            ),
            GovernanceAuditProfile(
                name="positive_safe_records",
                description="Record positivi e sicuri devono essere promossi a PROBATIONARY/STABLE",
                record_count=5,
            ),
            GovernanceAuditProfile(
                name="unsafe_high_fitness_records",
                description="Record con fitness alto ma safety basso o regression alta",
                record_count=5,
                expected_risk_type="UNSAFE_MEMORY_PROMOTION_DETECTED",
            ),
            GovernanceAuditProfile(
                name="drift_accumulation_records",
                description="Record con drift progressivo e peggioramento phi/energy/cognitive",
                record_count=5,
                expected_risk_type="EVOLUTIONARY_MEMORY_DRIFT_DETECTED",
            ),
            GovernanceAuditProfile(
                name="conflicting_records",
                description="Record contraddittori: fitness migliora ma phi/energy/safety peggiora",
                record_count=6,
                expected_risk_type="CONFLICT_RESOLUTION_WEAK",
            ),
            GovernanceAuditProfile(
                name="memory_bloat_profile",
                description="Molti record VOLATILE/EXPERIMENTAL mai riusati",
                record_count=12,
                expected_risk_type="MEMORY_BLOAT_DETECTED",
            ),
            GovernanceAuditProfile(
                name="forgetting_policy_profile",
                description="Record inutili, rumorosi o mai riusati devono essere dimenticati",
                record_count=8,
            ),
            GovernanceAuditProfile(
                name="reused_useful_records",
                description="Record riusati con outcome positivo non devono essere dimenticati",
                record_count=5,
            ),
            GovernanceAuditProfile(
                name="quarantined_reuse_attempt",
                description="Tentativo di riuso di record QUARANTINED deve essere bloccato",
                record_count=3,
                expected_risk_type="QUARANTINED_REUSE_BLOCKED",
            ),
            GovernanceAuditProfile(
                name="full_governance_realistic_profile",
                description="Mix realistico di record safe, unsafe, rumorosi, conflittuali, riusati e obsoleti",
                record_count=20,
            ),
            GovernanceAuditProfile(
                name="consolidation_too_weak",
                description="Nessun record positivo promosso oltre EXPERIMENTAL",
                record_count=5,
                expected_risk_type="CONSOLIDATION_TOO_WEAK",
            ),
        ]

    # ------------------------------------------------------------------ #
    # Record loaders
    # ------------------------------------------------------------------ #

    def load_real_records_if_available(self) -> List[EvolutionaryMemoryRecord]:
        records: List[EvolutionaryMemoryRecord] = []
        report_dir = Path("reports/evolutionary_memory")
        if not report_dir.exists():
            return records
        for path in sorted(report_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for item in data:
                        try:
                            records.append(EvolutionaryMemoryRecord(**item))
                        except Exception:
                            pass
                elif isinstance(data, dict):
                    try:
                        records.append(EvolutionaryMemoryRecord(**data))
                    except Exception:
                        pass
            except Exception:
                continue
        return records

    def build_synthetic_records_for_profile(
        self,
        profile: GovernanceAuditProfile,
    ) -> List[EvolutionaryMemoryRecord]:
        records: List[EvolutionaryMemoryRecord] = []
        n = profile.record_count
        if n == 0:
            return records

        if profile.name == "positive_safe_records":
            for i in range(n):
                records.append(
                    EvolutionaryMemoryRecord(
                        record_id=f"pos_safe_{uuid.uuid4().hex[:6]}",
                        source_cycle_id="c1",
                        source_task="t55",
                        source_profile=profile.name,
                        fitness_delta=random.uniform(0.2, 0.8),
                        phi_delta=random.uniform(0.0, 0.2),
                        energy_delta=random.uniform(-0.05, 0.1),
                        safety_score=random.uniform(0.75, 1.0),
                        confidence=random.uniform(0.5, 1.0),
                        drift_score=random.uniform(0.0, 0.2),
                        regression_score=random.uniform(0.0, 0.15),
                        reuse_count=random.choice([0, 1, 2]),
                        status=EvolutionaryMemoryStatus.VOLATILE.value,
                    )
                )

        elif profile.name == "unsafe_high_fitness_records":
            for i in range(n):
                records.append(
                    EvolutionaryMemoryRecord(
                        record_id=f"unsafe_{uuid.uuid4().hex[:6]}",
                        source_cycle_id="c1",
                        source_task="t55",
                        source_profile=profile.name,
                        fitness_delta=random.uniform(0.5, 1.0),
                        phi_delta=random.uniform(-0.3, -0.05),
                        safety_score=random.uniform(0.1, 0.35),
                        confidence=random.uniform(0.3, 0.7),
                        drift_score=random.uniform(0.0, 0.3),
                        regression_score=random.uniform(0.3, 0.6),
                        reuse_count=0,
                        status=EvolutionaryMemoryStatus.VOLATILE.value,
                    )
                )

        elif profile.name == "drift_accumulation_records":
            for i in range(n):
                records.append(
                    EvolutionaryMemoryRecord(
                        record_id=f"drift_{uuid.uuid4().hex[:6]}",
                        source_cycle_id="c1",
                        source_task="t56",
                        source_profile=profile.name,
                        fitness_delta=random.uniform(-0.2, 0.1),
                        phi_delta=random.uniform(-0.3, -0.05),
                        energy_delta=random.uniform(-0.3, -0.05),
                        cognitive_delta=random.uniform(-0.3, -0.05),
                        safety_score=random.uniform(0.4, 0.7),
                        confidence=random.uniform(0.2, 0.5),
                        drift_score=random.uniform(0.4, 0.7),
                        regression_score=random.uniform(0.3, 0.6),
                        reuse_count=0,
                        status=EvolutionaryMemoryStatus.VOLATILE.value,
                    )
                )

        elif profile.name == "conflicting_records":
            for i in range(n // 2):
                records.append(
                    EvolutionaryMemoryRecord(
                        record_id=f"conf_a_{uuid.uuid4().hex[:6]}",
                        source_cycle_id="c1",
                        source_task="t55",
                        source_profile=profile.name,
                        fitness_delta=random.uniform(0.3, 0.6),
                        phi_delta=random.uniform(0.05, 0.2),
                        energy_delta=random.uniform(0.05, 0.2),
                        safety_score=random.uniform(0.7, 1.0),
                        confidence=random.uniform(0.5, 0.9),
                        reuse_count=1,
                        status=EvolutionaryMemoryStatus.VOLATILE.value,
                    )
                )
                records.append(
                    EvolutionaryMemoryRecord(
                        record_id=f"conf_b_{uuid.uuid4().hex[:6]}",
                        source_cycle_id="c1",
                        source_task="t55",
                        source_profile=profile.name,
                        fitness_delta=random.uniform(0.3, 0.6),
                        phi_delta=random.uniform(-0.2, -0.05),
                        energy_delta=random.uniform(-0.2, -0.05),
                        safety_score=random.uniform(0.2, 0.5),
                        confidence=random.uniform(0.2, 0.5),
                        reuse_count=0,
                        status=EvolutionaryMemoryStatus.VOLATILE.value,
                    )
                )

        elif profile.name == "memory_bloat_profile":
            for i in range(n):
                records.append(
                    EvolutionaryMemoryRecord(
                        record_id=f"bloat_{uuid.uuid4().hex[:6]}",
                        source_cycle_id="c1",
                        source_task="t55",
                        source_profile=profile.name,
                        fitness_delta=random.uniform(-0.1, 0.15),
                        safety_score=random.uniform(0.4, 0.7),
                        confidence=random.uniform(0.1, 0.4),
                        reuse_count=0,
                        status=EvolutionaryMemoryStatus.VOLATILE.value,
                    )
                )

        elif profile.name == "forgetting_policy_profile":
            for i in range(n):
                records.append(
                    EvolutionaryMemoryRecord(
                        record_id=f"noise_{uuid.uuid4().hex[:6]}",
                        source_cycle_id="c1",
                        source_task="t55",
                        source_profile=profile.name,
                        fitness_delta=random.uniform(-0.6, -0.1),
                        safety_score=random.uniform(0.1, 0.4),
                        confidence=random.uniform(0.0, 0.2),
                        reuse_count=0,
                        status=EvolutionaryMemoryStatus.VOLATILE.value,
                    )
                )

        elif profile.name == "reused_useful_records":
            for i in range(n):
                records.append(
                    EvolutionaryMemoryRecord(
                        record_id=f"reuse_{uuid.uuid4().hex[:6]}",
                        source_cycle_id="c1",
                        source_task="t56",
                        source_profile=profile.name,
                        fitness_delta=random.uniform(0.2, 0.6),
                        phi_delta=random.uniform(0.0, 0.15),
                        safety_score=random.uniform(0.6, 1.0),
                        confidence=random.uniform(0.4, 0.9),
                        reuse_count=random.choice([2, 3, 5]),
                        status=EvolutionaryMemoryStatus.STABLE.value,
                    )
                )

        elif profile.name == "quarantined_reuse_attempt":
            for i in range(n):
                records.append(
                    EvolutionaryMemoryRecord(
                        record_id=f"quar_{uuid.uuid4().hex[:6]}",
                        source_cycle_id="c1",
                        source_task="t55",
                        source_profile=profile.name,
                        fitness_delta=random.uniform(-0.2, 0.3),
                        safety_score=random.uniform(0.1, 0.35),
                        confidence=random.uniform(0.1, 0.3),
                        reuse_count=0,
                        status=EvolutionaryMemoryStatus.QUARANTINED.value,
                    )
                )

        elif profile.name == "consolidation_too_weak":
            for i in range(n):
                records.append(
                    EvolutionaryMemoryRecord(
                        record_id=f"weak_{uuid.uuid4().hex[:6]}",
                        source_cycle_id="c1",
                        source_task="t55",
                        source_profile=profile.name,
                        fitness_delta=random.uniform(0.05, 0.2),
                        safety_score=random.uniform(0.4, 0.55),
                        confidence=random.uniform(0.2, 0.4),
                        reuse_count=0,
                        status=EvolutionaryMemoryStatus.EXPERIMENTAL.value,
                    )
                )

        elif profile.name == "full_governance_realistic_profile":
            # Mix realistico
            for i in range(5):
                records.append(
                    EvolutionaryMemoryRecord(
                        record_id=f"real_safe_{i}_{uuid.uuid4().hex[:4]}",
                        source_cycle_id="c1",
                        source_task="t56",
                        source_profile=profile.name,
                        fitness_delta=random.uniform(0.2, 0.6),
                        phi_delta=random.uniform(0.0, 0.1),
                        safety_score=random.uniform(0.7, 1.0),
                        confidence=random.uniform(0.5, 0.9),
                        reuse_count=random.choice([0, 1, 2]),
                        status=EvolutionaryMemoryStatus.VOLATILE.value,
                    )
                )
            for i in range(5):
                records.append(
                    EvolutionaryMemoryRecord(
                        record_id=f"real_unsafe_{i}_{uuid.uuid4().hex[:4]}",
                        source_cycle_id="c1",
                        source_task="t56",
                        source_profile=profile.name,
                        fitness_delta=random.uniform(0.3, 0.7),
                        phi_delta=random.uniform(-0.2, 0.0),
                        safety_score=random.uniform(0.1, 0.4),
                        confidence=random.uniform(0.2, 0.6),
                        reuse_count=0,
                        status=EvolutionaryMemoryStatus.VOLATILE.value,
                    )
                )
            for i in range(5):
                records.append(
                    EvolutionaryMemoryRecord(
                        record_id=f"real_noise_{i}_{uuid.uuid4().hex[:4]}",
                        source_cycle_id="c1",
                        source_task="t56",
                        source_profile=profile.name,
                        fitness_delta=random.uniform(-0.5, -0.1),
                        safety_score=random.uniform(0.2, 0.5),
                        confidence=random.uniform(0.0, 0.2),
                        reuse_count=0,
                        status=EvolutionaryMemoryStatus.VOLATILE.value,
                    )
                )
            for i in range(5):
                records.append(
                    EvolutionaryMemoryRecord(
                        record_id=f"real_reuse_{i}_{uuid.uuid4().hex[:4]}",
                        source_cycle_id="c1",
                        source_task="t56b",
                        source_profile=profile.name,
                        fitness_delta=random.uniform(0.1, 0.4),
                        phi_delta=random.uniform(-0.05, 0.1),
                        safety_score=random.uniform(0.5, 0.9),
                        confidence=random.uniform(0.3, 0.7),
                        reuse_count=random.choice([1, 2, 3]),
                        status=EvolutionaryMemoryStatus.PROBATIONARY.value,
                    )
                )

        else:
            # Fallback generico
            for i in range(n):
                records.append(
                    EvolutionaryMemoryRecord(
                        record_id=f"gen_{uuid.uuid4().hex[:6]}",
                        source_cycle_id="c1",
                        source_task="t55",
                        source_profile=profile.name,
                        fitness_delta=random.uniform(-0.2, 0.4),
                        safety_score=random.uniform(0.3, 0.8),
                        confidence=random.uniform(0.1, 0.6),
                        reuse_count=0,
                        status=EvolutionaryMemoryStatus.VOLATILE.value,
                    )
                )

        return records

    # ------------------------------------------------------------------ #
    # Audit execution
    # ------------------------------------------------------------------ #

    def run_profile(
        self,
        profile: GovernanceAuditProfile,
    ) -> GovernanceAuditProfileResult:
        # Reset store per profilo isolato
        self.governor = EvolutionaryMemoryGovernor(
            store=EvolutionaryMemoryStore(report_dir=str(self.reports_dir)),
            consolidation=ConsolidationPolicyEngine(),
            conflict_resolver=MemoryConflictResolver(),
            forgetting_engine=EvolutionaryForgettingEngine(),
            report_dir=str(self.reports_dir),
        )

        real_records = self.load_real_records_if_available() if profile.require_real_records else []
        synthetic_records = self.build_synthetic_records_for_profile(profile)

        all_records = real_records + synthetic_records
        for r in all_records:
            self.governor.store.add_record(r)

        # Esegui governance cycle
        cycle_result = self.governor.run_governance_cycle()

        # Audit
        audit = EvolutionaryMemoryAudit(self.governor.store)
        audit_result = audit.run_audit()

        # Conta unsafe promotions
        unsafe_promotion_count = 0
        quarantined_reuse_blocked_count = 0
        for r in self.governor.store.list_records():
            if r.status == EvolutionaryMemoryStatus.STABLE.value and r.safety_score < 0.5:
                unsafe_promotion_count += 1
            if r.status == EvolutionaryMemoryStatus.QUARANTINED.value and r.reuse_count > 0:
                quarantined_reuse_blocked_count += 1

        # Calcola promoted/degraded
        promoted = sum(
            1
            for r in self.governor.store.list_records()
            if r.status in (EvolutionaryMemoryStatus.STABLE.value, EvolutionaryMemoryStatus.PROBATIONARY.value)
        )
        degraded = sum(
            1
            for r in self.governor.store.list_records()
            if r.status in (EvolutionaryMemoryStatus.DEPRECATED.value, EvolutionaryMemoryStatus.FORGOTTEN.value)
        )
        quarantined = self.governor.store.count_by_status(EvolutionaryMemoryStatus.QUARANTINED.value)
        forgotten = self.governor.store.count_by_status(EvolutionaryMemoryStatus.FORGOTTEN.value)

        # Calcola drift aggregato dai record per i profili specifici
        mean_drift = sum(r.drift_score for r in self.governor.store.list_records()) / max(1, self.governor.store.total_records())

        verdict = audit_result.verdict
        # Override verdict per profili specifici
        if profile.expected_risk_type and profile.expected_risk_type != verdict:
            # Se l'audit non ha rilevato il rischio atteso, verifichiamo manualmente
            if profile.name == "unsafe_high_fitness_records" and unsafe_promotion_count > 0:
                verdict = "UNSAFE_MEMORY_PROMOTION_DETECTED"
            elif profile.name == "drift_accumulation_records" and mean_drift > 0.3:
                verdict = "EVOLUTIONARY_MEMORY_DRIFT_DETECTED"
            elif profile.name == "memory_bloat_profile" and audit_result.memory_bloat_score > 0.3:
                verdict = "MEMORY_BLOAT_DETECTED"
            elif profile.name == "quarantined_reuse_attempt" and quarantined_reuse_blocked_count > 0:
                verdict = "QUARANTINED_REUSE_BLOCKED"
            elif profile.name == "consolidation_too_weak" and promoted == 0 and len(all_records) > 3:
                verdict = "CONSOLIDATION_TOO_WEAK"
            elif profile.name == "conflicting_records" and audit_result.conflict_count == 0 and len(all_records) > 1:
                # Se ci sono record contraddittori ma nessun conflitto rilevato
                pass

        return GovernanceAuditProfileResult(
            profile_name=profile.name,
            input_record_count=len(all_records),
            promoted_count=promoted,
            degraded_count=degraded,
            quarantined_count=quarantined,
            forgotten_count=forgotten,
            conflict_count=audit_result.conflict_count,
            resolved_conflict_count=audit_result.resolved_conflict_count,
            unsafe_promotion_count=unsafe_promotion_count,
            quarantined_reuse_blocked_count=quarantined_reuse_blocked_count,
            memory_bloat_score=audit_result.memory_bloat_score,
            memory_quality_score=audit_result.memory_quality_score,
            governance_score=audit_result.governance_score,
            verdict=verdict,
        )

    def run_audit_suite(self) -> GovernanceAuditSuiteResult:
        profiles = self.build_default_profiles()
        results: List[GovernanceAuditProfileResult] = []
        total_records = 0
        total_promoted = 0
        total_quarantined = 0
        total_forgotten = 0
        total_conflicts = 0
        total_unsafe_promotions = 0

        for profile in profiles:
            result = self.run_profile(profile)
            results.append(result)
            total_records += result.input_record_count
            total_promoted += result.promoted_count
            total_quarantined += result.quarantined_count
            total_forgotten += result.forgotten_count
            total_conflicts += result.conflict_count
            total_unsafe_promotions += result.unsafe_promotion_count

        aggregate_memory_quality = (
            sum(r.memory_quality_score for r in results) / len(results) if results else 0.0
        )
        aggregate_governance = (
            sum(r.governance_score for r in results) / len(results) if results else 0.0
        )
        aggregate_bloat = (
            sum(r.memory_bloat_score for r in results) / len(results) if results else 0.0
        )

        aggregate_verdict = self.compute_aggregate_verdict(results)
        proceed_to_t58 = aggregate_verdict in (
            "EVOLUTIONARY_MEMORY_GOVERNANCE_REAL_RUN_VALIDATED",
            "GOVERNANCE_SAFE_BUT_PASSIVE",
        ) and total_unsafe_promotions == 0

        return GovernanceAuditSuiteResult(
            profile_count=len(profiles),
            total_records_processed=total_records,
            total_promoted_count=total_promoted,
            total_quarantined_count=total_quarantined,
            total_forgotten_count=total_forgotten,
            total_conflict_count=total_conflicts,
            total_unsafe_promotion_count=total_unsafe_promotions,
            aggregate_memory_quality_score=aggregate_memory_quality,
            aggregate_governance_score=aggregate_governance,
            aggregate_bloat_score=aggregate_bloat,
            aggregate_verdict=aggregate_verdict,
            proceed_to_t58=proceed_to_t58,
            profile_results=results,
        )

    def compute_aggregate_verdict(
        self,
        results: List[GovernanceAuditProfileResult],
    ) -> str:
        unsafe = sum(1 for r in results if r.verdict == "UNSAFE_MEMORY_PROMOTION_DETECTED")
        quarantine_reuse = sum(1 for r in results if r.verdict == "QUARANTINED_REUSE_DETECTED")
        bloat = sum(1 for r in results if r.verdict == "MEMORY_BLOAT_DETECTED")
        conflict_weak = sum(1 for r in results if r.verdict == "CONFLICT_RESOLUTION_WEAK")
        forgetting_agg = sum(1 for r in results if r.verdict == "FORGETTING_POLICY_TOO_AGGRESSIVE")
        consolidation_weak = sum(1 for r in results if r.verdict == "CONSOLIDATION_TOO_WEAK")
        drift = sum(1 for r in results if r.verdict == "EVOLUTIONARY_MEMORY_DRIFT_DETECTED")
        insufficient = sum(1 for r in results if r.verdict == "INSUFFICIENT_EVIDENCE")

        if unsafe > 0:
            return "UNSAFE_MEMORY_PROMOTION_DETECTED"
        if quarantine_reuse > 0:
            return "QUARANTINED_REUSE_DETECTED"
        if bloat > 0:
            return "MEMORY_BLOAT_DETECTED"
        if conflict_weak > 0:
            return "CONFLICT_RESOLUTION_WEAK"
        if forgetting_agg > 0:
            return "FORGETTING_POLICY_TOO_AGGRESSIVE"
        if consolidation_weak > 0:
            return "CONSOLIDATION_TOO_WEAK"
        if drift > 0:
            return "EVOLUTIONARY_MEMORY_DRIFT_DETECTED"

        scores = [r.governance_score for r in results if r.input_record_count > 0]
        mean_score = sum(scores) / len(scores) if scores else 0.0
        bloat_scores = [r.memory_bloat_score for r in results if r.input_record_count > 0]
        mean_bloat = sum(bloat_scores) / len(bloat_scores) if bloat_scores else 0.0

        if mean_score >= 0.70 and mean_bloat <= 0.30 and insufficient == 0:
            return "EVOLUTIONARY_MEMORY_GOVERNANCE_REAL_RUN_VALIDATED"
        if mean_score >= 0.45:
            return "GOVERNANCE_SAFE_BUT_PASSIVE"
        if insufficient == len(results):
            return "GOVERNANCE_INSUFFICIENT_EVIDENCE"
        return "GOVERNANCE_INSUFFICIENT_EVIDENCE"

    # ------------------------------------------------------------------ #
    # Reports
    # ------------------------------------------------------------------ #

    def generate_json_report(
        self,
        suite_result: GovernanceAuditSuiteResult,
    ) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.reports_dir / f"t57b_audit_{timestamp}.json"
        path.write_text(suite_result.model_dump_json(indent=2), encoding="utf-8")
        return str(path)

    def generate_markdown_report(
        self,
        suite_result: GovernanceAuditSuiteResult,
    ) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.reports_dir / f"t57b_audit_{timestamp}.md"
        lines = [
            "# T57B — Evolutionary Memory Governance Real-Run Audit Report",
            f"**Date:** {suite_result.timestamp}",
            f"**Aggregate Verdict:** `{suite_result.aggregate_verdict}`",
            f"**Proceed to T58:** {suite_result.proceed_to_t58}",
            "",
            "## Aggregate Metrics",
            f"- Profiles Run: {suite_result.profile_count}",
            f"- Total Records Processed: {suite_result.total_records_processed}",
            f"- Total Promoted: {suite_result.total_promoted_count}",
            f"- Total Quarantined: {suite_result.total_quarantined_count}",
            f"- Total Forgotten: {suite_result.total_forgotten_count}",
            f"- Total Conflicts: {suite_result.total_conflict_count}",
            f"- Unsafe Promotions: {suite_result.total_unsafe_promotion_count}",
            f"- Aggregate Memory Quality: {suite_result.aggregate_memory_quality_score:.4f}",
            f"- Aggregate Governance: {suite_result.aggregate_governance_score:.4f}",
            f"- Aggregate Bloat: {suite_result.aggregate_bloat_score:.4f}",
            "",
            "## Profile Results",
        ]
        for r in suite_result.profile_results:
            lines.append(f"### {r.profile_name}")
            lines.append(f"- Records: {r.input_record_count}")
            lines.append(f"- Promoted: {r.promoted_count}")
            lines.append(f"- Quarantined: {r.quarantined_count}")
            lines.append(f"- Forgotten: {r.forgotten_count}")
            lines.append(f"- Conflicts: {r.conflict_count}")
            lines.append(f"- Unsafe Promotions: {r.unsafe_promotion_count}")
            lines.append(f"- Memory Quality: {r.memory_quality_score:.4f}")
            lines.append(f"- Governance: {r.governance_score:.4f}")
            lines.append(f"- Verdict: `{r.verdict}`")
            lines.append("")
        lines.append("---")
        lines.append("*Generated by EvolutionaryMemoryGovernanceAuditRunner (T57B)*")
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)
