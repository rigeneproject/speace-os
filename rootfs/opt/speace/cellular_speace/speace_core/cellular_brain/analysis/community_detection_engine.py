from collections import defaultdict
from typing import Dict, List, Optional, Set

from pydantic import BaseModel, Field

from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType


class CommunityProfile(BaseModel):
    community_id: str
    neuron_ids: List[str] = Field(default_factory=list)
    size: int = 0
    mean_activation: float = 0.0
    mean_energy: float = 0.0
    mean_phi_proxy: float = 0.0
    internal_synapse_count: int = 0
    external_synapse_count: int = 0
    cohesion_score: float = 0.0
    isolation_score: float = 0.0
    dominant_cell_type: Optional[str] = None
    dominant_region: Optional[str] = None


class CommunityDetectionResult(BaseModel):
    communities: List[CommunityProfile] = Field(default_factory=list)
    community_count: int = 0
    modularity_proxy: float = 0.0
    isolated_neurons: List[str] = Field(default_factory=list)
    overloaded_communities: List[str] = Field(default_factory=list)
    weak_communities: List[str] = Field(default_factory=list)


class CommunityDetectionEngine:
    """Mesoscopic analyzer: detects functional neuron communities from circuit topology."""

    def __init__(
        self,
        cohesion_weak_threshold: float = 0.3,
        overload_activation_threshold: float = 0.8,
        overload_energy_threshold: float = 0.9,
    ):
        self.cohesion_weak_threshold = cohesion_weak_threshold
        self.overload_activation_threshold = overload_activation_threshold
        self.overload_energy_threshold = overload_energy_threshold

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def analyze(
        self,
        circuit: NeuralCircuit,
        memory: MorphologicalMemory | None = None,
    ) -> CommunityDetectionResult:
        """Run full community detection pipeline."""
        adjacency = self.build_adjacency_map(circuit)
        communities = self.detect_communities(circuit, adjacency)
        profiles: List[CommunityProfile] = []
        for idx, neuron_ids in enumerate(communities):
            profile = self.profile_community(circuit, neuron_ids, community_id=f"comm_{idx}")
            profiles.append(profile)

        result = CommunityDetectionResult(
            communities=profiles,
            community_count=len(profiles),
            isolated_neurons=self.find_isolated_neurons(circuit, adjacency),
            overloaded_communities=self.find_overloaded_communities(profiles),
            weak_communities=self.find_weak_communities(profiles),
        )
        result.modularity_proxy = self.compute_modularity_proxy(result)

        if memory is not None:
            memory.create_event(
                event_type=MorphologyEventType.COMMUNITY_DETECTED,
                source_id="community_detection_engine",
                metadata={
                    "community_count": result.community_count,
                    "modularity_proxy": result.modularity_proxy,
                    "isolated_neuron_count": len(result.isolated_neurons),
                    "weak_communities": result.weak_communities,
                    "overloaded_communities": result.overloaded_communities,
                },
            )

        return result

    def build_adjacency_map(
        self, circuit: NeuralCircuit
    ) -> Dict[str, Set[str]]:
        """Build undirected adjacency map from active synapses."""
        adjacency: Dict[str, Set[str]] = defaultdict(set)
        for syn in circuit.synapses:
            if syn.state == "pruned":
                continue
            adjacency[syn.source].add(syn.target)
            adjacency[syn.target].add(syn.source)
        return adjacency

    def detect_communities(
        self,
        circuit: NeuralCircuit,
        adjacency: Dict[str, Set[str]] | None = None,
    ) -> List[List[str]]:
        """Find connected components as initial communities."""
        if adjacency is None:
            adjacency = self.build_adjacency_map(circuit)

        all_neurons = self._all_neuron_ids(circuit)
        visited: Set[str] = set()
        communities: List[List[str]] = []

        for neuron_id in all_neurons:
            if neuron_id in visited:
                continue
            if neuron_id not in adjacency:
                # isolated neuron handled separately
                continue
            # BFS/DFS for connected component
            component: List[str] = []
            stack = [neuron_id]
            while stack:
                current = stack.pop()
                if current in visited:
                    continue
                visited.add(current)
                component.append(current)
                for neighbor in adjacency.get(current, set()):
                    if neighbor not in visited:
                        stack.append(neighbor)
            if component:
                communities.append(component)

        return communities

    def profile_community(
        self,
        circuit: NeuralCircuit,
        neuron_ids: List[str],
        community_id: str = "comm_0",
    ) -> CommunityProfile:
        """Compute profile for a single community."""
        neuron_map = self._neuron_map(circuit)
        neurons = [neuron_map[nid] for nid in neuron_ids if nid in neuron_map]
        size = len(neurons)

        mean_activation = sum(n.activation for n in neurons) / size if size else 0.0
        mean_energy = sum(n.energy for n in neurons) / size if size else 0.0
        # phi_proxy: normalized inverse variance of activations within community
        mean_phi_proxy = self._compute_phi_proxy([n.activation for n in neurons])

        # Count internal vs external synapses
        internal_set = set(neuron_ids)
        internal_synapses = 0
        external_synapses = 0
        for syn in circuit.synapses:
            if syn.state == "pruned":
                continue
            src_in = syn.source in internal_set
            tgt_in = syn.target in internal_set
            if src_in and tgt_in:
                internal_synapses += 1
            elif src_in or tgt_in:
                external_synapses += 1

        cohesion = internal_synapses / (internal_synapses + external_synapses + 1)

        # Dominant cell type and region
        type_counts: Dict[str, int] = defaultdict(int)
        region_counts: Dict[str, int] = defaultdict(int)
        for n in neurons:
            if n.cell_type:
                type_counts[n.cell_type] += 1
            if n.region:
                region_counts[n.region] += 1

        dominant_cell_type = max(type_counts, key=type_counts.get) if type_counts else None
        dominant_region = max(region_counts, key=region_counts.get) if region_counts else None

        return CommunityProfile(
            community_id=community_id,
            neuron_ids=list(neuron_ids),
            size=size,
            mean_activation=mean_activation,
            mean_energy=mean_energy,
            mean_phi_proxy=mean_phi_proxy,
            internal_synapse_count=internal_synapses,
            external_synapse_count=external_synapses,
            cohesion_score=cohesion,
            isolation_score=1.0 - cohesion,
            dominant_cell_type=dominant_cell_type,
            dominant_region=dominant_region,
        )

    def compute_modularity_proxy(
        self, result: CommunityDetectionResult
    ) -> float:
        """Weighted average of cohesion scores by community size."""
        total_weight = 0.0
        weighted_sum = 0.0
        for comm in result.communities:
            weight = comm.size
            total_weight += weight
            weighted_sum += comm.cohesion_score * weight
        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def find_isolated_neurons(
        self,
        circuit: NeuralCircuit,
        adjacency: Dict[str, Set[str]] | None = None,
    ) -> List[str]:
        """Neurons with zero active synaptic connections."""
        if adjacency is None:
            adjacency = self.build_adjacency_map(circuit)
        all_ids = self._all_neuron_ids(circuit)
        return [nid for nid in all_ids if nid not in adjacency or len(adjacency[nid]) == 0]

    def find_overloaded_communities(
        self, profiles: List[CommunityProfile]
    ) -> List[str]:
        """Communities with excessively high activation or energy."""
        overloaded: List[str] = []
        for profile in profiles:
            if (
                profile.mean_activation >= self.overload_activation_threshold
                or profile.mean_energy >= self.overload_energy_threshold
            ):
                overloaded.append(profile.community_id)
        return overloaded

    def find_weak_communities(
        self, profiles: List[CommunityProfile]
    ) -> List[str]:
        """Communities with low internal cohesion."""
        weak: List[str] = []
        for profile in profiles:
            if profile.cohesion_score < self.cohesion_weak_threshold:
                weak.append(profile.community_id)
        return weak

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _all_neuron_ids(circuit: NeuralCircuit) -> Set[str]:
        all_neurons = (
            circuit.input_neurons
            + circuit.hidden_neurons
            + circuit.output_neurons
        )
        return {n.cell_id for n in all_neurons}

    @staticmethod
    def _neuron_map(circuit: NeuralCircuit) -> Dict[str, DigitalNeuron]:
        all_neurons = (
            circuit.input_neurons
            + circuit.hidden_neurons
            + circuit.output_neurons
        )
        return {n.cell_id: n for n in all_neurons}

    @staticmethod
    def _compute_phi_proxy(activations: List[float]) -> float:
        if not activations:
            return 0.0
        total = sum(activations)
        if total == 0:
            return 0.0
        # Normalized inverse variance as a simple local coherence proxy
        mean = total / len(activations)
        variance = sum((a - mean) ** 2 for a in activations) / len(activations)
        max_variance = mean * (1.0 - mean) if 0 < mean < 1 else 1.0
        if max_variance == 0:
            return 1.0
        return max(0.0, 1.0 - (variance / max_variance))
