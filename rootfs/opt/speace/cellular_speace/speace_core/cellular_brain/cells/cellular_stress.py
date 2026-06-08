from typing import Dict, List, Literal

from pydantic import BaseModel, Field

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit


StressLevel = Literal["normal", "elevated", "high", "critical"]


class CellularStressState(BaseModel):
    """T42B — Per-cell stress snapshot with granular components."""

    cell_id: str
    stress_score: float = 0.0
    level: StressLevel = "normal"
    activation_stress: float = 0.0
    energy_stress: float = 0.0
    synaptic_stress: float = 0.0
    routing_stress: float = 0.0
    plasticity_stress: float = 0.0
    confidence_stress: float = 0.0
    firing_rate_contribution: float = 0.0
    apoptosis_risk_contribution: float = 0.0


class CellularStressResult(BaseModel):
    """Aggregate result of a stress evaluation pass."""

    per_cell: Dict[str, CellularStressState] = Field(default_factory=dict)
    mean_stress: float = 0.0
    max_stress: float = 0.0
    critical_count: int = 0
    high_count: int = 0
    elevated_count: int = 0


class CellularStressEngine:
    """T42B — Evaluate per-cell stress from energy, activation, and history.

    Stress accumulates when a neuron is energetically depleted, hyperactive,
    or carries high apoptosis risk. Stress levels drive downstream damage,
    repair, defense, and epigenetic adaptation.
    """

    def __init__(
        self,
        energy_weight: float = 0.35,
        activation_weight: float = 0.25,
        firing_weight: float = 0.20,
        apoptosis_risk_weight: float = 0.20,
        critical_threshold: float = 0.75,
        high_threshold: float = 0.50,
        elevated_threshold: float = 0.25,
    ):
        self.energy_weight = energy_weight
        self.activation_weight = activation_weight
        self.firing_weight = firing_weight
        self.apoptosis_risk_weight = apoptosis_risk_weight
        self.critical_threshold = critical_threshold
        self.high_threshold = high_threshold
        self.elevated_threshold = elevated_threshold

    def evaluate(self, circuit: NeuralCircuit) -> CellularStressResult:
        all_neurons = (
            circuit.input_neurons
            + circuit.hidden_neurons
            + circuit.output_neurons
        )
        per_cell: Dict[str, CellularStressState] = {}
        scores: List[float] = []
        critical_count = 0
        high_count = 0
        elevated_count = 0

        for neuron in all_neurons:
            state = self._compute_stress(neuron)
            per_cell[neuron.cell_id] = state
            scores.append(state.stress_score)
            if state.level == "critical":
                critical_count += 1
            elif state.level == "high":
                high_count += 1
            elif state.level == "elevated":
                elevated_count += 1

        mean_stress = sum(scores) / len(scores) if scores else 0.0
        max_stress = max(scores) if scores else 0.0
        return CellularStressResult(
            per_cell=per_cell,
            mean_stress=round(mean_stress, 4),
            max_stress=round(max_stress, 4),
            critical_count=critical_count,
            high_count=high_count,
            elevated_count=elevated_count,
        )

    def _compute_stress(self, neuron: DigitalNeuron) -> CellularStressState:
        # Energy depletion stress (inverse of energy)
        energy_stress = max(0.0, 1.0 - neuron.energy)
        # Activation stress (high sustained activation)
        activation_stress = min(1.0, abs(neuron.activation) / 2.0)
        # Firing rate stress (consecutive fires)
        firing_stress = min(1.0, neuron.consecutive_fires / 5.0)
        # Apoptosis risk stress
        apoptosis_stress = min(1.0, getattr(neuron, "apoptosis_risk", 0.0))
        # Synaptic stress: proxy from target count and weight instability
        synaptic_stress = self._synaptic_stress(neuron)
        # Routing stress: proxy from regional routing load
        routing_stress = self._routing_stress(neuron)
        # Plasticity stress: proxy from threshold instability
        plasticity_stress = self._plasticity_stress(neuron)
        # Confidence stress: proxy from error history length
        confidence_stress = self._confidence_stress(neuron)

        stress_score = (
            self.energy_weight * energy_stress
            + self.activation_weight * activation_stress
            + self.firing_weight * firing_stress
            + self.apoptosis_risk_weight * apoptosis_stress
        )
        # Blend in the new granular components with small weights so they inform but don't dominate
        stress_score = min(1.0, stress_score + 0.03 * synaptic_stress + 0.02 * routing_stress + 0.02 * plasticity_stress + 0.01 * confidence_stress)

        if stress_score >= self.critical_threshold:
            level: StressLevel = "critical"
        elif stress_score >= self.high_threshold:
            level = "high"
        elif stress_score >= self.elevated_threshold:
            level = "elevated"
        else:
            level = "normal"

        return CellularStressState(
            cell_id=neuron.cell_id,
            stress_score=round(stress_score, 4),
            level=level,
            activation_stress=round(activation_stress, 4),
            energy_stress=round(energy_stress, 4),
            synaptic_stress=round(synaptic_stress, 4),
            routing_stress=round(routing_stress, 4),
            plasticity_stress=round(plasticity_stress, 4),
            confidence_stress=round(confidence_stress, 4),
            firing_rate_contribution=round(firing_stress, 4),
            apoptosis_risk_contribution=round(apoptosis_stress, 4),
        )

    def _synaptic_stress(self, neuron: DigitalNeuron) -> float:
        target_count = len(getattr(neuron, "targets", []))
        return min(1.0, target_count / 20.0)

    def _routing_stress(self, neuron: DigitalNeuron) -> float:
        region = getattr(neuron, "region", None)
        if region:
            # Deep regions carry higher routing load
            deep_regions = {"limbic", "hippocampus", "default_mode", "prefrontal", "cerebellar", "brainstem_homeostatic"}
            return 0.3 if region in deep_regions else 0.1
        return 0.0

    def _plasticity_stress(self, neuron: DigitalNeuron) -> float:
        threshold = getattr(neuron, "threshold", 0.5)
        return min(1.0, abs(threshold - 0.5) / 0.5)

    def _confidence_stress(self, neuron: DigitalNeuron) -> float:
        error_history = getattr(neuron, "error_history", [])
        return min(1.0, len(error_history) / 10.0)
