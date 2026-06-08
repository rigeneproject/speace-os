import math
from typing import List

from pydantic import BaseModel

from speace_core.cellular_brain.cells.digital_astrocyte import DigitalAstrocyte
from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron


class SystemMetrics(BaseModel):
    tick: int = 0
    coherence_phi: float = 0.0
    mean_energy: float = 0.0
    active_neurons: int = 0
    pruned_synapses: int = 0
    myelinated_pathways: int = 0
    mean_latency_ms: float = 0.0
    noise_level: float = 0.0
    mutation_log: List[str] = []


class HomeostasisEngine:
    def compute_metrics(
        self,
        tick: int,
        neurons: List[DigitalNeuron],
        astrocytes: List[DigitalAstrocyte],
        synapse_count: int,
        pruned_count: int,
    ) -> SystemMetrics:
        energies = [n.energy for n in neurons]
        mean_energy = sum(energies) / len(energies) if energies else 0.0
        active = sum(1 for n in neurons if n.activation > 0.1)
        noise = sum(a.noise_level for a in astrocytes) / len(astrocytes) if astrocytes else 0.0

        # Coherence Phi as normalized inverse entropy of activations
        activations = [n.activation for n in neurons]
        phi = self._compute_phi(activations)

        return SystemMetrics(
            tick=tick,
            coherence_phi=phi,
            mean_energy=mean_energy,
            active_neurons=active,
            pruned_synapses=pruned_count,
            noise_level=noise,
        )

    def _compute_phi(self, values: List[float]) -> float:
        if not values:
            return 0.0
        total = sum(values)
        if total == 0:
            return 0.0
        probs = [v / total for v in values]
        entropy = -sum(p * math.log(p + 1e-12) for p in probs)
        max_entropy = math.log(len(values) + 1e-12)
        if max_entropy == 0:
            return 1.0
        return 1.0 - (entropy / max_entropy)
