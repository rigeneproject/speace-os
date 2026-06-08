from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from speace_core.cellular_brain.immune.pattern_anomaly_detector import AnomalyEvent
from speace_core.cellular_brain.immune.clone_deviation_monitor import DeviationEvent
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType


class ThreatLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ImmuneAction(BaseModel):
    action_type: str
    target_id: str
    target_type: str
    reason: str

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ImmuneResponseEngine:
    """Classifies threats and applies immune responses."""

    def __init__(
        self,
        low_threshold: float = 0.25,
        moderate_threshold: float = 0.5,
        high_threshold: float = 0.75,
    ):
        self.low_threshold = low_threshold
        self.moderate_threshold = moderate_threshold
        self.high_threshold = high_threshold

    def classify_threat(self, anomaly: AnomalyEvent) -> ThreatLevel:
        severity = anomaly.severity
        if severity >= self.high_threshold:
            return ThreatLevel.CRITICAL
        elif severity >= self.moderate_threshold:
            return ThreatLevel.HIGH
        elif severity >= self.low_threshold:
            return ThreatLevel.MODERATE
        return ThreatLevel.LOW

    def quarantine_entity(
        self,
        entity_id: str,
        entity_type: str,
        memory: Optional[MorphologicalMemory] = None,
    ) -> ImmuneAction:
        if memory is not None:
            memory.create_event(
                event_type=MorphologyEventType.MICROGLIA_PRUNING,
                metadata={
                    "action": "quarantine",
                    "entity_id": entity_id,
                    "entity_type": entity_type,
                },
            )
        return ImmuneAction(
            action_type="quarantine",
            target_id=entity_id,
            target_type=entity_type,
            reason="anomaly_detected",
        )

    def block_mutation(
        self,
        mutation_proposal: Dict[str, Any],
        memory: Optional[MorphologicalMemory] = None,
    ) -> ImmuneAction:
        if memory is not None:
            memory.create_event(
                event_type=MorphologyEventType.GENOME_MUTATED,
                metadata={
                    "action": "block",
                    "proposal": mutation_proposal,
                },
            )
        return ImmuneAction(
            action_type="block_mutation",
            target_id=mutation_proposal.get("id", "unknown"),
            target_type="mutation",
            reason="unauthorized",
        )

    def alert_operators(
        self,
        threat_level: ThreatLevel,
        anomalies: List[AnomalyEvent],
        memory: Optional[MorphologicalMemory] = None,
    ) -> None:
        if memory is not None:
            memory.create_event(
                event_type=MorphologyEventType.CONFIDENCE_EVALUATED,
                metadata={
                    "alert_type": "immune_alert",
                    "threat_level": threat_level.value,
                    "anomaly_count": len(anomalies),
                },
            )

    def respond_to_anomalies(
        self,
        anomalies: List[AnomalyEvent],
        memory: Optional[MorphologicalMemory] = None,
    ) -> List[ImmuneAction]:
        actions = []
        for anomaly in anomalies:
            level = self.classify_threat(anomaly)
            if level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL):
                actions.append(
                    self.quarantine_entity(
                        anomaly.entity_id, anomaly.entity_type, memory=memory
                    )
                )
            elif level == ThreatLevel.MODERATE:
                actions.append(
                    ImmuneAction(
                        action_type="monitor",
                        target_id=anomaly.entity_id,
                        target_type=anomaly.entity_type,
                        reason=f"moderate_threat:{anomaly.anomaly_type}",
                    )
                )
        if anomalies:
            max_level = max(
                (self.classify_threat(a) for a in anomalies),
                key=lambda l: [ThreatLevel.LOW, ThreatLevel.MODERATE, ThreatLevel.HIGH, ThreatLevel.CRITICAL].index(l),
            )
            self.alert_operators(max_level, anomalies, memory=memory)
        return actions
