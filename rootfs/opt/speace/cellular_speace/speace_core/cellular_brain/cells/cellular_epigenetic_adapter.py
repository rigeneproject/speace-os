from typing import Dict, List

from pydantic import BaseModel, Field

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType


class GeneExpressionProfile(BaseModel):
    """T42B — Local gene expression profile with numeric expression factors."""

    cell_id: str
    plasticity_expression: float = 1.0
    repair_expression: float = 0.0
    defense_expression: float = 0.0
    energy_expression: float = 1.0
    growth_expression: float = 0.0
    apoptosis_sensitivity: float = 0.5
    differentiation_bias: float = 0.0
    expression_shift_count: int = 0
    last_shift_tick: int = 0


class EpigeneticShift(BaseModel):
    """Record of a single epigenetic shift."""

    cell_id: str
    tick: int
    trigger: str = ""
    genes_added: List[str] = Field(default_factory=list)
    genes_removed: List[str] = Field(default_factory=list)


class CellularEpigeneticResult(BaseModel):
    """Aggregate result of an epigenetic adaptation pass."""

    profiles: Dict[str, GeneExpressionProfile] = Field(default_factory=dict)
    shifts: List[EpigeneticShift] = Field(default_factory=list)
    epigenetic_shift_count: int = 0
    mean_gene_count: float = 0.0
    epigenetic_adaptation_score: float = 0.0


