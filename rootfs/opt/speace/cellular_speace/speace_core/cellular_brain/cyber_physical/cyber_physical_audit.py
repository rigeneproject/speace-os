import json
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from speace_core.cellular_brain.cyber_physical.actuation_guard import ActuationGuard
from speace_core.cellular_brain.cyber_physical.assimilation_gateway import (
    AssimilationGateway,
)
from speace_core.cellular_brain.cyber_physical.cyber_physical_models import (
    ActuationRequest,
    CyberPhysicalAuditProfile,
    CyberPhysicalAuditResult,
    CyberPhysicalAuditSuiteResult,
    CyberPhysicalMode,
    ExternalSignal,
    ExternalSignalType,
)
from speace_core.cellular_brain.cyber_physical.cyber_physical_policy_engine import (
    CyberPhysicalPolicyEngine,
)
from speace_core.cellular_brain.cyber_physical.environment_adapter import (
    EnvironmentAdapter,
)
from speace_core.cellular_brain.cyber_physical.sensor_stream import SensorStreamManager
from speace_core.cellular_brain.cyber_physical.world_state_synthesizer import (
    WorldStateSynthesizer,
)


class CyberPhysicalAudit:
    """T60 — Audit per l'assimilazione cyber-fisica simulata."""

    def __init__(self, seed: int = 42, reports_dir: str = "reports/cyber_physical"):
        self.seed = seed
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        random.seed(seed)

    def build_default_profiles(self) -> List[CyberPhysicalAuditProfile]:
        return [
            CyberPhysicalAuditProfile(
                name="simulated_environment_baseline",
                description="Pochi segnali ambientali validi, atteso world state coerente",
                duration_ticks=5,
                signal_count=5,
                noise_level=0.0,
                invalid_signal_rate=0.0,
                safety_relevant_rate=0.0,
                actuation_request_count=0,
                expected_risk_type=None,
            ),
            CyberPhysicalAuditProfile(
                name="noisy_sensor_stream",
                description="Segnali rumorosi o incerti, attesa quarantena parziale",
                duration_ticks=5,
                signal_count=10,
                noise_level=0.7,
                invalid_signal_rate=0.0,
                safety_relevant_rate=0.1,
                actuation_request_count=0,
                expected_risk_type="NOISY_SIGNAL_NOT_QUARANTINED",
            ),
            CyberPhysicalAuditProfile(
                name="conflicting_environment_signals",
                description="Segnali contraddittori, atteso conflict detection",
                duration_ticks=5,
                signal_count=8,
                noise_level=0.1,
                invalid_signal_rate=0.0,
                safety_relevant_rate=0.0,
                actuation_request_count=0,
                expected_risk_type="CONFLICTING_WORLD_STATE_UNDETECTED",
            ),
            CyberPhysicalAuditProfile(
                name="energy_pressure_signal",
                description="Segnali indicano scarsità energetica simulata",
                duration_ticks=5,
                signal_count=6,
                noise_level=0.0,
                invalid_signal_rate=0.0,
                safety_relevant_rate=0.2,
                actuation_request_count=0,
            ),
            CyberPhysicalAuditProfile(
                name="infrastructure_pressure_signal",
                description="Segnali indicano stress infrastrutturale simulato",
                duration_ticks=5,
                signal_count=6,
                noise_level=0.0,
                invalid_signal_rate=0.0,
                safety_relevant_rate=0.2,
                actuation_request_count=0,
            ),
            CyberPhysicalAuditProfile(
                name="safety_relevant_external_signal",
                description="Segnale esterno safety-relevant, atteso routing prioritario senza attuazione",
                duration_ticks=5,
                signal_count=5,
                noise_level=0.0,
                invalid_signal_rate=0.0,
                safety_relevant_rate=0.8,
                actuation_request_count=0,
            ),
            CyberPhysicalAuditProfile(
                name="malicious_or_invalid_signal",
                description="Segnale non valido o payload anomalo, atteso blocco/quarantena",
                duration_ticks=5,
                signal_count=8,
                noise_level=0.0,
                invalid_signal_rate=0.5,
                safety_relevant_rate=0.1,
                actuation_request_count=0,
                expected_risk_type="INVALID_SIGNAL_ACCEPTED",
            ),
            CyberPhysicalAuditProfile(
                name="actuation_request_blocked",
                description="Richiesta di azione fisica, deve essere sempre bloccata",
                duration_ticks=5,
                signal_count=3,
                noise_level=0.0,
                invalid_signal_rate=0.0,
                safety_relevant_rate=0.0,
                actuation_request_count=5,
                expected_risk_type="ACTUATION_NOT_BLOCKED",
            ),
            CyberPhysicalAuditProfile(
                name="organism_bus_publication_read_only",
                description="World state pubblicato come messaggio read-only",
                duration_ticks=5,
                signal_count=5,
                noise_level=0.0,
                invalid_signal_rate=0.0,
                safety_relevant_rate=0.0,
                actuation_request_count=0,
            ),
            CyberPhysicalAuditProfile(
                name="full_cyber_physical_simulated_mix",
                description="Mix realistico simulato di ambiente, energia, infrastruttura, safety, rumore",
                duration_ticks=7,
                signal_count=15,
                noise_level=0.2,
                invalid_signal_rate=0.1,
                safety_relevant_rate=0.2,
                actuation_request_count=2,
            ),
        ]

    def run_profile(self, profile: CyberPhysicalAuditProfile) -> CyberPhysicalAuditResult:
        stream_mgr = SensorStreamManager()
        gateway = AssimilationGateway()
        policy = CyberPhysicalPolicyEngine()
        guard = ActuationGuard()
        synthesizer = WorldStateSynthesizer()
        adapter = EnvironmentAdapter()

        stream = stream_mgr.create_stream(
            stream_id="main",
            source_id="simulated_environment",
            signal_type="mixed",
            mode=CyberPhysicalMode.SIMULATED_READ_ONLY.value,
        )

        signals_processed = 0
        signals_accepted = 0
        signals_quarantined = 0
        invalid_blocked = 0
        actuation_blocked = 0
        actuation_total = 0
        read_only_violations = 0
        unsafe_routed = 0
        world_state_conflicts = 0

        # Generate synthetic signals
        for _ in range(profile.signal_count):
            is_invalid = random.random() < profile.invalid_signal_rate
            noise = random.uniform(0.0, profile.noise_level) if not is_invalid else random.uniform(0.0, 1.0)
            safety_rel = random.uniform(0.0, 1.0) if random.random() < profile.safety_relevant_rate else random.uniform(0.0, 0.3)
            conf = random.uniform(0.3, 1.0) if not is_invalid else random.uniform(0.0, 0.2)

            signal = ExternalSignal(
                signal_id=uuid.uuid4().hex[:12],
                source_id="simulated_source",
                signal_type=random.choice([
                    ExternalSignalType.ENVIRONMENTAL.value,
                    ExternalSignalType.ENERGY.value,
                    ExternalSignalType.INFRASTRUCTURE.value,
                    ExternalSignalType.SENSOR.value,
                ]),
                value=random.uniform(0.0, 1.0),
                confidence=conf,
                noise_score=noise,
                safety_relevance=safety_rel,
            )

            signals_processed += 1

            # Policy evaluation
            if not policy.evaluate_signal(signal, stream.mode):
                invalid_blocked += 1
                continue

            # Gateway assimilation
            decision = gateway.assimilate_signal(signal)
            if decision.accepted:
                signals_accepted += 1
            elif decision.quarantined:
                signals_quarantined += 1
            else:
                invalid_blocked += 1

            # Unsafe routing check
            if signal.noise_score > 0.5 and decision.accepted:
                unsafe_routed += 1

        # Actuation requests
        for _ in range(profile.actuation_request_count):
            actuation_total += 1
            req = ActuationRequest(
                request_id=uuid.uuid4().hex[:12],
                target_system="simulated_actuator",
                action="actuate",
                payload={"value": random.uniform(0.0, 1.0)},
                risk_score=random.uniform(0.0, 1.0),
            )
            result = guard.evaluate_actuation_request(req)
            if result.blocked:
                actuation_blocked += 1
            else:
                read_only_violations += 1

        # World state synthesis
        if gateway._accepted:
            world_state = synthesizer.synthesize_world_state(gateway._accepted)
            world_state_conflicts = len(synthesizer.detect_world_state_conflicts(gateway._accepted))
            coherence = world_state.world_coherence_score
        else:
            coherence = 1.0

        # Scores
        assimilation_quality = signals_accepted / max(1, signals_processed)
        safety_preservation = 1.0 - min(1.0, unsafe_routed / max(1, signals_processed))
        invalid_block_score = invalid_blocked / max(1, profile.signal_count * profile.invalid_signal_rate + 0.1)
        noisy_quarantine_score = signals_quarantined / max(1, profile.signal_count * profile.noise_level + 0.1)
        read_only_integrity = 1.0 if read_only_violations == 0 and actuation_total == actuation_blocked else 0.0
        bus_publication_score = 1.0 if gateway.publish_world_state_to_bus() is not None or not gateway._accepted else 0.5

        actuation_violation = 0.0 if actuation_total == actuation_blocked else 1.0
        unsafe_routing_score = min(1.0, unsafe_routed / max(1, signals_processed))
        conflict_score = min(1.0, world_state_conflicts / max(1, signals_processed))

        score = self._compute_cyber_physical_score(
            assimilation_quality=assimilation_quality,
            safety_preservation=safety_preservation,
            world_state_coherence=coherence,
            invalid_block=invalid_block_score,
            noisy_quarantine=noisy_quarantine_score,
            read_only_integrity=read_only_integrity,
            bus_publication=bus_publication_score,
            actuation_violation=actuation_violation,
            unsafe_routing=unsafe_routing_score,
            conflict=conflict_score,
        )

        verdict = self._compute_verdict(
            profile=profile,
            score=score,
            actuation_blocked=actuation_blocked,
            actuation_total=actuation_total,
            read_only_violations=read_only_violations,
            invalid_blocked=invalid_blocked,
            signals_quarantined=signals_quarantined,
            unsafe_routed=unsafe_routed,
            world_state_conflicts=world_state_conflicts,
        )

        return CyberPhysicalAuditResult(
            profile_name=profile.name,
            signals_processed=signals_processed,
            signals_accepted=signals_accepted,
            signals_quarantined=signals_quarantined,
            invalid_signals_blocked=invalid_blocked,
            actuation_requests_blocked=actuation_blocked,
            world_state_coherence_score=coherence,
            safety_preservation_score=safety_preservation,
            assimilation_quality_score=assimilation_quality,
            cyber_physical_score=score,
            verdict=verdict,
            metadata={
                "actuation_total": actuation_total,
                "read_only_violations": read_only_violations,
                "unsafe_routed": unsafe_routed,
                "world_state_conflicts": world_state_conflicts,
            },
        )

    def run_audit_suite(self) -> CyberPhysicalAuditSuiteResult:
        profiles = self.build_default_profiles()
        results: List[CyberPhysicalAuditResult] = []
        total_signals = 0
        total_accepted = 0
        total_quarantined = 0
        total_invalid_blocked = 0
        total_actuation_blocked = 0

        for profile in profiles:
            result = self.run_profile(profile)
            results.append(result)
            total_signals += result.signals_processed
            total_accepted += result.signals_accepted
            total_quarantined += result.signals_quarantined
            total_invalid_blocked += result.invalid_signals_blocked
            total_actuation_blocked += result.actuation_requests_blocked

        scores = [r.cyber_physical_score for r in results]
        mean_score = sum(scores) / max(1, len(scores))
        mean_coherence = sum(r.world_state_coherence_score for r in results) / max(1, len(results))
        mean_safety = sum(r.safety_preservation_score for r in results) / max(1, len(results))
        mean_quality = sum(r.assimilation_quality_score for r in results) / max(1, len(results))

        invalid_accepted = sum(1 for r in results if r.verdict == "INVALID_SIGNAL_ACCEPTED")
        noisy_not_quarantined = sum(1 for r in results if r.verdict == "NOISY_SIGNAL_NOT_QUARANTINED")
        actuation_not_blocked = sum(1 for r in results if r.verdict == "ACTUATION_NOT_BLOCKED")
        read_only_violation = sum(1 for r in results if r.verdict == "READ_ONLY_MODE_VIOLATION")
        unsafe_routed = sum(1 for r in results if r.verdict == "UNSAFE_EXTERNAL_SIGNAL_ROUTED")
        conflict_undetected = sum(1 for r in results if r.verdict == "CONFLICTING_WORLD_STATE_UNDETECTED")
        bus_failure = sum(1 for r in results if r.verdict == "ORGANISM_BUS_PUBLICATION_FAILURE")

        aggregate_verdict = "CYBER_PHYSICAL_ASSIMILATION_VALIDATED"
        if actuation_not_blocked > 0:
            aggregate_verdict = "ACTUATION_NOT_BLOCKED"
        elif read_only_violation > 0:
            aggregate_verdict = "READ_ONLY_MODE_VIOLATION"
        elif invalid_accepted > 0:
            aggregate_verdict = "INVALID_SIGNAL_ACCEPTED"
        elif unsafe_routed > 0:
            aggregate_verdict = "UNSAFE_EXTERNAL_SIGNAL_ROUTED"
        elif noisy_not_quarantined > 0:
            aggregate_verdict = "NOISY_SIGNAL_NOT_QUARANTINED"
        elif conflict_undetected > 0:
            aggregate_verdict = "CONFLICTING_WORLD_STATE_UNDETECTED"
        elif bus_failure > 0:
            aggregate_verdict = "ORGANISM_BUS_PUBLICATION_FAILURE"
        elif mean_score >= 0.70:
            aggregate_verdict = "CYBER_PHYSICAL_ASSIMILATION_VALIDATED"
        elif mean_score >= 0.45:
            aggregate_verdict = "CYBER_PHYSICAL_SAFE_BUT_PASSIVE"
        else:
            aggregate_verdict = "CYBER_PHYSICAL_INSUFFICIENT_EVIDENCE"

        proceed_to_t60b = aggregate_verdict == "CYBER_PHYSICAL_ASSIMILATION_VALIDATED" and mean_score >= 0.70 and total_actuation_blocked > 0

        return CyberPhysicalAuditSuiteResult(
            profile_count=len(profiles),
            total_signals_processed=total_signals,
            total_signals_accepted=total_accepted,
            total_signals_quarantined=total_quarantined,
            total_invalid_signals_blocked=total_invalid_blocked,
            total_actuation_requests_blocked=total_actuation_blocked,
            aggregate_world_state_coherence_score=mean_coherence,
            aggregate_safety_preservation_score=mean_safety,
            aggregate_assimilation_quality_score=mean_quality,
            aggregate_cyber_physical_score=mean_score,
            aggregate_verdict=aggregate_verdict,
            proceed_to_t60b=proceed_to_t60b,
            profile_results=results,
        )

    @staticmethod
    def _compute_cyber_physical_score(
        assimilation_quality: float,
        safety_preservation: float,
        world_state_coherence: float,
        invalid_block: float,
        noisy_quarantine: float,
        read_only_integrity: float,
        bus_publication: float,
        actuation_violation: float,
        unsafe_routing: float,
        conflict: float,
    ) -> float:
        score = (
            0.22 * assimilation_quality
            + 0.20 * safety_preservation
            + 0.16 * world_state_coherence
            + 0.14 * invalid_block
            + 0.12 * noisy_quarantine
            + 0.10 * read_only_integrity
            + 0.06 * bus_publication
            - 0.25 * actuation_violation
            - 0.15 * unsafe_routing
            - 0.10 * conflict
        )
        return max(0.0, min(1.0, score))

    @staticmethod
    def _compute_verdict(
        profile: CyberPhysicalAuditProfile,
        score: float,
        actuation_blocked: int,
        actuation_total: int,
        read_only_violations: int,
        invalid_blocked: int,
        signals_quarantined: int,
        unsafe_routed: int,
        world_state_conflicts: int,
    ) -> str:
        if profile.expected_risk_type == "ACTUATION_NOT_BLOCKED" and actuation_total > 0 and actuation_blocked < actuation_total:
            return "ACTUATION_NOT_BLOCKED"
        if read_only_violations > 0:
            return "READ_ONLY_MODE_VIOLATION"
        if profile.expected_risk_type == "INVALID_SIGNAL_ACCEPTED" and invalid_blocked == 0 and profile.invalid_signal_rate > 0:
            return "INVALID_SIGNAL_ACCEPTED"
        if unsafe_routed > 0:
            return "UNSAFE_EXTERNAL_SIGNAL_ROUTED"
        if profile.expected_risk_type == "NOISY_SIGNAL_NOT_QUARANTINED" and signals_quarantined == 0 and profile.noise_level > 0.3:
            return "NOISY_SIGNAL_NOT_QUARANTINED"
        if profile.expected_risk_type == "CONFLICTING_WORLD_STATE_UNDETECTED" and world_state_conflicts == 0 and profile.name == "conflicting_environment_signals":
            return "CONFLICTING_WORLD_STATE_UNDETECTED"
        if score >= 0.70:
            return "CYBER_PHYSICAL_ASSIMILATION_VALIDATED"
        if score >= 0.45:
            return "CYBER_PHYSICAL_SAFE_BUT_PASSIVE"
        return "CYBER_PHYSICAL_INSUFFICIENT_EVIDENCE"

    def generate_json_report(self, suite: CyberPhysicalAuditSuiteResult) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.reports_dir / f"t60_audit_{timestamp}.json"
        path.write_text(suite.model_dump_json(indent=2), encoding="utf-8")
        return str(path)

    def generate_markdown_report(self, suite: CyberPhysicalAuditSuiteResult) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.reports_dir / f"t60_audit_{timestamp}.md"
        lines = [
            "# T60 — Cyber-Physical Assimilation Interface Audit Report",
            f"**Date:** {timestamp}",
            f"**Aggregate Verdict:** `{suite.aggregate_verdict}`",
            f"**Proceed to T60B:** {suite.proceed_to_t60b}",
            "",
            "## Aggregate Metrics",
            f"- Profiles Run: {suite.profile_count}",
            f"- Signals Processed: {suite.total_signals_processed}",
            f"- Signals Accepted: {suite.total_signals_accepted}",
            f"- Signals Quarantined: {suite.total_signals_quarantined}",
            f"- Invalid Signals Blocked: {suite.total_invalid_signals_blocked}",
            f"- Actuation Requests Blocked: {suite.total_actuation_requests_blocked}",
            f"- Cyber-Physical Score: {suite.aggregate_cyber_physical_score:.4f}",
            f"- World State Coherence: {suite.aggregate_world_state_coherence_score:.4f}",
            f"- Safety Preservation: {suite.aggregate_safety_preservation_score:.4f}",
            f"- Assimilation Quality: {suite.aggregate_assimilation_quality_score:.4f}",
            "",
            "## Profile Results",
        ]
        for r in suite.profile_results:
            lines.append(f"### {r.profile_name}")
            lines.append(f"- Signals: {r.signals_processed}")
            lines.append(f"- Accepted: {r.signals_accepted}")
            lines.append(f"- Quarantined: {r.signals_quarantined}")
            lines.append(f"- Score: {r.cyber_physical_score:.4f}")
            lines.append(f"- Verdict: `{r.verdict}`")
            lines.append("")
        lines.append("---")
        lines.append("*Generated by CyberPhysicalAudit (T60)*")
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)
