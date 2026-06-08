from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class ILFState(BaseModel):
    """Snapshot dello stato ILF in un dato momento."""

    timestamp: float
    cycle: int
    coherence: float = 0.0
    adaptation: float = 0.0
    continuity: float = 0.0
    goal_alignment: float = 0.0
    value: float = 0.0

    # Metriche dettagliate
    internal_diversity: float = 0.0
    functional_integration: float = 0.0
    cognitive_stability: float = 0.0
    learning_efficiency: float = 0.0
    error_rate: float = 0.0

    # Contesti opzionali
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def is_healthy(self) -> bool:
        """L'ILF è in uno stato accettabile."""
        return self.value >= 0.3

    def is_stagnant(self, threshold: float = 0.01) -> bool:
        """L'ILF non sta migliorando significativamente."""
        return self.continuity < threshold

    def to_summary(self) -> Dict[str, float]:
        return {
            "ilf_value": self.value,
            "coherence": self.coherence,
            "adaptation": self.adaptation,
            "continuity": self.continuity,
            "goal_alignment": self.goal_alignment,
        }