import math
from typing import Dict


class DriveConflictResolver:
    """Resolves conflicts between competing drives using winner-take-all with inhibition.

    When two or more drives demand incompatible actions, the resolver:
    1. Identifies the dominant (highest-urgency) drive.
    2. Amplifies it via a competitive gain factor.
    3. Suppresses conflicting drives by a damping factor.
    4. Returns a dict of modulation weights (0..1+) that downstream systems can apply.
    """

    # Pair-wise conflict matrix: if drive A is dominant, how much should drive B be damped?
    # Higher value = more suppression. 1.0 = no suppression. 0.0 = full suppression.
    _DEFAULT_CONFLICTS: Dict[str, Dict[str, float]] = {
        "self_preservation": {
            "information_exploration": 0.2,
            "adaptive_exploration": 0.2,
            "resource_acquisition": 0.6,
            "energy_conservation": 0.8,
            "homeostatic_equilibrium": 0.9,
            "coherence_maintenance": 0.7,
        },
        "energy_conservation": {
            "resource_acquisition": 0.1,
            "information_exploration": 0.5,
            "adaptive_exploration": 0.4,
            "self_preservation": 0.9,
            "homeostatic_equilibrium": 0.9,
            "coherence_maintenance": 0.8,
        },
        "resource_acquisition": {
            "energy_conservation": 0.3,
            "self_preservation": 0.8,
            "information_exploration": 0.7,
            "adaptive_exploration": 0.6,
            "homeostatic_equilibrium": 0.8,
            "coherence_maintenance": 0.8,
        },
        "information_exploration": {
            "self_preservation": 0.3,
            "energy_conservation": 0.6,
            "homeostatic_equilibrium": 0.8,
            "coherence_maintenance": 0.7,
            "resource_acquisition": 0.7,
            "adaptive_exploration": 0.9,
        },
        "homeostatic_equilibrium": {
            "adaptive_exploration": 0.6,
            "information_exploration": 0.7,
            "resource_acquisition": 0.8,
            "self_preservation": 0.9,
            "energy_conservation": 0.9,
            "coherence_maintenance": 0.9,
        },
        "adaptive_exploration": {
            "homeostatic_equilibrium": 0.5,
            "coherence_maintenance": 0.5,
            "self_preservation": 0.4,
            "energy_conservation": 0.6,
            "resource_acquisition": 0.7,
            "information_exploration": 0.9,
        },
        "coherence_maintenance": {
            "adaptive_exploration": 0.5,
            "information_exploration": 0.8,
            "self_preservation": 0.8,
            "energy_conservation": 0.9,
            "resource_acquisition": 0.9,
            "homeostatic_equilibrium": 0.9,
        },
    }

    def __init__(
        self,
        winner_amplification: float = 1.3,
        conflict_matrix: Dict[str, Dict[str, float]] = None,
    ):
        self.winner_amplification = winner_amplification
        self._conflict_matrix = conflict_matrix or self._default_conflict_matrix()

    def _default_conflict_matrix(self) -> Dict[str, Dict[str, float]]:
        """Return a deep copy of the default conflict matrix."""
        return {
            outer: {inner: val for inner, val in inner_dict.items()}
            for outer, inner_dict in self._DEFAULT_CONFLICTS.items()
        }

    def resolve(self, drives: Dict[str, float]) -> Dict[str, float]:
        """Return a dict of modulation weights for each drive.

        Parameters
        ----------
        drives : dict[str, float]
            Mapping of drive name to raw urgency (or any scalar signal).

        Returns
        -------
        dict[str, float]
            Modulation weight for each drive. The dominant drive is amplified;
            conflicting drives are suppressed based on the conflict matrix.
        """
        if not drives:
            return {}

        # Identify winner
        winner_name = max(drives, key=drives.get)
        winner_value = drives[winner_name]

        # If all drives are zero / flat, return uniform weights
        total = sum(abs(v) for v in drives.values())
        if total == 0:
            return {name: 1.0 for name in drives}

        weights: Dict[str, float] = {}
        winner_conflicts = self._conflict_matrix.get(winner_name, {})

        for name, value in drives.items():
            if name == winner_name:
                # Amplify the winner
                weights[name] = value * self.winner_amplification
            else:
                # Apply conflict suppression
                damping = winner_conflicts.get(name, 1.0)
                weights[name] = value * damping

        return weights

    def get_drive_balance(self, drives: Dict[str, float]) -> float:
        """Measure how balanced vs. lopsided the drive landscape is.

        Returns a value in [0, 1] where:
        - 0.0 = perfectly balanced (all drives equal)
        - 1.0 = completely lopsided (one drive dominates)

        Uses the Gini coefficient of the drive values as a balance metric.
        """
        if not drives:
            return 0.0

        values = list(drives.values())
        n = len(values)
        if n == 1:
            return 1.0

        total = sum(values)
        if total == 0:
            return 0.0

        # Normalise to probability distribution
        probs = [v / total for v in values]

        # Shannon entropy balance: 1 - (entropy / max_entropy)
        entropy = -sum(p * math.log(p + 1e-12) for p in probs)
        max_entropy = math.log(n)
        if max_entropy == 0:
            return 0.0

        # Entropy = 1.0 when perfectly balanced, 0.0 when lopsided.
        # We want lopsided = 1.0, so invert.
        return 1.0 - (entropy / max_entropy)
