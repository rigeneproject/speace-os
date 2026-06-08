from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WorldEntityType(str, Enum):
    ENVIRONMENT = "environment"
    INFRASTRUCTURE = "infrastructure"
    ENERGY_SYSTEM = "energy_system"
    SENSOR_SOURCE = "sensor_source"
    HUMAN_CONTEXT = "human_context"
    ORGANISM_SUBSYSTEM = "organism_subsystem"
    UNKNOWN = "unknown"


class WorldEntity(BaseModel):
    entity_id: str
    entity_type: str
    name: str = ""
    state: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    uncertainty: float = 0.0
    safety_relevance: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorldZone(BaseModel):
    zone_id: str
    name: str = ""
    entities: List[str] = Field(default_factory=list)
    environmental_pressure: float = 0.0
    infrastructure_pressure: float = 0.0
    energy_pressure: float = 0.0
    safety_pressure: float = 0.0
    uncertainty_score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorldConstraint(BaseModel):
    constraint_id: str
    name: str = ""
    constraint_type: str = ""
    severity: float = 0.5
    hard_constraint: bool = False
    description: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CausalLink(BaseModel):
    link_id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str = "influences"
    strength: float = 0.5
    confidence: float = 1.0
    delay_ticks: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorldScenario(BaseModel):
    scenario_id: str
    name: str = ""
    initial_state_id: str = ""
    horizon_ticks: int = 5
    perturbations: List[Dict[str, Any]] = Field(default_factory=list)
    simulated_actions: List[Dict[str, Any]] = Field(default_factory=list)
    expected_risk_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorldModelSnapshot(BaseModel):
    snapshot_id: str
    timestamp: str = ""
    entities: List[WorldEntity] = Field(default_factory=list)
    zones: List[WorldZone] = Field(default_factory=list)
    constraints: List[WorldConstraint] = Field(default_factory=list)
    causal_links: List[CausalLink] = Field(default_factory=list)
    global_uncertainty_score: float = 0.0
    global_coherence_score: float = 1.0
    global_risk_score: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CausalSimulationResult(BaseModel):
    scenario_id: str
    ticks_simulated: int = 0
    causal_chains_detected: int = 0
    contradictions_detected: int = 0
    constraint_violations_detected: int = 0
    predicted_risk_score: float = 0.0
    predicted_coherence_score: float = 1.0
    predicted_energy_pressure: float = 0.0
    predicted_safety_pressure: float = 0.0
    safe_to_publish_read_only: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ImpactAssessment(BaseModel):
    assessment_id: str
    scenario_id: str
    impact_score: float = 0.0
    safety_impact_score: float = 0.0
    energy_impact_score: float = 0.0
    infrastructure_impact_score: float = 0.0
    uncertainty_impact_score: float = 0.0
    reversible: bool = True
    requires_human_review: bool = False
    allowed_as_simulation_only: bool = True
    blocked_reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorldModelAuditProfile(BaseModel):
    name: str
    description: str = ""
    duration_ticks: int = 5
    entity_count: int = 5
    zone_count: int = 2
    scenario_type: str = "baseline"
    conflict_level: float = 0.0
    uncertainty_level: float = 0.0
    expected_risk_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorldModelAuditResult(BaseModel):
    profile_name: str
    snapshots_generated: int = 0
    scenarios_built: int = 0
    simulations_run: int = 0
    causal_chains_detected: int = 0
    contradictions_detected: int = 0
    constraint_violations_detected: int = 0
    unsafe_simulated_actions_blocked: int = 0
    bus_publications: int = 0
    read_only_violations: int = 0
    real_action_attempts_blocked: int = 0
    average_world_model_coherence_score: float = 0.0
    average_prediction_quality_score: float = 0.0
    average_safety_preservation_score: float = 0.0
    world_model_sandbox_score: float = 0.0
    verdict: str = "EXTERNAL_WORLD_MODEL_INSUFFICIENT_EVIDENCE"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorldModelAuditSuiteResult(BaseModel):
    profile_count: int = 0
    total_snapshots_generated: int = 0
    total_scenarios_built: int = 0
    total_simulations_run: int = 0
    total_causal_chains_detected: int = 0
    total_contradictions_detected: int = 0
    total_constraint_violations_detected: int = 0
    total_unsafe_simulated_actions_blocked: int = 0
    total_bus_publications: int = 0
    total_read_only_violations: int = 0
    total_real_action_attempts_blocked: int = 0
    aggregate_world_model_coherence_score: float = 0.0
    aggregate_prediction_quality_score: float = 0.0
    aggregate_safety_preservation_score: float = 0.0
    aggregate_read_only_integrity_score: float = 0.0
    aggregate_world_model_sandbox_score: float = 0.0
    aggregate_verdict: str = "EXTERNAL_WORLD_MODEL_INSUFFICIENT_EVIDENCE"
    proceed_to_t61b: bool = False
    profile_results: List[WorldModelAuditResult] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# T61B models
