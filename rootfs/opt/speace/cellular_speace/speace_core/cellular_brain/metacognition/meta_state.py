"""Meta-state Pydantic models for T127 — Metacognitive Monitoring Layer."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CognitiveObservation(BaseModel):
    workspace_stability: float = 0.0
    narrative_coherence: float = 0.0
    regulation_density: float = 0.0
    drive_oscillations: float = 0.0
    dialogue_patterns: float = 0.0
    vector_drift: float = 0.0
    memory_quality: float = 0.0


class CognitiveErrorDetection(BaseModel):
    repetitive_loop: bool = False
    contradiction: bool = False
    overfocus: bool = False
    similarity_collapse: bool = False
    memory_saturation: bool = False
    regulation_oscillation: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)


class StrategyEvaluation(BaseModel):
    regulation_id: str = ""
    pre_health: float = 0.0
    post_health: float = 0.0
    delta: float = 0.0
    improved: bool = False


class EpistemicConfidence(BaseModel):
    confidence_score: float = 0.0
    uncertainty_score: float = 0.0
    novelty_score: float = 0.0


class MetaState(BaseModel):
    meta_state_label: str = "stable"
    cognitive_observation: CognitiveObservation = Field(default_factory=CognitiveObservation)
    error_detection: CognitiveErrorDetection = Field(default_factory=CognitiveErrorDetection)
    epistemic_confidence: EpistemicConfidence = Field(default_factory=EpistemicConfidence)
    strategy_evaluation: Optional[StrategyEvaluation] = None
    reflective_narrative: str = ""
    timestamp: float = 0.0
