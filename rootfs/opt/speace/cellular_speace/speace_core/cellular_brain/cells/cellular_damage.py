from typing import Dict, List, Literal

from pydantic import BaseModel, Field

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit


DamageLevel = Literal["none", "reversible", "functional", "structural", "critical"]


class CellularDamageState(BaseModel):
    """T42B — Per-cell damage snapshot with granular components."""

    cell_id: str
    damage_score: float = 0.0
    level: DamageLevel = "none"
    reversible_damage: float = 0.0
    functional_damage: float = 0.0
    structural_damage: float = 0.0
    critical_damage: float = 0.0
    stress_exposure: float = 0.0
    cumulative_stress: float = 0.0
    repair_attempts: int = 0
    successful_repairs: int = 0


class CellularDamageResult(BaseModel):
    """Aggregate result of a damage evaluation pass."""

    per_cell: Dict[str, CellularDamageState] = Field(default_factory=dict)
    mean_damage: float = 0.0
    max_damage: float = 0.0
    reversible_count: int = 0
    functional_count: int = 0
    structural_count: int = 0
    critical_count: int = 0


class CellularDamageEngine:
    """T42B — Track and classify per-cell damage with granular components.

    Damage is a lagging indicator of stress. Cells accumulate damage when
    stress remains elevated across ticks. Damage levels gate the efficacy
    of repair and trigger defense escalation.
    """

    def __init__(
        self,
        stress_decay: float = 0.1,
        damage_accumulation_rate: float = 0.15,
        reversible_threshold: float = 0.20,
        functional_threshold: float = 0.40,
        structural_threshold: float = 0.60,
        critical_threshold: float = 0.80,
    ):
        self.stress_decay = stress_decay
        self.damage_accumulation_rate = damage_accumulation_rate
        self.reversible_threshold = reversible_threshold
        self.functional_threshold = functional_threshold
        self.structural_threshold = structural_threshold
        self.critical_threshold = critical_threshold

    def evaluate(
        self,
        circuit: NeuralCircuit,
        stress_result: "CellularStressResult",
        previous_damage: Dict[str, CellularDamageState] | None = None,
    ) -> CellularDamageResult:
        all_neurons = (
            circuit.input_neurons
            + circuit.hidden_neurons
            + circuit.output_neurons
        )
        per_cell: Dict[str, CellularDamageState] = {}
        scores: List[float] = []
        rev_count = func_count = struct_count = crit_count = 0

        prev = previous_damage or {}
        for neuron in all_neurons:
            old = prev.get(neuron.cell_id)
            state = self._compute_damage(neuron, stress_result, old)
            per_cell[neuron.cell_id] = state
            scores.append(state.damage_score)
            if state.level == "reversible":
                rev_count += 1
            elif state.level == "functional":
                func_count += 1
            elif state.level == "structural":
                struct_count += 1
            elif state.level == "critical":
                crit_count += 1

        mean_damage = sum(scores) / len(scores) if scores else 0.0
        max_damage = max(scores) if scores else 0.0
        return CellularDamageResult(
            per_cell=per_cell,
            mean_damage=round(mean_damage, 4),
            max_damage=round(max_damage, 4),
            reversible_count=rev_count,
            functional_count=func_count,
            structural_count=struct_count,
            critical_count=crit_count,
        )

    def _compute_damage(
        self,
        neuron: DigitalNeuron,
        stress_result: "CellularStressResult",
        old: CellularDamageState | None,
    ) -> CellularDamageState:
        stress = stress_result.per_cell.get(neuron.cell_id)
        current_stress = stress.stress_score if stress else 0.0

        if old is not None:
            cumulative = max(0.0, old.cumulative_stress * (1.0 - self.stress_decay) + current_stress)
            damage = min(1.0, old.damage_score + self.damage_accumulation_rate * current_stress)
            attempts = old.repair_attempts
            successes = old.successful_repairs
        else:
            cumulative = current_stress
            damage = self.damage_accumulation_rate * current_stress
            attempts = 0
            successes = 0

        # Granular damage decomposition
        reversible = min(damage, self.reversible_threshold)
        remaining = max(0.0, damage - reversible)
        functional = min(remaining, self.functional_threshold - self.reversible_threshold)
        remaining = max(0.0, remaining - functional)
        structural = min(remaining, self.structural_threshold - self.functional_threshold)
        remaining = max(0.0, remaining - structural)
        critical = remaining

        if damage >= self.critical_threshold:
            level: DamageLevel = "critical"
        elif damage >= self.structural_threshold:
            level = "structural"
        elif damage >= self.functional_threshold:
            level = "functional"
        elif damage >= self.reversible_threshold:
            level = "reversible"
        else:
            level = "none"

        return CellularDamageState(
            cell_id=neuron.cell_id,
            damage_score=round(damage, 4),
            level=level,
            reversible_damage=round(reversible, 4),
            functional_damage=round(functional, 4),
            structural_damage=round(structural, 4),
            critical_damage=round(critical, 4),
            stress_exposure=round(current_stress, 4),
            cumulative_stress=round(cumulative, 4),
            repair_attempts=attempts,
            successful_repairs=successes,
        )
