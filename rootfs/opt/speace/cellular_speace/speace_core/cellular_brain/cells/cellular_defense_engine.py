from typing import Dict, List

from pydantic import BaseModel, Field

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType


class DefenseAction(BaseModel):
    """Single defense action applied to a cell."""

    cell_id: str
    action: str = ""
    applied: bool = False
    reason: str = ""


class CellularDefenseResult(BaseModel):
    """Aggregate result of a defense pass."""

    actions: List[DefenseAction] = Field(default_factory=list)
    quarantined_count: int = 0
    firewall_count: int = 0
    snooze_count: int = 0
    routing_block_count: int = 0
    plasticity_lock_count: int = 0
    input_filter_count: int = 0
    immune_alert_count: int = 0
    defense_activation_count: int = 0


class CellularDefenseEngine:
    """T42B — Cellular defense layer: quarantine, firewall, snooze, routing_block,
    plasticity_lock, input_filtering, immune_alert.

    Defense actions are triggered by stress/damage thresholds and aim to
    contain failing cells before they propagate failure to the circuit.
    """

    def __init__(
        self,
        quarantine_stress_threshold: float = 0.70,
        quarantine_damage_threshold: float = 0.60,
        firewall_stress_threshold: float = 0.50,
        snooze_stress_threshold: float = 0.60,
        routing_block_stress_threshold: float = 0.55,
        plasticity_lock_stress_threshold: float = 0.65,
        input_filter_stress_threshold: float = 0.45,
        immune_alert_damage_threshold: float = 0.70,
        snooze_duration: int = 3,
        max_defenses_per_cycle: int = 5,
    ):
        self.quarantine_stress_threshold = quarantine_stress_threshold
        self.quarantine_damage_threshold = quarantine_damage_threshold
        self.firewall_stress_threshold = firewall_stress_threshold
        self.snooze_stress_threshold = snooze_stress_threshold
        self.routing_block_stress_threshold = routing_block_stress_threshold
        self.plasticity_lock_stress_threshold = plasticity_lock_stress_threshold
        self.input_filter_stress_threshold = input_filter_stress_threshold
        self.immune_alert_damage_threshold = immune_alert_damage_threshold
        self.snooze_duration = snooze_duration
        self.max_defenses_per_cycle = max_defenses_per_cycle

    def run(
        self,
        circuit: NeuralCircuit,
        stress_per_cell: Dict[str, "CellularStressState"],
        damage_per_cell: Dict[str, "CellularDamageState"],
        memory: MorphologicalMemory | None = None,
    ) -> CellularDefenseResult:
        from speace_core.cellular_brain.cells.cellular_stress import CellularStressState
        from speace_core.cellular_brain.cells.cellular_damage import CellularDamageState

        all_neurons = {
            n.cell_id: n
            for n in circuit.input_neurons
            + circuit.hidden_neurons
            + circuit.output_neurons
        }
        actions: List[DefenseAction] = []
        quarantined = 0
        firewalled = 0
        snoozed = 0
        routing_blocked = 0
        plasticity_locked = 0
        input_filtered = 0
        immune_alerts = 0
        defenses_done = 0

        # Sort by combined stress+damage descending
        def combined_score(cell_id: str) -> float:
            s = stress_per_cell.get(cell_id)
            d = damage_per_cell.get(cell_id)
            return (s.stress_score if s else 0.0) + (d.damage_score if d else 0.0)

        sorted_ids = sorted(all_neurons.keys(), key=combined_score, reverse=True)

        for cell_id in sorted_ids:
            if defenses_done >= self.max_defenses_per_cycle:
                break
            neuron = all_neurons[cell_id]
            stress = stress_per_cell.get(cell_id)
            damage = damage_per_cell.get(cell_id)

            action = self._evaluate_defense(neuron, stress, damage)
            if action.applied:
                actions.append(action)
                defenses_done += 1
                if action.action == "quarantine":
                    quarantined += 1
                elif action.action == "firewall":
                    firewalled += 1
                elif action.action == "snooze":
                    snoozed += 1
                elif action.action == "temporary_routing_block":
                    routing_blocked += 1
                elif action.action == "plasticity_lock":
                    plasticity_locked += 1
                elif action.action == "input_filtering":
                    input_filtered += 1
                elif action.action == "immune_alert":
                    immune_alerts += 1

                if memory is not None:
                    event_type = MorphologyEventType.CELLULAR_DEFENSE_APPLIED
                    if action.action == "quarantine":
                        event_type = MorphologyEventType.CELL_QUARANTINED
                    elif action.action == "immune_alert":
                        event_type = MorphologyEventType.CELLULAR_IMMUNE_ALERT
                    memory.create_event(
                        event_type=event_type,
                        source_id="cellular_defense_engine",
                        target_id=cell_id,
                        metadata={
                            "action": action.action,
                            "reason": action.reason,
                            "stress_score": stress.stress_score if stress else 0.0,
                            "damage_score": damage.damage_score if damage else 0.0,
                        },
                    )

        return CellularDefenseResult(
            actions=actions,
            quarantined_count=quarantined,
            firewall_count=firewalled,
            snooze_count=snoozed,
            routing_block_count=routing_blocked,
            plasticity_lock_count=plasticity_locked,
            input_filter_count=input_filtered,
            immune_alert_count=immune_alerts,
            defense_activation_count=len(actions),
        )

    def _evaluate_defense(
        self,
        neuron: DigitalNeuron,
        stress: "CellularStressState | None",
        damage: "CellularDamageState | None",
    ) -> DefenseAction:
        stress_score = stress.stress_score if stress else 0.0
        damage_score = damage.damage_score if damage else 0.0

        # Skip protected neurons
        if getattr(neuron, "is_critical", False):
            return DefenseAction(cell_id=neuron.cell_id, action="none", applied=False, reason="protected")
        if getattr(neuron, "neuron_role", "") in ("input", "output"):
            return DefenseAction(cell_id=neuron.cell_id, action="none", applied=False, reason="io_protected")

        # Quarantine: highest escalation — drop all targets, zero activation
        if (
            stress_score >= self.quarantine_stress_threshold
            and damage_score >= self.quarantine_damage_threshold
        ):
            neuron.targets = []
            neuron.activation = 0.0
            neuron.energy = max(0.0, neuron.energy - 0.1)
            return DefenseAction(
                cell_id=neuron.cell_id,
                action="quarantine",
                applied=True,
                reason="stress_and_damage_threshold",
            )

        # Immune alert: triggered by critical damage regardless of stress
        if damage_score >= self.immune_alert_damage_threshold:
            return DefenseAction(
                cell_id=neuron.cell_id,
                action="immune_alert",
                applied=True,
                reason="critical_damage",
            )

        # Plasticity lock: freeze learning when stress is high
        if stress_score >= self.plasticity_lock_stress_threshold:
            neuron.plasticity_rate = 0.0
            return DefenseAction(
                cell_id=neuron.cell_id,
                action="plasticity_lock",
                applied=True,
                reason="stress_threshold",
            )

        # Temporary routing block: prevent outgoing signals but keep targets
        if stress_score >= self.routing_block_stress_threshold:
            neuron.activation = 0.0
            return DefenseAction(
                cell_id=neuron.cell_id,
                action="temporary_routing_block",
                applied=True,
                reason="stress_threshold",
            )

        # Firewall: block outgoing signals by clearing targets temporarily
        if stress_score >= self.firewall_stress_threshold:
            neuron.targets = []
            return DefenseAction(
                cell_id=neuron.cell_id,
                action="firewall",
                applied=True,
                reason="stress_threshold",
            )

        # Input filtering: raise threshold to dampen incoming signals
        if stress_score >= self.input_filter_stress_threshold:
            neuron.threshold = min(1.0, neuron.threshold * 1.2)
            return DefenseAction(
                cell_id=neuron.cell_id,
                action="input_filtering",
                applied=True,
                reason="stress_threshold",
            )

        # Snooze: force refractory-like pause
        if stress_score >= self.snooze_stress_threshold:
            neuron.snooze_counter = self.snooze_duration
            neuron.activation = 0.0
            return DefenseAction(
                cell_id=neuron.cell_id,
                action="snooze",
                applied=True,
                reason="stress_threshold",
            )

        return DefenseAction(cell_id=neuron.cell_id, action="none", applied=False, reason="no_threshold_met")
