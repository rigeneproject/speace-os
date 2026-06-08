from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class BrainRegionProfile(BaseModel):
    region_id: str
    name: str
    region_type: str
    neuron_ids: List[str] = Field(default_factory=list)
    synapse_ids: List[str] = Field(default_factory=list)
    dominant_cell_types: List[str] = Field(default_factory=list)
    mean_energy: float = 0.0
    local_phi: float = 0.0
    local_confidence: Optional[float] = None
    community_count: int = 0
    role_description: Optional[str] = None


class BrainRegion:
    """Functional neurocellular region in SPEACE."""

    def __init__(
        self,
        region_id: str,
        region_type: str,
        neuron_ids: Optional[List[str]] = None,
        dominant_cell_types: Optional[List[str]] = None,
        role_description: Optional[str] = None,
    ):
        self.region_id = region_id
        self.region_type = region_type
        self.neuron_ids = neuron_ids or []
        self.synapse_ids: List[str] = []
        self.dominant_cell_types = dominant_cell_types or []
        self.role_description = role_description or ""
        self._input_buffer: List[float] = []
        self._output_buffer: List[float] = []

    # ------------------------------------------------------------------ #
    # Local metrics
    # ------------------------------------------------------------------ #

    def compute_local_metrics(self, circuit) -> BrainRegionProfile:
        """Compute energy, phi, and community proxy for this region."""
        from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit

        if not isinstance(circuit, NeuralCircuit):
            return self.to_profile()

        all_neurons = circuit.input_neurons + circuit.hidden_neurons + circuit.output_neurons
        region_neurons = [
            n for n in all_neurons if n.cell_id in self.neuron_ids
        ]
        region_synapses = [
            s for s in circuit.synapses
            if s.source in self.neuron_ids and s.target in self.neuron_ids
        ]

        mean_energy = (
            sum(n.energy for n in region_neurons) / len(region_neurons)
            if region_neurons
            else 0.0
        )

        # Local phi proxy: ratio of internal vs total synaptic weight
        internal_weight = sum(s.weight for s in region_synapses if s.state != "pruned")
        all_weight = sum(
            s.weight
            for s in circuit.synapses
            if s.source in self.neuron_ids or s.target in self.neuron_ids
            if s.state != "pruned"
        )
        local_phi = internal_weight / (all_weight + 1e-12) if all_weight > 0 else 0.0

        return BrainRegionProfile(
            region_id=self.region_id,
            name=self.region_type,
            region_type=self.region_type,
            neuron_ids=self.neuron_ids,
            synapse_ids=[s.cell_id for s in region_synapses],
            dominant_cell_types=self.dominant_cell_types,
            mean_energy=mean_energy,
            local_phi=local_phi,
            role_description=self.role_description,
        )

    def to_profile(self) -> BrainRegionProfile:
        return BrainRegionProfile(
            region_id=self.region_id,
            name=self.region_type,
            region_type=self.region_type,
            neuron_ids=self.neuron_ids,
            synapse_ids=self.synapse_ids,
            dominant_cell_types=self.dominant_cell_types,
            role_description=self.role_description,
        )

    # ------------------------------------------------------------------ #
    # Signal I/O
    # ------------------------------------------------------------------ #

    def receive_signal(self, signal: List[float]) -> None:
        self._input_buffer.extend(signal)

    def emit_signal(self) -> List[float]:
        output = self._output_buffer.copy()
        self._output_buffer.clear()
        return output

    def flush_buffers(self) -> None:
        self._input_buffer.clear()
        self._output_buffer.clear()

    # ------------------------------------------------------------------ #
    # Regulation
    # ------------------------------------------------------------------ #

    def regulate_region(self, circuit) -> None:
        """Apply region-specific regulation (e.g., energy normalization)."""
        all_neurons = circuit.input_neurons + circuit.hidden_neurons + circuit.output_neurons
        region_neurons = [
            n for n in all_neurons if n.cell_id in self.neuron_ids
        ]
        if not region_neurons:
            return
        mean_energy = sum(n.energy for n in region_neurons) / len(region_neurons)
        if mean_energy > 0.9:
            for n in region_neurons:
                n.energy *= 0.98
        elif mean_energy < 0.3:
            for n in region_neurons:
                n.energy = min(1.0, n.energy + 0.02)
