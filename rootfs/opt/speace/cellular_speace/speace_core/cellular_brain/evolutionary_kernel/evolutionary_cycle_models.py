from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EvolutionPhase(str, Enum):
    EXPLORATION = "exploration"
    SELECTION = "selection"
    FEEDBACK = "feedback"
    RECONFIGURATION = "reconfiguration"


class EvolutionCycleState(BaseModel):
    phase: EvolutionPhase = EvolutionPhase.EXPLORATION
    cycle_number: int = 0
    generation_id: str = Field(default_factory=lambda: f"gen_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
    entropy_before: float = 0.0
    entropy_after: float = 0.0
    perturbation_strength: float = 0.0
    fitness_score: float = 0.0
    selected_variant_id: Optional[str] = None
    reconfiguration_applied: bool = False
    safety_passed: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EvolutionCycleResult(BaseModel):
    cycle_number: int
    generation_id: str
    success: bool = False
    phases_completed: List[EvolutionPhase] = Field(default_factory=list)
    entropy_delta: float = 0.0
    fitness_score: float = 0.0
    variant_count: int = 0
    selected_variant_id: Optional[str] = None
    reconfiguration_applied: bool = False
    safety_passed: bool = False
    rollback_triggered: bool = False
    reason: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EDDCVTMetrics(BaseModel):
    total_cycles: int = 0
    successful_cycles: int = 0
    failed_cycles: int = 0
    mean_entropy_delta: float = 0.0
    mean_fitness_score: float = 0.0
    mean_perturbation_strength: float = 0.0
    reconfiguration_rate: float = 0.0
    safety_pass_rate: float = 0.0
    rollback_rate: float = 0.0
    current_phase: EvolutionPhase = EvolutionPhase.EXPLORATION
    last_cycle_result: Optional[EvolutionCycleResult] = None
    cycle_history: List[EvolutionCycleResult] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
