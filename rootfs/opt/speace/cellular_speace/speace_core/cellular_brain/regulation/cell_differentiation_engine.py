from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regulation.homeostasis_engine import SystemMetrics
from speace_core.dna.models import SharedGenome


class DifferentiationContext(BaseModel):
    region: Optional[str] = None
    energy: float = 1.0
    activation: float = 0.0
    connectivity: int = 0
    role: str = "excitatory"
    consecutive_fires: int = 0
    cell_type: str = "generic_neuron"
    layer: Optional[str] = None
    phi: Optional[float] = None
    mean_energy: Optional[float] = None


class CellDifferentiationEngine:
    """Engine that specializes DigitalNeurons based on context, genome rules, and circuit state."""

    def __init__(
        self,
        genome: SharedGenome,
        memory: Optional[MorphologicalMemory] = None,
    ):
        self.genome = genome
        self.memory = memory

    def evaluate_cell_context(
        self,
        neuron: DigitalNeuron,
        circuit: NeuralCircuit,
        metrics: Optional[SystemMetrics] = None,
    ) -> DifferentiationContext:
        conn = self._connectivity_count(neuron, circuit)
        return DifferentiationContext(
            region=neuron.region,
            energy=neuron.energy,
            activation=neuron.activation,
            connectivity=conn,
            role=neuron.neuron_role,
            consecutive_fires=neuron.consecutive_fires,
            cell_type=neuron.cell_type,
            layer=neuron.layer,
            phi=metrics.coherence_phi if metrics else None,
            mean_energy=metrics.mean_energy if metrics else None,
        )

    def select_cell_fate(self, context: DifferentiationContext) -> str:
        """Select cell type based on context and genome rules."""
        region = (context.region or "").lower()
        role = context.role.lower()
        energy = context.energy
        connectivity = context.connectivity
        fires = context.consecutive_fires

        # Input / sensory
        if role == "input" or region in {"sensory", "input"}:
            return "sensory_neuron"

        # Output / motor
        if role == "output" or region in {"motor", "output"}:
            return "motor_neuron"

        # Memory / hippocampus
        if region in {"hippocampus", "memory"}:
            return "hippocampal_neuron"

        # Prefrontal / control
        if region in {"prefrontal", "pfc", "control"}:
            return "prefrontal_neuron"

        # Language-specialized regions
        if region in {"auditory", "language_input"} or role == "auditory":
            return "auditory_neuron"
        if region in {"wernicke", "comprehension", "language_comprehension"} or role == "comprehension":
            return "wernicke_neuron"
        if region in {"broca", "production", "language_production"} or role == "production":
            return "broca_neuron"
        if region in {"semantic", "symbolic", "grounding"} or role == "semantic_pointer":
            return "semantic_pointer_neuron"

        # Hyperactive → inhibitory (stabilization)
        if fires >= 5:
            return "inhibitory_neuron"

        # Low energy + high connectivity → regulatory (energy management)
        if energy < 0.25 and connectivity > 3:
            return "regulatory_neuron"

        return "generic_neuron"

    def apply_differentiation(
        self,
        neuron: DigitalNeuron,
        new_type: str,
        context: DifferentiationContext,
    ) -> None:
        """Apply phenotypic changes to the neuron based on its new type."""
        old_type = neuron.cell_type
        rule = self.genome.get_differentiation_rule(new_type)

        neuron.cell_type = new_type
        neuron.differentiation_state = "differentiated"
        neuron.differentiation_score = min(1.0, neuron.differentiation_score + 0.25)

        if rule:
            neuron.threshold += rule.threshold_modifier
            neuron.threshold = max(0.1, min(1.0, neuron.threshold))
            neuron.plasticity_rate *= rule.plasticity_modifier
            if rule.refractory_period > 0:
                neuron.refractory_period = rule.refractory_period
            # Store gene expression metadata
            neuron.gene_expression = {
                "threshold_modifier": rule.threshold_modifier,
                "plasticity_modifier": rule.plasticity_modifier,
                "energy_profile": rule.energy_profile,
                "signal_sign": rule.signal_sign,
                "memory_affinity": rule.memory_affinity,
                "inhibition_affinity": rule.inhibition_affinity,
            }
            if rule.role:
                neuron.neuron_role = rule.role

        # T14 — Inhibitory phenotype
        if new_type == "inhibitory_neuron":
            neuron.inhibitory = True
            neuron.neuron_role = "inhibitory"
            neuron.inhibition_strength = 1.0
            if neuron.refractory_period == 0:
                neuron.refractory_period = 2

        # Language-specialized phenotypes
        if new_type == "auditory_neuron":
            neuron.neuron_role = "auditory"
            if neuron.phoneme_sensitivity == 0.0:
                neuron.phoneme_sensitivity = 0.7
        if new_type == "broca_neuron":
            neuron.neuron_role = "production"
        if new_type == "wernicke_neuron":
            neuron.neuron_role = "comprehension"
            if neuron.comprehension_strength == 0.0:
                neuron.comprehension_strength = 0.6
        if new_type == "semantic_pointer_neuron":
            neuron.neuron_role = "semantic_pointer"

        # Record epigenetic mark
        neuron.epigenetic_marks[new_type] = {
            "from": old_type,
            "score": neuron.differentiation_score,
        }

    def differentiate_cell(
        self,
        neuron: DigitalNeuron,
        circuit: NeuralCircuit,
        metrics: Optional[SystemMetrics] = None,
    ) -> str:
        """Full differentiation pipeline: evaluate, select, apply, record."""
        context = self.evaluate_cell_context(neuron, circuit, metrics=metrics)
        new_type = self.select_cell_fate(context)

        if new_type == neuron.cell_type and neuron.differentiation_state == "differentiated":
            return new_type

        old_type = neuron.cell_type
        self.apply_differentiation(neuron, new_type, context)

        if circuit.memory:
            circuit.memory.create_event(
                event_type=MorphologyEventType.CELL_DIFFERENTIATED,
                source_id="cell_differentiation_engine",
                target_id=neuron.cell_id,
                region_id=neuron.region,
                phi_before=context.phi,
                metadata={
                    "from_type": old_type,
                    "to_type": new_type,
                    "differentiation_state": neuron.differentiation_state,
                    "differentiation_score": neuron.differentiation_score,
                    "gene_expression": neuron.gene_expression,
                    "reason": "region_expression_rule",
                },
            )

        return new_type

    def differentiate_circuit(
        self,
        circuit: NeuralCircuit,
        metrics: Optional[SystemMetrics] = None,
    ) -> List[str]:
        """Differentiate all non-differentiated neurons in the circuit."""
        all_neurons = (
            circuit.input_neurons
            + circuit.hidden_neurons
            + circuit.output_neurons
        )
        results: List[str] = []
        for neuron in all_neurons:
            if neuron.differentiation_state != "differentiated":
                new_type = self.differentiate_cell(neuron, circuit, metrics=metrics)
                results.append(new_type)
        return results

    def _connectivity_count(
        self, neuron: DigitalNeuron, circuit: NeuralCircuit
    ) -> int:
        return sum(
            1
            for s in circuit.synapses
            if s.source == neuron.cell_id or s.target == neuron.cell_id
        )
