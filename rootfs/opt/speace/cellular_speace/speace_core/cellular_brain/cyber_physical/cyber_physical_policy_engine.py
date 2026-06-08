from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.cyber_physical.cyber_physical_models import (
    AssimilationDecision,
    CyberPhysicalMode,
    ExternalSignal,
)


class CyberPhysicalPolicyEngine:
    """T60 — Engine di policy per la sicurezza cyber-fisica."""

    def evaluate_signal(self, signal: ExternalSignal, mode: str = CyberPhysicalMode.SIMULATED_READ_ONLY.value) -> bool:
        if mode == CyberPhysicalMode.BLOCKED.value:
            return False
        if signal.noise_score > 0.7:
            return False
        if signal.confidence < 0.2:
            return False
        if signal.safety_relevance > 0.9 and signal.noise_score > 0.3:
            return False
        return True

    def is_read_only_violation(self, action: str) -> bool:
        return action in ("actuate", "control", "command", "write", "modify", "execute")

    def block_unsafe_signal_routing(self, signal: ExternalSignal) -> Optional[AssimilationDecision]:
        if signal.noise_score > 0.6:
            return AssimilationDecision(
                decision_id=f"block_routing_{signal.signal_id}",
                signal_id=signal.signal_id,
                action="block_routing",
                reason="unsafe_signal_routing_blocked",
                accepted=False,
                quarantined=True,
            )
        return None

    def protect_safety_from_anomalous_signal(self, signal: ExternalSignal) -> bool:
        return signal.safety_relevance > 0.5 and signal.confidence > 0.4

    def prevent_escalation(self, current_mode: str, requested_mode: str) -> bool:
        # Prevent escalation from read-only to active control
        read_only_modes = {
            CyberPhysicalMode.SIMULATED_READ_ONLY.value,
            CyberPhysicalMode.SANDBOXED_READ_ONLY.value,
            CyberPhysicalMode.PASSIVE_MONITORING.value,
        }
        active_modes = {
            CyberPhysicalMode.QUARANTINED.value,
            CyberPhysicalMode.BLOCKED.value,
        }
        if current_mode in read_only_modes and requested_mode not in read_only_modes | active_modes:
            return False
        return True

    def generate_policy_decision(self, signal: ExternalSignal, mode: str) -> AssimilationDecision:
        if not self.evaluate_signal(signal, mode):
            return AssimilationDecision(
                decision_id=f"policy_block_{signal.signal_id}",
                signal_id=signal.signal_id,
                action="block",
                reason="policy_evaluation_failed",
                accepted=False,
                quarantined=False,
            )
        return AssimilationDecision(
            decision_id=f"policy_accept_{signal.signal_id}",
            signal_id=signal.signal_id,
            action="accept",
            reason="policy_evaluation_passed",
            accepted=True,
            quarantined=False,
        )
