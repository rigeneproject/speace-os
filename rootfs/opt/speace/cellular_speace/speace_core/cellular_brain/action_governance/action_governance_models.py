from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ExternalActionType(str, Enum):
    OBSERVE_ONLY = "observe_only"
    NOTIFY = "notify"
    RECOMMEND = "recommend"
    THROTTLE_SIMULATED = "throttle_simulated"
    RECONFIGURE_SIMULATED = "reconfigure_simulated"
    RESOURCE_SHIFT_SIMULATED = "resource_shift_simulated"
    ISOLATE_SIMULATED = "isolate_simulated"
    ACTUATE_EXTERNAL = "actuate_external"
    CONNECT_EXTERNAL = "connect_external"
    UNKNOWN = "unknown"


class ActionGovernanceMode(str, Enum):
    BLOCKED = "blocked"
    SIMULATION_ONLY = "simulation_only"
    HUMAN_REVIEW_ONLY = "human_review_only"
    SAFE_NOOP = "safe_noop"


class ActionRiskClass(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ExternalActionProposal(BaseModel):
    proposal_id: str
    action_type: ExternalActionType = ExternalActionType.UNKNOWN
    title: str = ""
    description: str = ""
    source_snapshot_id: Optional[str] = None
    source_scenario_id: Optional[str] = None
    source_assessment_id: Optional[str] = None
    target_entity_id: Optional[str] = None
    target_zone_id: Optional[str] = None
    intended_effect: str = ""
    simulated_only: bool = True
    requested_real_execution: bool = False
    estimated_urgency: float = 0.0
    estimated_benefit: float = 0.0
    estimated_risk: float = 0.0
    uncertainty_score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActionRiskAssessment(BaseModel):
    assessment_id: str
    proposal_id: str
    risk_class: ActionRiskClass = ActionRiskClass.UNKNOWN
    safety_risk_score: float = 0.0
    infrastructure_risk_score: float = 0.0
    energy_risk_score: float = 0.0
    reversibility_risk_score: float = 0.0
    uncertainty_risk_score: float = 0.0
    externality_risk_score: float = 0.0
    aggregate_risk_score: float = 0.0
    requires_human_review: bool = False
    blocked_reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReversibilityAssessment(BaseModel):
    assessment_id: str
    proposal_id: str
    reversible: bool = True
    reversibility_score: float = 0.0
    rollback_available: bool = False
    rollback_complexity_score: float = 0.0
    irreversible_effect_detected: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActionGovernanceDecision(BaseModel):
    decision_id: str
    proposal_id: str
    governance_mode: ActionGovernanceMode = ActionGovernanceMode.BLOCKED
    allowed_as_simulation: bool = False
    allowed_for_real_execution: bool = False
    requires_human_review: bool = False
    blocked: bool = False
    blocked_reason: Optional[str] = None
    safety_preservation_score: float = 0.0
    read_only_integrity_score: float = 0.0
    decision_confidence: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActionReviewPacket(BaseModel):
    packet_id: str
    proposal_id: str
    decision_id: str
    summary: str = ""
    risk_assessment: Dict[str, Any] = Field(default_factory=dict)
    reversibility_assessment: Dict[str, Any] = Field(default_factory=dict)
    impact_summary: Dict[str, Any] = Field(default_factory=dict)
    human_review_required: bool = False
    recommended_human_decision: str = ""
    contains_real_execution_credentials: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActionGovernanceAuditProfile(BaseModel):
    name: str
    description: str = ""
    action_type: ExternalActionType = ExternalActionType.UNKNOWN
    simulated_only: bool = True
    requested_real_execution: bool = False
    conflict_level: float = 0.0
    uncertainty_level: float = 0.0
    risk_class_override: Optional[ActionRiskClass] = None
    expected_governance_mode: Optional[ActionGovernanceMode] = None
    expected_risk_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActionGovernanceAuditResult(BaseModel):
    profile_name: str
    proposals_generated: int = 0
    proposals_blocked: int = 0
    proposals_simulation_only: int = 0
    proposals_human_review_only: int = 0
    safe_noop_count: int = 0
    real_execution_attempts: int = 0
    real_execution_attempts_blocked: int = 0
    unsafe_action_attempts: int = 0
    unsafe_action_attempts_blocked: int = 0
    review_packets_generated: int = 0
    bus_publications: int = 0
    unsafe_bus_publications_blocked: int = 0
    read_only_violations: int = 0
    average_risk_class_score: float = 0.0
    average_reversibility_score: float = 0.0
    average_safety_preservation_score: float = 0.0
    average_decision_confidence: float = 0.0
    action_governance_sandbox_score: float = 0.0
    verdict: str = "EXTERNAL_ACTION_GOVERNANCE_INSUFFICIENT_EVIDENCE"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActionGovernanceSuiteResult(BaseModel):
    profile_count: int = 0
    total_proposals_generated: int = 0
    total_proposals_blocked: int = 0
    total_proposals_simulation_only: int = 0
    total_proposals_human_review_only: int = 0
    total_safe_noop_count: int = 0
    total_real_execution_attempts: int = 0
    total_real_execution_attempts_blocked: int = 0
    total_unsafe_action_attempts: int = 0
    total_unsafe_action_attempts_blocked: int = 0
    total_review_packets_generated: int = 0
    total_bus_publications: int = 0
    total_unsafe_bus_publications_blocked: int = 0
    total_read_only_violations: int = 0
    aggregate_risk_classification_score: float = 0.0
    aggregate_safety_preservation_score: float = 0.0
    aggregate_reversibility_score: float = 0.0
    aggregate_human_review_coverage_score: float = 0.0
    aggregate_policy_consistency_score: float = 0.0
    aggregate_read_only_integrity_score: float = 0.0
    aggregate_bus_publication_integrity_score: float = 0.0
    aggregate_decision_confidence_score: float = 0.0
    aggregate_review_packet_safety_score: float = 0.0
    aggregate_action_governance_sandbox_score: float = 0.0
    aggregate_verdict: str = "EXTERNAL_ACTION_GOVERNANCE_INSUFFICIENT_EVIDENCE"
    proceed_to_t62b: bool = False
    profile_results: List[ActionGovernanceAuditResult] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActionGovernanceRealRunProfile(BaseModel):
    name: str
    description: str = ""
    duration_cycles: int = 1
    proposal_count: int = 3
    risk_mix: Dict[str, float] = Field(default_factory=dict)
    action_type_mix: Dict[str, float] = Field(default_factory=dict)
    uncertainty_level: float = 0.0
    irreversibility_level: float = 0.0
    conflict_level: float = 0.0
    real_execution_attempts: int = 0
    external_connection_attempts: int = 0
    unsafe_payload_attempts: int = 0
    expected_risk_type: Optional[str] = None
    requires_real_fixtures: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActionGovernanceRealRunProfileResult(BaseModel):
    profile_name: str
    cycles_run: int = 0
    proposals_generated: int = 0
    proposals_evaluated: int = 0
    proposals_blocked: int = 0
    proposals_simulation_only: int = 0
    proposals_human_review_only: int = 0
    safe_noop_count: int = 0
    high_risk_proposals: int = 0
    critical_risk_proposals: int = 0
    high_or_critical_reviewed_or_blocked: int = 0
    irreversible_actions_detected: int = 0
    irreversible_actions_blocked: int = 0
    conflicting_proposals_detected: int = 0
    real_execution_attempts_total: int = 0
    real_execution_attempts_blocked: int = 0
    external_connection_attempts_total: int = 0
    external_connection_attempts_blocked: int = 0
    unsafe_action_attempts_total: int = 0
    unsafe_action_attempts_blocked: int = 0
    unsafe_payload_attempts_total: int = 0
    unsafe_payload_attempts_blocked: int = 0
    review_packets_generated: int = 0
    unsafe_review_packets_blocked: int = 0
    bus_publications: int = 0
    unsafe_bus_publications_blocked: int = 0
    read_only_violations: int = 0
    average_risk_classification_score: float = 0.0
    average_reversibility_score: float = 0.0
    average_human_review_coverage_score: float = 0.0
    average_policy_consistency_score: float = 0.0
    average_safety_preservation_score: float = 0.0
    read_only_integrity_score: float = 0.0
    action_governance_real_run_score: float = 0.0
    verdict: str = "EXTERNAL_ACTION_GOVERNANCE_REAL_RUN_INSUFFICIENT_EVIDENCE"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActionGovernanceRealRunSuiteResult(BaseModel):
    profile_count: int = 0
    total_cycles_run: int = 0
    total_proposals_generated: int = 0
    total_proposals_evaluated: int = 0
    total_proposals_blocked: int = 0
    total_proposals_simulation_only: int = 0
    total_proposals_human_review_only: int = 0
    total_high_risk_proposals: int = 0
    total_critical_risk_proposals: int = 0
    total_high_or_critical_reviewed_or_blocked: int = 0
    total_irreversible_actions_detected: int = 0
    total_irreversible_actions_blocked: int = 0
    total_real_execution_attempts: int = 0
    total_real_execution_attempts_blocked: int = 0
    total_external_connection_attempts: int = 0
    total_external_connection_attempts_blocked: int = 0
    total_unsafe_payload_attempts: int = 0
    total_unsafe_payload_attempts_blocked: int = 0
    total_review_packets_generated: int = 0
    total_unsafe_review_packets_blocked: int = 0
    total_bus_publications: int = 0
    total_unsafe_bus_publications_blocked: int = 0
    total_read_only_violations: int = 0
    aggregate_risk_classification_score: float = 0.0
    aggregate_reversibility_score: float = 0.0
    aggregate_human_review_coverage_score: float = 0.0
    aggregate_policy_consistency_score: float = 0.0
    aggregate_safety_preservation_score: float = 0.0
    aggregate_read_only_integrity_score: float = 0.0
    aggregate_action_governance_real_run_score: float = 0.0
    aggregate_verdict: str = "EXTERNAL_ACTION_GOVERNANCE_REAL_RUN_INSUFFICIENT_EVIDENCE"
    proceed_to_t63: bool = False
    profile_results: List[ActionGovernanceRealRunProfileResult] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
