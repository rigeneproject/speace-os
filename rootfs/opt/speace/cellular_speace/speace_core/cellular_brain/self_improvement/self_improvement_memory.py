import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.memory.morphology_events import MorphologyEvent, MorphologyEventType


class SelfImprovementHistoryEntry(BaseModel):
    entry_id: str
    entry_type: str
    timestamp: str
    data: Dict[str, Any] = Field(default_factory=dict)


class SelfImprovementMemory:
    """T46 — Persistent memory for self-improvement cycles, outcomes, and learned mappings."""

    def __init__(
        self,
        base_path: str = "data/self_improvement",
        memory=None,
    ):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.history_path = self.base_path / "history.jsonl"
        self.memory = memory

    # ------------------------------------------------------------------ #
    # History logging
    # ------------------------------------------------------------------ #

    def write_history_event(
        self,
        entry_type: str,
        data: Dict[str, Any],
    ) -> SelfImprovementHistoryEntry:
        entry = SelfImprovementHistoryEntry(
            entry_id=f"sim-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{hash(str(data)) & 0xFFFF:04x}",
            entry_type=entry_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=data,
        )
        record = entry.model_dump()
        with open(self.history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return entry

    def load_history(self) -> List[SelfImprovementHistoryEntry]:
        results: List[SelfImprovementHistoryEntry] = []
        if not self.history_path.exists():
            return results
        with open(self.history_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                results.append(SelfImprovementHistoryEntry(**data))
        return results

    def get_history_by_type(self, entry_type: str) -> List[SelfImprovementHistoryEntry]:
        return [e for e in self.load_history() if e.entry_type == entry_type]

    # ------------------------------------------------------------------ #
    # Convenience wrappers
    # ------------------------------------------------------------------ #

    def record_limitation_detected(self, limitation_type: str, details: Dict[str, Any]) -> SelfImprovementHistoryEntry:
        return self.write_history_event("limitation_detected", {"limitation_type": limitation_type, **details})

    def record_proposal_generated(self, proposal_id: str, limitation_type: str, task_id: str) -> SelfImprovementHistoryEntry:
        return self.write_history_event("proposal_generated", {
            "proposal_id": proposal_id,
            "limitation_type": limitation_type,
            "task_id": task_id,
        })

    def record_proposal_accepted(self, proposal_id: str, limitation_type: str) -> SelfImprovementHistoryEntry:
        return self.write_history_event("proposal_accepted", {
            "proposal_id": proposal_id,
            "limitation_type": limitation_type,
        })

    def record_proposal_rejected(self, proposal_id: str, limitation_type: str, reason: str) -> SelfImprovementHistoryEntry:
        return self.write_history_event("proposal_rejected", {
            "proposal_id": proposal_id,
            "limitation_type": limitation_type,
            "reason": reason,
        })

    def record_audit_outcome(self, outcome_id: str, proposal_id: str, verdict: str, net_gain: float) -> SelfImprovementHistoryEntry:
        return self.write_history_event("audit_outcome", {
            "outcome_id": outcome_id,
            "proposal_id": proposal_id,
            "verdict": verdict,
            "net_gain": net_gain,
        })

    def record_learning_update(
        self,
        limitation_type: str,
        task_id: str,
        confidence: float,
        mean_net_gain: float,
    ) -> SelfImprovementHistoryEntry:
        return self.write_history_event("learning_update", {
            "limitation_type": limitation_type,
            "task_id": task_id,
            "confidence": confidence,
            "mean_net_gain": mean_net_gain,
        })

    # ------------------------------------------------------------------ #
    # Summary helpers
    # ------------------------------------------------------------------ #

    def summarize(self) -> Dict[str, Any]:
        history = self.load_history()
        return {
            "total_entries": len(history),
            "limitation_count": len([e for e in history if e.entry_type == "limitation_detected"]),
            "proposal_count": len([e for e in history if e.entry_type == "proposal_generated"]),
            "accepted_count": len([e for e in history if e.entry_type == "proposal_accepted"]),
            "rejected_count": len([e for e in history if e.entry_type == "proposal_rejected"]),
            "outcome_count": len([e for e in history if e.entry_type == "audit_outcome"]),
            "learning_update_count": len([e for e in history if e.entry_type == "learning_update"]),
        }
