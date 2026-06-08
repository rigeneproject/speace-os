from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict


class AnomalyEvent(BaseModel):
    entity_type: str
    entity_id: str
    anomaly_type: str
    severity: float  # 0.0–1.0
    details: Dict[str, Any] = {}

    model_config = ConfigDict(arbitrary_types_allowed=True)


class AnomalyReport(BaseModel):
    anomalies: List[AnomalyEvent] = []
    summary: str = ""

    model_config = ConfigDict(arbitrary_types_allowed=True)


class PatternAnomalyDetector:
    """Detects anomalous patterns in neurons, synapses, and assemblies."""

    def __init__(
        self,
        neuron_activation_max: float = 3.0,
        neuron_activation_min: float = -1.0,
        synapse_weight_max: float = 2.0,
        synapse_weight_change_threshold: float = 0.5,
        assembly_similarity_max: float = 0.95,
        assembly_similarity_min: float = 0.05,
    ):
        self.neuron_activation_max = neuron_activation_max
        self.neuron_activation_min = neuron_activation_min
        self.synapse_weight_max = synapse_weight_max
        self.synapse_weight_change_threshold = synapse_weight_change_threshold
        self.assembly_similarity_max = assembly_similarity_max
        self.assembly_similarity_min = assembly_similarity_min
        self._previous_weights: Dict[str, float] = {}

    def detect_neuron_anomalies(self, neurons) -> List[AnomalyEvent]:
        events = []
        for neuron in neurons:
            activation = getattr(neuron, "activation", 0.0)
            if activation > self.neuron_activation_max:
                events.append(
                    AnomalyEvent(
                        entity_type="neuron",
                        entity_id=getattr(neuron, "cell_id", "unknown"),
                        anomaly_type="extreme_activation",
                        severity=min(1.0, (activation - self.neuron_activation_max) / 2.0),
                        details={"activation": activation},
                    )
                )
            elif activation < self.neuron_activation_min:
                events.append(
                    AnomalyEvent(
                        entity_type="neuron",
                        entity_id=getattr(neuron, "cell_id", "unknown"),
                        anomaly_type="extreme_negative_activation",
                        severity=min(1.0, abs(activation - self.neuron_activation_min) / 1.0),
                        details={"activation": activation},
                    )
                )
        return events

    def detect_synapse_anomalies(self, synapses) -> List[AnomalyEvent]:
        events = []
        for syn in synapses:
            weight = getattr(syn, "weight", 0.0)
            key = f"{getattr(syn, 'source', '')}-{getattr(syn, 'target', '')}"
            prev = self._previous_weights.get(key, weight)
            delta = abs(weight - prev)

            if weight > self.synapse_weight_max:
                events.append(
                    AnomalyEvent(
                        entity_type="synapse",
                        entity_id=key,
                        anomaly_type="extreme_weight",
                        severity=min(1.0, (weight - self.synapse_weight_max) / 1.0),
                        details={"weight": weight},
                    )
                )
            elif delta > self.synapse_weight_change_threshold:
                events.append(
                    AnomalyEvent(
                        entity_type="synapse",
                        entity_id=key,
                        anomaly_type="sudden_weight_change",
                        severity=min(1.0, delta / 1.0),
                        details={"weight": weight, "previous": prev, "delta": delta},
                    )
                )
            self._previous_weights[key] = weight
        return events

    def detect_assembly_anomalies(self, assemblies) -> List[AnomalyEvent]:
        events = []
        if not assemblies:
            return events
        # Check for collapse (too similar) and fragmentation (too dissimilar)
        for i, a1 in enumerate(assemblies):
            sig1 = getattr(a1, "signature", None)
            if sig1 is None:
                continue
            for j, a2 in enumerate(assemblies):
                if i >= j:
                    continue
                sig2 = getattr(a2, "signature", None)
                if sig2 is None:
                    continue
                similarity = self._cosine_similarity(sig1, sig2)
                if similarity > self.assembly_similarity_max:
                    events.append(
                        AnomalyEvent(
                            entity_type="assembly",
                            entity_id=f"{getattr(a1, 'id', i)}-{getattr(a2, 'id', j)}",
                            anomaly_type="functional_collapse",
                            severity=min(1.0, (similarity - self.assembly_similarity_max) / 0.05),
                            details={"similarity": similarity},
                        )
                    )
                elif similarity < self.assembly_similarity_min:
                    events.append(
                        AnomalyEvent(
                            entity_type="assembly",
                            entity_id=f"{getattr(a1, 'id', i)}-{getattr(a2, 'id', j)}",
                            anomaly_type="fragmentation",
                            severity=min(1.0, (self.assembly_similarity_min - similarity) / 0.05),
                            details={"similarity": similarity},
                        )
                    )
        return events

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def detect_all(self, neurons, synapses, assemblies=None) -> AnomalyReport:
        anomalies = []
        anomalies.extend(self.detect_neuron_anomalies(neurons))
        anomalies.extend(self.detect_synapse_anomalies(synapses))
        if assemblies is not None:
            anomalies.extend(self.detect_assembly_anomalies(assemblies))
        summary = f"Detected {len(anomalies)} anomalies"
        return AnomalyReport(anomalies=anomalies, summary=summary)
