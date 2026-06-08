import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CriticalityState(BaseModel):
    state: str = "balanced"  # rigid, balanced, chaotic, collapsing
    system_entropy: float = 0.0
    behavioral_diversity: float = 0.0
    modularity_score: float = 0.0
    pathway_volatility: float = 0.0
    coherence_phi: float = 0.0
    mean_energy: float = 0.0
    plasticity_rate: float = 0.0
    instability_mean: float = 0.0
    order_chaos_balance: float = 0.0
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CriticalityMonitor:
    """Monitor criticality metrics and classify system state."""

    def __init__(
        self,
        entropy_window: int = 10,
        phi_baseline: float = 0.25,
        energy_baseline: float = 0.5,
    ):
        self.entropy_window = entropy_window
        self.phi_baseline = phi_baseline
        self.energy_baseline = energy_baseline
        self._history: List[CriticalityState] = []
        self._phi_history: List[float] = []
        self._energy_history: List[float] = []

    # ------------------------------------------------------------------ #
    # Core metrics
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_system_entropy(
        activations: List[float],
    ) -> float:
        if not activations:
            return 0.0
        total = sum(activations)
        if total == 0:
            return 1.0
        probs = [a / total for a in activations]
        entropy = -sum(p * math.log(p + 1e-12) for p in probs)
        max_entropy = math.log(len(activations) + 1e-12)
        if max_entropy == 0:
            return 0.0
        return entropy / max_entropy

    @staticmethod
    def compute_behavioral_diversity(
        neuron_activations: List[float],
    ) -> float:
        if not neuron_activations:
            return 0.0
        mean_act = sum(neuron_activations) / len(neuron_activations)
        variance = sum((a - mean_act) ** 2 for a in neuron_activations) / len(neuron_activations)
        return round(min(1.0, math.sqrt(variance)), 4)

    @staticmethod
    def compute_modularity_score(
        region_activations: Dict[str, float],
        inter_region_flow: Dict[str, float],
    ) -> float:
        if not region_activations:
            return 0.0
        total_activation = sum(region_activations.values())
        if total_activation == 0:
            return 0.0
        # Modularity proxy: high intra-region activation relative to inter-region flow
        intra = total_activation
        inter = sum(inter_region_flow.values())
        if intra + inter == 0:
            return 0.0
        return round(intra / (intra + inter), 4)

    @staticmethod
    def compute_pathway_volatility(
        pathway_strengths: List[float],
        previous_strengths: Optional[List[float]] = None,
    ) -> float:
        if not pathway_strengths:
            return 0.0
        if previous_strengths is None or len(previous_strengths) != len(pathway_strengths):
            return 0.0
        diffs = [abs(s - p) for s, p in zip(pathway_strengths, previous_strengths)]
        return round(sum(diffs) / len(diffs), 4)

    # ------------------------------------------------------------------ #
    # State classification
    # ------------------------------------------------------------------ #

    def classify_state(self, metrics: CriticalityState) -> str:
        entropy = metrics.system_entropy
        diversity = metrics.behavioral_diversity
        volatility = metrics.pathway_volatility
        instability = metrics.instability_mean
        phi = metrics.coherence_phi
        energy = metrics.mean_energy

        # Rigid: low entropy, low diversity, low volatility, stable
        if entropy < 0.2 and diversity < 0.2 and volatility < 0.1 and instability < 0.2:
            return "rigid"

        # Collapsing: high instability, very low phi, very high energy stress
        if instability > 0.75 or (phi < 0.1 and energy > 0.9):
            return "collapsing"

        # Chaotic: high entropy, high diversity, high volatility
        if entropy > 0.7 and diversity > 0.6 and volatility > 0.3:
            return "chaotic"

        # Balanced: intermediate values
        return "balanced"

    def compute_order_chaos_balance(self, metrics: CriticalityState) -> float:
        """Return a score in [0,1] where 0.5 is ideal balance."""
        entropy_norm = metrics.system_entropy
        diversity_norm = metrics.behavioral_diversity
        volatility_norm = min(1.0, metrics.pathway_volatility * 3.0)

        order_score = 1.0 - max(entropy_norm, diversity_norm, volatility_norm)
        chaos_score = max(entropy_norm, diversity_norm, volatility_norm)
        # Balance is closeness to 0.5
        balance = 1.0 - abs(order_score - chaos_score)
        return round(max(0.0, min(1.0, balance)), 4)

    # ------------------------------------------------------------------ #
    # Update cycle
    # ------------------------------------------------------------------ #

    def update(
        self,
        neuron_activations: Optional[List[float]] = None,
        region_activations: Optional[Dict[str, float]] = None,
        inter_region_flow: Optional[Dict[str, float]] = None,
        pathway_strengths: Optional[List[float]] = None,
        previous_pathway_strengths: Optional[List[float]] = None,
        coherence_phi: float = 0.0,
        mean_energy: float = 0.0,
        plasticity_rate: float = 0.0,
        instability_mean: float = 0.0,
    ) -> CriticalityState:
        entropy = self.compute_system_entropy(neuron_activations or [])
        diversity = self.compute_behavioral_diversity(neuron_activations or [])
        modularity = self.compute_modularity_score(
            region_activations or {}, inter_region_flow or {}
        )
        volatility = self.compute_pathway_volatility(
            pathway_strengths or [], previous_pathway_strengths
        )

        state = CriticalityState(
            system_entropy=entropy,
            behavioral_diversity=diversity,
            modularity_score=modularity,
            pathway_volatility=volatility,
            coherence_phi=coherence_phi,
            mean_energy=mean_energy,
            plasticity_rate=plasticity_rate,
            instability_mean=instability_mean,
        )
        state.state = self.classify_state(state)
        state.order_chaos_balance = self.compute_order_chaos_balance(state)

        self._history.append(state)
        if len(self._history) > self.entropy_window:
            self._history.pop(0)
        self._phi_history.append(coherence_phi)
        if len(self._phi_history) > self.entropy_window:
            self._phi_history.pop(0)
        self._energy_history.append(mean_energy)
        if len(self._energy_history) > self.entropy_window:
            self._energy_history.pop(0)

        return state

    def latest_state(self) -> Optional[CriticalityState]:
        return self._history[-1] if self._history else None

    def phi_trend(self) -> float:
        if len(self._phi_history) < 2:
            return 0.0
        return round(self._phi_history[-1] - self._phi_history[0], 4)

    def energy_trend(self) -> float:
        if len(self._energy_history) < 2:
            return 0.0
        return round(self._energy_history[-1] - self._energy_history[0], 4)

    def summary(self) -> Dict[str, Any]:
        latest = self.latest_state()
        return {
            "latest_state": latest.model_dump() if latest else None,
            "history_length": len(self._history),
            "phi_trend": self.phi_trend(),
            "energy_trend": self.energy_trend(),
        }
