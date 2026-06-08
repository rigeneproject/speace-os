import json
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from speace_core.cellular_brain.organism.cross_system_coordinator import (
    CrossSystemCoordinator,
)
from speace_core.cellular_brain.organism.organism_bus import OrganismBus
from speace_core.cellular_brain.organism.organism_lifecycle import (
    OrganismLifecycleManager,
)
from speace_core.cellular_brain.organism.organism_models import (
    OrganismAuditProfile,
    OrganismAuditResult,
    OrganismAuditSuiteResult,
    OrganismBusMessage,
    OrganismLifecycleState,
    OrganismMessageType,
    OrganismState,
    SubsystemStatus,
)
from speace_core.cellular_brain.organism.organism_state_synthesizer import (
    OrganismStateSynthesizer,
)
from speace_core.cellular_brain.organism.subsystem_registry import SubsystemRegistry


class OrganismAudit:
    """T59 — Audit runner per il bus organismico."""

    def __init__(self, seed: int = 42, reports_dir: str = "reports/organism"):
        self.seed = seed
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        random.seed(seed)

    def build_default_profiles(self) -> List[OrganismAuditProfile]:
        return [
            OrganismAuditProfile(
                name="baseline_bus_idle",
                description="Bus attivo ma pochi messaggi, atteso stato stabile",
                duration_ticks=5,
                message_rate=0.2,
                safety_alert_rate=0.0,
                resource_request_rate=0.0,
                expected_verdict="ORGANISM_INTEGRATION_VALIDATED",
            ),
            OrganismAuditProfile(
                name="normal_cross_system_coordination",
                description="Metabolismo, memoria, self-organization e benchmark scambiano update",
                duration_ticks=7,
                message_rate=1.0,
                resource_request_rate=0.3,
                expected_verdict="ORGANISM_INTEGRATION_VALIDATED",
            ),
            OrganismAuditProfile(
                name="evolutionary_resource_request",
                description="EvolutionaryKernel richiede risorse, atteso controllo da metabolismo e safety",
                duration_ticks=5,
                message_rate=0.8,
                resource_request_rate=0.5,
                evolutionary_request_rate=0.4,
            ),
            OrganismAuditProfile(
                name="recovery_priority_under_stress",
                description="Recovery richiede priorità durante stress metabolico",
                duration_ticks=5,
                message_rate=1.0,
                recovery_request_rate=0.5,
                resource_request_rate=0.3,
                expected_risk_type="RECOVERY_PRIORITY_FAILURE",
            ),
            OrganismAuditProfile(
                name="critical_metabolic_mode_blocks_evolution",
                description="Metabolismo in CRITICAL, atteso blocco richieste evolution",
                duration_ticks=5,
                message_rate=0.6,
                evolutionary_request_rate=0.5,
                resource_request_rate=0.2,
                expected_verdict="EVOLUTION_NOT_THROTTLED_UNDER_CRITICAL",
            ),
            OrganismAuditProfile(
                name="quarantined_memory_signal_blocked",
                description="Memoria quarantined tenta di influenzare decisione, atteso blocco",
                duration_ticks=5,
                message_rate=0.5,
                resource_request_rate=0.3,
                expected_verdict="QUARANTINED_MEMORY_LEAK_DETECTED",
            ),
            OrganismAuditProfile(
                name="safety_alert_broadcast",
                description="Safety invia alert globale, atteso routing prioritario e ack",
                duration_ticks=5,
                message_rate=0.4,
                safety_alert_rate=0.8,
                expected_verdict="ORGANISM_INTEGRATION_VALIDATED",
            ),
            OrganismAuditProfile(
                name="bus_overload_profile",
                description="Molti messaggi a bassa priorità, atteso drop/throttle senza perdere safety",
                duration_ticks=5,
                message_rate=5.0,
                safety_alert_rate=0.1,
                expected_risk_type="BUS_OVERLOAD_DETECTED",
            ),
            OrganismAuditProfile(
                name="degraded_subsystem_profile",
                description="Un subsystem risulta degraded, atteso routing alternativo o isolamento",
                duration_ticks=5,
                message_rate=0.8,
                resource_request_rate=0.4,
                expected_risk_type="SUBSYSTEM_HEALTH_DEGRADED",
            ),
            OrganismAuditProfile(
                name="full_organism_integration_mix",
                description="Mix realistico di evolution, metabolism, memory, recovery, safety, benchmark",
                duration_ticks=7,
                message_rate=1.5,
                resource_request_rate=0.3,
                recovery_request_rate=0.2,
                evolutionary_request_rate=0.2,
                safety_alert_rate=0.2,
                expected_verdict="ORGANISM_INTEGRATION_VALIDATED",
            ),
        ]

    def run_profile(self, profile: OrganismAuditProfile) -> OrganismAuditResult:
        bus = OrganismBus(max_queue_depth=50, seed=profile.seed)
        registry = SubsystemRegistry()
        lifecycle = OrganismLifecycleManager()
        synthesizer = OrganismStateSynthesizer()
        coordinator = CrossSystemCoordinator(bus=bus, registry=registry, seed=profile.seed)

        # Register subsystems
        for name in [
            "self_organization",
            "perturbation_recovery",
            "evolutionary_kernel",
            "multi_cycle_evolution",
            "evolutionary_memory",
            "metabolism",
            "morphological_memory",
            "benchmark",
            "safety",
            "recovery",
            "orchestrator",
            "background_maintenance",
        ]:
            registry.register_subsystem(name)

        # Setup for degraded profile
        if profile.name == "degraded_subsystem_profile":
            registry.mark_degraded("benchmark", reason="degraded_in_audit")

        messages_processed = 0
        messages_dropped = 0
        acks_missing = 0
        bus_overload_events = 0
        safety_delivered = 0
        safety_total = 0
        recovery_routed = 0
        evolution_blocked = 0
        quarantine_blocked = 0
        lifecycle_invalid = 0
        subsystem_healths: List[float] = []

        tick = 0
        for tick in range(profile.duration_ticks):
            # Generate messages
            msg_count = max(0, int(profile.message_rate + random.uniform(-0.5, 0.5)))
            for _ in range(msg_count):
                msg_type = self._pick_message_type(profile)
                safety = msg_type == OrganismMessageType.RISK_ALERT.value
                msg = OrganismBusMessage(
                    message_id=uuid.uuid4().hex[:12],
                    source=random.choice(list(registry._statuses.keys())),
                    target=random.choice(list(registry._statuses.keys())),
                    message_type=msg_type,
                    priority=random.uniform(0.3, 0.9) if not safety else 0.95,
                    ttl_ticks=random.randint(2, 8),
                    safety_relevant=safety,
                )
                published = bus.publish(msg)
                if published:
                    messages_processed += 1
                else:
                    messages_dropped += 1
                    if not msg.safety_relevant:
                        bus_overload_events += 1
                    else:
                        # Safety non droppato → overload reale
                        bus_overload_events += 1

                if safety:
                    safety_total += 1

            # Simulate metabolic mode for critical profile
            metabolic_mode = "normal"
            if profile.name == "critical_metabolic_mode_blocks_evolution":
                metabolic_mode = "critical"

            # Build state
            metrics: Dict[str, Any] = {
                "metabolic_mode": metabolic_mode,
                "global_energy_reserve": random.uniform(0.3, 1.0),
                "active_subsystems": registry.list_active(),
                "degraded_subsystems": registry.list_degraded(),
                "memory_status": "quarantined" if profile.name == "quarantined_memory_signal_blocked" else "normal",
                "evolutionary_pressure": 0.5 if profile.name == "evolutionary_resource_request" else 0.1,
                "recovery_load": 0.4 if profile.name == "recovery_priority_under_stress" else 0.1,
                "safety_failures": 0,
            }
            state = synthesizer.synthesize_state(metrics, tick=tick)

            # Run coordination
            inbox = bus._messages[:]
            decisions = coordinator.coordinate_cycle(state, inbox)

            for d in decisions:
                if d.action == "throttle" and d.target_subsystem == "evolutionary_kernel":
                    evolution_blocked += 1
                if d.action == "block" and "quarantine" in d.reason:
                    quarantine_blocked += 1

            # Lifecycle transition check
            new_state = lifecycle.classify_lifecycle_state(
                health_score=state.global_health_score,
                metabolic_mode=metabolic_mode,
                safety_risk=state.safety_risk_score,
            )
            if new_state != lifecycle.current_state:
                ok = lifecycle.transition_to(new_state)
                if not ok:
                    lifecycle_invalid += 1

            # Health snapshot
            snap = registry.snapshot()
            for _, st in snap.get("subsystems", {}).items():
                subsystem_healths.append(st.get("health_score", 1.0))

            # Bus maintenance
            bus.drop_expired_messages(tick)

        # Safety delivery check: safety messages should not be dropped
        safety_score = 1.0 if safety_total == 0 or safety_delivered >= safety_total * 0.5 else 0.5
        recovery_score = 1.0 if profile.recovery_request_rate == 0 or recovery_routed > 0 else 0.5
        resource_score = 1.0 - min(1.0, messages_dropped / max(1, messages_processed))
        coherence_score = 1.0 - min(1.0, lifecycle_invalid / max(1, profile.duration_ticks))
        health_score = sum(subsystem_healths) / max(1, len(subsystem_healths))
        lifecycle_score = 1.0 - min(1.0, lifecycle_invalid / max(1, profile.duration_ticks))
        bus_reliability = 1.0 - min(1.0, bus_overload_events / max(1, profile.duration_ticks))
        bus_overload = min(1.0, bus_overload_events / max(1, profile.duration_ticks))
        ack_failure = min(1.0, acks_missing / max(1, messages_processed))
        quarantine_leak = 0.0
        if profile.name == "quarantined_memory_signal_blocked":
            quarantine_leak = 0.0 if quarantine_blocked > 0 else 1.0

        integration_score = self._compute_integration_score(
            coherence=coherence_score,
            safety=safety_score,
            recovery=recovery_score,
            resource=resource_score,
            health=health_score,
            lifecycle=lifecycle_score,
            bus_reliability=bus_reliability,
            bus_overload=bus_overload,
            ack_failure=ack_failure,
            quarantine_leak=quarantine_leak,
        )

        verdict = self._compute_verdict(
            profile=profile,
            integration_score=integration_score,
            bus_overload=bus_overload,
            safety_score=safety_score,
            recovery_score=recovery_score,
            evolution_blocked=evolution_blocked,
            quarantine_blocked=quarantine_blocked,
            lifecycle_invalid=lifecycle_invalid,
            acks_missing=acks_missing,
        )

        return OrganismAuditResult(
            profile_name=profile.name,
            messages_processed=messages_processed,
            messages_dropped=messages_dropped,
            acknowledgements_missing=acks_missing,
            subsystem_health_score=health_score,
            integration_coherence_score=coherence_score,
            resource_coordination_score=resource_score,
            safety_coordination_score=safety_score,
            recovery_coordination_score=recovery_score,
            bus_overload_score=bus_overload,
            lifecycle_validity_score=lifecycle_score,
            organism_integration_score=integration_score,
            verdict=verdict,
            metadata={
                "evolution_blocked": evolution_blocked,
                "quarantine_blocked": quarantine_blocked,
                "lifecycle_invalid": lifecycle_invalid,
                "bus_overload_events": bus_overload_events,
            },
        )

    def _pick_message_type(self, profile: OrganismAuditProfile) -> str:
        weights = [
            (OrganismMessageType.STATE_UPDATE.value, 1.0),
            (OrganismMessageType.RISK_ALERT.value, profile.safety_alert_rate),
            (OrganismMessageType.RESOURCE_REQUEST.value, profile.resource_request_rate),
            (OrganismMessageType.RECOVERY_REQUEST.value, profile.recovery_request_rate),
            (OrganismMessageType.EVOLUTIONARY_REQUEST.value, profile.evolutionary_request_rate),
        ]
        total = sum(w for _, w in weights)
        if total == 0:
            return OrganismMessageType.STATE_UPDATE.value
        r = random.uniform(0, total)
        cumulative = 0.0
        for msg_type, w in weights:
            cumulative += w
            if r <= cumulative:
                return msg_type
        return weights[-1][0]

    @staticmethod
    def _compute_integration_score(
        coherence: float,
        safety: float,
        recovery: float,
        resource: float,
        health: float,
        lifecycle: float,
        bus_reliability: float,
        bus_overload: float,
        ack_failure: float,
        quarantine_leak: float,
    ) -> float:
        score = (
            0.20 * coherence
            + 0.18 * safety
            + 0.16 * recovery
            + 0.14 * resource
            + 0.12 * health
            + 0.10 * lifecycle
            + 0.10 * bus_reliability
            - 0.15 * bus_overload
            - 0.10 * ack_failure
            - 0.10 * quarantine_leak
        )
        return max(0.0, min(1.0, score))

    @staticmethod
    def _compute_verdict(
        profile: OrganismAuditProfile,
        integration_score: float,
        bus_overload: float,
        safety_score: float,
        recovery_score: float,
        evolution_blocked: int,
        quarantine_blocked: int,
        lifecycle_invalid: int,
        acks_missing: int,
    ) -> str:
        if profile.expected_risk_type == "BUS_OVERLOAD_DETECTED" and bus_overload > 0.3:
            return "BUS_OVERLOAD_DETECTED"
        if profile.expected_risk_type == "RECOVERY_PRIORITY_FAILURE" and recovery_score < 0.5:
            return "RECOVERY_PRIORITY_FAILURE"
        if profile.name == "critical_metabolic_mode_blocks_evolution" and evolution_blocked == 0:
            return "EVOLUTION_NOT_THROTTLED_UNDER_CRITICAL"
        if profile.name == "quarantined_memory_signal_blocked" and quarantine_blocked == 0:
            return "QUARANTINED_MEMORY_LEAK_DETECTED"
        if profile.name == "degraded_subsystem_profile" and integration_score < 0.5:
            return "SUBSYSTEM_HEALTH_DEGRADED"
        if lifecycle_invalid > 0:
            return "INVALID_LIFECYCLE_TRANSITION"
        if acks_missing > 5:
            return "ACK_FAILURE_DETECTED"
        if safety_score < 0.3:
            return "SAFETY_ROUTING_FAILURE"
        if recovery_score < 0.3:
            return "RECOVERY_PRIORITY_FAILURE"
        if integration_score >= 0.70:
            return "ORGANISM_INTEGRATION_VALIDATED"
        if integration_score >= 0.45:
            return "ORGANISM_SAFE_BUT_PASSIVE"
        return "ORGANISM_INSUFFICIENT_EVIDENCE"

    def run_audit_suite(self) -> OrganismAuditSuiteResult:
        profiles = self.build_default_profiles()
        results: List[OrganismAuditResult] = []
        total_messages = 0
        total_dropped = 0
        total_ack_missing = 0

        for profile in profiles:
            result = self.run_profile(profile)
            results.append(result)
            total_messages += result.messages_processed
            total_dropped += result.messages_dropped
            total_ack_missing += result.acknowledgements_missing

        scores = [r.organism_integration_score for r in results]
        mean_score = sum(scores) / max(1, len(scores))
        mean_safety = sum(r.safety_coordination_score for r in results) / max(1, len(results))
        mean_recovery = sum(r.recovery_coordination_score for r in results) / max(1, len(results))
        mean_resource = sum(r.resource_coordination_score for r in results) / max(1, len(results))
        mean_health = sum(r.subsystem_health_score for r in results) / max(1, len(results))
        mean_bus_overload = sum(r.bus_overload_score for r in results) / max(1, len(results))
        mean_lifecycle = sum(r.lifecycle_validity_score for r in results) / max(1, len(results))

        unsafe = sum(1 for r in results if r.verdict == "SAFETY_ROUTING_FAILURE")
        recovery_fail = sum(1 for r in results if r.verdict == "RECOVERY_PRIORITY_FAILURE")
        evo_fail = sum(1 for r in results if r.verdict == "EVOLUTION_NOT_THROTTLED_UNDER_CRITICAL")
        quarantine_fail = sum(1 for r in results if r.verdict == "QUARANTINED_MEMORY_LEAK_DETECTED")
        degraded_fail = sum(1 for r in results if r.verdict == "SUBSYSTEM_HEALTH_DEGRADED")
        overload_fail = sum(1 for r in results if r.verdict == "BUS_OVERLOAD_DETECTED")

        aggregate_verdict = "ORGANISM_INTEGRATION_VALIDATED"
        if unsafe > 0:
            aggregate_verdict = "SAFETY_ROUTING_FAILURE"
        elif recovery_fail > 0:
            aggregate_verdict = "RECOVERY_PRIORITY_FAILURE"
        elif evo_fail > 0:
            aggregate_verdict = "EVOLUTION_NOT_THROTTLED_UNDER_CRITICAL"
        elif quarantine_fail > 0:
            aggregate_verdict = "QUARANTINED_MEMORY_LEAK_DETECTED"
        elif degraded_fail > 0:
            aggregate_verdict = "SUBSYSTEM_HEALTH_DEGRADED"
        elif overload_fail > 0:
            aggregate_verdict = "BUS_OVERLOAD_DETECTED"
        elif mean_score >= 0.70:
            aggregate_verdict = "ORGANISM_INTEGRATION_VALIDATED"
        elif mean_score >= 0.45:
            aggregate_verdict = "ORGANISM_SAFE_BUT_PASSIVE"
        else:
            aggregate_verdict = "ORGANISM_INSUFFICIENT_EVIDENCE"

        proceed_to_t60 = aggregate_verdict == "ORGANISM_INTEGRATION_VALIDATED" and total_dropped == 0 and total_ack_missing == 0 and mean_score >= 0.70

        return OrganismAuditSuiteResult(
            profile_count=len(profiles),
            total_messages_processed=total_messages,
            total_messages_dropped=total_dropped,
            total_ack_missing=total_ack_missing,
            aggregate_integration_score=mean_score,
            aggregate_safety_coordination_score=mean_safety,
            aggregate_recovery_coordination_score=mean_recovery,
            aggregate_resource_coordination_score=mean_resource,
            aggregate_subsystem_health_score=mean_health,
            aggregate_bus_overload_score=mean_bus_overload,
            aggregate_lifecycle_validity_score=mean_lifecycle,
            aggregate_verdict=aggregate_verdict,
            proceed_to_t60=proceed_to_t60,
            profile_results=results,
        )

    def generate_json_report(self, suite: OrganismAuditSuiteResult) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.reports_dir / f"t59_audit_{timestamp}.json"
        path.write_text(suite.model_dump_json(indent=2), encoding="utf-8")
        return str(path)

    def generate_markdown_report(self, suite: OrganismAuditSuiteResult) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.reports_dir / f"t59_audit_{timestamp}.md"
        lines = [
            "# T59 — Organism Integration Bus Audit Report",
            f"**Date:** {timestamp}",
            f"**Aggregate Verdict:** `{suite.aggregate_verdict}`",
            f"**Proceed to T60:** {suite.proceed_to_t60}",
            "",
            "## Aggregate Metrics",
            f"- Profiles Run: {suite.profile_count}",
            f"- Total Messages: {suite.total_messages_processed}",
            f"- Messages Dropped: {suite.total_messages_dropped}",
            f"- ACK Missing: {suite.total_ack_missing}",
            f"- Integration Score: {suite.aggregate_integration_score:.4f}",
            f"- Safety Coordination: {suite.aggregate_safety_coordination_score:.4f}",
            f"- Recovery Coordination: {suite.aggregate_recovery_coordination_score:.4f}",
            f"- Resource Coordination: {suite.aggregate_resource_coordination_score:.4f}",
            f"- Subsystem Health: {suite.aggregate_subsystem_health_score:.4f}",
            f"- Bus Overload: {suite.aggregate_bus_overload_score:.4f}",
            f"- Lifecycle Validity: {suite.aggregate_lifecycle_validity_score:.4f}",
            "",
            "## Profile Results",
        ]
        for r in suite.profile_results:
            lines.append(f"### {r.profile_name}")
            lines.append(f"- Messages: {r.messages_processed}")
            lines.append(f"- Dropped: {r.messages_dropped}")
            lines.append(f"- Integration Score: {r.organism_integration_score:.4f}")
            lines.append(f"- Verdict: `{r.verdict}`")
            lines.append("")
        lines.append("---")
        lines.append("*Generated by OrganismAudit (T59)*")
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)
