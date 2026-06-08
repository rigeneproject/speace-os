from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CyberPhysicalMode(str, Enum):
    SIMULATED_READ_ONLY = "simulated_read_only"
    SANDBOXED_READ_ONLY = "sandboxed_read_only"
    PASSIVE_MONITORING = "passive_monitoring"
    QUARANTINED = "quarantined"
    BLOCKED = "blocked"


class ExternalSignalType(str, Enum):
    ENVIRONMENTAL = "environmental"
    ENERGY = "energy"
    INFRASTRUCTURE = "infrastructure"
    SENSOR = "sensor"
    SYSTEM_HEALTH = "system_health"
    HUMAN_FEEDBACK = "human_feedback"
    NETWORK_STATUS = "network_status"
    UNKNOWN = "unknown"


class ExternalSignal(BaseModel):
    signal_id: str
    source_id: str
    signal_type: str
    timestamp: str = ""
    value: Any = 0.0
    confidence: float = 1.0
    safety_relevance: float = 0.0
    noise_score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SensorStream(BaseModel):
    stream_id: str
    source_id: str
    signal_type: str
    mode: str = CyberPhysicalMode.SIMULATED_READ_ONLY.value
    active: bool = True
    last_timestamp: Optional[str] = None
    sample_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorldStateSnapshot(BaseModel):
    snapshot_id: str
    timestamp: str = ""
    signal_count: int = 0
    environmental_pressure: float = 0.0
    infrastructure_pressure: float = 0.0
    energy_pressure: float = 0.0
    safety_pressure: float = 0.0
    uncertainty_score: float = 0.0
    world_coherence_score: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AssimilationDecision(BaseModel):
    decision_id: str
    signal_id: Optional[str] = None
    action: str
    reason: str = ""
    accepted: bool = False
    quarantined: bool = False
    safety_relevant: bool = False
    organism_bus_message_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ActuationRequest(BaseModel):
    request_id: str
    target_system: str
    action: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    risk_score: float = 0.0
    requires_human_approval: bool = True
    blocked: bool = True
    reason: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CyberPhysicalAuditProfile(BaseModel):
    name: str
    description: str = ""
    duration_ticks: int = 5
    signal_count: int = 10
    noise_level: float = 0.0
    invalid_signal_rate: float = 0.0
    safety_relevant_rate: float = 0.0
    actuation_request_count: int = 0
    expected_risk_type: Optional[str] = None
    seed: int = 42


class CyberPhysicalAuditResult(BaseModel):
    profile_name: str
    signals_processed: int = 0
    signals_accepted: int = 0
    signals_quarantined: int = 0
    invalid_signals_blocked: int = 0
    actuation_requests_blocked: int = 0
    world_state_coherence_score: float = 1.0
    safety_preservation_score: float = 1.0
    assimilation_quality_score: float = 1.0
    cyber_physical_score: float = 0.0
    verdict: str = "CYBER_PHYSICAL_INSUFFICIENT_EVIDENCE"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CyberPhysicalAuditSuiteResult(BaseModel):
    profile_count: int = 0
    total_signals_processed: int = 0
    total_signals_accepted: int = 0
    total_signals_quarantined: int = 0
    total_invalid_signals_blocked: int = 0
    total_actuation_requests_blocked: int = 0
    aggregate_world_state_coherence_score: float = 0.0
    aggregate_safety_preservation_score: float = 0.0
    aggregate_assimilation_quality_score: float = 0.0
    aggregate_cyber_physical_score: float = 0.0
    aggregate_verdict: str = "CYBER_PHYSICAL_INSUFFICIENT_EVIDENCE"
    proceed_to_t60b: bool = False
    profile_results: List[CyberPhysicalAuditResult] = Field(default_factory=list)


# T60B — Cyber-Physical Assimilation Real-Run Audit models
class CyberPhysicalRealRunProfile(BaseModel):
    name: str
    description: str = ""
    duration_ticks: int = 5
    stream_count: int = 1
    signal_mix: Dict[str, float] = Field(default_factory=dict)
    noise_level: float = 0.0
    conflict_level: float = 0.0
    actuation_attempts: int = 0
    expected_risk_type: Optional[str] = None
    requires_real_fixtures: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CyberPhysicalRealRunProfileResult(BaseModel):
    profile_name: str
    ticks_run: int = 0
    streams_processed: int = 0
    signals_processed: int = 0
    signals_accepted: int = 0
    signals_quarantined: int = 0
    invalid_signals_blocked: int = 0
    noisy_signals_quarantined: int = 0
    conflicting_signals_detected: int = 0
    world_states_generated: int = 0
    bus_publications: int = 0
    unsafe_bus_publications_blocked: int = 0
    actuation_requests_total: int = 0
    actuation_requests_blocked: int = 0
    read_only_violations: int = 0
    real_connection_attempts_blocked: int = 0
    average_world_coherence_score: float = 0.0
    average_assimilation_quality_score: float = 0.0
    average_safety_preservation_score: float = 0.0
    read_only_integrity_score: float = 0.0
    cyber_physical_real_run_score: float = 0.0
    verdict: str = "CYBER_PHYSICAL_REAL_RUN_INSUFFICIENT_EVIDENCE"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CyberPhysicalRealRunSuiteResult(BaseModel):
    profile_count: int = 0
    total_ticks_run: int = 0
    total_streams_processed: int = 0
    total_signals_processed: int = 0
    total_signals_accepted: int = 0
    total_signals_quarantined: int = 0
    total_invalid_signals_blocked: int = 0
    total_actuation_requests: int = 0
    total_actuation_requests_blocked: int = 0
    total_read_only_violations: int = 0
    total_real_connection_attempts_blocked: int = 0
    aggregate_world_coherence_score: float = 0.0
    aggregate_assimilation_quality_score: float = 0.0
    aggregate_safety_preservation_score: float = 0.0
    aggregate_read_only_integrity_score: float = 0.0
    aggregate_cyber_physical_real_run_score: float = 0.0
    aggregate_verdict: str = "CYBER_PHYSICAL_REAL_RUN_INSUFFICIENT_EVIDENCE"
    proceed_to_t61: bool = False
    profile_results: List[CyberPhysicalRealRunProfileResult] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
