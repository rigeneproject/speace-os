import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_models import (
    ConsolidationDecision,
    EvolutionaryMemoryRecord,
    EvolutionaryMemoryStatus,
)


class EvolutionaryMemoryStore:
    """T57 — Persistent store for evolutionary memory records."""

    def __init__(self, report_dir: str = "reports/evolutionary_memory"):
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self._records: Dict[str, EvolutionaryMemoryRecord] = {}
        self._decisions: List[ConsolidationDecision] = []

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #

    def add_record(self, record: EvolutionaryMemoryRecord) -> None:
        if record.record_id in self._records:
            return
        self._records[record.record_id] = record

    def get_record(self, record_id: str) -> Optional[EvolutionaryMemoryRecord]:
        return self._records.get(record_id)

    def list_records(
        self,
        status: Optional[str] = None,
        source_task: Optional[str] = None,
    ) -> List[EvolutionaryMemoryRecord]:
        results = list(self._records.values())
        if status is not None:
            results = [r for r in results if r.status == status]
        if source_task is not None:
            results = [r for r in results if r.source_task == source_task]
        return results

    def update_status(self, record_id: str, new_status: str, reason: str) -> ConsolidationDecision:
        record = self._records.get(record_id)
        if record is None:
            return ConsolidationDecision(
                record_id=record_id,
                previous_status="",
                new_status=new_status,
                reason=f"Record not found: {reason}",
            )
        decision = ConsolidationDecision(
            record_id=record_id,
            previous_status=record.status,
            new_status=new_status,
            reason=reason,
        )
        record.status = new_status
        self._decisions.append(decision)
        return decision

    def increment_reuse(self, record_id: str) -> None:
        record = self._records.get(record_id)
        if record is not None:
            record.reuse_count += 1

    # ------------------------------------------------------------------ #
    # Export
    # ------------------------------------------------------------------ #

    def export_json(self, path: Optional[Path] = None) -> Path:
        target = path or self.report_dir / f"evolutionary_memory_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        data = [r.model_dump() for r in self._records.values()]
        target.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return target

    def export_markdown(self, path: Optional[Path] = None) -> Path:
        target = path or self.report_dir / f"evolutionary_memory_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
        lines = ["# Evolutionary Memory Store Report", f"**Records:** {len(self._records)}", ""]
        for status in EvolutionaryMemoryStatus:
            count = len([r for r in self._records.values() if r.status == status.value])
            lines.append(f"- {status.value}: {count}")
        lines.append("")
        lines.append("## Records")
        for r in self._records.values():
            lines.append(
                f"- {r.record_id} | status={r.status} | fitness_delta={r.fitness_delta:.4f} |"
                f" safety={r.safety_score:.4f} | reuse={r.reuse_count}"
            )
        target.write_text("\n".join(lines), encoding="utf-8")
        return target

    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #

    def count_by_status(self, status: str) -> int:
        return sum(1 for r in self._records.values() if r.status == status)

    def total_records(self) -> int:
        return len(self._records)

    def get_decisions(self) -> List[ConsolidationDecision]:
        return list(self._decisions)
