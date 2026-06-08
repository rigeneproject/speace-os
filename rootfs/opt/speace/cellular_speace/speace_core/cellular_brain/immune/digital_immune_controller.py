from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.immune.pattern_anomaly_detector import PatternAnomalyDetector
from speace_core.cellular_brain.immune.clone_deviation_monitor import CloneDeviationMonitor
from speace_core.cellular_brain.immune.immune_response_engine import ImmuneResponseEngine
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory


class DigitalImmuneController:
    """Coordinates the digital immune system."""

    def __init__(
        self,
        anomaly_detector: Optional[PatternAnomalyDetector] = None,
        deviation_monitor: Optional[CloneDeviationMonitor] = None,
        response_engine: Optional[ImmuneResponseEngine] = None,
    ):
        self.anomaly_detector = anomaly_detector or PatternAnomalyDetector()
        self.deviation_monitor = deviation_monitor or CloneDeviationMonitor()
        self.response_engine = response_engine or ImmuneResponseEngine()
        self.immune_state: Dict[str, Any] = {"active_alerts": 0, "quarantined": []}

    def tick(self, orchestrator: Any) -> None:
        """Run one immune cycle."""
        circuit = orchestrator.circuit
        all_neurons = (
            circuit.input_neurons + circuit.hidden_neurons + circuit.output_neurons
        )
        assemblies = None
        store = getattr(orchestrator, "_semantic_memory_store", None)
        if store is not None:
            assemblies = getattr(store, "_assemblies", None)
            if hasattr(assemblies, "values"):
                assemblies = list(assemblies.values())

        report = self.anomaly_detector.detect_all(
            neurons=all_neurons,
            synapses=circuit.synapses,
            assemblies=assemblies,
        )

        memory: Optional[MorphologicalMemory] = getattr(orchestrator, "_memory", None)
        actions = self.response_engine.respond_to_anomalies(
            report.anomalies, memory=memory
        )

        for action in actions:
            if action.action_type == "quarantine":
                self.immune_state["quarantined"].append(action.target_id)

        self.immune_state["active_alerts"] = len(report.anomalies)
        self.immune_state["last_action_count"] = len(actions)
