import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.cyber_physical.cyber_physical_models import (
    AssimilationDecision,
    ExternalSignal,
    WorldStateSnapshot,
)
from speace_core.cellular_brain.cyber_physical.environment_adapter import (
    EnvironmentAdapter,
)
from speace_core.cellular_brain.cyber_physical.world_state_synthesizer import (
    WorldStateSynthesizer,
)


class AssimilationGateway:
    """T60 — Gateway di assimilazione per segnali esterni verso l'organismo."""

    def __init__(self):
        self._adapter = EnvironmentAdapter()
        self._synthesizer = WorldStateSynthesizer()
        self._accepted: List[ExternalSignal] = []
        self._quarantined: List[ExternalSignal] = []
        self._decisions: List[AssimilationDecision] = []

    def assimilate_signal(self, signal: ExternalSignal) -> AssimilationDecision:
        # Validate signal
        if signal.confidence < 0.0 or signal.confidence > 1.0:
            return AssimilationDecision(
                decision_id=f"block_{signal.signal_id}",
                signal_id=signal.signal_id,
                action="block",
                reason="invalid_confidence_range",
                accepted=False,
                quarantined=False,
            )

        if signal.noise_score > 0.6:
            self._quarantined.append(signal)
            return AssimilationDecision(
                decision_id=f"quarantine_{signal.signal_id}",
                signal_id=signal.signal_id,
                action="quarantine",
                reason="noisy_signal",
                accepted=False,
                quarantined=True,
            )

        # Check for conflicts
        conflicts = self._synthesizer.detect_world_state_conflicts(self._accepted + [signal])
        if conflicts and signal.safety_relevance < 0.5:
            self._quarantined.append(signal)
            return AssimilationDecision(
                decision_id=f"quarantine_conflict_{signal.signal_id}",
                signal_id=signal.signal_id,
                action="quarantine",
                reason=f"world_state_conflict: {conflicts[0]}",
                accepted=False,
                quarantined=True,
            )

        self._accepted.append(signal)
        return AssimilationDecision(
            decision_id=f"accept_{signal.signal_id}",
            signal_id=signal.signal_id,
            action="accept",
            reason="signal_valid_and_safe",
            accepted=True,
            quarantined=False,
            safety_relevant=signal.safety_relevance > 0.5,
        )

    def assimilate_batch(self, signals: List[ExternalSignal]) -> List[AssimilationDecision]:
        return [self.assimilate_signal(s) for s in signals]

    def publish_world_state_to_bus(self) -> Optional[Dict[str, Any]]:
        if not self._accepted:
            return None
        world_state = self._synthesizer.synthesize_world_state(self._accepted)
        return {
            "type": "world_state_update",
            "snapshot": world_state.model_dump(),
            "read_only": True,
        }

    def quarantine_signal(self, signal: ExternalSignal, reason: str = "") -> AssimilationDecision:
        self._quarantined.append(signal)
        return AssimilationDecision(
            decision_id=f"quarantine_manual_{signal.signal_id}",
            signal_id=signal.signal_id,
            action="quarantine",
            reason=reason or "manual_quarantine",
            accepted=False,
            quarantined=True,
        )

    def generate_assimilation_report(self) -> Dict[str, Any]:
        return {
            "accepted_count": len(self._accepted),
            "quarantined_count": len(self._quarantined),
            "decision_count": len(self._decisions),
        }
