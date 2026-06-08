from typing import List

from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.execution.burst_engine import BurstResult
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType


class InhibitionEngine:
    """Stabilization engine: refractory, snooze, runaway detection, decay."""

    def __init__(
        self,
        max_consecutive_fires: int = 5,
        default_snooze_duration: int = 3,
        activation_decay: float = 0.10,
        runaway_activation_threshold: float = 1.5,
    ):
        self.max_consecutive_fires = max_consecutive_fires
        self.default_snooze_duration = default_snooze_duration
        self.activation_decay = activation_decay
        self.runaway_activation_threshold = runaway_activation_threshold

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def stabilize_after_burst(
        self,
        circuit: NeuralCircuit,
        burst_result: BurstResult | None = None,
        memory: MorphologicalMemory | None = None,
    ) -> None:
        """Full stabilization pass after a burst cycle."""
        self.update_refractory_states(circuit)
        self.update_snooze_states(circuit)
        self.apply_decay(circuit)
        self.detect_and_handle_runaway(circuit, memory)
        self.apply_dynamic_snooze(circuit, memory)

    def update_refractory_states(self, circuit: NeuralCircuit) -> None:
        """Decrement refractory counters for all neurons."""
        all_neurons = (
            circuit.input_neurons
            + circuit.hidden_neurons
            + circuit.output_neurons
        )
        for neuron in all_neurons:
            if neuron.refractory_counter > 0:
                neuron.refractory_counter -= 1

    def update_snooze_states(self, circuit: NeuralCircuit) -> None:
        """Decrement snooze counters for all neurons."""
        all_neurons = (
            circuit.input_neurons
            + circuit.hidden_neurons
            + circuit.output_neurons
        )
        for neuron in all_neurons:
            if neuron.snooze_counter > 0:
                neuron.snooze_counter -= 1

    def apply_decay(self, circuit: NeuralCircuit) -> None:
        """Decay activation of all neurons that did not just fire."""
        all_neurons = (
            circuit.input_neurons
            + circuit.hidden_neurons
            + circuit.output_neurons
        )
        for neuron in all_neurons:
            if neuron.activation > 0.0:
                neuron.activation *= (1.0 - self.activation_decay)
                if neuron.activation < 1e-6:
                    neuron.activation = 0.0

    def detect_and_handle_runaway(
        self,
        circuit: NeuralCircuit,
        memory: MorphologicalMemory | None = None,
    ) -> List[str]:
        """Find neurons with activation above threshold and forcibly dampen."""
        handled: List[str] = []
        all_neurons = (
            circuit.input_neurons
            + circuit.hidden_neurons
            + circuit.output_neurons
        )
        for neuron in all_neurons:
            if neuron.activation >= self.runaway_activation_threshold:
                neuron.activation = max(0.0, neuron.activation - 0.5)
                handled.append(neuron.cell_id)
        return handled

    def apply_dynamic_snooze(
        self,
        circuit: NeuralCircuit,
        memory: MorphologicalMemory | None = None,
    ) -> List[str]:
        """Snooze neurons that fired too many times consecutively."""
        snoozed: List[str] = []
        all_neurons = (
            circuit.input_neurons
            + circuit.hidden_neurons
            + circuit.output_neurons
        )
        for neuron in all_neurons:
            if neuron.consecutive_fires >= self.max_consecutive_fires:
                self.apply_snooze(neuron, reason="max_consecutive_fires")
                snoozed.append(neuron.cell_id)
                if memory is not None:
                    memory.create_event(
                        event_type=MorphologyEventType.NEURON_SNOOZED,
                        source_id="inhibition_engine",
                        target_id=neuron.cell_id,
                        metadata={
                            "mechanism": "inhibition_engine",
                            "reason": "max_consecutive_fires",
                            "consecutive_fires": neuron.consecutive_fires,
                            "snooze_duration": neuron.snooze_counter,
                            "last_fired_burst": neuron.last_fired_burst,
                        },
                    )
        return snoozed

    @staticmethod
    def apply_snooze(neuron: DigitalNeuron, reason: str = "manual") -> None:
        """Put a neuron into snooze state."""
        neuron.snooze_counter = max(1, getattr(neuron, "snooze_duration", 0))
        if neuron.snooze_counter == 0:
            neuron.snooze_counter = 3
        neuron.activation = 0.0
        neuron.consecutive_fires = 0

    @staticmethod
    def is_inhibitory(neuron: DigitalNeuron) -> bool:
        return neuron.inhibitory or neuron.neuron_role == "inhibitory"

    @staticmethod
    def apply_inhibitory_signal(
        source: DigitalNeuron, target: DigitalNeuron, strength: float
    ) -> None:
        """Apply a direct inhibitory signal to a target neuron."""
        mod = source.inhibition_strength if source.inhibitory else 1.0
        target.activation -= abs(strength) * mod
        target.activation = max(0.0, target.activation)
