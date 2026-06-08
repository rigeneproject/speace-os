from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MetabolicMode(str, Enum):
    NORMAL = "normal"
    CONSERVATION = "conservation"
    STRESS = "stress"
    RECOVERY = "recovery"
    CRITICAL = "critical"
    SUSPENDED = "suspended"


class ResourceClass(str, Enum):
    SAFETY = "safety"
    MEMORY = "memory"
    SELF_ORGANIZATION = "self_organization"
    EVOLUTIONARY_KERNEL = "evolutionary_kernel"
    EVOLUTIONARY_MEMORY = "evolutionary_memory"
    ROUTING = "routing"
    REPAIR = "repair"
    DEFENSE = "defense"
    BENCHMARK = "benchmark"
    BACKGROUND_MAINTENANCE = "background_maintenance"


class ResourceBudget(BaseModel):
    total_energy_budget: float = 1.0
    available_energy: float = 1.0
    reserved_safety_budget: float = 0.15
    reserved_recovery_budget: float = 0.10
    module_allocations: Dict[str, float] = Field(default_factory=dict)
    hard_caps: Dict[str, float] = Field(default_factory=dict)
    soft_caps: Dict[str, float] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CognitiveCostProfile(BaseModel):
    module_name: str
    resource_class: str = ResourceClass.BACKGROUND_MAINTENANCE.value
    base_cost: float = 0.01
    last_cycle_cost: float = 0.0
    rolling_average_cost: float = 0.0
    peak_cost: float = 0.0
    usefulness_score: float = 0.5
    safety_priority: float = 0.5
    throttling_sensitivity: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MetabolicState(BaseModel):
    mode: str = MetabolicMode.NORMAL.value
    energy_reserve: float = 1.0
    metabolic_pressure: float = 0.0
    resource_allocation_efficiency: float = 1.0
    cognitive_cost_total: float = 0.0
    safety_preservation_score: float = 1.0
    critical_function_protection_score: float = 1.0
    throttling_level: float = 0.0
    starvation_risk: float = 0.0
    overconsumption_risk: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MetabolicDecision(BaseModel):
    decision_id: str
    target_module: str
    action: str = ""
    previous_allocation: float = 0.0
    new_allocation: float = 0.0
    reason: str = ""
    reversible: bool = True
    safety_impact: float = 0.0
    expected_energy_delta: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MetabolicAuditResult(BaseModel):
    profile_name: str = ""
    initial_state: MetabolicState = Field(default_factory=MetabolicState)
    final_state: MetabolicState = Field(default_factory=MetabolicState)
    decisions: List[MetabolicDecision] = Field(default_factory=list)
    energy_saved_score: float = 0.0
    cognitive_preservation_score: float = 0.0
    safety_preservation_score: float = 0.0
    recovery_support_score: float = 0.0
    over_throttling_score: float = 0.0
    starvation_score: float = 0.0
    metabolic_governance_score: float = 0.0
    verdict: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MetabolicRealRunProfile(BaseModel):
    name: str
    description: str = ""
    duration_cycles: int = 5
    workload_mix: Dict[str, float] = Field(default_factory=dict)
    initial_energy: float = 1.0
    expected_mode: Optional[str] = None
    expected_risk_type: Optional[str] = None
    requires_real_reports: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MetabolicRealRunProfileResult(BaseModel):
    profile_name: str = ""
    cycles_run: int = 0
    initial_energy: float = 0.0
    final_energy: float = 0.0
    average_metabolic_pressure: float = 0.0
    average_throttling_level: float = 0.0
    average_safety_preservation_score: float = 0.0
    average_recovery_support_score: float = 0.0
    average_critical_function_protection_score: float = 0.0
    evolutionary_throttle_count: int = 0
    memory_starvation_count: int = 0
    safety_starvation_count: int = 0
    recovery_starvation_count: int = 0
    over_throttling_count: int = 0
    under_throttling_count: int = 0
    budget_overflow_count: int = 0
    budget_leakage_count: int = 0
    real_run_metabolic_score: float = 0.0
    verdict: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MetabolicRealRunSuiteResult(BaseModel):
    profile_count: int = 0
    total_cycles_run: int = 0
    aggregate_metabolic_score: float = 0.0
    aggregate_safety_preservation_score: float = 0.0
    aggregate_recovery_support_score: float = 0.0
    aggregate_critical_function_protection_score: float = 0.0
    aggregate_resource_efficiency_score: float = 0.0
    total_evolutionary_throttle_count: int = 0
    total_safety_starvation_count: int = 0
    total_recovery_starvation_count: int = 0
    total_memory_starvation_count: int = 0
    total_budget_overflow_count: int = 0
    total_budget_leakage_count: int = 0
    aggregate_verdict: str = ""
    proceed_to_t59: bool = False
    profile_results: List[MetabolicRealRunProfileResult] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
