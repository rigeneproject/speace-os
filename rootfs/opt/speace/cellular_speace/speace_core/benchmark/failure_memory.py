"""Failure Memory — permanent record of every ARC failure.

Each failure captures:
  - Failure Pattern (grid-level description of what went wrong)
  - Failure Cause (why the engine couldn't solve it)
  - Failed Hypothesis (what program was tried)
  - Corrective Strategy (what primitive or composition would fix it)

Records persist across restarts in data/failure_memory/
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

FAILURE_MEMORY_DIR = Path("data/failure_memory")


@dataclass
class FailureRecord:
    task_id: str
    failure_pattern: str
    failure_cause: str
    failed_hypothesis: str
    corrective_strategy: str
    match_score: float = 0.0
    candidates_explored: int = 0
    train_examples: int = 0
    test_examples: int = 0
    input_shape: str = ""
    output_shape: str = ""
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    metadata: Dict[str, Any] = field(default_factory=dict)


class FailureMemoryStore:
    """Persistent store for failure records, backed by JSON files."""

    def __init__(self, directory: str | Path = FAILURE_MEMORY_DIR) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._records: Dict[str, List[FailureRecord]] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_failure(self, record: FailureRecord) -> None:
        task_id = record.task_id
        if task_id not in self._records:
            self._records[task_id] = []
        self._records[task_id].append(record)
        self._save_task(task_id)
        logger.info(
            "Failure recorded: %s | pattern=%s | cause=%s | strategy=%s",
            task_id, record.failure_pattern, record.failure_cause, record.corrective_strategy,
        )

    def get_failures(self, task_id: Optional[str] = None) -> List[FailureRecord]:
        if task_id:
            return self._records.get(task_id, [])
        all_records: List[FailureRecord] = []
        for records in self._records.values():
            all_records.extend(records)
        return all_records

    def get_failure_count(self) -> int:
        return sum(len(rs) for rs in self._records.values())

    def get_failure_patterns(self) -> Dict[str, int]:
        patterns: Dict[str, int] = {}
        for records in self._records.values():
            for r in records:
                patterns[r.failure_pattern] = patterns.get(r.failure_pattern, 0) + 1
        return patterns

    def get_failure_causes(self) -> Dict[str, int]:
        causes: Dict[str, int] = {}
        for records in self._records.values():
            for r in records:
                causes[r.failure_cause] = causes.get(r.failure_cause, 0) + 1
        return causes

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_failures": self.get_failure_count(),
            "unique_tasks": len(self._records),
            "failure_patterns": self.get_failure_patterns(),
            "failure_causes": self.get_failure_causes(),
            "tasks": {tid: len(rs) for tid, rs in self._records.items()},
        }

    # ------------------------------------------------------------------
    # Classification helpers
    # ------------------------------------------------------------------

    @staticmethod
    def classify_failure(
        task_id: str,
        candidates: int,
        match_score: float,
        train_count: int,
        test_count: int,
        input_shape: str,
        output_shape: str,
        best_explanation: str = "",
    ) -> FailureRecord:
        if candidates == 0:
            failure_pattern = "no_candidates"
            failure_cause = "nessuna primitiva o composizione matcha tutti i training pair"
            corrective_strategy = "aggiungere nuove primitive o estendere brute-force params"
        elif match_score == 0.0:
            failure_pattern = "prediction_mismatch"
            failure_cause = "candidato trovato ma prediczione test non corrisponde"
            corrective_strategy = "raffinare la composizione o aumentare profondità ricerca"
        elif match_score < 0.5:
            failure_pattern = "partial_match"
            failure_cause = "prediczione parziale (<50% pixel match)"
            corrective_strategy = "migliorare primitive per task o aggiungere pattern-specifiche"
        elif match_score < 1.0:
            failure_pattern = "near_match"
            failure_cause = "prediczione quasi corretta ma non esatta"
            corrective_strategy = "aggiungere varianti della primitiva candidate"
        else:
            failure_pattern = "unknown"
            failure_cause = "fallimento non classificato"
            corrective_strategy = "analizzare manualmente"

        return FailureRecord(
            task_id=task_id,
            failure_pattern=failure_pattern,
            failure_cause=failure_cause,
            failed_hypothesis=best_explanation or "nessuna",
            corrective_strategy=corrective_strategy,
            match_score=match_score,
            candidates_explored=candidates,
            train_examples=train_count,
            test_examples=test_count,
            input_shape=input_shape,
            output_shape=output_shape,
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        for path in self.directory.glob("*.json"):
            task_id = path.stem
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                records = [FailureRecord(**item) for item in data]
                self._records[task_id] = records
            except Exception as exc:
                logger.warning("Failed to load failure records from %s: %s", path, exc)

    def _save_task(self, task_id: str) -> None:
        records = self._records.get(task_id, [])
        path = self.directory / f"{task_id}.json"
        data = [asdict(r) for r in records]
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def _save_all(self) -> None:
        for task_id in self._records:
            self._save_task(task_id)
