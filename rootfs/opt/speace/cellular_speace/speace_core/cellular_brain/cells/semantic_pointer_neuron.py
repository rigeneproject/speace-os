from typing import List, Optional

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.base.digital_signal import DigitalSignal


class SemanticPointerNeuron(DigitalNeuron):
    """Language-specialized neuron that binds symbols to cell assemblies.

    Acts as a distributed pointer from a symbolic label to a population
    of cells, enabling symbolic grounding: the link between a word/concept
    and its neural substrate.
    """

    cell_type: str = "semantic_pointer_neuron"
    symbol: Optional[str] = None
    assembly_id: Optional[str] = None
    binding_strength: float = 0.0

    async def receive(self, signal: DigitalSignal) -> None:
        # Strengthen binding when receiving matching symbol or assembly activation
        if signal.meaning == "ground_symbol" and hasattr(signal, "payload"):
            payload = signal.payload
            if isinstance(payload, dict):
                incoming_symbol = payload.get("symbol")
                incoming_assembly = payload.get("assembly_id")
                if incoming_symbol and incoming_assembly:
                    self.symbol = incoming_symbol
                    self.assembly_id = incoming_assembly
                    self.binding_strength = min(1.0, self.binding_strength + 0.1)
            elif isinstance(payload, str):
                self.symbol = payload
                self.binding_strength = min(1.0, self.binding_strength + 0.05)
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
                        strength=self.activation * self.binding_strength,
                        meaning="semantic_pointer",
                        payload={
                            "symbol": self.symbol,
                            "assembly_id": self.assembly_id,
                            "binding_strength": self.binding_strength,
                        },
                    )
                )
            self.activation = 0.0
            self.consecutive_fires += 1
        else:
            self.activation *= 0.5
            self.consecutive_fires = 0
        return signals
