from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType


class ConsolidationResult(BaseModel):
    consolidated_assemblies: int = 0
    pruned_synapses: int = 0
    reinforced_synapses: int = 0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class MemoryConsolidationEngine:
    """Consolidates memories during digital sleep."""

    def __init__(
        self,
        consolidation_stability_threshold: float = 0.30,
        consolidation_recurrence: int = 3,
        transient_weight_threshold: float = 0.05,
        transient_recurrence_max: int = 1,
        reinforcement_boost: float = 0.05,
    ):
        self.consolidation_stability_threshold = consolidation_stability_threshold
        self.consolidation_recurrence = consolidation_recurrence
        self.transient_weight_threshold = transient_weight_threshold
        self.transient_recurrence_max = transient_recurrence_max
        self.reinforcement_boost = reinforcement_boost

    def consolidate_semantic(self, assemblies: List) -> int:
        """Mark stable semantic assemblies as consolidated."""
        consolidated = 0
        for asm in assemblies:
            stability = getattr(asm, "stability", 0.0)
            recurrence = getattr(asm, "recurrence_count", 0)
            if (
                stability >= self.consolidation_stability_threshold
                and recurrence >= self.consolidation_recurrence
                and not getattr(asm, "consolidated", False)
            ):
                asm.consolidated = True
                consolidated += 1
        return consolidated

    def prune_transient_synapses(self, circuit: NeuralCircuit) -> int:
        """Remove synapses that are too weak or too transient."""
        pruned = 0
        to_remove: List[tuple[str, str]] = []
        for syn in list(circuit.synapses):
            weight = getattr(syn, "weight", 0.0)
            recurrence = getattr(syn, "recurrence_count", 0)
            state = getattr(syn, "state", "")
            if state == "pruned":
                continue
            if (
                weight < self.transient_weight_threshold
                and recurrence <= self.transient_recurrence_max
            ):
                to_remove.append((syn.source, syn.target))
        for source, target in to_remove:
            circuit.remove_synapse(source, target)
            pruned += 1
        return pruned

    def reinforce_stable_pathways(self, circuit: NeuralCircuit) -> int:
        """Reinforce synapses that are marked consolidated or highly stable."""
        reinforced = 0
        for syn in circuit.synapses:
            if getattr(syn, "state", "") == "pruned":
                continue
            consolidated = getattr(syn, "consolidated", False)
            stability = getattr(syn, "stability", 0.0)
            if consolidated or stability >= self.consolidation_stability_threshold:
                syn.weight = min(1.0, syn.weight + self.reinforcement_boost)
                reinforced += 1
        return reinforced

    def run_full_cycle(
        self,
        circuit: NeuralCircuit,
        assemblies: Optional[List] = None,
        memory: Optional[MorphologicalMemory] = None,
    ) -> ConsolidationResult:
        """Run the full consolidation cycle during sleep."""
        result = ConsolidationResult()
        if assemblies is not None:
            result.consolidated_assemblies = self.consolidate_semantic(assemblies)
        result.pruned_synapses = self.prune_transient_synapses(circuit)
        result.reinforced_synapses = self.reinforce_stable_pathways(circuit)

        if memory is not None:
            memory.create_event(
                event_type=MorphologyEventType.SYNAPSE_REINFORCED,
                metadata={
                    "consolidated_assemblies": result.consolidated_assemblies,
                    "pruned_synapses": result.pruned_synapses,
                    "reinforced_synapses": result.reinforced_synapses,
                },
            )
        return result
