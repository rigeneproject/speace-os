from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class OrganismSubsystem(str, Enum):
    SELF_ORGANIZATION = "self_organization"
    PERTURBATION_RECOVERY = "perturbation_recovery"
    EVOLUTIONARY_KERNEL = "evolutionary_kernel"
    MULTI_CYCLE_EVOLUTION = "multi_cycle_evolution"
    EVOLUTIONARY_MEMORY = "evolutionary_memory"
    METABOLISM = "metabolism"
    MORPHOLOGICAL_MEMORY = "morphological_memory"
    BENCHMARK = "benchmark"
    SAFETY = "safety"
    RECOVERY = "recovery"
    ORCHESTRATOR = "orchestrator"
    BACKGROUND_MAINTENANCE = "background_maintenance"


class OrganismMessageType(str, Enum):
    STATE_UPDATE = "state_update"
    RESOURCE_REQUEST = "resource_request"
    RESOURCE_GRANT = "resource_grant"
    RESOURCE_DENIAL = "resource_denial"
    RISK_ALERT = "risk_alert"
    RECOVERY_REQUEST = "recovery_request"
    RECOVERY_STATUS = "recovery_status"
    EVOLUTIONARY_REQUEST = "evolutionary_request"
    EVOLUTIONARY_OUTCOME = "evolutionary_outcome"
    MEMORY_GOVERNANCE_UPDATE = "memory_governance_update"
    METABOLIC_MODE_CHANGE = "metabolic_mode_change"
    CRITICALITY_UPDATE = "criticality_update"
    SAFETY_BLOCK = "safety_block"
    AUDIT_EVENT = "audit_event"
    LIFECYCLE_TRANSITION = "lifecycle_transition"


class OrganismLifecycleState(str, Enum):
    INITIALIZING = "initializing"
    BASELINE = "baseline"
    ACTIVE = "active"
    CONSERVATION = "conservation"
    RECOVERY = "recovery"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    SUSPENDED = "suspended"
    AUDIT_ONLY = "audit_only"


class OrganismBusMessage(BaseModel):
    message_id: str
    source: str
    target: Optional[str] = None
    message_type: str
    priority: float = 0.5
    timestamp: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    requires_ack: bool = False
    ttl_ticks: int = 10
    safety_relevant: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SubsystemStatus(BaseModel):
    subsystem_name: str
    enabled: bool = True
    health_score: float = 1.0
    last_seen_tick: int = 0
    current_load: float = 0.0
    resource_need: float = 0.0
    risk_level: float = 0.0
    degraded: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrganismState(BaseModel):
    tick: int = 0
    global_health_score: float = 1.0
    global_coherence_phi: float = 0.0
    global_energy_reserve: float = 1.0
    metabolic_mode: str = "normal"
    criticality_score: float = 0.0
    recovery_pressure: float = 0.0
    evolutionary_pressure: float = 0.0
    memory_governance_score: float = 1.0
    safety_risk_score: float = 0.0
    active_subsystems: List[str] = Field(default_factory=list)
    degraded_subsystems: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IntegrationDecision(BaseModel):
    decision_id: str
    tick: int = 0
    target_subsystem: str
    action: str
    reason: str = ""
    priority: float = 0.5
    reversible: bool = True
    safety_impact: float = 0.0
    metabolic_impact: float = 0.0
    expected_coherence_delta: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrganismAuditProfile(BaseModel):
    name: str
    description: str = ""
    duration_ticks: int = 5
    message_rate: float = 1.0
    safety_alert_rate: float = 0.0
    resource_request_rate: float = 0.0
    recovery_request_rate: float = 0.0
    evolutionary_request_rate: float = 0.0
    expected_risk_type: Optional[str] = None
    expected_verdict: Optional[str] = None
    seed: int = 42


class OrganismAuditResult(BaseModel):
    profile_name: str
    messages_processed: int = 0
    messages_dropped: int = 0
    acknowledgements_missing: int = 0
    subsystem_health_score: float = 1.0
    integration_coherence_score: float = 1.0
    resource_coordination_score: float = 1.0
    safety_coordination_score: float = 1.0
    recovery_coordination_score: float = 1.0
    bus_overload_score: float = 0.0
    lifecycle_validity_score: float = 1.0
    organism_integration_score: float = 0.0
    verdict: str = "ORGANISM_INSUFFICIENT_EVIDENCE"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrganismAuditSuiteResult(BaseModel):
    profile_count: int = 0
    total_messages_processed: int = 0
    total_messages_dropped: int = 0
    total_ack_missing: int = 0
    aggregate_integration_score: float = 0.0
    aggregate_safety_coordination_score: float = 0.0
    aggregate_recovery_coordination_score: float = 0.0
    aggregate_resource_coordination_score: float = 0.0
    aggregate_subsystem_health_score: float = 0.0
    aggregate_bus_overload_score: float = 0.0
    aggregate_lifecycle_validity_score: float = 0.0
    aggregate_verdict: str = "ORGANISM_INSUFFICIENT_EVIDENCE"
    proceed_to_t60: bool = False
    profile_results: List[OrganismAuditResult] = Field(default_factory=list)


# T59B — Organism Integration Real-Run Audit models
class OrganismRealRunProfile(BaseModel):
    name: str
    description: str = ""
    duration_ticks: int = 5
    workload_mix: Dict[str, float] = Field(default_factory=dict)
    initial_lifecycle_state: str = "initializing"
    initial_metabolic_mode: str = "normal"
    expected_risk_type: Optional[str] = None
    requires_real_reports: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrganismRealRunProfileResult(BaseModel):
    profile_name: str
    ticks_run: int = 0
    messages_published: int = 0
    messages_delivered: int = 0
    messages_dropped: int = 0
    ack_failure_count: int = 0
    safety_messages_preserved: int = 0
    safety_routing_failure_count: int = 0
    recovery_priority_failure_count: int = 0
    evolution_throttle_count: int = 0
    critical_evolution_block_count: int = 0
    quarantined_memory_block_count: int = 0
    bus_overload_count: int = 0
    degraded_subsystem_isolation_count: int = 0
    invalid_lifecycle_transition_count: int = 0
    average_global_health_score: float = 0.0
    average_integration_coherence_score: float = 0.0
    average_resource_coordination_score: float = 0.0
    average_safety_coordination_score: float = 0.0
    average_recovery_coordination_score: float = 0.0
    real_run_organism_score: float = 0.0
    verdict: str = "ORGANISM_REAL_RUN_INSUFFICIENT_EVIDENCE"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrganismRealRunSuiteResult(BaseModel):
    profile_count: int = 0
    total_ticks_run: int = 0
    total_messages_published: int = 0
    total_messages_dropped: int = 0
    total_ack_failure_count: int = 0
    total_safety_routing_failure_count: int = 0
    total_recovery_priority_failure_count: int = 0
    total_quarantined_memory_leak_count: int = 0
    total_critical_evolution_block_count: int = 0
    aggregate_global_health_score: float = 0.0
    aggregate_integration_coherence_score: float = 0.0
    aggregate_safety_coordination_score: float = 0.0
    aggregate_recovery_coordination_score: float = 0.0
    aggregate_resource_coordination_score: float = 0.0
    aggregate_bus_reliability_score: float = 0.0
    aggregate_organism_score: float = 0.0
    aggregate_verdict: str = "ORGANISM_REAL_RUN_INSUFFICIENT_EVIDENCE"
    proceed_to_t60: bool = False
    profile_results: List[OrganismRealRunProfileResult] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
