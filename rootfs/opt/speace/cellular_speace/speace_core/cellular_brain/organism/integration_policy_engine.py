from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.organism.organism_models import (
    IntegrationDecision,
    OrganismBusMessage,
)


class IntegrationPolicyEngine:
    """T59 — Engine di policy per il coordinamento organismico."""

    def __init__(self):
        self._blocked_reasons: List[str] = []

    def evaluate_message(self, message: OrganismBusMessage, metabolic_mode: str = "normal") -> bool:
        # TTL valido
        if message.ttl_ticks <= 0:
            return False

        # Safety ha priorità massima
        if message.safety_relevant:
            return True

        # EvolutionaryKernel non può richiedere risorse se metabolic mode è CRITICAL
        if (
            message.source == "evolutionary_kernel"
            and message.message_type in ("resource_request", "evolutionary_request")
            and metabolic_mode == "critical"
        ):
            return False

        return True

    def prioritize_messages(self, messages: List[OrganismBusMessage]) -> List[OrganismBusMessage]:
        # Safety-relevant first, then higher priority
        return sorted(
            messages,
            key=lambda m: (not m.safety_relevant, -m.priority, m.ttl_ticks),
        )

    def block_evolution_under_critical(self, metabolic_mode: str) -> bool:
        return metabolic_mode == "critical"

    def block_quarantined_memory(self, memory_status: str) -> bool:
        return memory_status == "quarantined"

    def is_recovery_priority_above_evolution(self, metabolic_mode: str) -> bool:
        return metabolic_mode in ("stress", "critical")

    def is_safety_highest_priority(self, messages: List[OrganismBusMessage]) -> bool:
        if not messages:
            return True
        safety_msgs = [m for m in messages if m.safety_relevant]
        non_safety = [m for m in messages if not m.safety_relevant]
        if not safety_msgs:
            return True
        min_safety = min(m.priority for m in safety_msgs)
        max_non_safety = max(m.priority for m in non_safety) if non_safety else 0.0
        return min_safety >= max_non_safety

    def generate_decision_from_policy(
        self,
        message: OrganismBusMessage,
        metabolic_mode: str,
        memory_status: str,
    ) -> Optional[IntegrationDecision]:
        if not self.evaluate_message(message, metabolic_mode):
            return IntegrationDecision(
                decision_id=f"block_{message.message_id}",
                target_subsystem=message.source,
                action="block",
                reason="policy_evaluation_failed",
                priority=1.0,
                reversible=True,
                safety_impact=0.0,
                metabolic_impact=0.0,
            )

        if (
            message.source == "evolutionary_kernel"
            and message.message_type in ("resource_request", "evolutionary_request")
            and self.block_evolution_under_critical(metabolic_mode)
        ):
            return IntegrationDecision(
                decision_id=f"throttle_evo_{message.message_id}",
                target_subsystem="evolutionary_kernel",
                action="throttle",
                reason="metabolic_mode_critical",
                priority=0.9,
                reversible=True,
                safety_impact=0.0,
                metabolic_impact=0.1,
            )

        if self.block_quarantined_memory(memory_status):
            return IntegrationDecision(
                decision_id=f"block_quarantine_{message.message_id}",
                target_subsystem=message.source,
                action="block",
                reason="quarantined_memory_blocked",
                priority=1.0,
                reversible=True,
                safety_impact=0.0,
                metabolic_impact=0.0,
            )

        return None
