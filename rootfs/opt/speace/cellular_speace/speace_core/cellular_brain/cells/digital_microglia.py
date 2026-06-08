from typing import TYPE_CHECKING, List

from speace_core.cellular_brain.base.digital_cell import DigitalCell
from speace_core.cellular_brain.base.digital_signal import DigitalSignal

if TYPE_CHECKING:
    from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
    from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse


class DigitalMicroglia(DigitalCell):
    async def receive(self, signal: DigitalSignal) -> None:
        pass

    async def tick(self) -> List[DigitalSignal]:
        return []

    def inspect(
        self,
        neurons: List["DigitalNeuron"],
        synapses: List["DigitalSynapse"],
    ) -> List[str]:
        pruned: List[str] = []
        for syn in synapses:
            if syn.trust < 0.1 and syn.use_count < 3:
                syn.state = "pruned"
                pruned.append(syn.cell_id)
        for neuron in neurons:
            if len(neuron.error_history) > 10:
                neuron.epigenome.modulation_factors["quarantined"] = 1.0
                neuron.state = "quarantined"
        return pruned
