from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CurriculumStageType(str, Enum):
    OBSERVATION = "observation"
    GROUNDING_SEMANTIC = "grounding_semantic"
    IMITATION_SANDBOX = "imitation_sandbox"
    CAUSAL_PREDICTION = "causal_prediction"
    ERROR_CORRECTION = "error_correction"
    MEMORY_CONSOLIDATION = "memory_consolidation"
    ACTION_SIMULATION = "action_simulation"
    TRANSFER = "transfer"
    UNKNOWN = "unknown"


class LearningRiskClass(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class CurriculumStage(BaseModel):
    stage_id: str
    stage_type: CurriculumStageType = CurriculumStageType.UNKNOWN
    name: str = ""
    description: str = ""
    order: int = 0
    required_stages: List[str] = Field(default_factory=list)
    simulated_only: bool = True
    requires_human_review: bool = False
    estimated_difficulty: float = 0.0
    estimated_safety: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LearningEpisode(BaseModel):
    episode_id: str
    stage_id: str = ""
    stage_type: CurriculumStageType = CurriculumStageType.UNKNOWN
    stimulus_id: Optional[str] = None
    target_output: Optional[str] = None
    predicted_output: Optional[str] = None
    error_detected: bool = False
    error_magnitude: float = 0.0
    correction_applied: bool = False
    correction_confidence: float = 0.0
    consolidated: bool = False
    simulated_only: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DevelopmentalMemoryRecord(BaseModel):
    record_id: str
    episode_id: str
    stage_id: str
    consolidation_strength: float = 0.0
    recall_attempts: int = 0
    recall_successes: int = 0
    semantic_grounding_score: float = 0.0
    transferability_score: float = 0.0
    safety_preservation_score: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ImitationTrace(BaseModel):
    trace_id: str
    episode_id: str
    source_pattern: str = ""
    target_pattern: str = ""
    trace_confidence: float = 0.0
    contains_dangerous_action: bool = False
    blocked: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PostnatalLearningAuditProfile(BaseModel):
    name: str
    description: str = ""
    duration_cycles: int = 1
    episode_count: int = 3
    stage_mix: Dict[str, float] = Field(default_factory=dict)
    uncertainty_level: float = 0.0
    error_rate: float = 0.0
    dangerous_trace_attempts: int = 0
    simulated_only: bool = True
    expected_risk_type: Optional[str] = None
    requires_real_fixtures: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PostnatalLearningProfileResult(BaseModel):
    profile_name: str
    cycles_run: int = 0
    episodes_generated: int = 0
    episodes_evaluated: int = 0
    episodes_blocked: int = 0
    episodes_simulated_only: int = 0
    episodes_human_review_only: int = 0
    error_episodes_detected: int = 0
    error_episodes_corrected: int = 0
    dangerous_traces_detected: int = 0
    dangerous_traces_blocked: int = 0
    high_risk_episodes: int = 0
    critical_risk_episodes: int = 0
    high_or_critical_reviewed_or_blocked: int = 0
    memory_records_generated: int = 0
    unsafe_memory_records_blocked: int = 0
    review_packets_generated: int = 0
    unsafe_review_packets_blocked: int = 0
    bus_publications: int = 0
    unsafe_bus_publications_blocked: int = 0
    read_only_violations: int = 0
    average_risk_classification_score: float = 0.0
    average_error_correction_score: float = 0.0
    average_human_review_coverage_score: float = 0.0
    average_policy_consistency_score: float = 0.0
    average_safety_preservation_score: float = 0.0
    read_only_integrity_score: float = 0.0
    postnatal_learning_score: float = 0.0
    verdict: str = "POSTNATAL_LEARNING_INSUFFICIENT_EVIDENCE"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PostnatalLearningSuiteResult(BaseModel):
    profile_count: int = 0
    total_cycles_run: int = 0
    total_episodes_generated: int = 0
    total_episodes_evaluated: int = 0
    total_episodes_blocked: int = 0
    total_episodes_simulated_only: int = 0
    total_episodes_human_review_only: int = 0
    total_error_episodes_detected: int = 0
    total_error_episodes_corrected: int = 0
    total_dangerous_traces_detected: int = 0
    total_dangerous_traces_blocked: int = 0
    total_high_risk_episodes: int = 0
    total_critical_risk_episodes: int = 0
    total_high_or_critical_reviewed_or_blocked: int = 0
    total_memory_records_generated: int = 0
    total_unsafe_memory_records_blocked: int = 0
    total_review_packets_generated: int = 0
    total_unsafe_review_packets_blocked: int = 0
    total_bus_publications: int = 0
    total_unsafe_bus_publications_blocked: int = 0
    total_read_only_violations: int = 0
    aggregate_risk_classification_score: float = 0.0
    aggregate_error_correction_score: float = 0.0
    aggregate_human_review_coverage_score: float = 0.0
    aggregate_policy_consistency_score: float = 0.0
    aggregate_safety_preservation_score: float = 0.0
    aggregate_read_only_integrity_score: float = 0.0
    aggregate_postnatal_learning_score: float = 0.0
    aggregate_verdict: str = "POSTNATAL_LEARNING_INSUFFICIENT_EVIDENCE"
    proceed_to_t63b: bool = False
    profile_results: List[PostnatalLearningProfileResult] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PostnatalLearningRealRunProfile(BaseModel):
    name: str
    description: str = ""
    duration_cycles: int = 3
    stage_sequence: List[str] = Field(default_factory=list)
    episodes_per_stage: int = 3
    safe_trace_ratio: float = 1.0
    dangerous_trace_ratio: float = 0.0
    recurring_error_ratio: float = 0.0
    regression_pressure: float = 0.0
    memory_reuse_pressure: float = 0.0
    safety_conflict_level: float = 0.0
    action_simulation_pressure: float = 0.0
    expected_verdict_type: Optional[str] = None
    simulated_only: bool = True
    requires_real_fixtures: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PostnatalLearningRealRunProfileResult(BaseModel):
    profile_name: str
    cycles_run: int = 0
    stages_run: int = 0
    episodes_run: int = 0
    successful_episodes: int = 0
    failed_episodes: int = 0
    safe_traces_processed: int = 0
    dangerous_traces_detected: int = 0
    dangerous_traces_blocked: int = 0
    recurring_errors_detected: int = 0
    recurring_errors_corrected: int = 0
    regressions_detected: int = 0
    regressions_isolated: int = 0
    memory_records_created: int = 0
    memory_records_reused: int = 0
    memory_bloat_events: int = 0
    human_review_required_count: int = 0
    simulated_action_count: int = 0
    real_action_attempt_count: int = 0
    real_action_attempt_blocked_count: int = 0
    architecture_patch_attempt_count: int = 0
    architecture_patch_blocked_count: int = 0
    unsafe_behavior_count: int = 0
    unsafe_behavior_blocked_count: int = 0
    average_competence_gain_score: float = 0.0
    average_semantic_grounding_score: float = 0.0
    average_imitation_accuracy_score: float = 0.0
    average_causal_prediction_score: float = 0.0
    average_error_correction_score: float = 0.0
    average_memory_consolidation_score: float = 0.0
    average_safety_preservation_score: float = 0.0
    read_only_integrity_score: float = 0.0
    postnatal_real_run_score: float = 0.0
    verdict: str = "POSTNATAL_LEARNING_REAL_RUN_INSUFFICIENT_EVIDENCE"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PostnatalLearningRealRunSuiteResult(BaseModel):
    profile_count: int = 0
    total_cycles_run: int = 0
    total_stages_run: int = 0
    total_episodes_run: int = 0
    total_successful_episodes: int = 0
    total_dangerous_traces_detected: int = 0
    total_dangerous_traces_blocked: int = 0
    total_recurring_errors_detected: int = 0
    total_recurring_errors_corrected: int = 0
    total_regressions_detected: int = 0
    total_regressions_isolated: int = 0
    total_memory_records_created: int = 0
    total_memory_records_reused: int = 0
    total_memory_bloat_events: int = 0
    total_human_review_required: int = 0
    total_simulated_actions: int = 0
    total_real_action_attempts: int = 0
    total_real_action_attempts_blocked: int = 0
    total_architecture_patch_attempts: int = 0
    total_architecture_patch_blocked: int = 0
    total_unsafe_behavior_count: int = 0
    total_unsafe_behavior_blocked: int = 0
    aggregate_competence_gain_score: float = 0.0
    aggregate_semantic_grounding_score: float = 0.0
    aggregate_imitation_accuracy_score: float = 0.0
    aggregate_causal_prediction_score: float = 0.0
    aggregate_error_correction_score: float = 0.0
    aggregate_memory_consolidation_score: float = 0.0
    aggregate_memory_reuse_score: float = 0.0
    aggregate_safety_preservation_score: float = 0.0
    aggregate_read_only_integrity_score: float = 0.0
    aggregate_postnatal_real_run_score: float = 0.0
    aggregate_verdict: str = "POSTNATAL_LEARNING_REAL_RUN_INSUFFICIENT_EVIDENCE"
    proceed_to_t64: bool = False
    profile_results: List[PostnatalLearningRealRunProfileResult] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
