import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.memory.morphology_events import MorphologyEvent, MorphologyEventType
from speace_core.cellular_brain.self_improvement.outcome_tracker import ProposalOutcome


class ProposalLearningRecord(BaseModel):
    limitation_type: str
    proposed_task_id: str
    attempts: int = 0
    successes: int = 0
    partial_successes: int = 0
    regressions: int = 0
    mean_net_gain: float = 0.0
    confidence: float = 0.0
    last_outcome_id: Optional[str] = None


class ProposalLearningEngine:
    """T46 — Learn from proposal outcomes and update mapping confidence."""

    def __init__(
        self,
        base_path: str = "data/self_improvement",
        memory=None,
    ):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.records_path = self.base_path / "learning_records.jsonl"
        self.memory = memory
        self._records: Dict[str, ProposalLearningRecord] = {}
        self._load_records()

    # ------------------------------------------------------------------ #
    # Record update
    # ------------------------------------------------------------------ #

    def update_from_outcome(self, outcome: ProposalOutcome) -> ProposalLearningRecord:
        key = f"{outcome.originating_limitation_type}-{outcome.implemented_task_id}"
        record = self._records.get(key)
        if record is None:
            record = ProposalLearningRecord(
                limitation_type=outcome.originating_limitation_type,
                proposed_task_id=outcome.implemented_task_id,
            )

        record.attempts += 1
        if outcome.success:
            record.successes += 1
        elif outcome.partial_success:
            record.partial_successes += 1
        if outcome.regression_detected:
            record.regressions += 1

        # Incremental mean net gain
        old_mean = record.mean_net_gain
        n = record.attempts
        record.mean_net_gain = old_mean + (outcome.net_gain - old_mean) / n
        record.mean_net_gain = round(record.mean_net_gain, 4)

        record.confidence = self._compute_confidence(record)
        record.last_outcome_id = outcome.id

        self._records[key] = record
        self._persist_record(record)

        event_type = (
            MorphologyEventType.SELF_IMPROVEMENT_MAPPING_REINFORCED
            if outcome.success
            else MorphologyEventType.SELF_IMPROVEMENT_MAPPING_WEAKENED
            if outcome.regression_detected
            else MorphologyEventType.SELF_IMPROVEMENT_CONFIDENCE_UPDATED
        )
        self._log_event(
            event_type,
            {
                "record_key": key,
                "limitation_type": record.limitation_type,
                "proposed_task_id": record.proposed_task_id,
                "attempts": record.attempts,
                "successes": record.successes,
                "regressions": record.regressions,
                "confidence": record.confidence,
                "mean_net_gain": record.mean_net_gain,
                "outcome_id": outcome.id,
            },
        )

        return record

    # ------------------------------------------------------------------ #
    # Confidence formula
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_confidence(record: ProposalLearningRecord) -> float:
        if record.attempts == 0:
            return 0.0
        success_rate = record.successes / record.attempts
        partial_rate = record.partial_successes / record.attempts
        regression_rate = record.regressions / record.attempts
        normalized_gain = max(-1.0, min(1.0, record.mean_net_gain))
        # Map [-1, 1] to [0, 1]
        normalized_gain = (normalized_gain + 1.0) / 2.0

        confidence = (
            0.35 * success_rate
            + 0.25 * partial_rate
            + 0.25 * normalized_gain
            - 0.15 * regression_rate
        )
        return round(max(0.0, min(1.0, confidence)), 4)

    # ------------------------------------------------------------------ #
    # Retrieval
    # ------------------------------------------------------------------ #

    def get_learning_record(
        self,
        limitation_type: str,
        proposed_task_id: str,
    ) -> Optional[ProposalLearningRecord]:
        key = f"{limitation_type}-{proposed_task_id}"
        return self._records.get(key)

    def load_learning_records(self) -> List[ProposalLearningRecord]:
        return list(self._records.values())

    # ------------------------------------------------------------------ #
    # Ranking
    # ------------------------------------------------------------------ #

    def rank_candidate_proposals(
        self,
        limitation_type: str,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Rank candidates by learned confidence for this limitation type."""
        scored = []
        for cand in candidates:
            task_id = cand.get("task_id") or cand.get("proposed_task_id") or cand.get("title", "")
            record = self.get_learning_record(limitation_type, task_id)
            if record is not None:
                score = record.confidence
                # Boost for known successes, penalize regressions
                if record.regressions > 0:
                    score *= 0.5
                if record.successes > 0:
                    score += 0.1
            else:
                score = 0.0
            scored.append((score, cand))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [cand for _, cand in scored]

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _persist_record(self, record: ProposalLearningRecord) -> None:
        # Read all existing, replace this key, rewrite
        all_records: Dict[str, ProposalLearningRecord] = {}
        if self.records_path.exists():
            with open(self.records_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    data.pop("_stored_at", None)
                    r = ProposalLearningRecord(**data)
                    all_records[f"{r.limitation_type}-{r.proposed_task_id}"] = r
        key = f"{record.limitation_type}-{record.proposed_task_id}"
        all_records[key] = record
        with open(self.records_path, "w", encoding="utf-8") as f:
            for r in all_records.values():
                data = r.model_dump()
                data["_stored_at"] = datetime.now(timezone.utc).isoformat()
                f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def _load_records(self) -> None:
        if not self.records_path.exists():
            return
        with open(self.records_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                data.pop("_stored_at", None)
                record = ProposalLearningRecord(**data)
                key = f"{record.limitation_type}-{record.proposed_task_id}"
                self._records[key] = record

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _log_event(
        self,
        event_type: MorphologyEventType,
        metadata: Dict[str, Any],
    ) -> None:
        if self.memory is None or not hasattr(self.memory, "log_event"):
            return
        try:
            event = MorphologyEvent(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=event_type,
                timestamp=datetime.now(timezone.utc).timestamp(),
                metadata=metadata,
            )
            self.memory.log_event(event)
        except Exception:
            logging.getLogger(__name__).warning("Proposal learning step failed", exc_info=True)
