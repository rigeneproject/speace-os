"""UtilityDriveSystem — biological-style dynamic motivational drives for SPEACE (T165).

Six drives evolve via leaky integration from homeostatic, narrative, curiosity,
and causal world model inputs. Cross-inhibition prevents incompatible drives from
simultaneously dominating.
"""

from typing import Any, Dict, List, Optional


class UtilityDriveSystem:
    """Dynamic drive vector with leaky integration and cross-inhibition."""

    DRIVE_NAMES = (
        "exploration",
        "stability",
        "rest",
        "social_interaction",
        "prediction_error_reduction",
        "energy_conservation",
    )

    # Pairs of drives that mutually inhibit each other
    INHIBITION_PAIRS: List[tuple[str, str]] = [
        ("exploration", "rest"),
        ("exploration", "energy_conservation"),
        ("social_interaction", "rest"),
    ]

    def __init__(
        self,
        leak: float = 0.85,
        initial_values: Optional[Dict[str, float]] = None,
    ) -> None:
        if not 0.0 <= leak <= 1.0:
            raise ValueError("leak must be in [0, 1]")
        self._leak = leak
        self._drives: Dict[str, float] = {
            name: 0.5 for name in self.DRIVE_NAMES
        }
        if initial_values:
            for k, v in initial_values.items():
                if k in self._drives:
                    self._drives[k] = float(v)
        self._history: List[Dict[str, float]] = []
        self._max_history = 200

    # ------------------------------------------------------------------ #
    # Update
    # ------------------------------------------------------------------ #

    def tick(
        self,
        *,
        curiosity_score: float = 0.0,
        novelty_score: float = 0.0,
        prediction_error: float = 0.0,
        coherence: float = 0.0,
        noise_level: float = 0.0,
        energy: float = 1.0,
        circadian_phase: str = "day",
        dialogue_recency: float = 0.0,
        distributed_node_count: int = 0,
        metabolism_cost: float = 0.0,
        causal_model_uncertainty: float = 0.0,
        endogenous_bonus: float = 0.0,
    ) -> Dict[str, float]:
        """Update all drives via leaky integration from contextual inputs.

        Returns the updated drive vector.
        """
        # Compute raw inputs per drive [0, 1]
        inputs = {
            "exploration": self._blend(curiosity_score, novelty_score, prediction_error + endogenous_bonus),
            "stability": self._blend(coherence, 1.0 - noise_level, energy),
            "rest": self._blend(
                1.0 - energy,
                1.0 if circadian_phase in ("night", "sleep") else 0.0,
                0.0,  # placeholder for load; updated below
            ),
            "social_interaction": self._blend(dialogue_recency, 1.0 if distributed_node_count > 0 else 0.0, 0.0),
            "prediction_error_reduction": self._blend(prediction_error, causal_model_uncertainty, 0.0),
            "energy_conservation": self._blend(metabolism_cost, 1.0 - energy, 0.0),
        }

        # Adjust rest with cognitive load proxy (not passed directly; use energy dip)
        if energy < 0.3:
            inputs["rest"] = max(inputs["rest"], 0.7)

        # Leaky integration
        for name in self.DRIVE_NAMES:
            old = self._drives[name]
            new = self._leak * old + (1.0 - self._leak) * inputs[name]
            self._drives[name] = max(0.0, min(1.0, new))

        # Cross-inhibition
        for a, b in self.INHIBITION_PAIRS:
            da = self._drives[a]
            db = self._drives[b]
            if da > db:
                self._drives[b] *= max(0.0, 1.0 - da)
            elif db > da:
                self._drives[a] *= max(0.0, 1.0 - db)

        # Clamp again after inhibition
        for name in self.DRIVE_NAMES:
            self._drives[name] = max(0.0, min(1.0, self._drives[name]))

        # Record history
        self._history.append(dict(self._drives))
        if len(self._history) > self._max_history:
            self._history.pop(0)

        return dict(self._drives)

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get_drive(self, name: str) -> float:
        return self._drives.get(name, 0.0)

    def get_dominant_drive(self) -> str:
        return max(self._drives, key=self._drives.get)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "drives": dict(self._drives),
            "dominant_drive": self.get_dominant_drive(),
            "history_sample": [dict(h) for h in self._history[-20:]],
        }

    @staticmethod
    def _blend(a: float, b: float, c: float) -> float:
        """Simple weighted blend of three inputs."""
        return max(0.0, min(1.0, (a + b + c) / 3.0))
