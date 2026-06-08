from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EvolutionaryMemoryStatus(str, Enum):
    VOLATILE = "volatile"
    EXPERIMENTAL = "experimental"
    PROBATIONARY = "probationary"
    STABLE = "stable"
    FROZEN_POLICY = "frozen_policy"
    QUARANTINED = "quarantined"
    DEPRECATED = "deprecated"
    FORGOTTEN = "forgotten"


class EvolutionaryMemoryRecord(BaseModel):
    record_id: str
    source_cycle_id: str
    source_task: str
    source_profile: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    variant_id: Optional[str] = None
    mutation_type: Optional[str] = None
    perturbation_type: Optional[str] = None
    fitness_delta: float = 0.0
    phi_delta: float = 0.0
    energy_delta: float = 0.0
    cognitive_delta: float = 0.0
    recovery_score: float = 0.0
    drift_score: float = 0.0
    regression_score: float = 0.0
    safety_score: float = 0.5
    confidence: float = 0.0
    generalization_score: float = 0.0
    reuse_count: int = 0
    status: str = EvolutionaryMemoryStatus.VOLATILE.value
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConsolidationDecision(BaseModel):
    record_id: str
    previous_status: str
    new_status: str
    reason: str
    confidence_delta: float = 0.0
    governance_verdict: str = ""
    requires_human_review: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MemoryConflict(BaseModel):
    conflict_id: str
    record_a_id: str
    record_b_id: str
    conflict_type: str
    severity: float = Field(default=0.0, ge=0.0, le=1.0)
    resolution: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvolutionaryMemoryAuditResult(BaseModel):
    total_records: int = 0
    stable_records: int = 0
    experimental_records: int = 0
    quarantined_records: int = 0
    forgotten_records: int = 0
    conflict_count: int = 0
    resolved_conflict_count: int = 0
    memory_bloat_score: float = 0.0
    memory_quality_score: float = 0.0
    consolidation_score: float = 0.0
    forgetting_score: float = 0.0
    governance_score: float = 0.0
    verdict: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GovernanceAuditProfile(BaseModel):
    name: str
    description: str = ""
    record_count: int = 0
    expected_risk_type: Optional[str] = None
    require_real_records: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GovernanceAuditProfileResult(BaseModel):
    profile_name: str
    input_record_count: int = 0
    promoted_count: int = 0
    degraded_count: int = 0
    quarantined_count: int = 0
    forgotten_count: int = 0
    conflict_count: int = 0
    resolved_conflict_count: int = 0
    unsafe_promotion_count: int = 0
    quarantined_reuse_blocked_count: int = 0
    memory_bloat_score: float = 0.0
    memory_quality_score: float = 0.0
    governance_score: float = 0.0
    verdict: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GovernanceAuditSuiteResult(BaseModel):
    profile_count: int = 0
    total_records_processed: int = 0
    total_promoted_count: int = 0
    total_quarantined_count: int = 0
    total_forgotten_count: int = 0
    total_conflict_count: int = 0
    total_unsafe_promotion_count: int = 0
    aggregate_memory_quality_score: float = 0.0
    aggregate_governance_score: float = 0.0
    aggregate_bloat_score: float = 0.0
    aggregate_verdict: str = ""
    proceed_to_t58: bool = False
    profile_results: List[GovernanceAuditProfileResult] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
