from typing import Dict, Optional

from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType


class STDPPlasticityEngine:
    """Spike-Timing-Dependent Plasticity engine driven by burst firing order."""

    def __init__(
        self,
        ltp_rate: float = 0.05,
        ltd_rate: float = 0.03,
        stdp_window: int = 1,
        min_weight: float = 0.0,
        max_weight: float = 1.0,
    ):
        self.ltp_rate = ltp_rate
        self.ltd_rate = ltd_rate
        self.stdp_window = stdp_window
        self.min_weight = min_weight
        self.max_weight = max_weight

    def compute_delta_burst(
        self, pre_neuron: DigitalNeuron, post_neuron: DigitalNeuron
    ) -> int | None:
        """Return post.last_fired_burst - pre.last_fired_burst, or None if either never fired."""
        if pre_neuron.last_fired_burst == 0 or post_neuron.last_fired_burst == 0:
            return None
        return post_neuron.last_fired_burst - pre_neuron.last_fired_burst

    def compute_weight_delta(self, delta_burst: int) -> float:
        """Map burst timing difference to a weight change."""
        if delta_burst == 1:
            return self.ltp_rate
        if delta_burst == -1:
            return -self.ltd_rate
        return 0.0

    def apply_stdp_to_synapse(
        self,
        synapse: DigitalSynapse,
        pre_neuron: DigitalNeuron,
        post_neuron: DigitalNeuron,
        memory: MorphologicalMemory | None = None,
    ) -> float | None:
        """Apply STDP to a single synapse and optionally record the event."""
        delta_burst = self.compute_delta_burst(pre_neuron, post_neuron)
        if delta_burst is None or abs(delta_burst) > self.stdp_window:
            return None

        weight_delta = self.compute_weight_delta(delta_burst)
        if weight_delta == 0.0:
            return None

        old_weight = synapse.weight
        new_weight = old_weight + weight_delta
        new_weight = max(self.min_weight, min(self.max_weight, new_weight))

        if abs(new_weight - old_weight) < 1e-9:
            return None

        synapse.weight = new_weight

        if memory is not None:
            event_type = (
                MorphologyEventType.SYNAPSE_REINFORCED
                if weight_delta > 0
                else MorphologyEventType.SYNAPSE_WEAKENED
            )
            memory.create_event(
                event_type=event_type,
                source_id=pre_neuron.cell_id,
                target_id=post_neuron.cell_id,
                metadata={
                    "mechanism": "stdp",
                    "pre_neuron_id": pre_neuron.cell_id,
                    "post_neuron_id": post_neuron.cell_id,
                    "pre_last_fired_burst": pre_neuron.last_fired_burst,
                    "post_last_fired_burst": post_neuron.last_fired_burst,
                    "delta_burst": delta_burst,
                    "old_weight": old_weight,
                    "new_weight": new_weight,
                },
            )

        return weight_delta

    def apply_stdp(
        self,
        circuit: NeuralCircuit,
        memory: MorphologicalMemory | None = None,
    ) -> Dict[str, int]:
        """Apply STDP to all active synapses in the circuit."""
        results: Dict[str, int] = {"reinforced": 0, "weakened": 0, "unchanged": 0}
        neuron_map = self._neuron_map(circuit)

        for syn in circuit.synapses:
            if syn.state == "pruned":
                continue
            pre = neuron_map.get(syn.source)
            post = neuron_map.get(syn.target)
            if pre is None or post is None:
                continue

            delta = self.apply_stdp_to_synapse(syn, pre, post, memory)
            if delta is None:
                results["unchanged"] += 1
            elif delta > 0:
                results["reinforced"] += 1
            else:
                results["weakened"] += 1

        return results

    @staticmethod
    def _neuron_map(circuit: NeuralCircuit) -> dict[str, DigitalNeuron]:
        all_neurons = (
            circuit.input_neurons
            + circuit.hidden_neurons
            + circuit.output_neurons
        )
        return {n.cell_id: n for n in all_neurons}
