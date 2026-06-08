from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CapabilityMaturityState(str, Enum):
    UNOBSERVED = "unobserved"
    EMERGING = "emerging"
    IMMATURE = "immature"
    MATURING = "maturing"
    MATURE_SANDBOXED = "mature_sandboxed"
    REGRESSIVE = "regressive"
    SAFETY_BLOCKED = "safety_blocked"
    QUARANTINED = "quarantined"
    DEPRECATED = "deprecated"


class CapabilityRiskClass(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class CapabilityRecord(BaseModel):
    capability_id: str
    name: str = ""
    description: str = ""
    maturity_state: CapabilityMaturityState = CapabilityMaturityState.UNOBSERVED
    risk_class: CapabilityRiskClass = CapabilityRiskClass.UNKNOWN
    evidence_count: int = 0
    success_rate: float = 0.0
    regression_rate: float = 0.0
    safety_violation_count: int = 0
    human_review_required_count: int = 0
    sandbox_only: bool = True
    real_world_enabled: bool = False
    confidence_score: float = 0.0
    maturity_score: float = 0.0
    last_updated_at: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CapabilityMaturationResult(BaseModel):
    capability_count: int = 0
    mature_sandboxed_count: int = 0
    immature_count: int = 0
    regressive_count: int = 0
    safety_blocked_count: int = 0
    quarantined_count: int = 0
    aggregate_maturity_score: float = 0.0
    aggregate_safety_score: float = 0.0
    aggregate_confidence_score: float = 0.0
    read_only_integrity_score: float = 0.0
    unsafe_capability_enabled_count: int = 0
    real_world_capability_enabled_count: int = 0
    maturity_verdict: str = "CAPABILITY_MATURATION_INSUFFICIENT_EVIDENCE"
    proceed_to_t64b: bool = False
    capability_records: List[CapabilityRecord] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CapabilityMaturationRealRunProfile(BaseModel):
    name: str
    description: str = ""
    duration_cycles: int = 3
    capability_ids: List[str] = Field(default_factory=list)
    evidence_volume: int = 3
    positive_evidence_ratio: float = 1.0
    weak_evidence_ratio: float = 0.0
    regression_ratio: float = 0.0
    safety_violation_ratio: float = 0.0
    quarantine_pressure: float = 0.0
    real_world_enable_attempts: int = 0
    maturity_drift_pressure: float = 0.0
    conflicting_evidence_level: float = 0.0
    expected_verdict_type: Optional[str] = None
    simulated_only: bool = True
    requires_real_fixtures: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CapabilityMaturationRealRunProfileResult(BaseModel):
    profile_name: str
    cycles_run: int = 0
    capabilities_evaluated: int = 0
    evidence_records_processed: int = 0
    mature_sandboxed_count: int = 0
    emerging_count: int = 0
    immature_count: int = 0
    regressive_count: int = 0
    safety_blocked_count: int = 0
    quarantined_count: int = 0
    conflicting_evidence_count: int = 0
    regressions_detected: int = 0
    regressions_isolated: int = 0
    safety_violations_detected: int = 0
    safety_violations_blocked: int = 0
    real_world_enable_attempts: int = 0
    real_world_enable_attempts_blocked: int = 0
    unsafe_capability_enabled_count: int = 0
    maturity_drift_detected_count: int = 0
    maturity_drift_blocked_count: int = 0
    average_maturity_score: float = 0.0
    average_confidence_score: float = 0.0
    average_safety_score: float = 0.0
    average_stability_score: float = 0.0
    read_only_integrity_score: float = 0.0
    capability_real_run_score: float = 0.0
    verdict: str = "CAPABILITY_MATURATION_REAL_RUN_INSUFFICIENT_EVIDENCE"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CapabilityMaturationRealRunSuiteResult(BaseModel):
    profile_count: int = 0
    total_cycles_run: int = 0
    total_capabilities_evaluated: int = 0
    total_evidence_records_processed: int = 0
    total_mature_sandboxed_count: int = 0
    total_emerging_count: int = 0
    total_immature_count: int = 0
    total_regressive_count: int = 0
    total_safety_blocked_count: int = 0
    total_quarantined_count: int = 0
    total_conflicting_evidence_count: int = 0
    total_regressions_detected: int = 0
    total_regressions_isolated: int = 0
    total_safety_violations_detected: int = 0
    total_safety_violations_blocked: int = 0
    total_real_world_enable_attempts: int = 0
    total_real_world_enable_attempts_blocked: int = 0
    total_unsafe_capability_enabled_count: int = 0
    total_maturity_drift_detected_count: int = 0
    total_maturity_drift_blocked_count: int = 0
    aggregate_maturity_score: float = 0.0
    aggregate_confidence_score: float = 0.0
    aggregate_safety_score: float = 0.0
    aggregate_stability_score: float = 0.0
    aggregate_read_only_integrity_score: float = 0.0
    aggregate_capability_real_run_score: float = 0.0
    aggregate_verdict: str = "CAPABILITY_MATURATION_REAL_RUN_INSUFFICIENT_EVIDENCE"
    proceed_to_t65: bool = False
    profile_results: List[CapabilityMaturationRealRunProfileResult] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
