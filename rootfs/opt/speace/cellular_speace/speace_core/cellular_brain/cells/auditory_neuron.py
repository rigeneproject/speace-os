from typing import List

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.base.digital_signal import DigitalSignal


class AuditoryNeuron(DigitalNeuron):
    """Language-specialized neuron for auditory/speech input processing.

    Represents early cortical processing of symbolic auditory input,
    analogous to primary and secondary auditory cortices.
    """

    cell_type: str = "auditory_neuron"
    receptive_field: str = ""
    phoneme_sensitivity: float = 0.7
    temporal_window: int = 3

    async def receive(self, signal: DigitalSignal) -> None:
        # Auditory neurons are more sensitive to rapid temporal sequences
        if signal.meaning == "phoneme" or signal.meaning == "sound_token":
            self.activation += signal.strength * self.phoneme_sensitivity
        else:
            self.activation += signal.strength

    async def tick(self) -> List[DigitalSignal]:
        signals: List[DigitalSignal] = []
        if self.activation >= self.threshold and self.energy > 0.1:
            self.energy = max(0.0, self.energy - 0.05)
            for target_id in self.targets:
                signals.append(
                    DigitalSignal(
                        source=self.cell_id,
                        target=target_id,
                        strength=self.activation,
                        meaning="auditory_token",
                    )
                )
            self.activation = 0.0
            self.consecutive_fires += 1
        else:
            self.activation *= 0.5
            self.consecutive_fires = 0
        return signals
