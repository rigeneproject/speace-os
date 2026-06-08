import uuid
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.capability_maturation.capability_maturation_models import (
    CapabilityMaturityState,
    CapabilityRecord,
    CapabilityRiskClass,
)


DEFAULT_CAPABILITIES = [
    ("observation_stability", "Observation stability"),
    ("semantic_grounding", "Semantic grounding"),
    ("safe_imitation", "Safe imitation"),
    ("dangerous_trace_rejection", "Dangerous trace rejection"),
    ("causal_prediction", "Causal prediction"),
    ("error_correction", "Error correction"),
    ("regression_detection", "Regression detection"),
    ("memory_consolidation", "Memory consolidation"),
    ("memory_reuse", "Memory reuse"),
    ("memory_bloat_control", "Memory bloat control"),
    ("human_review_alignment", "Human review alignment"),
    ("action_simulation_safety", "Action simulation safety"),
    ("policy_conflict_resolution", "Policy conflict resolution"),
    ("read_only_integrity", "Read-only integrity"),
]


class CapabilityRegistry:
    """Registry of tracked capabilities."""

    def __init__(self):
        self._records: Dict[str, CapabilityRecord] = {}

    def initialize_defaults(self) -> None:
        for cid, name in DEFAULT_CAPABILITIES:
            self.add_capability(
                CapabilityRecord(
                    capability_id=cid,
                    name=name,
                    maturity_state=CapabilityMaturityState.UNOBSERVED,
                    risk_class=CapabilityRiskClass.UNKNOWN,
                )
            )

    def add_capability(self, record: CapabilityRecord) -> None:
        self._records[record.capability_id] = record

    def get_capability(self, capability_id: str) -> Optional[CapabilityRecord]:
        return self._records.get(capability_id)

    def get_all_capabilities(self) -> List[CapabilityRecord]:
        return list(self._records.values())

    def update_capability(self, capability_id: str, **kwargs: Any) -> None:
        record = self._records.get(capability_id)
        if record is None:
            return
        for key, value in kwargs.items():
            if key in CapabilityRecord.model_fields:
                setattr(record, key, value)

    def record_count(self) -> int:
        return len(self._records)
