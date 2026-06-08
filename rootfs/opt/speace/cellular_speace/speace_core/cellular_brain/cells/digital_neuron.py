from typing import List

from speace_core.cellular_brain.base.digital_cell import DigitalCell
from speace_core.cellular_brain.base.digital_signal import DigitalSignal


class DigitalNeuron(DigitalCell):
    threshold: float = 0.5
    activation: float = 0.0
    plasticity_rate: float = 0.05
    targets: List[str] = []
    error_history: List[float] = []

    # T9 — ApoptosisEngine fields
    neuron_role: str = "excitatory"
    is_critical: bool = False
    snooze_counter: int = 0
    refractory_counter: int = 0
    refractory_period: int = 0
    consecutive_fires: int = 0
    last_fired_tick: int | None = None
    utility_score: float = 0.0
    apoptosis_risk: float = 0.0

    # T12 — EventDrivenBurstEngine fields
    last_fired_burst: int = 0

    # T14 — InhibitoryNeuron & Snooze fields
    inhibitory: bool = False
    inhibition_strength: float = 1.0
    max_consecutive_fires: int = 5

    # T10 — CellDifferentiationEngine fields
    cell_type: str = "generic_neuron"
    region: str | None = None
    layer: str | None = None
    differentiation_state: str = "undifferentiated"
    differentiation_score: float = 0.0
    gene_expression: dict = {}
    epigenetic_marks: dict = {}

    # T132 — Linguistic phenotype fields
    phoneme_sensitivity: float = 0.0
    grammatical_role: str = ""
    sequence_buffer: list = []
    comprehension_strength: float = 0.0
    context_window: list = []
    symbol: str | None = None
    assembly_id: str | None = None
    binding_strength: float = 0.0

    async def receive(self, signal: DigitalSignal) -> None:
        self.activation += signal.strength

    async def tick(self) -> List[DigitalSignal]:
        # T9 — handle snooze and refractory
        if self.snooze_counter > 0:
            self.snooze_counter -= 1
            self.activation *= 0.5
            return []
        if self.refractory_counter > 0:
            self.refractory_counter -= 1
            self.activation *= 0.5
            return []

        signals: List[DigitalSignal] = []
        if self.activation >= self.threshold and self.energy > 0.1:
            self.energy = max(0.0, self.energy - 0.05)
            for target_id in self.targets:
                signals.append(
                    DigitalSignal(
                        source=self.cell_id,
                        target=target_id,
                        strength=self.activation,
                    )
                )
            self.activation = 0.0
            self.consecutive_fires += 1
            if self.refractory_period > 0:
                self.refractory_counter = self.refractory_period
        else:
            self.activation *= 0.5
            self.consecutive_fires = 0
        return signals

    def adapt(self, feedback_score: float) -> None:
        self.threshold -= self.plasticity_rate * feedback_score
        self.threshold = max(0.1, min(1.0, self.threshold))
        self.local_memory.append(feedback_score)
        if feedback_score < 0:
            self.error_history.append(feedback_score)
