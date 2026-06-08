import random
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class PerturbationPulse(BaseModel):
    pulse_id: str
    target_type: str  # "activation", "energy", "weight", "routing", "semantic"
    strength: float = Field(default=0.0, ge=0.0, le=1.0)
    target_ids: List[str] = Field(default_factory=list)
    metadata: Dict[str, float] = Field(default_factory=dict)


class PerturbationField:
    """T55 — Controlled perturbation field V(x,t) for EDD-CVT."""

    def __init__(self, base_strength: float = 0.1, seed: int = 42):
        self.base_strength = base_strength
        self.rng = random.Random(seed)
        self._pulse_count: int = 0

    # ------------------------------------------------------------------ #
    # Pulse generation
    # ------------------------------------------------------------------ #

    def generate_pulse(
        self,
        target_type: str,
        candidate_ids: List[str],
        strength: Optional[float] = None,
        top_k: Optional[int] = None,
    ) -> PerturbationPulse:
        s = strength if strength is not None else self.base_strength
        if top_k is not None and candidate_ids:
            targets = self.rng.sample(candidate_ids, min(top_k, len(candidate_ids)))
        else:
            targets = list(candidate_ids)
        self._pulse_count += 1
        return PerturbationPulse(
            pulse_id=f"pulse_{self._pulse_count}_{target_type}",
            target_type=target_type,
            strength=s,
            target_ids=targets,
        )

    # ------------------------------------------------------------------ #
    # Batch generation
    # ------------------------------------------------------------------ #

    def generate_field_pulse_batch(
        self,
        neuron_ids: List[str],
        synapse_ids: List[str],
        strength: Optional[float] = None,
    ) -> List[PerturbationPulse]:
        s = strength if strength is not None else self.base_strength
        pulses: List[PerturbationPulse] = []
        if neuron_ids:
            pulses.append(self.generate_pulse("activation", neuron_ids, strength=s, top_k=max(1, len(neuron_ids) // 4)))
        if neuron_ids:
            pulses.append(self.generate_pulse("energy", neuron_ids, strength=s * 0.6, top_k=max(1, len(neuron_ids) // 6)))
        if synapse_ids:
            pulses.append(self.generate_pulse("weight", synapse_ids, strength=s * 0.4, top_k=max(1, len(synapse_ids) // 8)))
        return pulses

    # ------------------------------------------------------------------ #
    # Adaptive strength
    # ------------------------------------------------------------------ #

    def adaptive_strength(
        self,
        entropy_delta: float,
        fitness_delta: float,
        min_strength: float = 0.05,
        max_strength: float = 0.5,
    ) -> float:
        """Increase strength when entropy is low and fitness is stagnant."""
        if entropy_delta < 0 and fitness_delta <= 0:
            candidate = self.base_strength * 1.2
        elif entropy_delta > 0.1 and fitness_delta > 0:
            candidate = self.base_strength * 0.8
        else:
            candidate = self.base_strength
        return max(min_strength, min(max_strength, candidate))

    # ------------------------------------------------------------------ #
    # Apply pulse to circuit
    # ------------------------------------------------------------------ #

    @staticmethod
    def apply_pulse(
        pulse: PerturbationPulse,
        neurons: Optional[List] = None,
        synapses: Optional[List] = None,
    ) -> None:
        if pulse.target_type == "activation" and neurons is not None:
            for n in neurons:
                if hasattr(n, "activation") and hasattr(n, "cell_id") and n.cell_id in pulse.target_ids:
                    n.activation = min(1.0, n.activation + pulse.strength)
        elif pulse.target_type == "energy" and neurons is not None:
            for n in neurons:
                if hasattr(n, "energy") and hasattr(n, "cell_id") and n.cell_id in pulse.target_ids:
                    n.energy = max(0.1, n.energy - pulse.strength)
        elif pulse.target_type == "weight" and synapses is not None:
            for s in synapses:
                if hasattr(s, "weight") and hasattr(s, "cell_id") and s.cell_id in pulse.target_ids:
                    s.weight = min(1.0, s.weight + pulse.strength * 0.1)
