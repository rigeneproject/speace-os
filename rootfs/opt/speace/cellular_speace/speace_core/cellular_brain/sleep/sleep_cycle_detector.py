from enum import Enum
from typing import List

from pydantic import BaseModel, ConfigDict

from speace_core.cellular_brain.regulation.homeostasis_engine import SystemMetrics


class SleepPhase(str, Enum):
    AWAKE = "awake"
    SLEEP_ELIGIBLE = "sleep_eligible"
    SLEEPING = "sleeping"


class SleepState(BaseModel):
    phase: SleepPhase = SleepPhase.AWAKE
    stability_score: float = 0.0
    ticks_in_current_phase: int = 0
    consecutive_stable_ticks: int = 0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class SleepCycleDetector:
    """Detects when the system is stable enough to enter digital sleep."""

    def __init__(
        self,
        stability_window: int = 20,
        min_consecutive_stable: int = 5,
        phi_delta_threshold: float = 0.02,
        energy_delta_threshold: float = 0.03,
        active_neuron_change_threshold: float = 0.05,
    ):
        self.stability_window = stability_window
        self.min_consecutive_stable = min_consecutive_stable
        self.phi_delta_threshold = phi_delta_threshold
        self.energy_delta_threshold = energy_delta_threshold
        self.active_neuron_change_threshold = active_neuron_change_threshold

    def detect(self, metrics_log: List[SystemMetrics]) -> SleepState:
        if len(metrics_log) < self.stability_window:
            return SleepState(phase=SleepPhase.AWAKE, stability_score=0.0)

        recent = metrics_log[-self.stability_window :]
        phi_values = [m.coherence_phi for m in recent]
        energy_values = [m.mean_energy for m in recent]
        active_values = [m.active_neurons for m in recent]

        phi_delta = max(phi_values) - min(phi_values)
        energy_delta = max(energy_values) - min(energy_values)
        active_delta = max(active_values) - min(active_values)
        max_active = max(active_values) if active_values else 1
        active_ratio = active_delta / max_active if max_active > 0 else 0.0

        stable = (
            phi_delta <= self.phi_delta_threshold
            and energy_delta <= self.energy_delta_threshold
            and active_ratio <= self.active_neuron_change_threshold
        )

        stability_score = 1.0 - min(
            1.0,
            (
                phi_delta / self.phi_delta_threshold
                + energy_delta / self.energy_delta_threshold
                + active_ratio / self.active_neuron_change_threshold
            )
            / 3.0,
        )

        return SleepState(
            phase=SleepPhase.SLEEP_ELIGIBLE if stable else SleepPhase.AWAKE,
            stability_score=stability_score,
            consecutive_stable_ticks=sum(1 for _ in range(len(recent) - 1) if stable),
        )
