import random
import uuid
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.organism.integration_policy_engine import (
    IntegrationPolicyEngine,
)
from speace_core.cellular_brain.organism.organism_bus import OrganismBus
from speace_core.cellular_brain.organism.organism_models import (
    IntegrationDecision,
    OrganismBusMessage,
    OrganismMessageType,
    OrganismState,
)
from speace_core.cellular_brain.organism.subsystem_registry import SubsystemRegistry


class CrossSystemCoordinator:
    """T59 — Coordinatore cross-sistema per l'organismo computazionale."""

    def __init__(
        self,
        bus: Optional[OrganismBus] = None,
        registry: Optional[SubsystemRegistry] = None,
        policy_engine: Optional[IntegrationPolicyEngine] = None,
        seed: int = 42,
    ):
        self.bus = bus or OrganismBus(seed=seed)
        self.registry = registry or SubsystemRegistry()
        self.policy = policy_engine or IntegrationPolicyEngine()
        self._decisions: List[IntegrationDecision] = []
        random.seed(seed)

    def coordinate_cycle(
        self,
        organism_state: OrganismState,
        incoming_messages: List[OrganismBusMessage],
    ) -> List[IntegrationDecision]:
        self._decisions.clear()

        # Ordina messaggi per priorità
        prioritized = self.policy.prioritize_messages(incoming_messages)

        for msg in prioritized:
            decision = self.policy.generate_decision_from_policy(
                msg,
                metabolic_mode=organism_state.metabolic_mode,
                memory_status=organism_state.metadata.get("memory_status", "normal"),
            )
            if decision:
                self._decisions.append(decision)
            else:
                # Messaggio consentito: route
                self._route_message(msg, organism_state)

        # Applica logiche globali
        self._apply_global_coordination(organism_state)

        return list(self._decisions)

    def _route_message(self, msg: OrganismBusMessage, organism_state: OrganismState) -> None:
        # Se target disabilitato/degraded, non route
        if msg.target:
            status = self.registry.get_status(msg.target)
            if status and (not status.enabled or status.degraded):
                self._decisions.append(
                    IntegrationDecision(
                        decision_id=f"route_fail_{msg.message_id}",
                        target_subsystem=msg.target,
                        action="block",
                        reason="target_disabled_or_degraded",
                        priority=0.8,
                        reversible=True,
                    )
                )
                return
        self.bus.publish(msg)

    def _apply_global_coordination(self, organism_state: OrganismState) -> None:
        # Throttle evolution if needed
        if organism_state.metabolic_mode in ("critical", "stress") and organism_state.evolutionary_pressure > 0.3:
            self._decisions.append(
                IntegrationDecision(
                    decision_id=f"evo_throttle_{uuid.uuid4().hex[:8]}",
                    target_subsystem="evolutionary_kernel",
                    action="throttle",
                    reason="global_coordination_evolution_under_stress",
                    priority=0.85,
                    reversible=True,
                    safety_impact=0.0,
                    metabolic_impact=0.2,
                )
            )

        # Protect safety
        if organism_state.safety_risk_score > 0.5:
            self._decisions.append(
                IntegrationDecision(
                    decision_id=f"safety_protect_{uuid.uuid4().hex[:8]}",
                    target_subsystem="safety",
                    action="protect",
                    reason="safety_risk_elevated",
                    priority=1.0,
                    reversible=True,
                    safety_impact=0.0,
                    metabolic_impact=0.1,
                )
            )

    def route_resource_requests(self, requests: List[OrganismBusMessage]) -> List[IntegrationDecision]:
        decisions: List[IntegrationDecision] = []
        for req in requests:
            if req.message_type == OrganismMessageType.RESOURCE_REQUEST.value:
                status = self.registry.get_status(req.source)
                if status and status.degraded:
                    decisions.append(
                        IntegrationDecision(
                            decision_id=f"deny_{req.message_id}",
                            target_subsystem=req.source,
                            action="deny",
                            reason="subsystem_degraded",
                            priority=0.7,
                            reversible=True,
                        )
                    )
                else:
                    decisions.append(
                        IntegrationDecision(
                            decision_id=f"grant_{req.message_id}",
                            target_subsystem=req.source,
                            action="grant",
                            reason="resource_request_approved",
                            priority=0.5,
                            reversible=True,
                        )
                    )
        return decisions

    def prioritize_recovery(self, messages: List[OrganismBusMessage]) -> List[OrganismBusMessage]:
        recovery = [m for m in messages if m.message_type == OrganismMessageType.RECOVERY_REQUEST.value]
        other = [m for m in messages if m.message_type != OrganismMessageType.RECOVERY_REQUEST.value]
        return recovery + other

    def throttle_evolution_if_needed(self, organism_state: OrganismState) -> Optional[IntegrationDecision]:
        if organism_state.metabolic_mode == "critical" and organism_state.evolutionary_pressure > 0.0:
            return IntegrationDecision(
                decision_id=f"evo_throttle_{uuid.uuid4().hex[:8]}",
                target_subsystem="evolutionary_kernel",
                action="throttle",
                reason="metabolic_critical",
                priority=0.9,
                reversible=True,
            )
        return None

    def protect_safety(self, organism_state: OrganismState) -> Optional[IntegrationDecision]:
        if organism_state.safety_risk_score > 0.3:
            return IntegrationDecision(
                decision_id=f"safety_protect_{uuid.uuid4().hex[:8]}",
                target_subsystem="safety",
                action="protect",
                reason="safety_risk_above_threshold",
                priority=1.0,
                reversible=True,
            )
        return None

    def generate_decisions(self, organism_state: OrganismState) -> List[IntegrationDecision]:
        decisions: List[IntegrationDecision] = []
        evo = self.throttle_evolution_if_needed(organism_state)
        if evo:
            decisions.append(evo)
        safety = self.protect_safety(organism_state)
        if safety:
            decisions.append(safety)
        return decisions
