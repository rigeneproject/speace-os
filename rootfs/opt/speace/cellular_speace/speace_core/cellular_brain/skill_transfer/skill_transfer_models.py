from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SkillTransferState(str, Enum):
    NOT_OBSERVED = "not_observed"
    TRANSFER_CANDIDATE = "transfer_candidate"
    TRANSFER_TESTED = "transfer_tested"
    TRANSFERRED_SANDBOXED = "transferred_sandboxed"
    GENERALIZES_SANDBOXED = "generalizes_sandboxed"
    OVERFITTED = "overfitted"
    NEGATIVE_TRANSFER = "negative_transfer"
    SAFETY_BLOCKED = "safety_blocked"
    QUARANTINED = "quarantined"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class SkillTransferCandidate(BaseModel):
    skill_id: str
    source_capability_id: str = ""
    name: str = ""
    description: str = ""
    source_maturity_score: float = 0.0
    source_confidence_score: float = 0.0
    source_safety_score: float = 0.0
    sandbox_only: bool = True
    real_world_enabled: bool = False
    eligible_for_transfer: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TransferScenario(BaseModel):
    scenario_id: str
    name: str = ""
    description: str = ""
    source_domain: str = ""
    target_domain: str = ""
    novelty_score: float = 0.0
    difficulty_score: float = 0.0
    risk_score: float = 0.0
    requires_external_action: bool = False
    simulated_only: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SkillTransferResult(BaseModel):
    skill_id: str = ""
    scenario_id: str = ""
    transfer_state: SkillTransferState = SkillTransferState.NOT_OBSERVED
    transfer_success_score: float = 0.0
    generalization_score: float = 0.0
    overfitting_score: float = 0.0
    negative_transfer_score: float = 0.0
    safety_score: float = 0.0
    confidence_score: float = 0.0
    read_only_integrity_score: float = 1.0
    sandbox_only: bool = True
    real_world_enabled: bool = False
    blocked: bool = False
    quarantined: bool = False
    verdict: str = "SKILL_TRANSFER_INSUFFICIENT_EVIDENCE"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SkillTransferAuditResult(BaseModel):
    candidate_count: int = 0
    scenario_count: int = 0
    transfer_attempt_count: int = 0
    transferred_sandboxed_count: int = 0
    generalized_sandboxed_count: int = 0
    overfitted_count: int = 0
    negative_transfer_count: int = 0
    safety_blocked_count: int = 0
    quarantined_count: int = 0
    unsafe_transfer_enabled_count: int = 0
    real_world_enabled_count: int = 0
    aggregate_transfer_score: float = 0.0
    aggregate_generalization_score: float = 0.0
    aggregate_safety_score: float = 0.0
    aggregate_read_only_integrity_score: float = 1.0
    read_only_integrity_score: float = 1.0
    transfer_verdict: str = "SKILL_TRANSFER_INSUFFICIENT_EVIDENCE"
    proceed_to_t65b: bool = False
    results: List[SkillTransferResult] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SkillTransferRealRunProfile(BaseModel):
    name: str
    description: str = ""
    duration_cycles: int = 3
    candidate_skill_ids: List[str] = Field(default_factory=list)
    scenario_count: int = 8
    source_domain: str = ""
    target_domain: str = ""
    novelty_pressure: float = 0.0
    difficulty_pressure: float = 0.0
    noise_pressure: float = 0.0
    conflict_pressure: float = 0.0
    overfitting_pressure: float = 0.0
    negative_transfer_pressure: float = 0.0
    safety_risk_pressure: float = 0.0
    real_world_enable_attempts: int = 0
    expected_verdict_type: Optional[str] = None
    simulated_only: bool = True
    requires_real_fixtures: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SkillTransferRealRunProfileResult(BaseModel):
    profile_name: str
    cycles_run: int = 0
    candidates_evaluated: int = 0
    scenarios_run: int = 0
    transfer_attempts: int = 0
    successful_transfers: int = 0
    generalized_sandboxed_count: int = 0
    overfitted_count: int = 0
    negative_transfer_count: int = 0
    safety_blocked_count: int = 0
    quarantined_count: int = 0
    real_world_enable_attempts: int = 0
    real_world_enable_attempts_blocked: int = 0
    unsafe_transfer_enabled_count: int = 0
    read_only_violation_count: int = 0
    average_transfer_score: float = 0.0
    average_generalization_score: float = 0.0
    average_novelty_adaptation_score: float = 0.0
    average_safety_score: float = 0.0
    average_confidence_score: float = 0.0
    average_overfitting_score: float = 0.0
    average_negative_transfer_score: float = 0.0
    read_only_integrity_score: float = 1.0
    skill_transfer_real_run_score: float = 0.0
    verdict: str = "SKILL_TRANSFER_REAL_RUN_INSUFFICIENT_EVIDENCE"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SkillTransferRealRunSuiteResult(BaseModel):
    profile_count: int = 0
    total_cycles_run: int = 0
    total_candidates_evaluated: int = 0
    total_scenarios_run: int = 0
    total_transfer_attempts: int = 0
    total_successful_transfers: int = 0
    total_generalized_sandboxed_count: int = 0
    total_overfitted_count: int = 0
    total_negative_transfer_count: int = 0
    total_safety_blocked_count: int = 0
    total_quarantined_count: int = 0
    total_real_world_enable_attempts: int = 0
    total_real_world_enable_attempts_blocked: int = 0
    total_unsafe_transfer_enabled_count: int = 0
    total_read_only_violation_count: int = 0
    aggregate_transfer_score: float = 0.0
    aggregate_generalization_score: float = 0.0
    aggregate_novelty_adaptation_score: float = 0.0
    aggregate_safety_score: float = 0.0
    aggregate_confidence_score: float = 0.0
    aggregate_overfitting_score: float = 0.0
    aggregate_negative_transfer_score: float = 0.0
    aggregate_read_only_integrity_score: float = 1.0
    aggregate_skill_transfer_real_run_score: float = 0.0
    aggregate_verdict: str = "SKILL_TRANSFER_REAL_RUN_INSUFFICIENT_EVIDENCE"
    proceed_to_t66: bool = False
    profile_results: List[SkillTransferRealRunProfileResult] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
