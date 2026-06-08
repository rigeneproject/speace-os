from typing import List

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse


class PlasticityEngine:
    def update(
        self,
        synapses: List[DigitalSynapse],
        neurons: List[DigitalNeuron],
        feedback_score: float,
    ) -> None:
        for syn in synapses:
            if syn.state == "pruned":
                continue
            if feedback_score > 0:
                syn.reinforce(feedback_score)
            else:
                syn.weaken(abs(feedback_score))
        for neuron in neurons:
            neuron.adapt(feedback_score)
