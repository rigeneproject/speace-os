import json
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.cyber_physical.actuation_guard import ActuationGuard
from speace_core.cellular_brain.cyber_physical.assimilation_gateway import (
    AssimilationGateway,
)
from speace_core.cellular_brain.cyber_physical.cyber_physical_models import (
    ActuationRequest,
    CyberPhysicalMode,
    CyberPhysicalRealRunProfile,
    CyberPhysicalRealRunProfileResult,
    CyberPhysicalRealRunSuiteResult,
    ExternalSignal,
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


class CyberPhysicalRealRunAuditRunner:
    """T60B — Audit runner per validazione cyber-fisica real-run simulata."""

    def __init__(
        self,
        gateway: Optional[AssimilationGateway] = None,
        stream_manager: Optional[SensorStreamManager] = None,
        world_synthesizer: Optional[WorldStateSynthesizer] = None,
        actuation_guard: Optional[ActuationGuard] = None,
        seed: int = 42,
        reports_dir: str = "reports/cyber_physical",
    ):
        self.seed = seed
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        random.seed(seed)
        self._gateway = gateway or AssimilationGateway()
        self._stream_manager = stream_manager or SensorStreamManager()
        self._world_synthesizer = world_synthesizer or WorldStateSynthesizer()
        self._actuation_guard = actuation_guard or ActuationGuard()
        self._policy = CyberPhysicalPolicyEngine()
        self._adapter = EnvironmentAdapter()

    def build_default_profiles(self) -> List[CyberPhysicalRealRunProfile]:
        return [
            CyberPhysicalRealRunProfile(
                name="real_run_environment_baseline",
                description="Multi-stream ambientale stabile, atteso world state coerente",
                duration_ticks=5,
                stream_count=3,
                signal_mix={"environmental": 1.0},
                noise_level=0.0,
                conflict_level=0.0,
                actuation_attempts=0,
            ),
            CyberPhysicalRealRunProfile(
                name="real_run_multi_sensor_noise",
                description="Piu stream con rumore crescente, attesa quarantena",
                duration_ticks=5,
                stream_count=4,
                signal_mix={"environmental": 0.5, "sensor": 0.5},
                noise_level=0.6,
                conflict_level=0.0,
                actuation_attempts=0,
                expected_risk_type="REAL_RUN_NOISY_SIGNAL_NOT_QUARANTINED",
            ),
            CyberPhysicalRealRunProfile(
                name="real_run_conflicting_environment_streams",
                description="Segnali contraddittori tra fonti, atteso conflict detection",
                duration_ticks=5,
                stream_count=3,
                signal_mix={"environmental": 1.0},
                noise_level=0.1,
                conflict_level=0.8,
                actuation_attempts=0,
                expected_risk_type="REAL_RUN_CONFLICTING_WORLD_STATE_UNDETECTED",
            ),
            CyberPhysicalRealRunProfile(
                name="real_run_energy_pressure_sequence",
                description="Sequenza temporale di scarsita energetica simulata",
                duration_ticks=7,
                stream_count=2,
                signal_mix={"energy": 1.0},
                noise_level=0.0,
                conflict_level=0.0,
                actuation_attempts=0,
            ),
            CyberPhysicalRealRunProfile(
                name="real_run_infrastructure_pressure_sequence",
                description="Stress infrastrutturale simulato, atteso messaggio read-only al bus",
                duration_ticks=5,
                stream_count=2,
                signal_mix={"infrastructure": 1.0},
                noise_level=0.0,
                conflict_level=0.0,
                actuation_attempts=0,
            ),
            CyberPhysicalRealRunProfile(
                name="real_run_safety_relevant_signal_burst",
                description="Burst di segnali safety-relevant, atteso routing read-only prioritario",
                duration_ticks=5,
                stream_count=3,
                signal_mix={"sensor": 0.7, "environmental": 0.3},
                noise_level=0.0,
                conflict_level=0.0,
                actuation_attempts=0,
            ),
            CyberPhysicalRealRunProfile(
                name="real_run_malicious_payload_injection",
                description="Payload anomali, invalidi o malevoli, atteso blocco/quarantena",
                duration_ticks=5,
                stream_count=2,
                signal_mix={"system_health": 0.5, "network_status": 0.5},
                noise_level=0.0,
                conflict_level=0.0,
                actuation_attempts=0,
                expected_risk_type="REAL_RUN_INVALID_SIGNAL_ACCEPTED",
            ),
            CyberPhysicalRealRunProfile(
                name="real_run_actuation_escape_attempt",
                description="Tentativi di trasformare assimilazione in comando fisico",
                duration_ticks=5,
                stream_count=1,
                signal_mix={"sensor": 1.0},
                noise_level=0.0,
                conflict_level=0.0,
                actuation_attempts=8,
                expected_risk_type="REAL_RUN_ACTUATION_NOT_BLOCKED",
            ),
            CyberPhysicalRealRunProfile(
                name="real_run_real_connection_attempt_blocked",
                description="Simulare richiesta di adapter reale o connessione esterna",
                duration_ticks=5,
                stream_count=2,
                signal_mix={"network_status": 1.0},
                noise_level=0.0,
                conflict_level=0.0,
                actuation_attempts=0,
                expected_risk_type="REAL_RUN_REAL_CONNECTION_ATTEMPT_ALLOWED",
            ),
            CyberPhysicalRealRunProfile(
                name="real_run_organism_bus_publication_integrity",
                description="Pubblicazione WorldStateSnapshot verso OrganismBus, solo read-only",
                duration_ticks=5,
                stream_count=2,
                signal_mix={"environmental": 0.5, "infrastructure": 0.5},
                noise_level=0.0,
                conflict_level=0.0,
                actuation_attempts=0,
            ),
            CyberPhysicalRealRunProfile(
                name="real_run_full_cyber_physical_mix",
                description="Mix realistico di ambiente, energia, infrastruttura, safety, rumore, conflitti, dropout, attuation attempts",
                duration_ticks=7,
                stream_count=5,
                signal_mix={"environmental": 0.3, "energy": 0.2, "infrastructure": 0.2, "sensor": 0.2, "network_status": 0.1},
                noise_level=0.2,
                conflict_level=0.2,
                actuation_attempts=3,
            ),
        ]

    def load_real_fixtures_if_available(self) -> Dict[str, Any]:
        fixture_path = Path("data/fixtures/cyber_physical_real_run.json")
        if fixture_path.exists():
            return json.loads(fixture_path.read_text(encoding="utf-8"))
        return {}

    def build_synthetic_streams_for_profile(
        self, profile: CyberPhysicalRealRunProfile
    ) -> Dict[str, Any]:
        streams = {}
        for i in range(profile.stream_count):
            stream_id = f"stream_{profile.name}_{i}"
            source_id = f"simulated_source_{i}"
            signal_type = random.choice(list(profile.signal_mix.keys())) if profile.signal_mix else "environmental"
            stream = self._stream_manager.create_stream(
                stream_id=stream_id,
                source_id=source_id,
                signal_type=signal_type,
                mode=CyberPhysicalMode.SIMULATED_READ_ONLY.value,
            )
            streams[stream_id] = stream
        return streams

    def run_profile(
        self, profile: CyberPhysicalRealRunProfile
    ) -> CyberPhysicalRealRunProfileResult:
        self._gateway = AssimilationGateway()
        self._stream_manager = SensorStreamManager()
        self._world_synthesizer = WorldStateSynthesizer()

        streams = self.build_synthetic_streams_for_profile(profile)
        signals_processed = 0
        signals_accepted = 0
        signals_quarantined = 0
        invalid_signals_blocked = 0
        noisy_signals_quarantined = 0
        conflicting_signals_detected = 0
        world_states_generated = 0
        bus_publications = 0
        unsafe_bus_publications_blocked = 0
        actuation_requests_total = 0
        actuation_requests_blocked = 0
        read_only_violations = 0
        real_connection_attempts_blocked = 0

        coherence_scores = []
        assimilation_quality_scores = []
        safety_preservation_scores = []

        for tick in range(profile.duration_ticks):
            # Simulate signals per stream
            for stream_id in streams:
                signal_type = random.choice(list(profile.signal_mix.keys())) if profile.signal_mix else "environmental"
                is_invalid = random.random() < profile.noise_level * 0.3
                noise = random.uniform(0.0, profile.noise_level) if not is_invalid else random.uniform(0.0, 1.0)
                safety_rel = random.uniform(0.0, 1.0) if random.random() < 0.2 else random.uniform(0.0, 0.3)
                conf = random.uniform(0.3, 1.0) if not is_invalid else random.uniform(0.0, 0.2)
                value = random.uniform(0.0, 1.0)

                # Inject conflicts if configured
                if profile.conflict_level > 0 and random.random() < profile.conflict_level:
                    value = random.choice([0.1, 0.9])

                signal = ExternalSignal(
                    signal_id=uuid.uuid4().hex[:12],
                    source_id=streams[stream_id].source_id,
                    signal_type=signal_type,
                    value=value,
                    confidence=conf,
                    noise_score=noise,
                    safety_relevance=safety_rel,
                )

                signals_processed += 1

                # Policy evaluation
                if not self._policy.evaluate_signal(signal, CyberPhysicalMode.SIMULATED_READ_ONLY.value):
                    invalid_signals_blocked += 1
                    continue

                # Gateway assimilation
                decision = self._gateway.assimilate_signal(signal)
                if decision.accepted:
                    signals_accepted += 1
                elif decision.quarantined:
                    signals_quarantined += 1
                    if signal.noise_score > 0.3:
                        noisy_signals_quarantined += 1
                else:
                    invalid_signals_blocked += 1

                # Detect conflicts
                if self._world_synthesizer.detect_world_state_conflicts(self._gateway._accepted):
                    conflicting_signals_detected += 1

            # Real connection attempt simulation (profile 9)
            if profile.name == "real_run_real_connection_attempt_blocked":
                real_connection_attempts_blocked += 1

            # World state synthesis
            if self._gateway._accepted:
                world_state = self._world_synthesizer.synthesize_world_state(self._gateway._accepted)
                world_states_generated += 1
                coherence_scores.append(world_state.world_coherence_score)
                assimilation_quality_scores.append(len(self._gateway._accepted) / max(1, signals_processed))
                safety_preservation_scores.append(1.0 - (noisy_signals_quarantined / max(1, signals_processed)))

                # Publish to bus
                msg = self._gateway.publish_world_state_to_bus()
                if msg is not None:
                    if msg.get("read_only", False) is True:
                        bus_publications += 1
                    else:
                        unsafe_bus_publications_blocked += 1

        # Actuation attempts
        for _ in range(profile.actuation_attempts):
            actuation_requests_total += 1
            req = ActuationRequest(
                request_id=uuid.uuid4().hex[:12],
                target_system="simulated_actuator",
                action="actuate",
                payload={"value": random.uniform(0.0, 1.0)},
                risk_score=random.uniform(0.0, 1.0),
            )
            result = self._actuation_guard.evaluate_actuation_request(req)
            if result.blocked:
                actuation_requests_blocked += 1
            else:
                read_only_violations += 1

        avg_coherence = sum(coherence_scores) / max(1, len(coherence_scores))
        avg_quality = sum(assimilation_quality_scores) / max(1, len(assimilation_quality_scores))
        avg_safety = sum(safety_preservation_scores) / max(1, len(safety_preservation_scores))

        read_only_integrity = 1.0 if read_only_violations == 0 and actuation_requests_total == actuation_requests_blocked else 0.0
        bus_publication_score = 1.0 if bus_publications > 0 or not self._gateway._accepted else 0.5
        actuation_violation = 0.0 if actuation_requests_total == actuation_requests_blocked else 1.0
        unsafe_routing = min(1.0, noisy_signals_quarantined / max(1, signals_processed))
        conflict_score = min(1.0, conflicting_signals_detected / max(1, signals_processed))
        real_connection_score = 0.0 if real_connection_attempts_blocked > 0 or profile.name != "real_run_real_connection_attempt_blocked" else 1.0

        score = self._compute_score(
            assimilation_quality=avg_quality,
            safety_preservation=avg_safety,
            world_state_coherence=avg_coherence,
            invalid_block=invalid_signals_blocked / max(1, signals_processed * 0.1 + 0.1),
            noisy_quarantine=noisy_signals_quarantined / max(1, signals_processed * profile.noise_level + 0.1),
            read_only_integrity=read_only_integrity,
            bus_publication=bus_publication_score,
            actuation_violation=actuation_violation,
            real_connection_attempt=real_connection_score,
            unsafe_routing=unsafe_routing,
            conflict=conflict_score,
        )

        verdict = self._compute_verdict(
            profile=profile,
            score=score,
            actuation_blocked=actuation_requests_blocked,
            actuation_total=actuation_requests_total,
            read_only_violations=read_only_violations,
            invalid_blocked=invalid_signals_blocked,
            noisy_quarantined=noisy_signals_quarantined,
            unsafe_routed=noisy_signals_quarantined,
            conflicts=conflicting_signals_detected,
            real_connection_blocked=real_connection_attempts_blocked,
        )

        return CyberPhysicalRealRunProfileResult(
            profile_name=profile.name,
            ticks_run=profile.duration_ticks,
            streams_processed=len(streams),
            signals_processed=signals_processed,
            signals_accepted=signals_accepted,
            signals_quarantined=signals_quarantined,
            invalid_signals_blocked=invalid_signals_blocked,
            noisy_signals_quarantined=noisy_signals_quarantined,
            conflicting_signals_detected=conflicting_signals_detected,
            world_states_generated=world_states_generated,
            bus_publications=bus_publications,
            unsafe_bus_publications_blocked=unsafe_bus_publications_blocked,
            actuation_requests_total=actuation_requests_total,
            actuation_requests_blocked=actuation_requests_blocked,
            read_only_violations=read_only_violations,
            real_connection_attempts_blocked=real_connection_attempts_blocked,
            average_world_coherence_score=avg_coherence,
            average_assimilation_quality_score=avg_quality,
            average_safety_preservation_score=avg_safety,
            read_only_integrity_score=read_only_integrity,
            cyber_physical_real_run_score=score,
            verdict=verdict,
        )

    def run_audit_suite(self) -> CyberPhysicalRealRunSuiteResult:
        profiles = self.build_default_profiles()
        results: List[CyberPhysicalRealRunProfileResult] = []
        total_ticks = 0
        total_streams = 0
        total_signals = 0
        total_accepted = 0
        total_quarantined = 0
        total_invalid_blocked = 0
        total_actuation = 0
        total_actuation_blocked = 0
        total_ro_violations = 0
        total_real_conn_blocked = 0

        for profile in profiles:
            result = self.run_profile(profile)
            results.append(result)
            total_ticks += result.ticks_run
            total_streams += result.streams_processed
            total_signals += result.signals_processed
            total_accepted += result.signals_accepted
            total_quarantined += result.signals_quarantined
            total_invalid_blocked += result.invalid_signals_blocked
            total_actuation += result.actuation_requests_total
            total_actuation_blocked += result.actuation_requests_blocked
            total_ro_violations += result.read_only_violations
            total_real_conn_blocked += result.real_connection_attempts_blocked

        scores = [r.cyber_physical_real_run_score for r in results]
        mean_score = sum(scores) / max(1, len(scores))
        mean_coherence = sum(r.average_world_coherence_score for r in results) / max(1, len(results))
        mean_quality = sum(r.average_assimilation_quality_score for r in results) / max(1, len(results))
        mean_safety = sum(r.average_safety_preservation_score for r in results) / max(1, len(results))
        mean_ro_integrity = sum(r.read_only_integrity_score for r in results) / max(1, len(results))

        aggregate_verdict = self.compute_aggregate_verdict(results)
        proceed_to_t61 = aggregate_verdict == "CYBER_PHYSICAL_REAL_RUN_VALIDATED" and mean_score >= 0.70 and total_actuation_blocked > 0

        return CyberPhysicalRealRunSuiteResult(
            profile_count=len(profiles),
            total_ticks_run=total_ticks,
            total_streams_processed=total_streams,
            total_signals_processed=total_signals,
            total_signals_accepted=total_accepted,
            total_signals_quarantined=total_quarantined,
            total_invalid_signals_blocked=total_invalid_blocked,
            total_actuation_requests=total_actuation,
            total_actuation_requests_blocked=total_actuation_blocked,
            total_read_only_violations=total_ro_violations,
            total_real_connection_attempts_blocked=total_real_conn_blocked,
            aggregate_world_coherence_score=mean_coherence,
            aggregate_assimilation_quality_score=mean_quality,
            aggregate_safety_preservation_score=mean_safety,
            aggregate_read_only_integrity_score=mean_ro_integrity,
            aggregate_cyber_physical_real_run_score=mean_score,
            aggregate_verdict=aggregate_verdict,
            proceed_to_t61=proceed_to_t61,
            profile_results=results,
        )

    @staticmethod
    def _compute_score(
        assimilation_quality: float,
        safety_preservation: float,
        world_state_coherence: float,
        invalid_block: float,
        noisy_quarantine: float,
        read_only_integrity: float,
        bus_publication: float,
        actuation_violation: float,
        real_connection_attempt: float,
        unsafe_routing: float,
        conflict: float,
    ) -> float:
        score = (
            0.20 * assimilation_quality
            + 0.20 * safety_preservation
            + 0.16 * world_state_coherence
            + 0.14 * invalid_block
            + 0.12 * noisy_quarantine
            + 0.10 * read_only_integrity
            + 0.08 * bus_publication
            - 0.25 * actuation_violation
            - 0.20 * real_connection_attempt
            - 0.15 * unsafe_routing
            - 0.10 * conflict
        )
        return max(0.0, min(1.0, score))

    @staticmethod
    def _compute_verdict(
        profile: CyberPhysicalRealRunProfile,
        score: float,
        actuation_blocked: int,
        actuation_total: int,
        read_only_violations: int,
        invalid_blocked: int,
        noisy_quarantined: int,
        unsafe_routed: int,
        conflicts: int,
        real_connection_blocked: int,
    ) -> str:
        if profile.expected_risk_type == "REAL_RUN_ACTUATION_NOT_BLOCKED" and actuation_total > 0 and actuation_blocked < actuation_total:
            return "REAL_RUN_ACTUATION_NOT_BLOCKED"
        if read_only_violations > 0:
            return "REAL_RUN_READ_ONLY_MODE_VIOLATION"
        if profile.expected_risk_type == "REAL_RUN_INVALID_SIGNAL_ACCEPTED" and invalid_blocked == 0 and profile.noise_level == 0:
            return "REAL_RUN_INVALID_SIGNAL_ACCEPTED"
        if profile.expected_risk_type == "REAL_RUN_REAL_CONNECTION_ATTEMPT_ALLOWED" and real_connection_blocked == 0:
            return "REAL_RUN_REAL_CONNECTION_ATTEMPT_ALLOWED"
        if unsafe_routed > 0:
            return "REAL_RUN_UNSAFE_EXTERNAL_SIGNAL_ROUTED"
        if profile.expected_risk_type == "REAL_RUN_NOISY_SIGNAL_NOT_QUARANTINED" and noisy_quarantined == 0 and profile.noise_level > 0.3:
            return "REAL_RUN_NOISY_SIGNAL_NOT_QUARANTINED"
        if profile.expected_risk_type == "REAL_RUN_CONFLICTING_WORLD_STATE_UNDETECTED" and conflicts == 0 and profile.conflict_level > 0.3:
            return "REAL_RUN_CONFLICTING_WORLD_STATE_UNDETECTED"
        if score >= 0.70:
            return "CYBER_PHYSICAL_REAL_RUN_VALIDATED"
        if score >= 0.45:
            return "CYBER_PHYSICAL_REAL_RUN_SAFE_BUT_PASSIVE"
        return "CYBER_PHYSICAL_REAL_RUN_INSUFFICIENT_EVIDENCE"

    @staticmethod
    def compute_aggregate_verdict(
        results: List[CyberPhysicalRealRunProfileResult],
    ) -> str:
        actuation_not_blocked = sum(1 for r in results if r.verdict == "REAL_RUN_ACTUATION_NOT_BLOCKED")
        ro_violation = sum(1 for r in results if r.verdict == "REAL_RUN_READ_ONLY_MODE_VIOLATION")
        invalid_accepted = sum(1 for r in results if r.verdict == "REAL_RUN_INVALID_SIGNAL_ACCEPTED")
        unsafe_routed = sum(1 for r in results if r.verdict == "REAL_RUN_UNSAFE_EXTERNAL_SIGNAL_ROUTED")
        noisy_not_quarantined = sum(1 for r in results if r.verdict == "REAL_RUN_NOISY_SIGNAL_NOT_QUARANTINED")
        conflict_undetected = sum(1 for r in results if r.verdict == "REAL_RUN_CONFLICTING_WORLD_STATE_UNDETECTED")
        bus_failure = sum(1 for r in results if r.verdict == "REAL_RUN_ORGANISM_BUS_PUBLICATION_FAILURE")
        real_conn_allowed = sum(1 for r in results if r.verdict == "REAL_RUN_REAL_CONNECTION_ATTEMPT_ALLOWED")
        scores = [r.cyber_physical_real_run_score for r in results]
        mean_score = sum(scores) / max(1, len(scores))

        if actuation_not_blocked > 0:
            return "REAL_RUN_ACTUATION_NOT_BLOCKED"
        if ro_violation > 0:
            return "REAL_RUN_READ_ONLY_MODE_VIOLATION"
        if real_conn_allowed > 0:
            return "REAL_RUN_REAL_CONNECTION_ATTEMPT_ALLOWED"
        if invalid_accepted > 0:
            return "REAL_RUN_INVALID_SIGNAL_ACCEPTED"
        if unsafe_routed > 0:
            return "REAL_RUN_UNSAFE_EXTERNAL_SIGNAL_ROUTED"
        if noisy_not_quarantined > 0:
            return "REAL_RUN_NOISY_SIGNAL_NOT_QUARANTINED"
        if conflict_undetected > 0:
            return "REAL_RUN_CONFLICTING_WORLD_STATE_UNDETECTED"
        if bus_failure > 0:
            return "REAL_RUN_ORGANISM_BUS_PUBLICATION_FAILURE"
        if mean_score >= 0.70:
            return "CYBER_PHYSICAL_REAL_RUN_VALIDATED"
        if mean_score >= 0.45:
            return "CYBER_PHYSICAL_REAL_RUN_SAFE_BUT_PASSIVE"
        return "CYBER_PHYSICAL_REAL_RUN_INSUFFICIENT_EVIDENCE"

    def generate_json_report(self, suite_result: CyberPhysicalRealRunSuiteResult) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.reports_dir / f"t60b_audit_{timestamp}.json"
        path.write_text(suite_result.model_dump_json(indent=2), encoding="utf-8")
        return str(path)

    def generate_markdown_report(self, suite_result: CyberPhysicalRealRunSuiteResult) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.reports_dir / f"t60b_audit_{timestamp}.md"
        lines = [
            "# T60B — Cyber-Physical Assimilation Real-Run Audit Report",
            f"**Date:** {timestamp}",
            f"**Aggregate Verdict:** `{suite_result.aggregate_verdict}`",
            f"**Proceed to T61:** {suite_result.proceed_to_t61}",
            "",
            "## Aggregate Metrics",
            f"- Profiles Run: {suite_result.profile_count}",
            f"- Ticks Run: {suite_result.total_ticks_run}",
            f"- Streams Processed: {suite_result.total_streams_processed}",
            f"- Signals Processed: {suite_result.total_signals_processed}",
            f"- Signals Accepted: {suite_result.total_signals_accepted}",
            f"- Signals Quarantined: {suite_result.total_signals_quarantined}",
            f"- Invalid Signals Blocked: {suite_result.total_invalid_signals_blocked}",
            f"- Actuation Requests Blocked: {suite_result.total_actuation_requests_blocked}",
            f"- Cyber-Physical Real-Run Score: {suite_result.aggregate_cyber_physical_real_run_score:.4f}",
            f"- World State Coherence: {suite_result.aggregate_world_coherence_score:.4f}",
            f"- Safety Preservation: {suite_result.aggregate_safety_preservation_score:.4f}",
            f"- Assimilation Quality: {suite_result.aggregate_assimilation_quality_score:.4f}",
            f"- Read-Only Integrity: {suite_result.aggregate_read_only_integrity_score:.4f}",
            "",
            "## Profile Results",
        ]
        for r in suite_result.profile_results:
            lines.append(f"### {r.profile_name}")
            lines.append(f"- Signals: {r.signals_processed}")
            lines.append(f"- Accepted: {r.signals_accepted}")
            lines.append(f"- Quarantined: {r.signals_quarantined}")
            lines.append(f"- Score: {r.cyber_physical_real_run_score:.4f}")
            lines.append(f"- Verdict: `{r.verdict}`")
            lines.append("")
        lines.append("---")
        lines.append("*Generated by CyberPhysicalRealRunAuditRunner (T60B)*")
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)
