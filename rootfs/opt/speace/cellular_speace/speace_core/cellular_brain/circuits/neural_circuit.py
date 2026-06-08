import random
from typing import List

from pydantic import BaseModel, ConfigDict, PrivateAttr, model_validator

from speace_core.cellular_brain.base.digital_signal import DigitalSignal
from speace_core.cellular_brain.cells.digital_astrocyte import DigitalAstrocyte
from speace_core.cellular_brain.cells.digital_microglia import DigitalMicroglia
from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_oligodendrocyte import DigitalOligodendrocyte
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType


class NeuralCircuit(BaseModel):
    circuit_id: str
    input_neurons: List[DigitalNeuron] = []
    hidden_neurons: List[DigitalNeuron] = []
    output_neurons: List[DigitalNeuron] = []
    synapses: List[DigitalSynapse] = []
    astrocytes: List[DigitalAstrocyte] = []
    microglia: List[DigitalMicroglia] = []
    oligodendrocytes: List[DigitalOligodendrocyte] = []
    feedback_buffer: List[float] = []
    memory: MorphologicalMemory | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _neuron_index: dict[str, DigitalNeuron] = PrivateAttr(default_factory=dict)
    _synapse_index: dict[tuple[str, str], DigitalSynapse] = PrivateAttr(default_factory=dict)

    @model_validator(mode="after")
    def _sync_indexes(self):
        self._neuron_index.clear()
        for n in self.input_neurons + self.hidden_neurons + self.output_neurons:
            self._neuron_index[n.cell_id] = n
        self._synapse_index.clear()
        for s in self.synapses:
            self._synapse_index[(s.source, s.target)] = s
        return self

    def add_neuron(self, neuron: DigitalNeuron) -> None:
        self.hidden_neurons.append(neuron)
        self._neuron_index[neuron.cell_id] = neuron

    def remove_neuron(self, cell_id: str) -> None:
        neuron = self._neuron_index.pop(cell_id, None)
        if neuron is None:
            return
        if neuron in self.input_neurons:
            self.input_neurons.remove(neuron)
        elif neuron in self.hidden_neurons:
            self.hidden_neurons.remove(neuron)
        elif neuron in self.output_neurons:
            self.output_neurons.remove(neuron)

    def add_synapse(self, synapse: DigitalSynapse) -> None:
        self.synapses.append(synapse)
        self._synapse_index[(synapse.source, synapse.target)] = synapse

    def remove_synapse(self, source: str, target: str) -> None:
        key = (source, target)
        synapse = self._synapse_index.pop(key, None)
        if synapse is not None:
            self.synapses.remove(synapse)

    def inject_input(self, pattern: List[float]) -> None:
        for neuron, strength in zip(self.input_neurons, pattern):
            neuron.activation += strength

    async def tick(self) -> List[DigitalSignal]:
        all_neurons = self.input_neurons + self.hidden_neurons + self.output_neurons
        outbound: List[DigitalSignal] = []

        # Astrocyte regulation
        for astro in self.astrocytes:
            astro.regulate(all_neurons)

        # Neuron firing
        for neuron in all_neurons:
            neuron_signals = await neuron.tick()
            for sig in neuron_signals:
                syn = self._find_synapse(sig.source, sig.target)
                if syn and syn.state != "pruned":
                    transmitted = syn.transmit(sig)
                    outbound.append(transmitted)

        # Route signals to targets
        for sig in outbound:
            target = self._find_neuron(sig.target)
            if target:
                await target.receive(sig)

        return outbound

    def apply_feedback(self, score: float) -> None:
        event_type = (
            MorphologyEventType.SYNAPSE_REINFORCED
            if score > 0
            else MorphologyEventType.SYNAPSE_WEAKENED
        )
        for syn in self.synapses:
            if syn.state == "pruned":
                continue
            old_weight = syn.weight
            if score > 0:
                syn.reinforce(score)
            else:
                syn.weaken(abs(score))
            if self.memory:
                self.memory.create_event(
                    event_type=event_type,
                    source_id=syn.source,
                    target_id=syn.target,
                    metadata={
                        "old_weight": old_weight,
                        "new_weight": syn.weight,
                        "feedback_score": score,
                    },
                )
        for neuron in self.hidden_neurons + self.output_neurons:
            neuron.adapt(score)
        self.feedback_buffer.append(score)

    def run_immune(self) -> None:
        all_neurons = self.input_neurons + self.hidden_neurons + self.output_neurons
        for mg in self.microglia:
            pruned = mg.inspect(all_neurons, self.synapses)
            if self.memory:
                for syn_id in pruned:
                    self.memory.create_event(
                        event_type=MorphologyEventType.SYNAPSE_PRUNED,
                        metadata={"synapse_id": syn_id, "reason": "low_trust_low_usage"},
                    )

    def _find_synapse(self, source: str, target: str) -> DigitalSynapse | None:
        return self._synapse_index.get((source, target))

    def _find_neuron(self, cell_id: str) -> DigitalNeuron | None:
        return self._neuron_index.get(cell_id)

    @property
    def output_activations(self) -> List[float]:
        return [n.activation for n in self.output_neurons]
