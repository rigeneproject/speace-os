"""Predictive Tension Layer — motivational force from prediction-error accumulation.

Predictive tension is the time-integrated, hierarchy-weighted prediction error
that acts as an endogenous drive to reduce model-world mismatch.  It is
separable from instantaneous prediction error: it *accumulates* when error
persists and *dissipates* when error is resolved.
"""

from typing import Any, Dict, List, Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from speace_core.cellular_brain.dynamics.predictive_coding_engine import PredictiveCodingEngine


class LayerTensionState(BaseModel):
    """Per-layer tension state."""

    layer_id: str
    level: int = 0
    instant_error: float = 0.0
    tension: float = 0.0
    weight: float = 1.0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class PredictiveTensionSnapshot(BaseModel):
    """System-wide tension snapshot."""

    total_tension: float = 0.0
    layer_states: List[LayerTensionState] = Field(default_factory=list)
    free_energy: float = 0.0
    mean_tension: float = 0.0
    max_layer_tension: float = 0.0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class PredictiveTensionLayer:
    """Accumulates hierarchy-weighted prediction error into motivational tension.

    Parameters
    ----------
    decay : float
        Tension decay per tick (0 = no decay, 1 = full reset).
    level_weights : dict
        Mapping from predictive-coding level (0,1,2) to tension weight.
    """

    def __init__(
        self,
        decay: float = 0.05,
        level_weights: Optional[Dict[int, float]] = None,
    ) -> None:
        self.decay = decay
        self.level_weights = level_weights or {0: 1.0, 1: 0.6, 2: 0.3}
        self._tensions: Dict[str, float] = {}

    def tick(self, engine: PredictiveCodingEngine) -> PredictiveTensionSnapshot:
        """Update tension from current predictive-coding state."""
        layer_states: List[LayerTensionState] = []
        total = 0.0
        max_tension = 0.0

        for layer_id, layer in engine.layers.items():
            level = int(layer.get("level", 0))
            weight = self.level_weights.get(level, 0.5)
            instant_error = float(np.sum(layer.get("prediction_error", np.zeros(1)) ** 2))

            # Accumulate tension: previous tension + weighted instant error, then decay
            prev = self._tensions.get(layer_id, 0.0)
            new_tension = (prev + weight * instant_error) * (1.0 - self.decay)
            self._tensions[layer_id] = new_tension

            state = LayerTensionState(
                layer_id=layer_id,
                level=level,
                instant_error=round(instant_error, 6),
                tension=round(new_tension, 6),
                weight=weight,
            )
            layer_states.append(state)
            total += new_tension
            if new_tension > max_tension:
                max_tension = new_tension

        snapshot = PredictiveTensionSnapshot(
            total_tension=round(total, 6),
            layer_states=layer_states,
            free_energy=round(engine.get_free_energy(), 6),
            mean_tension=round(total / max(1, len(layer_states)), 6),
            max_layer_tension=round(max_tension, 6),
        )
        return snapshot

    def get_drive_magnitude(self) -> float:
        """Return a scalar drive magnitude in [0, 1] for downstream modules."""
        total = sum(self._tensions.values())
        # Heuristic saturation: tension > 10.0 is treated as fully saturated
        return min(1.0, total / 10.0)

    def reset(self) -> None:
        self._tensions.clear()
