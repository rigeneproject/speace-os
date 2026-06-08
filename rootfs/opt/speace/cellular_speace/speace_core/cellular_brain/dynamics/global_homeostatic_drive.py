import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Drive:
    name: str
    setpoint: float
    weight: float
    current_value: float = 0.0


class GlobalHomeostaticDrive:
    """Global homeostatic drive system that modulates brain parameters.

    Maintains four core drives:
    - exploration: seek novelty and learning opportunities
    - stability: maintain coherence and prevent chaos
    - survival: avoid damage and ensure safety
    - efficiency: conserve energy and metabolic resources

    Drive signals interact: high survival need suppresses exploration,
    and low energy (efficiency) suppresses plasticity.
    """

    def __init__(
        self,
        plasticity_range: tuple = (0.0, 2.0),
        exploration_range: tuple = (0.0, 2.0),
        energy_supply_range: tuple = (0.5, 1.5),
        stability_range: tuple = (0.5, 1.5),
        survival_suppression_threshold: float = 0.3,
        efficiency_plasticity_threshold: float = -0.2,
    ):
        self._drives: Dict[str, Drive] = {}
        self._modulation: Dict[str, float] = {
            "plasticity_multiplier": 1.0,
            "exploration_multiplier": 1.0,
            "energy_supply_multiplier": 1.0,
            "stability_multiplier": 1.0,
        }
        self.plasticity_range = plasticity_range
        self.exploration_range = exploration_range
        self.energy_supply_range = energy_supply_range
        self.stability_range = stability_range
        self.survival_suppression_threshold = survival_suppression_threshold
        self.efficiency_plasticity_threshold = efficiency_plasticity_threshold

        # Register default drives
        self.register_drive("exploration", setpoint=0.5, weight=1.0)
        self.register_drive("stability", setpoint=0.5, weight=1.0)
        self.register_drive("survival", setpoint=0.2, weight=1.5)
        self.register_drive("efficiency", setpoint=0.6, weight=1.0)

    # ------------------------------------------------------------------ #
    # Drive management
    # ------------------------------------------------------------------ #

    def register_drive(self, name: str, setpoint: float, weight: float) -> None:
        """Register a new drive or overwrite an existing one."""
        self._drives[name] = Drive(name=name, setpoint=setpoint, weight=weight)

    def update_drive(self, name: str, current_value: float) -> None:
        """Update the current level of a registered drive."""
        if name not in self._drives:
            raise KeyError(f"Drive '{name}' is not registered")
        self._drives[name].current_value = current_value

    def get_drive_signal(self, name: str) -> float:
        """Return the drive signal: deviation from setpoint multiplied by weight."""
        if name not in self._drives:
            raise KeyError(f"Drive '{name}' is not registered")
        drive = self._drives[name]
        return (drive.current_value - drive.setpoint) * drive.weight

    def list_drives(self) -> List[str]:
        """Return names of all registered drives."""
        return list(self._drives.keys())

    # ------------------------------------------------------------------ #
    # Modulation computation
    # ------------------------------------------------------------------ #

    def get_global_modulation(self) -> Dict[str, float]:
        """Return the current global modulation multipliers.

        Multipliers are derived from drive signals with the following interactions:
        - High survival need suppresses exploration.
        - Low efficiency (energy deficit) suppresses plasticity.
        """
        return dict(self._modulation)

    def step(self) -> Dict[str, float]:
        """Recalculate all modulations based on current drive levels.

        Returns the updated modulation dictionary.
        """
        signals = {name: self.get_drive_signal(name) for name in self._drives}

        # Base multipliers derived from individual drive signals using tanh squashing
        exploration_signal = signals.get("exploration", 0.0)
        stability_signal = signals.get("stability", 0.0)
        survival_signal = signals.get("survival", 0.0)
        efficiency_signal = signals.get("efficiency", 0.0)

        # Interaction: high survival need suppresses exploration
        if survival_signal > self.survival_suppression_threshold:
            exploration_signal -= survival_signal * 0.5

        # Interaction: low energy (efficiency deficit) suppresses plasticity
        plasticity_signal = exploration_signal
        if efficiency_signal < self.efficiency_plasticity_threshold:
            plasticity_signal += efficiency_signal * 0.5  # efficiency_signal is negative

        self._modulation["plasticity_multiplier"] = self._squash(
            plasticity_signal, self.plasticity_range
        )
        self._modulation["exploration_multiplier"] = self._squash(
            exploration_signal, self.exploration_range
        )
        self._modulation["energy_supply_multiplier"] = self._squash(
            -efficiency_signal, self.energy_supply_range
        )
        self._modulation["stability_multiplier"] = self._squash(
            stability_signal, self.stability_range
        )

        return self.get_global_modulation()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _squash(signal: float, range_: tuple) -> float:
        """Map a real-valued signal to a range using tanh squashing.

        tanh maps [-inf, +inf] to [-1, 1]; we remap to [min, max].
        """
        lo, hi = range_
        normalized = math.tanh(signal)
        return lo + (hi - lo) * ((normalized + 1.0) / 2.0)
