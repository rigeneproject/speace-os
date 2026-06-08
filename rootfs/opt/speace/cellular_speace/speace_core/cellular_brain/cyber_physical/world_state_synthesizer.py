from typing import Any, Dict, List

from speace_core.cellular_brain.cyber_physical.cyber_physical_models import (
    ExternalSignal,
    WorldStateSnapshot,
)


class WorldStateSynthesizer:
    """T60 — Sintetizza lo stato del mondo dai segnali esterni accettati."""

    def synthesize_world_state(
        self,
        signals: List[ExternalSignal],
        snapshot_id: str = "world_state",
    ) -> WorldStateSnapshot:
        env_pressure = self.compute_environmental_pressure(signals)
        infra_pressure = self.compute_infrastructure_pressure(signals)
        energy_pressure = self.compute_energy_pressure(signals)
        safety_pressure = self.compute_safety_pressure(signals)
        uncertainty = self.compute_uncertainty(signals)
        coherence = self.compute_world_coherence_score(signals)

        return WorldStateSnapshot(
            snapshot_id=snapshot_id,
            signal_count=len(signals),
            environmental_pressure=env_pressure,
            infrastructure_pressure=infra_pressure,
            energy_pressure=energy_pressure,
            safety_pressure=safety_pressure,
            uncertainty_score=uncertainty,
            world_coherence_score=coherence,
            metadata={"source_signal_types": list(set(s.signal_type for s in signals))},
        )

    @staticmethod
    def compute_environmental_pressure(signals: List[ExternalSignal]) -> float:
        env_signals = [s for s in signals if s.signal_type == "environmental"]
        if not env_signals:
            return 0.0
        return sum(min(1.0, float(s.value) if isinstance(s.value, (int, float)) else 0.5) for s in env_signals) / len(env_signals)

    @staticmethod
    def compute_energy_pressure(signals: List[ExternalSignal]) -> float:
        energy_signals = [s for s in signals if s.signal_type == "energy"]
        if not energy_signals:
            return 0.0
        return sum(min(1.0, float(s.value) if isinstance(s.value, (int, float)) else 0.5) for s in energy_signals) / len(energy_signals)

    @staticmethod
    def compute_safety_pressure(signals: List[ExternalSignal]) -> float:
        safety_signals = [s for s in signals if s.safety_relevance > 0.5]
        if not safety_signals:
            return 0.0
        return sum(s.safety_relevance for s in safety_signals) / len(safety_signals)

    @staticmethod
    def compute_infrastructure_pressure(signals: List[ExternalSignal]) -> float:
        infra_signals = [s for s in signals if s.signal_type == "infrastructure"]
        if not infra_signals:
            return 0.0
        return sum(min(1.0, float(s.value) if isinstance(s.value, (int, float)) else 0.5) for s in infra_signals) / len(infra_signals)

    @staticmethod
    def compute_uncertainty(signals: List[ExternalSignal]) -> float:
        if not signals:
            return 0.0
        return sum(1.0 - s.confidence for s in signals) / len(signals)

    @staticmethod
    def compute_world_coherence_score(signals: List[ExternalSignal]) -> float:
        if not signals:
            return 1.0
        conflicts = WorldStateSynthesizer.detect_world_state_conflicts(signals)
        return max(0.0, 1.0 - len(conflicts) * 0.2)

    @staticmethod
    def detect_world_state_conflicts(signals: List[ExternalSignal]) -> List[str]:
        conflicts: List[str] = []
        # Detect contradictory environmental signals
        env_signals = [s for s in signals if s.signal_type == "environmental"]
        if len(env_signals) >= 2:
            vals = [float(s.value) if isinstance(s.value, (int, float)) else 0.5 for s in env_signals]
            if max(vals) - min(vals) > 0.5:
                conflicts.append("environmental_contradiction")
        # Detect safety vs energy conflict
        safety_high = any(s.safety_relevance > 0.7 for s in signals)
        energy_high = any(s.signal_type == "energy" and float(s.value) > 0.8 for s in signals if isinstance(s.value, (int, float)))
        if safety_high and energy_high:
            conflicts.append("safety_energy_conflict")
        return conflicts
