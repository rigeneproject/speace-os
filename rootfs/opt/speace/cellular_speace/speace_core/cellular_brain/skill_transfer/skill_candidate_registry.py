from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.skill_transfer.skill_transfer_models import (
    SkillTransferCandidate,
)


class SkillCandidateRegistry:
    """Registry of skill transfer candidates."""

    def __init__(self):
        self._records: Dict[str, SkillTransferCandidate] = {}

    def add_candidate(self, candidate: SkillTransferCandidate) -> None:
        self._records[candidate.skill_id] = candidate

    def get_candidate(self, skill_id: str) -> Optional[SkillTransferCandidate]:
        return self._records.get(skill_id)

    def get_all_candidates(self) -> List[SkillTransferCandidate]:
        return list(self._records.values())

    def update_candidate(self, skill_id: str, **kwargs: Any) -> None:
        record = self._records.get(skill_id)
        if record is None:
            return
        for key, value in kwargs.items():
            if key in SkillTransferCandidate.model_fields:
                setattr(record, key, value)

    def record_count(self) -> int:
        return len(self._records)