class CellularEpigeneticAdapter:
    """T42B — Local epigenetic adaptation per cell with numeric expression factors.

    Each cell maintains its own gene expression profile. Stress and damage
    triggers shift expression factors toward stress-response, repair, defense, or
    metabolic genes. Shifts are recorded and influence downstream behavior.
    """

    def __init__(
        self,
        stress_response_threshold: float = 0.50,
        repair_trigger_threshold: float = 0.40,
        defense_trigger_threshold: float = 0.60,
        metabolic_boost_threshold: float = 0.30,
    ):
        self.stress_response_threshold = stress_response_threshold
        self.repair_trigger_threshold = repair_trigger_threshold
        self.defense_trigger_threshold = defense_trigger_threshold
        self.metabolic_boost_threshold = metabolic_boost_threshold

    def adapt(
        self,
        circuit: NeuralCircuit,
        stress_per_cell: Dict[str, "CellularStressState"],
        damage_per_cell: Dict[str, "CellularDamageState"],
        current_tick: int,
        memory: MorphologicalMemory | None = None,
    ) -> CellularEpigeneticResult:
        from speace_core.cellular_brain.cells.cellular_stress import CellularStressState
        from speace_core.cellular_brain.cells.cellular_damage import CellularDamageState

        all_neurons = (
            circuit.input_neurons
            + circuit.hidden_neurons
            + circuit.output_neurons
        )
        profiles: Dict[str, GeneExpressionProfile] = {}
        shifts: List[EpigeneticShift] = []

        for neuron in all_neurons:
            stress = stress_per_cell.get(neuron.cell_id)
            damage = damage_per_cell.get(neuron.cell_id)
            profile, shift = self._adapt_cell(
                neuron, stress, damage, current_tick
            )
            profiles[neuron.cell_id] = profile
            if shift is not None:
                shifts.append(shift)
                if memory is not None:
                    memory.create_event(
                        event_type=MorphologyEventType.CELLULAR_EPIGENETIC_SHIFT,
                        source_id="cellular_epigenetic_adapter",
                        target_id=neuron.cell_id,
                        metadata={
                            "trigger": shift.trigger,
                            "genes_added": shift.genes_added,
                            "genes_removed": shift.genes_removed,
                            "tick": current_tick,
                        },
                    )

        # Compute epigenetic adaptation score: average of repair+defense expression
        if profiles:
            epigenetic_adaptation_score = sum(
                p.repair_expression + p.defense_expression for p in profiles.values()
            ) / (2 * len(profiles))
        else:
            epigenetic_adaptation_score = 0.0

        return CellularEpigeneticResult(
            profiles=profiles,
            shifts=shifts,
            epigenetic_shift_count=len(shifts),
            mean_gene_count=round(len(profiles) * 7 / max(len(profiles), 1), 4),
            epigenetic_adaptation_score=round(epigenetic_adaptation_score, 4),
        )

    def _adapt_cell(
        self,
        neuron: DigitalNeuron,
        stress: "CellularStressState | None",
        damage: "CellularDamageState | None",
        current_tick: int,
    ) -> tuple[GeneExpressionProfile, EpigeneticShift | None]:
        stress_score = stress.stress_score if stress else 0.0
        damage_score = damage.damage_score if damage else 0.0

        # Retrieve previous numeric expression factors if stored
        existing_marks = getattr(neuron, "epigenetic_marks", {}) or {}
        prev_plasticity = existing_marks.get("plasticity_expression", 1.0)
        prev_repair = existing_marks.get("repair_expression", 0.0)
        prev_defense = existing_marks.get("defense_expression", 0.0)
        prev_energy = existing_marks.get("energy_expression", 1.0)
        prev_growth = existing_marks.get("growth_expression", 0.0)
        prev_apoptosis = existing_marks.get("apoptosis_sensitivity", 0.5)
        prev_diff = existing_marks.get("differentiation_bias", 0.0)
        prev_shift_count = existing_marks.get("__shift_count", 0)
        prev_last_tick = existing_marks.get("__last_shift_tick", 0)

        # Baseline: moderate plasticity, neutral repair/defense/growth
        plasticity = prev_plasticity
        repair = prev_repair
        defense = prev_defense
        energy_expr = prev_energy
        growth = prev_growth
        apoptosis = prev_apoptosis
        diff_bias = prev_diff

        genes_added: List[str] = []
        genes_removed: List[str] = []

        if stress_score >= self.defense_trigger_threshold or damage_score >= 0.50:
            # Defense priority: boost defense and repair, suppress plasticity and growth
            defense = min(1.0, prev_defense + 0.2)
            repair = min(1.0, prev_repair + 0.15)
            plasticity = max(0.0, prev_plasticity - 0.15)
            growth = max(0.0, prev_growth - 0.1)
            genes_added.extend(["defense_priority", "repair_boost"])
            if prev_plasticity > 0.5:
                genes_removed.append("plasticity_high")
        elif damage_score >= self.repair_trigger_threshold:
            # Repair priority: boost repair and energy expression
            repair = min(1.0, prev_repair + 0.2)
            energy_expr = min(1.0, prev_energy + 0.1)
            plasticity = max(0.0, prev_plasticity - 0.1)
            genes_added.extend(["repair_priority", "energy_boost"])
        elif stress_score >= self.stress_response_threshold:
            # Stress response: moderate defense, some repair, reduced growth
            defense = min(1.0, prev_defense + 0.1)
            repair = min(1.0, prev_repair + 0.05)
            growth = max(0.0, prev_growth - 0.05)
            genes_added.append("stress_response")
        else:
            # Metabolic baseline: restore plasticity and growth if stress is low
            if stress_score < self.metabolic_boost_threshold and damage_score < self.repair_trigger_threshold:
                plasticity = min(1.0, prev_plasticity + 0.05)
                growth = min(1.0, prev_growth + 0.05)
                energy_expr = min(1.0, prev_energy + 0.05)
                genes_added.append("metabolic_baseline")

        # Apoptosis sensitivity modulation based on critical damage persistence
        if damage_score >= 0.80:
            apoptosis = min(1.0, prev_apoptosis + 0.1)
            genes_added.append("apoptosis_sensitized")
        elif damage_score < 0.30:
            apoptosis = max(0.0, prev_apoptosis - 0.05)

        # Differentiation bias: increase when cell is stable and growing
        if stress_score < 0.2 and growth > 0.3:
            diff_bias = min(1.0, prev_diff + 0.05)

        shift_occurred = (
            abs(plasticity - prev_plasticity) > 1e-6
            or abs(repair - prev_repair) > 1e-6
            or abs(defense - prev_defense) > 1e-6
            or abs(energy_expr - prev_energy) > 1e-6
            or abs(growth - prev_growth) > 1e-6
            or abs(apoptosis - prev_apoptosis) > 1e-6
            or abs(diff_bias - prev_diff) > 1e-6
            or genes_added
            or genes_removed
        )

        new_shift_count = prev_shift_count + (1 if shift_occurred else 0)
        new_last_tick = current_tick if shift_occurred else prev_last_tick

        profile = GeneExpressionProfile(
            cell_id=neuron.cell_id,
            plasticity_expression=round(plasticity, 4),
            repair_expression=round(repair, 4),
            defense_expression=round(defense, 4),
            energy_expression=round(energy_expr, 4),
            growth_expression=round(growth, 4),
            apoptosis_sensitivity=round(apoptosis, 4),
            differentiation_bias=round(diff_bias, 4),
            expression_shift_count=new_shift_count,
            last_shift_tick=new_last_tick,
        )

        # Persist numeric factors onto neuron for continuity
        neuron.epigenetic_marks = {
            "plasticity_expression": plasticity,
            "repair_expression": repair,
            "defense_expression": defense,
            "energy_expression": energy_expr,
            "growth_expression": growth,
            "apoptosis_sensitivity": apoptosis,
            "differentiation_bias": diff_bias,
            "__shift_count": new_shift_count,
            "__last_shift_tick": new_last_tick,
        }

        if shift_occurred:
            shift = EpigeneticShift(
                cell_id=neuron.cell_id,
                tick=current_tick,
                trigger=self._determine_trigger(stress_score, damage_score),
                genes_added=genes_added,
                genes_removed=genes_removed,
            )
        else:
            shift = None

        return profile, shift

    def _determine_trigger(self, stress_score: float, damage_score: float) -> str:
        if stress_score >= self.defense_trigger_threshold or damage_score >= 0.50:
            return "defense_priority"
        if damage_score >= self.repair_trigger_threshold:
            return "repair_priority"
        if stress_score >= self.stress_response_threshold:
            return "stress_response"
        return "metabolic_baseline"
