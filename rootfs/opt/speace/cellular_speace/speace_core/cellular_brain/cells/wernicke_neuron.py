from typing import List

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.base.digital_signal import DigitalSignal


class WernickeNeuron(DigitalNeuron):
    """Language-specialized neuron for semantic comprehension.

    Analogous to Wernicke's area: maps auditory/symbolic tokens to meaning.
    Critical for understanding and linking incoming symbolic labels to
    existing conceptual assemblies.
    """

    cell_type: str = "wernicke_neuron"
    semantic_field: str = ""
    comprehension_strength: float = 0.6
    context_window: List[str] = []

    async def receive(self, signal: DigitalSignal) -> None:
        # Wernicke neurons integrate auditory tokens and semantic pointers
        if signal.meaning in {"auditory_token", "symbolic_label", "semantic_pointer"}:
            self.activation += signal.strength * self.comprehension_strength
            if hasattr(signal, "payload") and signal.payload:
                token = signal.payload if isinstance(signal.payload, str) else str(signal.payload)
                self.context_window.append(token)
                if len(self.context_window) > 7:
                    self.context_window.pop(0)
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
                        meaning="comprehended_symbol",
                        payload=self.semantic_field,
                    )
                )
            self.activation = 0.0
            self.consecutive_fires += 1
        else:
            self.activation *= 0.5
            self.consecutive_fires = 0
        return signals
