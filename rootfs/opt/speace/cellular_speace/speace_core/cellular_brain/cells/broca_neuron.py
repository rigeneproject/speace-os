from typing import List

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.base.digital_signal import DigitalSignal


class BrocaNeuron(DigitalNeuron):
    """Language-specialized neuron for speech/language production.

    Analogous to Broca's area: motor planning and grammatical structuring
    of symbolic output. Responsible for assembling sequences of symbols
    into coherent productions.
    """

    cell_type: str = "broca_neuron"
    grammatical_role: str = ""
    production_readiness: float = 0.0
    sequence_buffer: List[str] = []

    async def receive(self, signal: DigitalSignal) -> None:
        # Broca neurons accumulate semantic pointers for production
        if signal.meaning == "semantic_pointer" or signal.meaning == "production_request":
            self.activation += signal.strength * 1.1
            if hasattr(signal, "payload") and signal.payload:
                token = signal.payload if isinstance(signal.payload, str) else str(signal.payload)
                self.sequence_buffer.append(token)
        else:
            self.activation += signal.strength

    async def tick(self) -> List[DigitalSignal]:
        signals: List[DigitalSignal] = []
        if self.activation >= self.threshold and self.energy > 0.1:
            self.energy = max(0.0, self.energy - 0.05)
            for target_id in self.targets:
                payload = self.sequence_buffer[:4] if self.sequence_buffer else []
                signals.append(
                    DigitalSignal(
                        source=self.cell_id,
                        target=target_id,
                        strength=self.activation,
                        meaning="symbolic_production",
                        payload=payload,
                    )
                )
            self.activation = 0.0
            self.consecutive_fires += 1
            self.sequence_buffer = []
        else:
            self.activation *= 0.5
            self.consecutive_fires = 0
        return signals
