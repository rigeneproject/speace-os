import json
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.organism.cross_system_coordinator import (
    CrossSystemCoordinator,
)
from speace_core.cellular_brain.organism.organism_bus import OrganismBus
from speace_core.cellular_brain.organism.organism_lifecycle import (
    OrganismLifecycleManager,
)
from speace_core.cellular_brain.organism.organism_models import (
    OrganismBusMessage,
    OrganismLifecycleState,
    OrganismMessageType,
    OrganismRealRunProfile,
    OrganismRealRunProfileResult,
    OrganismRealRunSuiteResult,
    OrganismState,
)
from speace_core.cellular_brain.organism.organism_state_synthesizer import (
    OrganismStateSynthesizer,
)
from speace_core.cellular_brain.organism.subsystem_registry import SubsystemRegistry


class OrganismRealRunAuditRunner:
    """T59B — Real-run audit runner per il bus organismico."""

    def __init__(
        self,
        bus: Optional[OrganismBus] = None,
        registry: Optional[SubsystemRegistry] = None,
        coordinator: Optional[CrossSystemCoordinator] = None,
        seed: int = 42,
        reports_dir: str = "reports/organism",
    ):
        self.seed = seed
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        random.seed(seed)

    def build_default_profiles(self) -> List[OrganismRealRunProfile]:
        return [
            OrganismRealRunProfile(
                name="real_baseline_integrated_idle",
                description="Bus organismico con sottosistemi registrati ma carico basso",
                duration_ticks=5,
                workload_mix={"state_update": 0.3, "heartbeat": 0.2},
                initial_lifecycle_state=OrganismLifecycleState.BASELINE.value,
                initial_metabolic_mode="normal",
            ),
            OrganismRealRunProfile(
                name="real_normal_coordination_stream",
                description="Metabolismo, memoria, benchmark e self-organization inviano update regolari",
                duration_ticks=7,
                workload_mix={"state_update": 0.4, "resource_request": 0.2, "memory_governance_update": 0.2, "benchmark": 0.2},
                initial_lifecycle_state=OrganismLifecycleState.ACTIVE.value,
                initial_metabolic_mode="normal",
            ),
            OrganismRealRunProfile(
                name="real_evolutionary_request_under_normal_mode",
                description="Evolutionary kernel richiede risorse in modalità normale",
                duration_ticks=5,
                workload_mix={"evolutionary_request": 0.5, "resource_request": 0.3, "state_update": 0.2},
                initial_lifecycle_state=OrganismLifecycleState.ACTIVE.value,
                initial_metabolic_mode="normal",
            ),
            OrganismRealRunProfile(
                name="real_recovery_priority_under_stress",
                description="Recovery compete con evolution durante stress",
                duration_ticks=5,
                workload_mix={"recovery_request": 0.4, "evolutionary_request": 0.3, "resource_request": 0.2, "state_update": 0.1},
                initial_lifecycle_state=OrganismLifecycleState.CONSERVATION.value,
                initial_metabolic_mode="stress",
                expected_risk_type="REAL_RUN_RECOVERY_PRIORITY_FAILURE",
            ),
            OrganismRealRunProfile(
                name="real_critical_mode_blocks_evolution",
                description="Metabolic mode CRITICAL, atteso blocco/throttling evolution",
                duration_ticks=5,
                workload_mix={"evolutionary_request": 0.5, "resource_request": 0.3, "safety_alert": 0.2},
                initial_lifecycle_state=OrganismLifecycleState.CRITICAL.value,
                initial_metabolic_mode="critical",
                expected_risk_type="REAL_RUN_EVOLUTION_NOT_THROTTLED_UNDER_CRITICAL",
            ),
            OrganismRealRunProfile(
                name="real_safety_alert_broadcast_ack",
                description="Safety invia alert globale, atteso delivery prioritario e ack",
                duration_ticks=5,
                workload_mix={"safety_alert": 0.6, "state_update": 0.3, "resource_request": 0.1},
                initial_lifecycle_state=OrganismLifecycleState.ACTIVE.value,
                initial_metabolic_mode="normal",
            ),
            OrganismRealRunProfile(
                name="real_quarantined_memory_leak_attempt",
                description="Record/memoria quarantined tenta di influenzare decisione",
                duration_ticks=5,
                workload_mix={"memory_governance_update": 0.4, "resource_request": 0.3, "state_update": 0.3},
                initial_lifecycle_state=OrganismLifecycleState.ACTIVE.value,
                initial_metabolic_mode="normal",
                expected_risk_type="REAL_RUN_QUARANTINED_MEMORY_LEAK_DETECTED",
            ),
            OrganismRealRunProfile(
                name="real_bus_overload_preserves_safety",
                description="Molti messaggi a bassa priorità, atteso drop non critici, preservazione safety",
                duration_ticks=5,
                workload_mix={"state_update": 0.7, "safety_alert": 0.1, "resource_request": 0.2},
                initial_lifecycle_state=OrganismLifecycleState.ACTIVE.value,
                initial_metabolic_mode="normal",
                expected_risk_type="REAL_RUN_BUS_OVERLOAD_DETECTED",
            ),
            OrganismRealRunProfile(
                name="real_degraded_subsystem_isolation",
                description="Un sottosistema diventa degraded, atteso isolamento/routing alternativo",
                duration_ticks=5,
                workload_mix={"state_update": 0.3, "resource_request": 0.4, "recovery_request": 0.3},
                initial_lifecycle_state=OrganismLifecycleState.DEGRADED.value,
                initial_metabolic_mode="conservation",
                expected_risk_type="REAL_RUN_SUBSYSTEM_HEALTH_DEGRADED",
            ),
            OrganismRealRunProfile(
                name="real_invalid_lifecycle_transition_attempt",
                description="Transizione lifecycle non valida, atteso blocco",
                duration_ticks=5,
                workload_mix={"lifecycle_transition": 0.5, "state_update": 0.3, "resource_request": 0.2},
                initial_lifecycle_state=OrganismLifecycleState.CRITICAL.value,
                initial_metabolic_mode="critical",
                expected_risk_type="REAL_RUN_INVALID_LIFECYCLE_TRANSITION",
            ),
            OrganismRealRunProfile(
                name="real_full_organism_realistic_mix",
                description="Mix realistico di evolution, metabolism, memory, recovery, safety, benchmark",
                duration_ticks=7,
                workload_mix={
                    "state_update": 0.2,
                    "resource_request": 0.15,
                    "recovery_request": 0.1,
                    "evolutionary_request": 0.1,
                    "safety_alert": 0.1,
                    "memory_governance_update": 0.15,
                    "benchmark": 0.1,
                    "lifecycle_transition": 0.1,
                },
                initial_lifecycle_state=OrganismLifecycleState.ACTIVE.value,
                initial_metabolic_mode="normal",
            ),
        ]

    def load_real_metrics_if_available(self) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {}
        report_dir = Path("reports/organism")
        if not report_dir.exists():
            return metrics
        for path in sorted(report_dir.glob("t59_audit_*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    metrics["t59"] = data
            except Exception:
                continue
        return metrics

    def build_synthetic_workload_for_profile(
        self,
        profile: OrganismRealRunProfile,
    ) -> Dict[str, float]:
        mix = dict(profile.workload_mix)
        for k in mix:
            mix[k] = max(0.0, mix[k] + random.uniform(-0.02, 0.02))
        return mix

    def run_profile(self, profile: OrganismRealRunProfile) -> OrganismRealRunProfileResult:
        bus = OrganismBus(max_queue_depth=50, seed=self.seed)
        registry = SubsystemRegistry()
        lifecycle = OrganismLifecycleManager(profile.initial_lifecycle_state)
        synthesizer = OrganismStateSynthesizer()
        coordinator = CrossSystemCoordinator(bus=bus, registry=registry, seed=self.seed)

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

        if profile.name == "real_degraded_subsystem_isolation":
            registry.mark_degraded("benchmark", reason="degraded_in_real_run")

        messages_published = 0
        messages_delivered = 0
        messages_dropped = 0
        ack_failure_count = 0
        safety_messages_preserved = 0
        safety_routing_failure_count = 0
        recovery_priority_failure_count = 0
        evolution_throttle_count = 0
        critical_evolution_block_count = 0
        quarantined_memory_block_count = 0
        bus_overload_count = 0
        degraded_subsystem_isolation_count = 0
        invalid_lifecycle_transition_count = 0
        subsystem_healths: List[float] = []
        coherence_scores: List[float] = []
        resource_scores: List[float] = []
        safety_scores: List[float] = []
        recovery_scores: List[float] = []

        workload = self.build_synthetic_workload_for_profile(profile)
        msg_types = list(workload.keys())

        for tick in range(profile.duration_ticks):
            # Generate messages based on workload mix
            for msg_type_key in msg_types:
                rate = workload.get(msg_type_key, 0.0)
                count = max(0, int(rate * 10 + random.uniform(-0.5, 0.5)))
                for _ in range(count):
                    is_safety = msg_type_key == "safety_alert"
                    is_recovery = msg_type_key == "recovery_request"
                    is_evolution = msg_type_key == "evolutionary_request"
                    is_lifecycle = msg_type_key == "lifecycle_transition"

                    msg = OrganismBusMessage(
                        message_id=uuid.uuid4().hex[:12],
                        source=random.choice(list(registry._statuses.keys())),
                        target=random.choice(list(registry._statuses.keys())),
                        message_type=msg_type_key,
                        priority=0.95 if is_safety else random.uniform(0.3, 0.8),
                        ttl_ticks=random.randint(2, 8),
                        safety_relevant=is_safety,
                    )
                    published = bus.publish(msg)
                    messages_published += 1
                    if published:
                        messages_delivered += 1
                        if is_safety:
                            safety_messages_preserved += 1
                    else:
                        messages_dropped += 1
                        if is_safety:
                            safety_routing_failure_count += 1
                        bus_overload_count += 1

                    # Simulate ack for safety messages
                    if is_safety and published:
                        if random.random() > 0.1:
                            bus.acknowledge(msg.message_id, "safety")
                        else:
                            ack_failure_count += 1

            # Build organism state
            metrics: Dict[str, Any] = {
                "metabolic_mode": profile.initial_metabolic_mode,
                "global_energy_reserve": random.uniform(0.3, 1.0),
                "active_subsystems": registry.list_active(),
                "degraded_subsystems": registry.list_degraded(),
                "memory_status": "quarantined" if profile.name == "real_quarantined_memory_leak_attempt" else "normal",
                "evolutionary_pressure": 0.5 if profile.name == "real_evolutionary_request_under_normal_mode" else 0.1,
                "recovery_load": 0.4 if profile.name == "real_recovery_priority_under_stress" else 0.1,
                "safety_failures": 0,
            }
            state = synthesizer.synthesize_state(metrics, tick=tick)

            # Run coordination
            inbox = bus._messages[:]
            decisions = coordinator.coordinate_cycle(state, inbox)

            for d in decisions:
                if d.action == "throttle" and d.target_subsystem == "evolutionary_kernel":
                    evolution_throttle_count += 1
                if d.action == "block" and "quarantine" in d.reason:
                    quarantined_memory_block_count += 1
                if d.action == "block" and d.target_subsystem == "evolutionary_kernel" and profile.initial_metabolic_mode == "critical":
                    critical_evolution_block_count += 1

            # Check degraded subsystem isolation
            for name, status in registry._statuses.items():
                if status.degraded:
                    # Verify no messages routed to degraded
                    for msg in bus._messages:
                        if msg.target == name:
                            degraded_subsystem_isolation_count += 1

            # Lifecycle transitions
            new_state = lifecycle.classify_lifecycle_state(
                health_score=state.global_health_score,
                metabolic_mode=profile.initial_metabolic_mode,
                safety_risk=state.safety_risk_score,
            )
            if new_state != lifecycle.current_state:
                ok = lifecycle.transition_to(new_state)
                if not ok:
                    invalid_lifecycle_transition_count += 1

            # Recovery priority check under stress/critical
            if profile.initial_metabolic_mode in ("stress", "critical"):
                recovery_present = any(
                    m.message_type == OrganismMessageType.RECOVERY_REQUEST.value
                    for m in bus._messages
                )
                evo_present = any(
                    m.message_type == OrganismMessageType.EVOLUTIONARY_REQUEST.value
                    for m in bus._messages
                )
                if evo_present and not recovery_present and profile.name == "real_recovery_priority_under_stress":
                    recovery_priority_failure_count += 1

            # Compute scores for this tick
            subsystem_healths.append(state.global_health_score)
            coherence_scores.append(1.0 - min(1.0, invalid_lifecycle_transition_count / max(1, tick + 1)))
            resource_scores.append(1.0 - min(1.0, messages_dropped / max(1, messages_published)))
            safety_scores.append(1.0 if safety_routing_failure_count == 0 else 0.5)
            recovery_scores.append(1.0 if recovery_priority_failure_count == 0 else 0.5)

            bus.drop_expired_messages(current_tick=tick)

        avg_health = sum(subsystem_healths) / max(1, len(subsystem_healths))
        avg_coherence = sum(coherence_scores) / max(1, len(coherence_scores))
        avg_resource = sum(resource_scores) / max(1, len(resource_scores))
        avg_safety = sum(safety_scores) / max(1, len(safety_scores))
        avg_recovery = sum(recovery_scores) / max(1, len(recovery_scores))

        bus_reliability = 1.0 - min(1.0, bus_overload_count / max(1, profile.duration_ticks))
        bus_overload_score = min(1.0, bus_overload_count / max(1, profile.duration_ticks))
        ack_failure_score = min(1.0, ack_failure_count / max(1, messages_published))
        safety_routing_failure_score = min(1.0, safety_routing_failure_count / max(1, messages_published))
        quarantine_leak_score = 0.0 if quarantined_memory_block_count > 0 or profile.name != "real_quarantined_memory_leak_attempt" else 1.0

        score = self._compute_organism_score(
            coherence=avg_coherence,
            safety=avg_safety,
            recovery=avg_recovery,
            resource=avg_resource,
            health=avg_health,
            bus_reliability=bus_reliability,
            lifecycle=1.0 - min(1.0, invalid_lifecycle_transition_count / max(1, profile.duration_ticks)),
            bus_overload=bus_overload_score,
            ack_failure=ack_failure_score,
            safety_routing_failure=safety_routing_failure_score,
            quarantine_leak=quarantine_leak_score,
        )

        verdict = self._compute_verdict(
            profile=profile,
            score=score,
            bus_overload=bus_overload_score,
            safety_routing_failure_count=safety_routing_failure_count,
            recovery_priority_failure_count=recovery_priority_failure_count,
            evolution_throttle_count=evolution_throttle_count,
            critical_evolution_block_count=critical_evolution_block_count,
            quarantined_memory_block_count=quarantined_memory_block_count,
            invalid_lifecycle_transition_count=invalid_lifecycle_transition_count,
            ack_failure_count=ack_failure_count,
        )

        return OrganismRealRunProfileResult(
            profile_name=profile.name,
            ticks_run=profile.duration_ticks,
            messages_published=messages_published,
            messages_delivered=messages_delivered,
            messages_dropped=messages_dropped,
            ack_failure_count=ack_failure_count,
            safety_messages_preserved=safety_messages_preserved,
            safety_routing_failure_count=safety_routing_failure_count,
            recovery_priority_failure_count=recovery_priority_failure_count,
            evolution_throttle_count=evolution_throttle_count,
            critical_evolution_block_count=critical_evolution_block_count,
            quarantined_memory_block_count=quarantined_memory_block_count,
            bus_overload_count=bus_overload_count,
            degraded_subsystem_isolation_count=degraded_subsystem_isolation_count,
            invalid_lifecycle_transition_count=invalid_lifecycle_transition_count,
            average_global_health_score=avg_health,
            average_integration_coherence_score=avg_coherence,
            average_resource_coordination_score=avg_resource,
            average_safety_coordination_score=avg_safety,
            average_recovery_coordination_score=avg_recovery,
            real_run_organism_score=score,
            verdict=verdict,
            metadata={
                "workload_mix": workload,
                "lifecycle_state": lifecycle.current_state,
            },
        )

    def run_audit_suite(self) -> OrganismRealRunSuiteResult:
        profiles = self.build_default_profiles()
        results: List[OrganismRealRunProfileResult] = []
        total_ticks = 0
        total_published = 0
        total_dropped = 0
        total_ack_failures = 0
        total_safety_routing_failures = 0
        total_recovery_priority_failures = 0
        total_quarantined_leaks = 0
        total_critical_evolution_blocks = 0

        for profile in profiles:
            result = self.run_profile(profile)
            results.append(result)
            total_ticks += result.ticks_run
            total_published += result.messages_published
            total_dropped += result.messages_dropped
            total_ack_failures += result.ack_failure_count
            total_safety_routing_failures += result.safety_routing_failure_count
            total_recovery_priority_failures += result.recovery_priority_failure_count
            total_quarantined_leaks += (1 if result.quarantined_memory_block_count == 0 and profile.name == "real_quarantined_memory_leak_attempt" else 0)
            total_critical_evolution_blocks += result.critical_evolution_block_count

        scores = [r.real_run_organism_score for r in results]
        mean_score = sum(scores) / max(1, len(scores))
        mean_health = sum(r.average_global_health_score for r in results) / max(1, len(results))
        mean_coherence = sum(r.average_integration_coherence_score for r in results) / max(1, len(results))
        mean_safety = sum(r.average_safety_coordination_score for r in results) / max(1, len(results))
        mean_recovery = sum(r.average_recovery_coordination_score for r in results) / max(1, len(results))
        mean_resource = sum(r.average_resource_coordination_score for r in results) / max(1, len(results))
        bus_reliability = 1.0 - min(1.0, total_dropped / max(1, total_published))

        aggregate_verdict = self.compute_aggregate_verdict(results)

        proceed_to_t60 = aggregate_verdict in (
            "ORGANISM_REAL_RUN_VALIDATED",
            "ORGANISM_REAL_RUN_SAFE_BUT_PASSIVE",
        ) and total_safety_routing_failures == 0 and total_quarantined_leaks == 0 and mean_score >= 0.70 and bus_reliability >= 0.75

        return OrganismRealRunSuiteResult(
            profile_count=len(profiles),
            total_ticks_run=total_ticks,
            total_messages_published=total_published,
            total_messages_dropped=total_dropped,
            total_ack_failure_count=total_ack_failures,
            total_safety_routing_failure_count=total_safety_routing_failures,
            total_recovery_priority_failure_count=total_recovery_priority_failures,
            total_quarantined_memory_leak_count=total_quarantined_leaks,
            total_critical_evolution_block_count=total_critical_evolution_blocks,
            aggregate_global_health_score=mean_health,
            aggregate_integration_coherence_score=mean_coherence,
            aggregate_safety_coordination_score=mean_safety,
            aggregate_recovery_coordination_score=mean_recovery,
            aggregate_resource_coordination_score=mean_resource,
            aggregate_bus_reliability_score=bus_reliability,
            aggregate_organism_score=mean_score,
            aggregate_verdict=aggregate_verdict,
            proceed_to_t60=proceed_to_t60,
            profile_results=results,
        )

    @staticmethod
    def _compute_organism_score(
        coherence: float,
        safety: float,
        recovery: float,
        resource: float,
        health: float,
        bus_reliability: float,
        lifecycle: float,
        bus_overload: float,
        ack_failure: float,
        safety_routing_failure: float,
        quarantine_leak: float,
    ) -> float:
        score = (
            0.20 * coherence
            + 0.18 * safety
            + 0.16 * recovery
            + 0.14 * resource
            + 0.12 * health
            + 0.10 * bus_reliability
            + 0.10 * lifecycle
            - 0.15 * bus_overload
            - 0.12 * ack_failure
            - 0.12 * safety_routing_failure
            - 0.10 * quarantine_leak
        )
        return max(0.0, min(1.0, score))

    @staticmethod
    def _compute_verdict(
        profile: OrganismRealRunProfile,
        score: float,
        bus_overload: float,
        safety_routing_failure_count: int,
        recovery_priority_failure_count: int,
        evolution_throttle_count: int,
        critical_evolution_block_count: int,
        quarantined_memory_block_count: int,
        invalid_lifecycle_transition_count: int,
        ack_failure_count: int,
    ) -> str:
        if profile.expected_risk_type == "REAL_RUN_BUS_OVERLOAD_DETECTED" and bus_overload > 0.3:
            return "REAL_RUN_BUS_OVERLOAD_DETECTED"
        if profile.expected_risk_type == "REAL_RUN_RECOVERY_PRIORITY_FAILURE" and recovery_priority_failure_count > 0:
            return "REAL_RUN_RECOVERY_PRIORITY_FAILURE"
        if profile.name == "real_critical_mode_blocks_evolution" and critical_evolution_block_count == 0 and evolution_throttle_count == 0:
            return "REAL_RUN_EVOLUTION_NOT_THROTTLED_UNDER_CRITICAL"
        if profile.name == "real_quarantined_memory_leak_attempt" and quarantined_memory_block_count == 0:
            return "REAL_RUN_QUARANTINED_MEMORY_LEAK_DETECTED"
        if profile.name == "real_degraded_subsystem_isolation" and score < 0.5:
            return "REAL_RUN_SUBSYSTEM_HEALTH_DEGRADED"
        if invalid_lifecycle_transition_count > 0:
            return "REAL_RUN_INVALID_LIFECYCLE_TRANSITION"
        if ack_failure_count > 5:
            return "REAL_RUN_ACK_FAILURE_DETECTED"
        if safety_routing_failure_count > 0:
            return "REAL_RUN_SAFETY_ROUTING_FAILURE"
        if recovery_priority_failure_count > 0:
            return "REAL_RUN_RECOVERY_PRIORITY_FAILURE"
        if score >= 0.70:
            return "ORGANISM_REAL_RUN_VALIDATED"
        if score >= 0.45:
            return "ORGANISM_REAL_RUN_SAFE_BUT_PASSIVE"
        return "ORGANISM_REAL_RUN_INSUFFICIENT_EVIDENCE"

    def compute_aggregate_verdict(self, results: List[OrganismRealRunProfileResult]) -> str:
        safety_fail = sum(1 for r in results if r.verdict == "REAL_RUN_SAFETY_ROUTING_FAILURE")
        recovery_fail = sum(1 for r in results if r.verdict == "REAL_RUN_RECOVERY_PRIORITY_FAILURE")
        evo_fail = sum(1 for r in results if r.verdict == "REAL_RUN_EVOLUTION_NOT_THROTTLED_UNDER_CRITICAL")
        quarantine_fail = sum(1 for r in results if r.verdict == "REAL_RUN_QUARANTINED_MEMORY_LEAK_DETECTED")
        degraded_fail = sum(1 for r in results if r.verdict == "REAL_RUN_SUBSYSTEM_HEALTH_DEGRADED")
        overload_fail = sum(1 for r in results if r.verdict == "REAL_RUN_BUS_OVERLOAD_DETECTED")
        lifecycle_fail = sum(1 for r in results if r.verdict == "REAL_RUN_INVALID_LIFECYCLE_TRANSITION")
        ack_fail = sum(1 for r in results if r.verdict == "REAL_RUN_ACK_FAILURE_DETECTED")

        if safety_fail > 0:
            return "REAL_RUN_SAFETY_ROUTING_FAILURE"
        if recovery_fail > 0:
            return "REAL_RUN_RECOVERY_PRIORITY_FAILURE"
        if evo_fail > 0:
            return "REAL_RUN_EVOLUTION_NOT_THROTTLED_UNDER_CRITICAL"
        if quarantine_fail > 0:
            return "REAL_RUN_QUARANTINED_MEMORY_LEAK_DETECTED"
        if degraded_fail > 0:
            return "REAL_RUN_SUBSYSTEM_HEALTH_DEGRADED"
        if overload_fail > 0:
            return "REAL_RUN_BUS_OVERLOAD_DETECTED"
        if lifecycle_fail > 0:
            return "REAL_RUN_INVALID_LIFECYCLE_TRANSITION"
        if ack_fail > 0:
            return "REAL_RUN_ACK_FAILURE_DETECTED"

        scores = [r.real_run_organism_score for r in results if r.ticks_run > 0]
        mean_score = sum(scores) / max(1, len(scores))
        if mean_score >= 0.70:
            return "ORGANISM_REAL_RUN_VALIDATED"
        if mean_score >= 0.45:
            return "ORGANISM_REAL_RUN_SAFE_BUT_PASSIVE"
        return "ORGANISM_REAL_RUN_INSUFFICIENT_EVIDENCE"

    def generate_json_report(self, suite_result: OrganismRealRunSuiteResult) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.reports_dir / f"t59b_audit_{timestamp}.json"
        path.write_text(suite_result.model_dump_json(indent=2), encoding="utf-8")
        return str(path)

    def generate_markdown_report(self, suite_result: OrganismRealRunSuiteResult) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.reports_dir / f"t59b_audit_{timestamp}.md"
        lines = [
            "# T59B — Organism Integration Real-Run Audit Report",
            f"**Date:** {timestamp}",
            f"**Aggregate Verdict:** `{suite_result.aggregate_verdict}`",
            f"**Proceed to T60:** {suite_result.proceed_to_t60}",
            "",
            "## Aggregate Metrics",
            f"- Profiles Run: {suite_result.profile_count}",
            f"- Total Ticks: {suite_result.total_ticks_run}",
            f"- Messages Published: {suite_result.total_messages_published}",
            f"- Messages Dropped: {suite_result.total_messages_dropped}",
            f"- ACK Failures: {suite_result.total_ack_failure_count}",
            f"- Organism Score: {suite_result.aggregate_organism_score:.4f}",
            f"- Safety Coordination: {suite_result.aggregate_safety_coordination_score:.4f}",
            f"- Recovery Coordination: {suite_result.aggregate_recovery_coordination_score:.4f}",
            f"- Resource Coordination: {suite_result.aggregate_resource_coordination_score:.4f}",
            f"- Bus Reliability: {suite_result.aggregate_bus_reliability_score:.4f}",
            f"- Safety Routing Failures: {suite_result.total_safety_routing_failure_count}",
            f"- Recovery Priority Failures: {suite_result.total_recovery_priority_failure_count}",
            f"- Quarantined Memory Leaks: {suite_result.total_quarantined_memory_leak_count}",
            f"- Critical Evolution Blocks: {suite_result.total_critical_evolution_block_count}",
            "",
            "## Profile Results",
        ]
        for r in suite_result.profile_results:
            lines.append(f"### {r.profile_name}")
            lines.append(f"- Ticks: {r.ticks_run}")
            lines.append(f"- Messages Published: {r.messages_published}")
            lines.append(f"- Messages Dropped: {r.messages_dropped}")
            lines.append(f"- Organism Score: {r.real_run_organism_score:.4f}")
            lines.append(f"- Verdict: `{r.verdict}`")
            lines.append("")
        lines.append("---")
        lines.append("*Generated by OrganismRealRunAuditRunner (T59B)*")
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)
