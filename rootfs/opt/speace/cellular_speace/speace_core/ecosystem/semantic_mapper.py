"""SemanticMapper — T131-B: maps external ecosystem entities to organismic metaphors."""

from typing import Any, Dict, List, Optional, Tuple


class SemanticMapper:
    """Maps external technology types to organismic semantic representations.

    T131-B adds system classification, functional roles, and relationship hints.
    This is read-only and descriptive only — it does not control anything.
    """

    _DEFAULT_MAP: Dict[str, str] = {
        "smart_grid": "circulatory_energetic",
        "power_grid": "circulatory_energetic",
        "iot_sensor": "sensory_termination",
        "sensor": "sensory_termination",
        "camera": "visual_organ",
        "microphone": "auditory_organ",
        "llm_agent": "cognitive_tissue",
        "ai_agent": "cognitive_tissue",
        "cloud_cluster": "neural_cluster",
        "server": "neural_cluster",
        "blockchain": "immutable_memory",
        "ledger": "immutable_memory",
        "robot": "motor_effector",
        "actuator": "motor_effector",
        "mqtt_broker": "synaptic_broker",
        "api_gateway": "membrane_gateway",
        "database": "episodic_store",
        "digital_twin": "mirror_body",
        "weather_station": "metabolic_sensor",
        "traffic_system": "circulatory_regulator",
        "rest_api": "membrane_gateway",
        "file": "episodic_store",
    }

    _SYSTEM_CLASS: Dict[str, str] = {
        "circulatory_energetic": "circulatory",
        "sensory_termination": "sensory",
        "visual_organ": "sensory",
        "auditory_organ": "sensory",
        "cognitive_tissue": "nervous",
        "neural_cluster": "nervous",
        "immutable_memory": "memory",
        "episodic_store": "memory",
        "motor_effector": "motor",
        "synaptic_broker": "nervous",
        "membrane_gateway": "boundary",
        "mirror_body": "nervous",
        "metabolic_sensor": "sensory",
        "circulatory_regulator": "circulatory",
    }

    _FUNCTIONAL_ROLE: Dict[str, str] = {
        "circulatory_energetic": "energy_transport",
        "sensory_termination": "input",
        "visual_organ": "input",
        "auditory_organ": "input",
        "cognitive_tissue": "processing",
        "neural_cluster": "processing",
        "immutable_memory": "storage",
        "episodic_store": "storage",
        "motor_effector": "output",
        "synaptic_broker": "relay",
        "membrane_gateway": "boundary",
        "mirror_body": "model",
        "metabolic_sensor": "input",
        "circulatory_regulator": "regulation",
    }

    _RELATIONSHIP_HINTS: Dict[str, List[str]] = {
        "circulatory_energetic": ["neural_cluster", "motor_effector", "episodic_store"],
        "sensory_termination": ["cognitive_tissue", "neural_cluster"],
        "visual_organ": ["cognitive_tissue", "neural_cluster"],
        "auditory_organ": ["cognitive_tissue", "neural_cluster"],
        "cognitive_tissue": ["sensory_termination", "motor_effector", "episodic_store", "immutable_memory"],
        "neural_cluster": ["cognitive_tissue", "synaptic_broker", "membrane_gateway"],
        "immutable_memory": ["cognitive_tissue", "neural_cluster"],
        "episodic_store": ["cognitive_tissue", "neural_cluster"],
        "motor_effector": ["circulatory_energetic", "cognitive_tissue"],
        "synaptic_broker": ["neural_cluster", "sensory_termination"],
        "membrane_gateway": ["neural_cluster", "cognitive_tissue"],
        "mirror_body": ["neural_cluster", "cognitive_tissue"],
        "metabolic_sensor": ["neural_cluster", "cognitive_tissue"],
        "circulatory_regulator": ["circulatory_energetic", "neural_cluster"],
    }

    def __init__(self, custom_map: Optional[Dict[str, str]] = None) -> None:
        self._mapping = dict(self._DEFAULT_MAP)
        if custom_map:
            self._mapping.update(custom_map)

    def map(self, source_type: str) -> Optional[str]:
        """Return organismic metaphor for a source type."""
        return self._mapping.get(source_type)

    def reverse_map(self, organismic_type: str) -> List[str]:
        """Return all external types that map to an organismic type."""
        return [k for k, v in self._mapping.items() if v == organismic_type]

    def system_class(self, source_type: str) -> Optional[str]:
        """Return organismic system classification (e.g. nervous, circulatory)."""
        metaphor = self.map(source_type)
        if metaphor is None:
            return None
        return self._SYSTEM_CLASS.get(metaphor)

    def functional_role(self, source_type: str) -> Optional[str]:
        """Return functional role (input, output, processing, storage, relay, boundary)."""
        metaphor = self.map(source_type)
        if metaphor is None:
            return None
        return self._FUNCTIONAL_ROLE.get(metaphor)

    def relationship_hints(self, source_type: str) -> List[str]:
        """Return organismic metaphors this source typically interacts with."""
        metaphor = self.map(source_type)
        if metaphor is None:
            return []
        return list(self._RELATIONSHIP_HINTS.get(metaphor, []))

    def describe(self, source_type: str) -> Dict[str, Any]:
        """Return a structured description."""
        metaphor = self.map(source_type)
        system = self.system_class(source_type)
        role = self.functional_role(source_type)
        hints = self.relationship_hints(source_type)
        return {
            "source_type": source_type,
            "organismic_metaphor": metaphor,
            "system_class": system,
            "functional_role": role,
            "typical_relationships": hints,
            "description": (
                f"{source_type} is perceived as {metaphor} ({system} system, {role})"
                if metaphor else "No mapping available"
            ),
        }

    def classify_by_system(self) -> Dict[str, List[str]]:
        """Group all mapped source types by organismic system."""
        groups: Dict[str, List[str]] = {}
        for source_type in self._mapping:
            system = self.system_class(source_type)
            if system is None:
                continue
            groups.setdefault(system, []).append(source_type)
        return groups

    def infer_relationship(
        self, source_a: str, source_b: str
    ) -> Optional[str]:
        """Infer a likely relationship between two source types based on organismic hints."""
        meta_a = self.map(source_a)
        meta_b = self.map(source_b)
        if meta_a is None or meta_b is None:
            return None
        if meta_b in self._RELATIONSHIP_HINTS.get(meta_a, []):
            return "afferent"
        if meta_a in self._RELATIONSHIP_HINTS.get(meta_b, []):
            return "efferent"
        sys_a = self.system_class(source_a)
        sys_b = self.system_class(source_b)
        if sys_a == sys_b and sys_a is not None:
            return "homologous"
        return "unrelated"

    def all_mappings(self) -> Dict[str, str]:
        """Return the full mapping dictionary."""
        return dict(self._mapping)
