from typing import Dict, List

from pydantic import BaseModel, Field

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType


class RepairAction(BaseModel):
    """Single repair action applied to a cell."""

    cell_id: str
    action: str = ""
    success: bool = False
    energy_cost: float = 0.0
    damage_before: float = 0.0
    damage_after: float = 0.0


class CellularRepairResult(BaseModel):
    """Aggregate result of a repair pass."""

    actions: List[RepairAction] = Field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    total_energy_cost: float = 0.0
    repair_success_rate: float = 0.0
    repair_failure_rate: float = 0.0


class CellularRepairEngine:
    """T42B — Repair damaged cells using energy-budgeted, biologically specific interventions.

    Repair efficacy depends on damage level and available energy.
    Reversible damage is cheap to fix; structural damage rarely heals.
    """

    def __init__(
        self,
        base_repair_cost: float = 0.05,
        reversible_heal_amount: float = 0.30,
        functional_heal_amount: float = 0.10,
        structural_heal_amount: float = 0.02,
        critical_heal_amount: float = 0.00,
        min_energy_to_repair: float = 0.20,
        max_repairs_per_cycle: int = 5,
    ):
        self.base_repair_cost = base_repair_cost
        self.reversible_heal_amount = reversible_heal_amount
        self.functional_heal_amount = functional_heal_amount
        self.structural_heal_amount = structural_heal_amount
        self.critical_heal_amount = critical_heal_amount
        self.min_energy_to_repair = min_energy_to_repair
        self.max_repairs_per_cycle = max_repairs_per_cycle

    def run(
        self,
        circuit: NeuralCircuit,
        damage_per_cell: Dict[str, "CellularDamageState"],
        memory: MorphologicalMemory | None = None,
    ) -> CellularRepairResult:
        from speace_core.cellular_brain.cells.cellular_damage import CellularDamageState

        all_neurons = {
            n.cell_id: n
            for n in circuit.input_neurons
            + circuit.hidden_neurons
            + circuit.output_neurons
        }
        actions: List[RepairAction] = []
        success_count = 0
        failure_count = 0
        total_energy_cost = 0.0
        repairs_done = 0

        # Prioritize by damage level (highest first)
        sorted_cells = sorted(
            damage_per_cell.items(),
            key=lambda x: x[1].damage_score,
            reverse=True,
        )

        for cell_id, damage_state in sorted_cells:
            if repairs_done >= self.max_repairs_per_cycle:
                break
            neuron = all_neurons.get(cell_id)
            if neuron is None:
                continue
            action = self._attempt_repair(neuron, damage_state, circuit)
            actions.append(action)
            repairs_done += 1
            if action.success:
                success_count += 1
            else:
                failure_count += 1
            total_energy_cost += action.energy_cost

            if memory is not None:
                event_type = (
                    MorphologyEventType.CELLULAR_REPAIR_SUCCEEDED
                    if action.success
                    else MorphologyEventType.CELLULAR_REPAIR_FAILED
                )
                memory.create_event(
                    event_type=event_type,
                    source_id="cellular_repair_engine",
                    target_id=cell_id,
                    metadata={
                        "action": action.action,
                        "energy_cost": action.energy_cost,
                        "damage_before": action.damage_before,
                        "damage_after": action.damage_after,
                    },
                )

        total = len(actions)
        repair_success_rate = success_count / total if total else 0.0
        repair_failure_rate = failure_count / total if total else 0.0
        return CellularRepairResult(
            actions=actions,
            success_count=success_count,
            failure_count=failure_count,
            total_energy_cost=round(total_energy_cost, 4),
            repair_success_rate=round(repair_success_rate, 4),
            repair_failure_rate=round(repair_failure_rate, 4),
        )

    def _attempt_repair(
        self,
        neuron: DigitalNeuron,
        damage_state: "CellularDamageState",
        circuit: NeuralCircuit,
    ) -> RepairAction:
        from speace_core.cellular_brain.cells.cellular_damage import CellularDamageState

        level = damage_state.level
        damage_before = damage_state.damage_score

        # Select specific biologically-inspired repair action based on dominant damage type
        if level == "reversible":
            action_name = "restore_energy"
            heal = self.reversible_heal_amount
            cost = self.base_repair_cost
        elif level == "functional":
            action_name = "lower_activation"
            heal = self.functional_heal_amount
            cost = self.base_repair_cost * 1.5
        elif level == "structural":
            action_name = "repair_synaptic_weights"
            heal = self.structural_heal_amount
            cost = self.base_repair_cost * 3.0
        elif level == "critical":
            action_name = "request_glial_support"
            heal = self.critical_heal_amount
            cost = self.base_repair_cost * 5.0
        else:
            return RepairAction(
                cell_id=neuron.cell_id,
                action="no_damage",
                success=True,
                energy_cost=0.0,
                damage_before=damage_before,
                damage_after=damage_before,
            )

        # Budget check: neuron must have enough energy
        if neuron.energy < max(self.min_energy_to_repair, cost):
            return RepairAction(
                cell_id=neuron.cell_id,
                action=action_name,
                success=False,
                energy_cost=0.0,
                damage_before=damage_before,
                damage_after=damage_before,
            )

        neuron.energy = max(0.0, neuron.energy - cost)

        # Apply the specific biological repair effect
        if action_name == "restore_energy":
            neuron.energy = min(1.0, neuron.energy + 0.15)
        elif action_name == "lower_activation":
            neuron.activation = max(0.0, neuron.activation - 0.3)
        elif action_name == "reset_refractory_state":
            neuron.refractory_counter = 0
        elif action_name == "repair_synaptic_weights":
            self._repair_synaptic_weights(neuron, circuit)
        elif action_name == "restore_threshold":
            neuron.threshold = max(0.1, min(1.0, neuron.threshold * 0.95 + 0.5 * 0.05))
        elif action_name == "reduce_plasticity":
            neuron.plasticity_rate = max(0.01, neuron.plasticity_rate * 0.8)
        elif action_name == "request_glial_support":
            # Glial support drains more energy but provides stronger healing
            neuron.energy = max(0.0, neuron.energy - 0.02)
            heal *= 1.5

        new_damage = max(0.0, damage_before - heal)

        return RepairAction(
            cell_id=neuron.cell_id,
            action=action_name,
            success=True,
            energy_cost=cost,
            damage_before=damage_before,
            damage_after=round(new_damage, 4),
        )

    def _repair_synaptic_weights(self, neuron: DigitalNeuron, circuit: NeuralCircuit) -> None:
        for syn in circuit.synapses:
            if syn.source == neuron.cell_id or syn.target == neuron.cell_id:
                if syn.state != "pruned":
                    syn.weight = max(0.01, min(1.0, syn.weight * 0.95 + 0.5 * 0.05))
