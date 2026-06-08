import math
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class EntropySnapshot(BaseModel):
    tick: int
    informational_entropy: float = 0.0
    thermodynamic_entropy: float = 0.0
    total_entropy: float = 0.0
    environmental_pressure: float = 0.0
    energy_cost: float = 0.0
    metadata: Dict[str, float] = Field(default_factory=dict)


class EntropyDynamicsMonitor:
    """T55 — Monitor informational and thermodynamic entropy for EDD-CVT."""

    def __init__(self, history_window: int = 100):
        self.history_window = history_window
        self._history: List[EntropySnapshot] = []
        self._tick: int = 0

    # ------------------------------------------------------------------ #
    # Core entropy computation
    # ------------------------------------------------------------------ #

    @staticmethod
    def _shannon_entropy(values: List[float]) -> float:
        total = sum(values)
        if total <= 0:
            return 0.0
        probs = [v / total for v in values if v > 0]
        return -sum(p * math.log(p) for p in probs)

    def compute_informational_entropy(
        self,
        activations: Optional[List[float]] = None,
        weights: Optional[List[float]] = None,
    ) -> float:
        s_info = 0.0
        if activations:
            s_info += self._shannon_entropy(activations)
        if weights:
            s_info += self._shannon_entropy(weights)
        return s_info

    def compute_thermodynamic_entropy(
        self,
        energies: Optional[List[float]] = None,
        mean_energy: float = 0.0,
    ) -> float:
        if energies:
            temps = [max(0.0, mean_energy - e) for e in energies]
            return self._shannon_entropy(temps)
        return 0.0

    def compute_total_entropy(
        self,
        informational: float,
        thermodynamic: float,
        alpha: float = 1.0,
        beta: float = 1.0,
    ) -> float:
        return alpha * informational + beta * thermodynamic

    # ------------------------------------------------------------------ #
    # Snapshot
    # ------------------------------------------------------------------ #

    def capture(
        self,
        tick: int,
        activations: Optional[List[float]] = None,
        weights: Optional[List[float]] = None,
        energies: Optional[List[float]] = None,
        mean_energy: float = 0.0,
        environmental_pressure: float = 0.0,
        energy_cost: float = 0.0,
    ) -> EntropySnapshot:
        s_info = self.compute_informational_entropy(activations, weights)
        s_thermo = self.compute_thermodynamic_entropy(energies, mean_energy)
        s_total = self.compute_total_entropy(s_info, s_thermo)
        snapshot = EntropySnapshot(
            tick=tick,
            informational_entropy=s_info,
            thermodynamic_entropy=s_thermo,
            total_entropy=s_total,
            environmental_pressure=environmental_pressure,
            energy_cost=energy_cost,
        )
        self._history.append(snapshot)
        if len(self._history) > self.history_window:
            self._history.pop(0)
        self._tick = tick
        return snapshot

    # ------------------------------------------------------------------ #
    # Derivatives
    # ------------------------------------------------------------------ #

    def entropy_derivative(self, ticks: int = 5) -> float:
        if len(self._history) < 2:
            return 0.0
        recent = self._history[-ticks:]
        if len(recent) < 2:
            recent = self._history
        deltas = [
            recent[i].total_entropy - recent[i - 1].total_entropy
            for i in range(1, len(recent))
        ]
        return sum(deltas) / len(deltas) if deltas else 0.0

    def should_mutate(self, threshold: float = 0.01) -> bool:
        return self.entropy_derivative() < threshold

    def should_stabilize(self, threshold: float = 0.05) -> bool:
        return self.entropy_derivative() > threshold

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #

    def summarize(self) -> Dict[str, float]:
        if not self._history:
            return {
                "informational_entropy": 0.0,
                "thermodynamic_entropy": 0.0,
                "total_entropy": 0.0,
                "entropy_derivative": 0.0,
                "mean_environmental_pressure": 0.0,
            }
        recent = self._history[-10:]
        return {
            "informational_entropy": sum(h.informational_entropy for h in recent) / len(recent),
            "thermodynamic_entropy": sum(h.thermodynamic_entropy for h in recent) / len(recent),
            "total_entropy": sum(h.total_entropy for h in recent) / len(recent),
            "entropy_derivative": self.entropy_derivative(),
            "mean_environmental_pressure": sum(h.environmental_pressure for h in recent) / len(recent),
        }
