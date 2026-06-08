from typing import Any, Dict, List

from speace_core.cellular_brain.cyber_physical.cyber_physical_models import (
    AssimilationDecision,
    CyberPhysicalMode,
    ExternalSignal,
    ExternalSignalType,
)


class EnvironmentAdapter:
    """T60 — Adattatore ambientale per segnali esterni simulati."""

    def normalize_signal(self, raw: Dict[str, Any]) -> ExternalSignal:
        signal_type = self.classify_signal_type(raw.get("type", "unknown"))
        value = raw.get("value", 0.0)
        confidence = max(0.0, min(1.0, raw.get("confidence", 1.0)))
        noise_score = max(0.0, min(1.0, raw.get("noise_score", 0.0)))
        safety_relevance = max(0.0, min(1.0, raw.get("safety_relevance", 0.0)))
        return ExternalSignal(
            signal_id=raw.get("signal_id", "unknown"),
            source_id=raw.get("source_id", "unknown"),
            signal_type=signal_type,
            timestamp=raw.get("timestamp", ""),
            value=value,
            confidence=confidence,
            safety_relevance=safety_relevance,
            noise_score=noise_score,
            metadata=raw.get("metadata", {}),
        )

    def normalize_batch(self, raw_signals: List[Dict[str, Any]]) -> List[ExternalSignal]:
        return [self.normalize_signal(r) for r in raw_signals]

    @staticmethod
    def detect_noise(signal: ExternalSignal) -> bool:
        return signal.noise_score > 0.5 or signal.confidence < 0.3

    @staticmethod
    def classify_signal_type(raw_type: str) -> str:
        mapping = {
            "temp": ExternalSignalType.ENVIRONMENTAL.value,
            "humidity": ExternalSignalType.ENVIRONMENTAL.value,
            "voltage": ExternalSignalType.ENERGY.value,
            "current": ExternalSignalType.ENERGY.value,
            "cpu": ExternalSignalType.INFRASTRUCTURE.value,
            "memory": ExternalSignalType.INFRASTRUCTURE.value,
            "ping": ExternalSignalType.NETWORK_STATUS.value,
            "latency": ExternalSignalType.NETWORK_STATUS.value,
            "health": ExternalSignalType.SYSTEM_HEALTH.value,
            "feedback": ExternalSignalType.HUMAN_FEEDBACK.value,
            "sensor": ExternalSignalType.SENSOR.value,
        }
        return mapping.get(raw_type, ExternalSignalType.UNKNOWN.value)

    @staticmethod
    def quarantine_invalid_signal(signal: ExternalSignal) -> AssimilationDecision:
        return AssimilationDecision(
            decision_id=f"quarantine_{signal.signal_id}",
            signal_id=signal.signal_id,
            action="quarantine",
            reason="invalid_or_noisy_signal",
            accepted=False,
            quarantined=True,
            safety_relevant=signal.safety_relevance > 0.5,
        )
