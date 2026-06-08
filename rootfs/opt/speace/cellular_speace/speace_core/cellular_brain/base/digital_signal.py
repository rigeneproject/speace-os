from typing import Any, Dict, List

from pydantic import BaseModel, Field


class DigitalSignal(BaseModel):
    source: str
    target: str | None = None
    strength: float = Field(default=0.0, ge=0.0)
    meaning: str = ""
    timestamp: float = 0.0
    payload: Any = None


class EpigeneticState(BaseModel):
    active_genes: List[str] = []
    modulation_factors: Dict[str, float] = Field(default_factory=dict)
    last_feedback_score: float = 0.0
