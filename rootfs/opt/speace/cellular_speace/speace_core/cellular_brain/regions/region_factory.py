import random
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.regions.brain_region import BrainRegion
from speace_core.cellular_brain.regions.region_connectome import InterRegionConnection
from speace_core.cellular_brain.regions.region_registry import RegionRegistry


class RegionFactory:
    """Factory to build regional brain architecture from genome instructions."""

    # Default pipeline: sensory → hippocampus → prefrontal → motor
    DEFAULT_PIPELINE: List[str] = ["sensory", "hippocampus", "prefrontal", "motor"]

    # T31 — Deep region pipeline with limbic, default_mode, cerebellar
    DEEP_REGION_PIPELINE: List[str] = [
        "sensory", "limbic", "hippocampus", "default_mode",
        "prefrontal", "cerebellar", "motor",
    ]

    @classmethod
    def build_from_genome(
        cls,
        circuit: NeuralCircuit,
        genome_dict: Dict[str, Any],
        seed: int = 42,
        deep_regions_enabled: bool = True,
    ) -> RegionRegistry:
        random.seed(seed)
        registry = RegionRegistry()
        brain_regions = genome_dict.get("brain_regions", {})

        if not brain_regions:
            # Fallback: assign neurons by role heuristics
            cls._assign_fallback_regions(circuit, registry, deep_regions_enabled=deep_regions_enabled)
            return registry

        # 1. Create regions from genome
        region_neuron_ids: Dict[str, List[str]] = {rid: [] for rid in brain_regions}
        all_assigned: set = set()

        # Sort hidden neurons into regions by dominant cell types
        for neuron in circuit.hidden_neurons:
            assigned = False
            for rid, spec in brain_regions.items():
                dominant = spec.get("dominant_cell_types", [])
                if neuron.neuron_role in dominant or neuron.cell_id.startswith(rid):
                    region_neuron_ids[rid].append(neuron.cell_id)
                    all_assigned.add(neuron.cell_id)
                    assigned = True
                    break
            if not assigned:
                # Round-robin assign unassigned neurons
                smallest = min(region_neuron_ids, key=lambda k: len(region_neuron_ids[k]))
                region_neuron_ids[smallest].append(neuron.cell_id)
                all_assigned.add(neuron.cell_id)

        # 2. Register regions
        for rid, spec in brain_regions.items():
            region = BrainRegion(
                region_id=rid,
                region_type=spec.get("region_type", rid),
                neuron_ids=region_neuron_ids[rid],
                dominant_cell_types=spec.get("dominant_cell_types", []),
                role_description=spec.get("role_description", ""),
            )
            registry.register(region)

        # 3. Build inter-region connections based on pipeline
        pipeline = cls.DEEP_REGION_PIPELINE if deep_regions_enabled else cls.DEFAULT_PIPELINE
        for i in range(len(pipeline) - 1):
            src = pipeline[i]
            tgt = pipeline[i + 1]
            if src in brain_regions and tgt in brain_regions:
                registry.connectome.add_connection(
                    source_region_id=src,
                    target_region_id=tgt,
                    connection_type="feedforward",
                    strength=0.5,
                    plasticity_enabled=True,
                    inhibitory=False,
                )

        # 4. Tag neurons with primary region
        for rid, region in registry.regions.items():
            for n_id in region.neuron_ids:
                neuron = circuit._find_neuron(n_id)
                if neuron is not None:
                    neuron.region = rid

        return registry

    @classmethod
    def _assign_fallback_regions(
        cls, circuit: NeuralCircuit, registry: RegionRegistry, deep_regions_enabled: bool = True
    ) -> None:
        """When genome has no brain_regions, assign by neuron role heuristics."""
        assignments: Dict[str, List[str]] = {
            "sensory": [],
            "hippocampus": [],
            "prefrontal": [],
            "motor": [],
        }
        if deep_regions_enabled:
            assignments.update({
                "limbic": [],
                "cerebellar": [],
                "default_mode": [],
                "brainstem_homeostatic": [],
            })

        for neuron in circuit.hidden_neurons:
            role = getattr(neuron, "neuron_role", "excitatory")
            if role in {"sensory_neuron", "input"}:
                assignments["sensory"].append(neuron.cell_id)
            elif role in {"hippocampal_neuron", "memory_neuron", "memory"}:
                assignments["hippocampus"].append(neuron.cell_id)
            elif role in {"prefrontal_neuron", "control", "inhibitory_neuron"}:
                assignments["prefrontal"].append(neuron.cell_id)
            elif role in {"motor_neuron", "output"}:
                assignments["motor"].append(neuron.cell_id)
            elif deep_regions_enabled and role in {"limbic_neuron", "salience"}:
                assignments["limbic"].append(neuron.cell_id)
            elif deep_regions_enabled and role in {"cerebellar_neuron", "error_correction"}:
                assignments["cerebellar"].append(neuron.cell_id)
            elif deep_regions_enabled and role in {"default_mode_neuron", "consolidation"}:
                assignments["default_mode"].append(neuron.cell_id)
            elif deep_regions_enabled and role in {"brainstem_neuron", "homeostasis"}:
                assignments["brainstem_homeostatic"].append(neuron.cell_id)
            else:
                # Round-robin
                smallest = min(assignments, key=lambda k: len(assignments[k]))
                assignments[smallest].append(neuron.cell_id)

        for rid, nids in assignments.items():
            region = BrainRegion(
                region_id=rid,
                region_type=rid,
                neuron_ids=nids,
            )
            registry.register(region)

        # Default pipeline connections
        pipeline = cls.DEEP_REGION_PIPELINE if deep_regions_enabled else cls.DEFAULT_PIPELINE
        for i in range(len(pipeline) - 1):
            src = pipeline[i]
            tgt = pipeline[i + 1]
            registry.connectome.add_connection(
                source_region_id=src,
                target_region_id=tgt,
                connection_type="feedforward",
                strength=0.5,
            )

        for rid, region in registry.regions.items():
            for n_id in region.neuron_ids:
                neuron = circuit._find_neuron(n_id)
                if neuron is not None:
                    neuron.region = rid
