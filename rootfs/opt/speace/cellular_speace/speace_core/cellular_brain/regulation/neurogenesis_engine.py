import random
from typing import Optional

from pydantic import BaseModel, Field
from uuid import uuid4

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regulation.cell_differentiation_engine import (
    CellDifferentiationEngine,
)


class NeurogenesisResult(BaseModel):
    created: bool
    neuron_id: Optional[str] = None
    neuron_type: Optional[str] = None
    reason: str = ""
    phi_before: Optional[float] = None
    metadata: dict = Field(default_factory=dict)


class NeurogenesisEngine:
    def __init__(
        self,
        error_threshold: int = 3,
        phi_threshold: float = 0.55,
        min_energy: float = 0.25,
        max_new_neurons_per_cycle: int = 3,
    ):
        self.error_threshold = error_threshold
        self.phi_threshold = phi_threshold
        self.min_energy = min_energy
        self.max_new_neurons_per_cycle = max_new_neurons_per_cycle

    def should_generate(
        self,
        error_count: int,
        phi: float,
        energy: float,
    ) -> bool:
        return (
            error_count >= self.error_threshold
            and phi <= self.phi_threshold
            and energy >= self.min_energy
        )

    def generate_neuron(
        self,
        circuit: NeuralCircuit,
        phi_before: float,
        reason: str,
        differentiation_engine: CellDifferentiationEngine | None = None,
    ) -> NeurogenesisResult:
        all_neurons = (
            circuit.input_neurons
            + circuit.hidden_neurons
            + circuit.output_neurons
        )
        if len(all_neurons) >= 1000:
            return NeurogenesisResult(
                created=False,
                reason="max_neuron_limit_reached",
            )

        neuron_id = f"ng_{str(uuid4())[:8]}"
        new_neuron = DigitalNeuron(
            cell_id=neuron_id,
            role="digital_neuron",
            threshold=0.5,
            plasticity_rate=0.05,
        )

        self._integrate_new_neuron(circuit, new_neuron)

        # T10 — differentiate newly created neuron
        if differentiation_engine is not None:
            new_type = differentiation_engine.differentiate_cell(
                new_neuron, circuit, metrics=None
            )
        else:
            new_type = "digital_neuron"

        if circuit.memory:
            circuit.memory.create_event(
                event_type=MorphologyEventType.NEURON_CREATED,
                source_id="neurogenesis_engine",
                target_id=neuron_id,
                phi_before=phi_before,
                metadata={
                    "reason": reason,
                    "neuron_type": new_type,
                    "initial_synapses": 4,
                },
            )

        return NeurogenesisResult(
            created=True,
            neuron_id=neuron_id,
            neuron_type=new_type,
            reason=reason,
            phi_before=phi_before,
        )

    def _integrate_new_neuron(
        self,
        circuit: NeuralCircuit,
        neuron: DigitalNeuron,
    ) -> None:
        circuit.hidden_neurons.append(neuron)

        all_neurons = (
            circuit.input_neurons
            + circuit.hidden_neurons
            + circuit.output_neurons
        )

        # Incoming synapses from 2 random existing neurons
        sources = random.sample(all_neurons, min(2, len(all_neurons)))
        for src in sources:
            if src.cell_id == neuron.cell_id:
                continue
            syn = DigitalSynapse(
                cell_id=f"syn_{src.cell_id}_{neuron.cell_id}",
                role="digital_synapse",
                source=src.cell_id,
                target=neuron.cell_id,
                weight=0.3,
                trust=0.3,
            )
            circuit.synapses.append(syn)
            src.targets.append(neuron.cell_id)

        # Outgoing synapses to 2 random existing neurons
        targets = random.sample(all_neurons, min(2, len(all_neurons)))
        for tgt in targets:
            if tgt.cell_id == neuron.cell_id:
                continue
            syn = DigitalSynapse(
                cell_id=f"syn_{neuron.cell_id}_{tgt.cell_id}",
                role="digital_synapse",
                source=neuron.cell_id,
                target=tgt.cell_id,
                weight=0.3,
                trust=0.3,
            )
            circuit.synapses.append(syn)
            neuron.targets.append(tgt.cell_id)
