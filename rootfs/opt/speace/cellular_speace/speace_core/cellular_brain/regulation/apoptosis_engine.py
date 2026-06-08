from typing import List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regulation.homeostasis_engine import SystemMetrics


class ApoptosisResult(BaseModel):
    snoozed: List[str] = Field(default_factory=list)
    pruned_synapses: List[str] = Field(default_factory=list)
    apoptosed: List[str] = Field(default_factory=list)
    reason: str = ""


class ApoptosisEngine:
    def __init__(
        self,
        low_utility_threshold: float = 0.15,
        high_energy_threshold: float = 0.85,
        low_connectivity_threshold: int = 1,
        apoptosis_risk_threshold: float = 0.75,
        max_apoptosis_per_cycle: int = 3,
        snooze_fire_threshold: int = 5,
        snooze_duration: int = 3,
        phi_threshold: float = 0.55,
        synapse_prune_threshold: float = 0.05,
    ):
        self.low_utility_threshold = low_utility_threshold
        self.high_energy_threshold = high_energy_threshold
        self.low_connectivity_threshold = low_connectivity_threshold
        self.apoptosis_risk_threshold = apoptosis_risk_threshold
        self.max_apoptosis_per_cycle = max_apoptosis_per_cycle
        self.snooze_fire_threshold = snooze_fire_threshold
        self.snooze_duration = snooze_duration
        self.phi_threshold = phi_threshold
        self.synapse_prune_threshold = synapse_prune_threshold

    def run(
        self,
        circuit: NeuralCircuit,
        metrics: SystemMetrics | None = None,
    ) -> ApoptosisResult:
        result = ApoptosisResult()
        current_tick = metrics.tick if metrics else 0
        phi_before = metrics.coherence_phi if metrics else None

        all_neurons = (
            circuit.input_neurons
            + circuit.hidden_neurons
            + circuit.output_neurons
        )

        # Phase 1 — evaluate utility, snooze hyperactive neurons
        for neuron in all_neurons:
            if self._is_protected(neuron, circuit):
                continue

            self._compute_utility(neuron, circuit, current_tick)

            if neuron.consecutive_fires >= self.snooze_fire_threshold:
                neuron.snooze_counter = self.snooze_duration
                result.snoozed.append(neuron.cell_id)
                if circuit.memory:
                    circuit.memory.create_event(
                        event_type=MorphologyEventType.NEURON_SNOOZED,
                        source_id="apoptosis_engine",
                        target_id=neuron.cell_id,
                        phi_before=phi_before,
                        metadata={
                            "reason": "hyperactive_firing",
                            "consecutive_fires": neuron.consecutive_fires,
                            "snooze_duration": self.snooze_duration,
                        },
                    )

        # Phase 2 — prune weak synapses (energy-based reinforcement)
        pruned_ids = self._prune_weak_synapses(circuit, phi_before)
        result.pruned_synapses.extend(pruned_ids)

        # Phase 3 — evaluate apoptosis risk and remove candidates
        candidates: List[tuple[DigitalNeuron, float]] = []
        for neuron in all_neurons:
            if self._is_protected(neuron, circuit):
                continue

            risk = self._compute_apoptosis_risk(neuron, circuit, phi_before)
            neuron.apoptosis_risk = risk
            if risk >= self.apoptosis_risk_threshold:
                candidates.append((neuron, risk))

        # Sort by highest risk, limit removals per cycle
        candidates.sort(key=lambda x: x[1], reverse=True)
        removed_count = 0
        for neuron, risk in candidates:
            if removed_count >= self.max_apoptosis_per_cycle:
                break
            removed_synapses = self._remove_neuron(circuit, neuron)
            result.apoptosed.append(neuron.cell_id)
            removed_count += 1
            if circuit.memory:
                circuit.memory.create_event(
                    event_type=MorphologyEventType.NEURON_APOPTOSIS,
                    source_id="apoptosis_engine",
                    target_id=neuron.cell_id,
                    phi_before=phi_before,
                    metadata={
                        "reason": "utility_energy_connectivity_phi",
                        "utility_score": neuron.utility_score,
                        "energy": neuron.energy,
                        "apoptosis_risk": risk,
                        "removed_synapses": len(removed_synapses),
                    },
                )

        if result.apoptosed:
            result.reason = "apoptosis_cycle_complete"
        return result

    def _is_protected(self, neuron: DigitalNeuron, circuit: NeuralCircuit) -> bool:
        if neuron.is_critical:
            return True
        if neuron.neuron_role in ("input", "output", "regulatory"):
            return True
        if neuron in circuit.input_neurons or neuron in circuit.output_neurons:
            return True
        return False

    def _compute_utility(
        self,
        neuron: DigitalNeuron,
        circuit: NeuralCircuit,
        current_tick: int,
    ) -> None:
        conn = self._connectivity_count(neuron, circuit)
        normalized_conn = min(1.0, conn / 5.0)
        recent = 0.0
        if neuron.last_fired_tick is not None and current_tick is not None:
            if current_tick - neuron.last_fired_tick <= 5:
                recent = 0.3
        activity = min(1.0, neuron.consecutive_fires / self.snooze_fire_threshold) * 0.3
        neuron.utility_score = normalized_conn * 0.4 + activity + recent

    def _connectivity_count(
        self, neuron: DigitalNeuron, circuit: NeuralCircuit
    ) -> int:
        return sum(
            1
            for s in circuit.synapses
            if s.source == neuron.cell_id or s.target == neuron.cell_id
        )

    def _compute_apoptosis_risk(
        self,
        neuron: DigitalNeuron,
        circuit: NeuralCircuit,
        phi_before: float | None,
    ) -> float:
        risk = 0.0
        if neuron.utility_score < self.low_utility_threshold:
            risk += 0.30
        if neuron.energy > self.high_energy_threshold:
            risk += 0.25
        conn = self._connectivity_count(neuron, circuit)
        if conn <= self.low_connectivity_threshold:
            risk += 0.25
        if phi_before is not None and phi_before < self.phi_threshold:
            risk += 0.20
        return risk

    def _prune_weak_synapses(
        self,
        circuit: NeuralCircuit,
        phi_before: float | None,
    ) -> List[str]:
        removed: List[str] = []
        to_remove = [
            s
            for s in circuit.synapses
            if s.state != "pruned"
            and (s.weight < self.synapse_prune_threshold or s.trust < self.synapse_prune_threshold)
        ]
        for syn in to_remove:
            syn.state = "pruned"
            removed.append(syn.cell_id)
            if circuit.memory:
                circuit.memory.create_event(
                    event_type=MorphologyEventType.SYNAPSE_PRUNED,
                    source_id="apoptosis_engine",
                    target_id=syn.cell_id,
                    phi_before=phi_before,
                    metadata={
                        "reason": "weak_synapse_pruning",
                        "weight": syn.weight,
                        "trust": syn.trust,
                        "threshold": self.synapse_prune_threshold,
                    },
                )
        return removed

    def _remove_neuron(
        self, circuit: NeuralCircuit, neuron: DigitalNeuron
    ) -> List[str]:
        removed_synapses: List[str] = []
        # Remove synapses connected to this neuron
        synapses_to_remove = [
            s
            for s in circuit.synapses
            if s.source == neuron.cell_id or s.target == neuron.cell_id
        ]
        for syn in synapses_to_remove:
            circuit.synapses.remove(syn)
            removed_synapses.append(syn.cell_id)
            # Clean up targets list on source neurons
            if syn.source == neuron.cell_id:
                continue
            src = circuit._find_neuron(syn.source)
            if src and neuron.cell_id in src.targets:
                src.targets.remove(neuron.cell_id)

        # Remove neuron from hidden_neurons
        if neuron in circuit.hidden_neurons:
            circuit.hidden_neurons.remove(neuron)

        return removed_synapses
