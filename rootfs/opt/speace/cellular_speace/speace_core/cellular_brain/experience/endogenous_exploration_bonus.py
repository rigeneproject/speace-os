"""Endogenous Exploration Bonus — intrinsically motivated curiosity signals.

Provides:
- Pseudo-count bonus: exploration bonus inversely proportional to sqrt(visit count)
- RND-like bonus: fixed-target vs online prediction error as novelty signal
"""

import math
import random
from typing import Any, Dict, Optional

import numpy as np
from pydantic import BaseModel, ConfigDict, Field


class ExplorationBonusResult(BaseModel):
    """Output of an exploration-bonus computation."""

    pseudo_count_bonus: float = 0.0
    rnd_bonus: float = 0.0
    total_bonus: float = 0.0
    visit_count: int = 0
    prediction_error: float = 0.0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ExplorationBonusModel:
    """Endogenous curiosity bonus model.

    Combines count-based and RND-like bonuses to produce an exploration
    signal independent of external reward.
    """

    def __init__(
        self,
        pseudo_count_scale: float = 0.5,
        pseudo_count_bonus_cap: float = 1.0,
        rnd_scale: float = 0.5,
        rnd_seed: int = 42,
        feature_dim: int = 8,
    ) -> None:
        self.pseudo_count_scale = pseudo_count_scale
        self.pseudo_count_bonus_cap = pseudo_count_bonus_cap
        self.rnd_scale = rnd_scale
        self._visit_counts: Dict[str, int] = {}
        self._feature_dim = feature_dim

        # Fixed RND target network (random, never trained)
        rng = np.random.default_rng(rnd_seed)
        self._rnd_target_weights = rng.standard_normal((feature_dim, feature_dim))
        self._rnd_target_bias = rng.standard_normal(feature_dim)

        # Online predictor (starts random, adapted via simple delta rule)
        self._rnd_online_weights = rng.standard_normal((feature_dim, feature_dim))
        self._rnd_online_bias = rng.standard_normal(feature_dim)
        self._rnd_lr = 0.01

    def _state_key(self, state: Any) -> str:
        """Hash a state descriptor into a countable key."""
        if isinstance(state, dict):
            # Sort keys for deterministic serialization
            return "|".join(f"{k}={v}" for k, v in sorted(state.items()))
        return str(state)

    def _extract_feature(self, state: Any) -> np.ndarray:
        """Create a simple fixed-size feature vector from an arbitrary state."""
        if isinstance(state, dict):
            # Hash-derived deterministic feature (not learned, so safe)
            vals = [hash(str(v)) % 1000 for v in state.values()]
            if len(vals) < self._feature_dim:
                vals += [0] * (self._feature_dim - len(vals))
            return np.array(vals[: self._feature_dim], dtype=float) / 1000.0
        if isinstance(state, (list, tuple, np.ndarray)):
            arr = np.asarray(state, dtype=float).flatten()[: self._feature_dim]
            pad = np.zeros(self._feature_dim - arr.shape[0])
            return np.concatenate([arr, pad])
        # Fallback: use hash to seed a deterministic vector
        h = abs(hash(str(state)))
        rng = np.random.default_rng(h)
        return rng.random(self._feature_dim).astype(float)

    def compute_bonus(
        self,
        state: Any,
        online_update: bool = True,
    ) -> ExplorationBonusResult:
        """Return exploration bonus for a state."""
        key = self._state_key(state)
        count = self._visit_counts.get(key, 0)
        pseudo_bonus = min(
            self.pseudo_count_bonus_cap,
            self.pseudo_count_scale / math.sqrt(1 + count),
        )
        self._visit_counts[key] = count + 1

        # RND-like bonus
        feat = self._extract_feature(state)
        target = np.tanh(self._rnd_target_weights @ feat + self._rnd_target_bias)
        online = np.tanh(self._rnd_online_weights @ feat + self._rnd_online_bias)
        pred_error = float(np.mean((target - online) ** 2))
        rnd_bonus = min(1.0, self.rnd_scale * pred_error)

        if online_update:
            # Simple delta-rule update of online predictor toward target
            delta = target - online
            self._rnd_online_weights += self._rnd_lr * np.outer(delta, feat)
            self._rnd_online_bias += self._rnd_lr * delta

        total = min(1.0, pseudo_bonus + rnd_bonus)
        return ExplorationBonusResult(
            pseudo_count_bonus=round(pseudo_bonus, 6),
            rnd_bonus=round(rnd_bonus, 6),
            total_bonus=round(total, 6),
            visit_count=count + 1,
            prediction_error=round(pred_error, 6),
        )

    def reset_counts(self) -> None:
        self._visit_counts.clear()

    def summary(self) -> Dict[str, Any]:
        if not self._visit_counts:
            return {"states_visited": 0, "mean_visits": 0.0}
        counts = list(self._visit_counts.values())
        return {
            "states_visited": len(counts),
            "mean_visits": sum(counts) / len(counts),
            "max_visits": max(counts),
        }