class WorldModelRealRunProfile(BaseModel):
    name: str
    description: str = ""
    duration_ticks: int = 5
    horizon_ticks: int = 10
    entity_count: int = 5
    zone_count: int = 2
    constraint_count: int = 0
    causal_link_count: int = 0
    conflict_level: float = 0.0
    uncertainty_growth_rate: float = 0.0
    perturbation_mix: Dict[str, float] = Field(default_factory=dict)
    simulated_action_attempts: int = 0
    real_action_attempts: int = 0
    expected_risk_type: Optional[str] = None
    requires_real_fixtures: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorldModelRealRunProfileResult(BaseModel):
    profile_name: str
    ticks_run: int = 0
    horizon_ticks: int = 0
    snapshots_generated: int = 0
    scenarios_built: int = 0
    simulations_run: int = 0
    entities_processed: int = 0
    zones_processed: int = 0
    constraints_evaluated: int = 0
    causal_links_evaluated: int = 0
    causal_chains_detected: int = 0
    contradictions_detected: int = 0
    constraint_violations_detected: int = 0
    uncertainty_growth_detected: int = 0
    prediction_drift_count: int = 0
    coherence_collapse_count: int = 0
    unsafe_simulated_actions_blocked: int = 0
    real_action_attempts_total: int = 0
    real_action_attempts_blocked: int = 0
    bus_publications: int = 0
    unsafe_bus_publications_blocked: int = 0
    read_only_violations: int = 0
    average_world_model_coherence_score: float = 0.0
    average_prediction_quality_score: float = 0.0
    average_safety_preservation_score: float = 0.0
    average_constraint_detection_score: float = 0.0
    average_causal_consistency_score: float = 0.0
    read_only_integrity_score: float = 1.0
    world_model_real_run_score: float = 0.0
    verdict: str = "EXTERNAL_WORLD_MODEL_REAL_RUN_INSUFFICIENT_EVIDENCE"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorldModelRealRunSuiteResult(BaseModel):
    profile_count: int = 0
    total_ticks_run: int = 0
    total_horizon_ticks: int = 0
    total_snapshots_generated: int = 0
    total_scenarios_built: int = 0
    total_simulations_run: int = 0
    total_contradictions_detected: int = 0
    total_constraint_violations_detected: int = 0
    total_prediction_drift_count: int = 0
    total_coherence_collapse_count: int = 0
    total_unsafe_simulated_actions_blocked: int = 0
    total_real_action_attempts: int = 0
    total_real_action_attempts_blocked: int = 0
    total_read_only_violations: int = 0
    total_unsafe_bus_publications_blocked: int = 0
    aggregate_world_model_coherence_score: float = 0.0
    aggregate_prediction_quality_score: float = 0.0
    aggregate_safety_preservation_score: float = 0.0
    aggregate_constraint_detection_score: float = 0.0
    aggregate_causal_consistency_score: float = 0.0
    aggregate_read_only_integrity_score: float = 0.0
    aggregate_world_model_real_run_score: float = 0.0
    aggregate_verdict: str = "EXTERNAL_WORLD_MODEL_REAL_RUN_INSUFFICIENT_EVIDENCE"
    proceed_to_t62: bool = False
    profile_results: List[WorldModelRealRunProfileResult] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
