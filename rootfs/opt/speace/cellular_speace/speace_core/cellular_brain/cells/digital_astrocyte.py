from typing import TYPE_CHECKING, List

from speace_core.cellular_brain.base.digital_cell import DigitalCell
from speace_core.cellular_brain.base.digital_signal import DigitalSignal

if TYPE_CHECKING:
    from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron


class DigitalAstrocyte(DigitalCell):
    region_id: str = "default"
    local_energy: float = 1.0
    noise_level: float = 0.0
    coherence_phi: float = 0.0

    async def receive(self, signal: DigitalSignal) -> None:
        if signal.meaning == "noise_report":
            self.noise_level += signal.strength

    async def tick(self) -> List[DigitalSignal]:
        return []

    def regulate(self, neurons: List["DigitalNeuron"]) -> None:
        if not neurons:
            return
        avg_activation = sum(n.activation for n in neurons) / len(neurons)
        if avg_activation > 0.85:
            for n in neurons:
                n.threshold += 0.05
        if self.noise_level > 0.6:
            self.suppress_noise(neurons)
        self.noise_level *= 0.9

    def suppress_noise(self, neurons: List["DigitalNeuron"]) -> None:
        for n in neurons:
            n.activation *= 0.8
