from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron


class FireCandidate(BaseModel):
    neuron_id: str
    activation: float
    threshold: float
    priority: float = 0.0
    source: Optional[str] = None
    created_at_burst: int = 0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class BurstResult(BaseModel):
    burst_id: int
    fired_neurons: List[str] = Field(default_factory=list)
    propagated_synapses: int = 0
    skipped_refractory: int = 0
    skipped_snoozed: int = 0
    mean_activation: float = 0.0
    fire_queue_size: int = 0


class EventDrivenBurstEngine:
    """Sparse burst engine: only active neurons fire, propagation is local."""

    def __init__(
        self,
        activation_threshold: float = 0.5,
        max_burst_size: int = 128,
        max_bursts_per_tick: int = 10,
        min_energy: float = 0.1,
    ):
        self.activation_threshold = activation_threshold
        self.max_burst_size = max_burst_size
        self.max_bursts_per_tick = max_bursts_per_tick
        self.min_energy = min_energy
        self._burst_counter: int = 0
        self._fire_queue: List[FireCandidate] = []

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def run_event_cycle(
        self,
        circuit: NeuralCircuit,
        max_bursts: int | None = None,
    ) -> List[BurstResult]:
        """Run bursts until queue is empty or max_bursts reached."""
        limit = max_bursts if max_bursts is not None else self.max_bursts_per_tick
        results: List[BurstResult] = []
        for _ in range(limit):
            self.clear_queue()
            self.collect_candidates(circuit)
            if not self._fire_queue:
                break
            self._burst_counter += 1
            result = self.process_burst(circuit, self._burst_counter)
            results.append(result)
        return results

    def collect_candidates(self, circuit: NeuralCircuit) -> List[FireCandidate]:
        """Find all neurons eligible to fire in the next burst."""
        candidates: List[FireCandidate] = []
        all_neurons = (
            circuit.input_neurons
            + circuit.hidden_neurons
            + circuit.output_neurons
        )
        for neuron in all_neurons:
            if not self._is_candidate(neuron):
                continue
            priority = neuron.activation - neuron.threshold
            candidates.append(
                FireCandidate(
                    neuron_id=neuron.cell_id,
                    activation=neuron.activation,
                    threshold=neuron.threshold,
                    priority=priority,
                    created_at_burst=self._burst_counter,
                )
            )
        # Sort by priority descending
        candidates.sort(key=lambda c: c.priority, reverse=True)
        self._fire_queue = candidates
        return candidates

    def process_burst(
        self,
        circuit: NeuralCircuit,
        burst_id: int,
    ) -> BurstResult:
        """Fire the top candidates and propagate activation."""
        if not self._fire_queue:
            return BurstResult(burst_id=burst_id)

        to_fire = self._fire_queue[: self.max_burst_size]
        fired_ids: List[str] = []
        propagated = 0
        skipped_refractory = 0
        skipped_snoozed = 0
        total_activation = 0.0

        neuron_map = self._neuron_map(circuit)

        for cand in to_fire:
            neuron = neuron_map.get(cand.neuron_id)
            if neuron is None:
                continue

            # Double-check eligibility (state may have changed)
            if not self._is_candidate(neuron):
                if neuron.refractory_counter > 0:
                    skipped_refractory += 1
                if neuron.snooze_counter > 0:
                    skipped_snoozed += 1
                continue

            # Fire
            neuron.energy = max(0.0, neuron.energy - 0.05)
            fire_activation = neuron.activation
            total_activation += fire_activation

            neuron.activation = 0.0
            neuron.consecutive_fires += 1
            neuron.last_fired_burst = burst_id
            if neuron.refractory_period > 0:
                neuron.refractory_counter = neuron.refractory_period

            fired_ids.append(neuron.cell_id)

            # Propagate through outgoing synapses
            for syn in circuit.synapses:
                if syn.state == "pruned":
                    continue
                if syn.source != neuron.cell_id:
                    continue
                target = neuron_map.get(syn.target)
                if target is None:
                    continue
                delta = fire_activation * syn.weight
                if neuron.inhibitory:
                    target.activation -= abs(delta) * neuron.inhibition_strength
                else:
                    target.activation += delta
                target.activation = max(0.0, target.activation)
                propagated += 1

        mean_activation = (
            total_activation / len(fired_ids) if fired_ids else 0.0
        )

        return BurstResult(
            burst_id=burst_id,
            fired_neurons=fired_ids,
            propagated_synapses=propagated,
            skipped_refractory=skipped_refractory,
            skipped_snoozed=skipped_snoozed,
            mean_activation=mean_activation,
            fire_queue_size=len(self._fire_queue),
        )

    def propagate_fire(
        self,
        circuit: NeuralCircuit,
        neuron: DigitalNeuron,
    ) -> int:
        """Propagate a single neuron's activation to its targets."""
        propagated = 0
        neuron_map = self._neuron_map(circuit)
        for syn in circuit.synapses:
            if syn.state == "pruned":
                continue
            if syn.source != neuron.cell_id:
                continue
            target = neuron_map.get(syn.target)
            if target is None:
                continue
            delta = neuron.activation * syn.weight
            if neuron.inhibitory:
                target.activation -= abs(delta) * neuron.inhibition_strength
            else:
                target.activation += delta
            target.activation = max(0.0, target.activation)
            propagated += 1
        return propagated

    def clear_queue(self) -> None:
        """Reset the fire queue."""
        self._fire_queue = []

    @property
    def burst_counter(self) -> int:
        return self._burst_counter

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _is_candidate(self, neuron: DigitalNeuron) -> bool:
        """Check if a neuron is eligible to fire in the current burst."""
        if neuron.activation < self.activation_threshold:
            return False
        if getattr(neuron, "snooze_counter", 0) > 0:
            return False
        if getattr(neuron, "refractory_counter", 0) > 0:
            return False
        if neuron.energy <= self.min_energy:
            return False
        return True

    @staticmethod
    def _neuron_map(circuit: NeuralCircuit) -> dict[str, DigitalNeuron]:
        all_neurons = (
            circuit.input_neurons
            + circuit.hidden_neurons
            + circuit.output_neurons
        )
        return {n.cell_id: n for n in all_neurons}
