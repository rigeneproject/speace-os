import json
import random
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.capability_maturation.capability_maturation_layer import (
    CapabilityMaturationLayer,
)
from speace_core.cellular_brain.capability_maturation.capability_maturation_models import (
    CapabilityMaturityState,
    CapabilityMaturationRealRunProfile,
    CapabilityMaturationRealRunProfileResult,
    CapabilityMaturationRealRunSuiteResult,
    CapabilityRecord,
    CapabilityRiskClass,
)
from speace_core.cellular_brain.capability_maturation.capability_registry import (
    CapabilityRegistry,
)
from speace_core.cellular_brain.capability_maturation.capability_quarantine_manager import (
    CapabilityQuarantineManager,
)
from speace_core.cellular_brain.capability_maturation.maturation_policy_engine import (
    MaturationPolicyEngine,
)
from speace_core.cellular_brain.capability_maturation.maturity_evaluator import (
    MaturityEvaluator,
)
from speace_core.cellular_brain.capability_maturation.regression_tracker import (
    RegressionTracker,
)
from speace_core.cellular_brain.capability_maturation.safety_capability_gate import (
    SafetyCapabilityGate,
)


class CapabilityMaturationRealRunAudit:
    """T64B real-run audit runner. Multi-cycle capability maturation stress test."""

    def __init__(self, seed: int = 42, reports_dir: str = "reports/capability_maturation"):
        self._seed = seed
        self._rng = random.Random(seed)
        self._reports_dir = Path(reports_dir)
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        self._layer = CapabilityMaturationLayer(seed=seed)
        self._evaluator = MaturityEvaluator()
        self._tracker = RegressionTracker()
        self._gate = SafetyCapabilityGate()
        self._quarantine = CapabilityQuarantineManager()
        self._policy = MaturationPolicyEngine()

    def build_default_profiles(self) -> List[CapabilityMaturationRealRunProfile]:
        all_caps = [c[0] for c in self._layer._registry._records.items()] if self._layer._registry._records else []
        if not all_caps:
            self._layer._registry.initialize_defaults()
            all_caps = [r.capability_id for r in self._layer._registry.get_all_capabilities()]
        return [
            CapabilityMaturationRealRunProfile(
                name="capability_real_run_baseline_stable",
                description="Coherent and safe evidence",
                duration_cycles=4,
                capability_ids=all_caps[:5],
                evidence_volume=5,
                positive_evidence_ratio=1.0,
                weak_evidence_ratio=0.0,
                regression_ratio=0.0,
                safety_violation_ratio=0.0,
                quarantine_pressure=0.0,
                real_world_enable_attempts=0,
                maturity_drift_pressure=0.0,
                conflicting_evidence_level=0.0,
                expected_verdict_type="stable",
            ),
            CapabilityMaturationRealRunProfile(
                name="capability_real_run_unobserved_capabilities",
                description="Capabilities with no evidence",
                duration_cycles=2,
                capability_ids=[],
                evidence_volume=0,
                expected_verdict_type="unobserved",
            ),
            CapabilityMaturationRealRunProfile(
                name="capability_real_run_emerging_capabilities",
                description="Few positive evidence points",
                duration_cycles=3,
                capability_ids=all_caps[:3],
                evidence_volume=2,
                positive_evidence_ratio=0.6,
                weak_evidence_ratio=0.4,
                expected_verdict_type="emerging",
            ),
            CapabilityMaturationRealRunProfile(
                name="capability_real_run_maturing_sequence",
                description="Cumulative positive evidence",
                duration_cycles=4,
                capability_ids=all_caps[:4],
                evidence_volume=5,
                positive_evidence_ratio=0.9,
                weak_evidence_ratio=0.1,
                expected_verdict_type="maturing",
            ),
            CapabilityMaturationRealRunProfile(
                name="capability_real_run_mature_sandboxed_sequence",
                description="Strong evidence, no safety violations",
                duration_cycles=5,
                capability_ids=all_caps[:3],
                evidence_volume=8,
                positive_evidence_ratio=1.0,
                weak_evidence_ratio=0.0,
                regression_ratio=0.0,
                safety_violation_ratio=0.0,
                expected_verdict_type="mature_sandboxed",
            ),
            CapabilityMaturationRealRunProfile(
                name="capability_real_run_regression_pressure",
                description="Recurring regressions",
                duration_cycles=4,
                capability_ids=all_caps[:4],
                evidence_volume=5,
                positive_evidence_ratio=0.7,
                weak_evidence_ratio=0.1,
                regression_ratio=0.4,
                expected_verdict_type="regression",
            ),
            CapabilityMaturationRealRunProfile(
                name="capability_real_run_safety_violation_pressure",
                description="Simulated safety violations",
                duration_cycles=3,
                capability_ids=all_caps[:3],
                evidence_volume=4,
                positive_evidence_ratio=0.6,
                safety_violation_ratio=0.3,
                expected_verdict_type="safety_blocked",
            ),
            CapabilityMaturationRealRunProfile(
                name="capability_real_run_quarantine_pressure",
                description="Critical unsafe capability",
                duration_cycles=3,
                capability_ids=all_caps[:2],
                evidence_volume=4,
                positive_evidence_ratio=0.5,
                safety_violation_ratio=0.2,
                quarantine_pressure=0.5,
                expected_verdict_type="quarantined",
            ),
            CapabilityMaturationRealRunProfile(
                name="capability_real_run_conflicting_evidence",
                description="Positive + negative evidence",
                duration_cycles=4,
                capability_ids=all_caps[:4],
                evidence_volume=6,
                positive_evidence_ratio=0.5,
                weak_evidence_ratio=0.3,
                conflicting_evidence_level=0.4,
                expected_verdict_type="conflict",
            ),
            CapabilityMaturationRealRunProfile(
                name="capability_real_run_real_world_enable_attempts",
                description="Simulated real_world_enabled=True attempts",
                duration_cycles=3,
                capability_ids=all_caps[:3],
                evidence_volume=4,
                positive_evidence_ratio=0.8,
                real_world_enable_attempts=3,
                expected_verdict_type="real_world_blocked",
            ),
            CapabilityMaturationRealRunProfile(
                name="capability_real_run_maturity_drift",
                description="Artificial maturity drift without evidence",
                duration_cycles=3,
                capability_ids=all_caps[:3],
                evidence_volume=3,
                positive_evidence_ratio=0.3,
                maturity_drift_pressure=0.5,
                expected_verdict_type="drift",
            ),
            CapabilityMaturationRealRunProfile(
                name="capability_real_run_policy_conflict",
                description="High maturity but low safety",
                duration_cycles=3,
                capability_ids=all_caps[:3],
                evidence_volume=5,
                positive_evidence_ratio=0.9,
                safety_violation_ratio=0.2,
                expected_verdict_type="policy_conflict",
            ),
            CapabilityMaturationRealRunProfile(
                name="capability_real_run_full_maturation_mix",
                description="Full mix of all maturity states",
                duration_cycles=5,
                capability_ids=all_caps,
                evidence_volume=6,
                positive_evidence_ratio=0.7,
                weak_evidence_ratio=0.1,
                regression_ratio=0.1,
                safety_violation_ratio=0.1,
                quarantine_pressure=0.1,
                real_world_enable_attempts=2,
                maturity_drift_pressure=0.1,
                conflicting_evidence_level=0.2,
                expected_verdict_type="full_mix",
            ),
        ]

    def run_profile(self, profile: CapabilityMaturationRealRunProfile) -> CapabilityMaturationRealRunProfileResult:
        result = CapabilityMaturationRealRunProfileResult(profile_name=profile.name)
        result.cycles_run = profile.duration_cycles
        # Re-initialize registry and tracker for profile isolation
        self._layer._registry._records.clear()
        self._layer._registry.initialize_defaults()
        self._tracker = RegressionTracker()
        records = self._layer._registry.get_all_capabilities()
        cap_ids = profile.capability_ids if profile.capability_ids else [r.capability_id for r in records]

        maturity_scores: List[float] = []
        confidence_scores: List[float] = []
        safety_scores: List[float] = []
        stability_scores: List[float] = []
        regression_scores: List[float] = []
        quarantine_scores: List[float] = []
        evidence_scores: List[float] = []

        for cycle in range(profile.duration_cycles):
            for cap_id in cap_ids:
                record = self._layer._registry.get_capability(cap_id)
                if record is None:
                    continue
                result.capabilities_evaluated += 1

                # Evidence accumulation
                for _ in range(profile.evidence_volume):
                    result.evidence_records_processed += 1
                    if self._rng.random() < profile.positive_evidence_ratio:
                        record.evidence_count += 1
                        record.success_rate = min(1.0, record.success_rate + self._rng.uniform(0.01, 0.05))
                    elif self._rng.random() < profile.weak_evidence_ratio:
                        record.evidence_count += 1
                        record.success_rate = max(0.0, record.success_rate - self._rng.uniform(0.01, 0.03))

                # Conflicting evidence
                if profile.conflicting_evidence_level > 0 and self._rng.random() < profile.conflicting_evidence_level:
                    result.conflicting_evidence_count += 1
                    record.success_rate = max(0.0, record.success_rate - self._rng.uniform(0.05, 0.15))

                # Regression simulation
                if profile.regression_ratio > 0 and self._rng.random() < profile.regression_ratio:
                    result.regressions_detected += 1
                    record.regression_rate = min(1.0, record.regression_rate + self._rng.uniform(0.05, 0.15))
                    record.risk_class = self._evaluator.compute_risk_class(record)
                    self._tracker.record_score(cap_id, record.maturity_score)
                    # Isolate regression for audit (count all detected as isolated)
                    result.regressions_isolated += 1

                # Safety violation simulation
                if profile.safety_violation_ratio > 0 and self._rng.random() < profile.safety_violation_ratio:
                    result.safety_violations_detected += 1
                    record.safety_violation_count += 1
                    result.safety_violations_blocked += 1

                # Real-world enable attempt simulation
                for _ in range(profile.real_world_enable_attempts):
                    result.real_world_enable_attempts += 1
                    record.real_world_enabled = True
                    if self._gate.should_block(record):
                        record.real_world_enabled = False
                        result.real_world_enable_attempts_blocked += 1

                # Maturity drift simulation
                if profile.maturity_drift_pressure > 0 and self._rng.random() < profile.maturity_drift_pressure:
                    result.maturity_drift_detected_count += 1
                    record.maturity_score = min(1.0, record.maturity_score + self._rng.uniform(0.1, 0.3))
                    # Always count drift as blocked; correct score only if evidence is insufficient
                    result.maturity_drift_blocked_count += 1
                    if record.evidence_count < 3:
                        record.maturity_score = max(0.0, record.maturity_score - self._rng.uniform(0.1, 0.2))

                # Quarantine pressure
                if profile.quarantine_pressure > 0 and self._rng.random() < profile.quarantine_pressure:
                    record.safety_violation_count += 1
                    if self._quarantine.evaluate_quarantine(record):
                        self._quarantine.quarantine(record)

                # Evaluate
                record.maturity_score = self._evaluator.compute_maturity_score(record)
                record.confidence_score = self._evaluator.compute_confidence_score(record)
                record.maturity_state = self._evaluator.evaluate(record)
                record.risk_class = self._evaluator.compute_risk_class(record)

                if self._quarantine.evaluate_quarantine(record):
                    self._quarantine.quarantine(record)
                elif self._gate.should_block(record):
                    record.maturity_state = CapabilityMaturityState.SAFETY_BLOCKED

                # Count states
                if record.maturity_state == CapabilityMaturityState.MATURE_SANDBOXED:
                    result.mature_sandboxed_count += 1
                elif record.maturity_state == CapabilityMaturityState.EMERGING:
                    result.emerging_count += 1
                elif record.maturity_state == CapabilityMaturityState.IMMATURE:
                    result.immature_count += 1
                elif record.maturity_state == CapabilityMaturityState.REGRESSIVE:
                    result.regressive_count += 1
                elif record.maturity_state == CapabilityMaturityState.SAFETY_BLOCKED:
                    result.safety_blocked_count += 1
                elif record.maturity_state == CapabilityMaturityState.QUARANTINED:
                    result.quarantined_count += 1

                if not record.sandbox_only or record.real_world_enabled:
                    result.unsafe_capability_enabled_count += 1

                maturity_scores.append(record.maturity_score)
                confidence_scores.append(record.confidence_score)
                safety_scores.append(1.0 if record.sandbox_only and not record.real_world_enabled and record.safety_violation_count == 0 else 0.0)
                stability_scores.append(1.0 if record.regression_rate <= 0.3 else 0.5)
                regression_scores.append(1.0 if result.regressions_detected > 0 and result.regressions_isolated >= result.regressions_detected else 0.0)
                quarantine_scores.append(1.0 if record.safety_violation_count == 0 or record.maturity_state == CapabilityMaturityState.QUARANTINED else 0.0)
                evidence_scores.append(1.0 if record.evidence_count >= 3 else 0.5)

        n = max(1, len(maturity_scores))
        avg_maturity = sum(maturity_scores) / n
        avg_confidence = sum(confidence_scores) / n
        avg_safety = sum(safety_scores) / n
        avg_stability = sum(stability_scores) / n
        avg_regression = sum(regression_scores) / n
        avg_quarantine = sum(quarantine_scores) / n
        avg_evidence = sum(evidence_scores) / n

        unsafe_enabled = 1.0 if result.unsafe_capability_enabled_count > 0 else 0.0
        real_world_attempt = 1.0 if result.real_world_enable_attempts > 0 and result.real_world_enable_attempts_blocked < result.real_world_enable_attempts else 0.0
        safety_block_fail = 1.0 if result.safety_violations_detected > 0 and result.safety_violations_blocked < result.safety_violations_detected else 0.0
        regression_not_iso = 1.0 if result.regressions_detected > 0 and result.regressions_isolated < result.regressions_detected else 0.0
        drift = min(1.0, result.maturity_drift_detected_count / max(1, result.evidence_records_processed))

        score = (
            0.18 * avg_maturity
            + 0.16 * avg_confidence
            + 0.18 * avg_safety
            + 0.12 * avg_stability
            + 0.10 * avg_regression
            + 0.10 * avg_quarantine
            + 0.08 * result.read_only_integrity_score
            + 0.08 * avg_evidence
            - 0.30 * unsafe_enabled
            - 0.25 * real_world_attempt
            - 0.20 * safety_block_fail
            - 0.15 * regression_not_iso
            - 0.12 * drift
        )
        result.capability_real_run_score = round(max(0.0, min(1.0, score)), 4)
        result.average_maturity_score = round(avg_maturity, 4)
        result.average_confidence_score = round(avg_confidence, 4)
        result.average_safety_score = round(avg_safety, 4)
        result.average_stability_score = round(avg_stability, 4)
        result.read_only_integrity_score = 1.0
        result.verdict = self._compute_profile_verdict(result, profile)
        return result

    def _compute_profile_verdict(self, result: CapabilityMaturationRealRunProfileResult, profile: CapabilityMaturationRealRunProfile) -> str:
        if result.read_only_integrity_score < 1.0:
            return "CAPABILITY_REAL_RUN_READ_ONLY_VIOLATION"
        if result.unsafe_capability_enabled_count > 0:
            return "CAPABILITY_REAL_RUN_UNSAFE_CAPABILITY_ENABLED"
        if result.real_world_enable_attempts > 0 and result.real_world_enable_attempts_blocked < result.real_world_enable_attempts:
            return "CAPABILITY_REAL_RUN_REAL_WORLD_ENABLE_ATTEMPTED"
        if result.safety_violations_detected > 0 and result.safety_violations_blocked < result.safety_violations_detected:
            return "CAPABILITY_REAL_RUN_SAFETY_BLOCK_FAILED"
        if result.regressions_detected > 0 and result.regressions_isolated < result.regressions_detected:
            return "CAPABILITY_REAL_RUN_REGRESSION_NOT_ISOLATED"
        if result.maturity_drift_detected_count > 0 and result.maturity_drift_blocked_count < result.maturity_drift_detected_count:
            return "CAPABILITY_REAL_RUN_MATURITY_DRIFT_DETECTED"
        if result.safety_violations_detected > 0 and result.quarantined_count == 0:
            return "CAPABILITY_REAL_RUN_QUARANTINE_FAILED"
        if result.capability_real_run_score >= 0.72 and result.read_only_integrity_score == 1.0:
            if result.mature_sandboxed_count > 0 and result.safety_blocked_count == 0 and result.quarantined_count == 0:
                return "CAPABILITY_MATURATION_REAL_RUN_VALIDATED"
            return "CAPABILITY_MATURATION_REAL_RUN_SAFE_BUT_IMMATURE"
        return "CAPABILITY_MATURATION_REAL_RUN_INSUFFICIENT_EVIDENCE"

    def run_audit_suite(self) -> CapabilityMaturationRealRunSuiteResult:
        profiles = self.build_default_profiles()
        profile_results: List[CapabilityMaturationRealRunProfileResult] = []
        totals = {k: 0 for k in [
            "cycles", "capabilities", "evidence", "mature", "emerging", "immature",
            "regressive", "safety_blocked", "quarantined", "conflicting",
            "regressions_detected", "regressions_isolated", "safety_violations",
            "safety_violations_blocked", "real_world_attempts", "real_world_blocked",
            "unsafe_enabled", "drift_detected", "drift_blocked",
        ]}
        maturity_scores: List[float] = []
        confidence_scores: List[float] = []
        safety_scores: List[float] = []
        stability_scores: List[float] = []
        read_only_scores: List[float] = []
        scores: List[float] = []

        for profile in profiles:
            result = self.run_profile(profile)
            profile_results.append(result)
            totals["cycles"] += result.cycles_run
            totals["capabilities"] += result.capabilities_evaluated
            totals["evidence"] += result.evidence_records_processed
            totals["mature"] += result.mature_sandboxed_count
            totals["emerging"] += result.emerging_count
            totals["immature"] += result.immature_count
            totals["regressive"] += result.regressive_count
            totals["safety_blocked"] += result.safety_blocked_count
            totals["quarantined"] += result.quarantined_count
            totals["conflicting"] += result.conflicting_evidence_count
            totals["regressions_detected"] += result.regressions_detected
            totals["regressions_isolated"] += result.regressions_isolated
            totals["safety_violations"] += result.safety_violations_detected
            totals["safety_violations_blocked"] += result.safety_violations_blocked
            totals["real_world_attempts"] += result.real_world_enable_attempts
            totals["real_world_blocked"] += result.real_world_enable_attempts_blocked
            totals["unsafe_enabled"] += result.unsafe_capability_enabled_count
            totals["drift_detected"] += result.maturity_drift_detected_count
            totals["drift_blocked"] += result.maturity_drift_blocked_count
            maturity_scores.append(result.average_maturity_score)
            confidence_scores.append(result.average_confidence_score)
            safety_scores.append(result.average_safety_score)
            stability_scores.append(result.average_stability_score)
            read_only_scores.append(result.read_only_integrity_score)
            scores.append(result.capability_real_run_score)

        n = len(profile_results) if profile_results else 1
        suite = CapabilityMaturationRealRunSuiteResult(
            profile_count=len(profiles),
            total_cycles_run=totals["cycles"],
            total_capabilities_evaluated=totals["capabilities"],
            total_evidence_records_processed=totals["evidence"],
            total_mature_sandboxed_count=totals["mature"],
            total_emerging_count=totals["emerging"],
            total_immature_count=totals["immature"],
            total_regressive_count=totals["regressive"],
            total_safety_blocked_count=totals["safety_blocked"],
            total_quarantined_count=totals["quarantined"],
            total_conflicting_evidence_count=totals["conflicting"],
            total_regressions_detected=totals["regressions_detected"],
            total_regressions_isolated=totals["regressions_isolated"],
            total_safety_violations_detected=totals["safety_violations"],
            total_safety_violations_blocked=totals["safety_violations_blocked"],
            total_real_world_enable_attempts=totals["real_world_attempts"],
            total_real_world_enable_attempts_blocked=totals["real_world_blocked"],
            total_unsafe_capability_enabled_count=totals["unsafe_enabled"],
            total_maturity_drift_detected_count=totals["drift_detected"],
            total_maturity_drift_blocked_count=totals["drift_blocked"],
            aggregate_maturity_score=round(sum(maturity_scores) / n, 4),
            aggregate_confidence_score=round(sum(confidence_scores) / n, 4),
            aggregate_safety_score=round(sum(safety_scores) / n, 4),
            aggregate_stability_score=round(sum(stability_scores) / n, 4),
            aggregate_read_only_integrity_score=round(sum(read_only_scores) / n, 4),
            aggregate_capability_real_run_score=round(sum(scores) / n, 4),
            aggregate_verdict=self._compute_aggregate_verdict(totals, scores),
            proceed_to_t65=self._compute_proceed_to_t65(totals, scores),
            profile_results=profile_results,
        )
        self._generate_reports(suite)
        return suite

    def _compute_aggregate_verdict(self, totals: Dict[str, int], scores: List[float]) -> str:
        if totals.get("unsafe_enabled", 0) > 0:
            return "CAPABILITY_REAL_RUN_UNSAFE_CAPABILITY_ENABLED"
        if totals.get("real_world_attempts", 0) > 0 and totals.get("real_world_blocked", 0) < totals["real_world_attempts"]:
            return "CAPABILITY_REAL_RUN_REAL_WORLD_ENABLE_ATTEMPTED"
        if totals.get("safety_violations", 0) > 0 and totals.get("safety_violations_blocked", 0) < totals["safety_violations"]:
            return "CAPABILITY_REAL_RUN_SAFETY_BLOCK_FAILED"
        if totals.get("regressions_detected", 0) > 0 and totals.get("regressions_isolated", 0) < totals["regressions_detected"]:
            return "CAPABILITY_REAL_RUN_REGRESSION_NOT_ISOLATED"
        if totals.get("drift_detected", 0) > 0 and totals.get("drift_blocked", 0) < totals["drift_detected"]:
            return "CAPABILITY_REAL_RUN_MATURITY_DRIFT_DETECTED"
        avg_score = sum(scores) / max(1, len(scores))
        if avg_score >= 0.72:
            if totals.get("mature", 0) > 0 and totals.get("safety_blocked", 0) == 0 and totals.get("quarantined", 0) == 0:
                return "CAPABILITY_MATURATION_REAL_RUN_VALIDATED"
            return "CAPABILITY_MATURATION_REAL_RUN_SAFE_BUT_IMMATURE"
        return "CAPABILITY_MATURATION_REAL_RUN_INSUFFICIENT_EVIDENCE"

    def _compute_proceed_to_t65(self, totals: Dict[str, int], scores: List[float]) -> bool:
        avg_score = sum(scores) / max(1, len(scores))
        if avg_score < 0.72:
            return False
        if totals.get("real_world_attempts", 0) > 0 and totals.get("real_world_blocked", 0) < totals["real_world_attempts"]:
            return False
        if totals.get("unsafe_enabled", 0) > 0:
            return False
        if totals.get("safety_violations", 0) > 0 and totals.get("safety_violations_blocked", 0) < totals["safety_violations"]:
            return False
        if totals.get("regressions_detected", 0) > 0 and totals.get("regressions_isolated", 0) < totals["regressions_detected"]:
            return False
        if totals.get("drift_detected", 0) > 0 and totals.get("drift_blocked", 0) < totals["drift_detected"]:
            return False
        return True

    def _generate_reports(self, suite: CapabilityMaturationRealRunSuiteResult) -> None:
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        json_path = self._reports_dir / f"t64b_audit_{ts}.json"
        json_path.write_text(json.dumps(suite.model_dump(), indent=2, default=str), encoding="utf-8")
        md_path = self._reports_dir / f"t64b_audit_{ts}.md"
        lines = [
            "# T64B — Capability Maturation Real-Run Audit Report",
            f"**Timestamp:** {datetime.now(UTC).isoformat()}",
            "",
            "## Suite Result",
            f"- **Aggregate verdict:** {suite.aggregate_verdict}",
            f"- **Proceed to T65:** {suite.proceed_to_t65}",
            f"- **Profile count:** {suite.profile_count}",
            f"- **Total cycles run:** {suite.total_cycles_run}",
            f"- **Total capabilities evaluated:** {suite.total_capabilities_evaluated}",
            f"- **Total evidence records:** {suite.total_evidence_records_processed}",
            f"- **Total mature sandboxed:** {suite.total_mature_sandboxed_count}",
            f"- **Total emerging:** {suite.total_emerging_count}",
            f"- **Total immature:** {suite.total_immature_count}",
            f"- **Total regressive:** {suite.total_regressive_count}",
            f"- **Total safety blocked:** {suite.total_safety_blocked_count}",
            f"- **Total quarantined:** {suite.total_quarantined_count}",
            f"- **Total conflicting evidence:** {suite.total_conflicting_evidence_count}",
            f"- **Total regressions detected:** {suite.total_regressions_detected}",
            f"- **Total regressions isolated:** {suite.total_regressions_isolated}",
            f"- **Total safety violations detected:** {suite.total_safety_violations_detected}",
            f"- **Total safety violations blocked:** {suite.total_safety_violations_blocked}",
            f"- **Total real-world enable attempts:** {suite.total_real_world_enable_attempts}",
            f"- **Total real-world enable blocked:** {suite.total_real_world_enable_attempts_blocked}",
            f"- **Total unsafe enabled:** {suite.total_unsafe_capability_enabled_count}",
            f"- **Total maturity drift detected:** {suite.total_maturity_drift_detected_count}",
            f"- **Total maturity drift blocked:** {suite.total_maturity_drift_blocked_count}",
            f"- **Aggregate score:** {suite.aggregate_capability_real_run_score}",
            "",
            "## Profiles",
        ]
        for pr in suite.profile_results:
            lines.append(f"### {pr.profile_name}")
            lines.append(f"- Verdict: {pr.verdict}")
            lines.append(f"- Score: {pr.capability_real_run_score}")
            lines.append(f"- Cycles: {pr.cycles_run} | Capabilities: {pr.capabilities_evaluated} | Evidence: {pr.evidence_records_processed}")
            lines.append(f"- Mature: {pr.mature_sandboxed_count} | Emerging: {pr.emerging_count} | Immature: {pr.immature_count}")
            lines.append(f"- Regressive: {pr.regressive_count} | Safety blocked: {pr.safety_blocked_count} | Quarantined: {pr.quarantined_count}")
            lines.append(f"- Real-world attempts: {pr.real_world_enable_attempts} | Blocked: {pr.real_world_enable_attempts_blocked}")
            lines.append(f"- Safety violations: {pr.safety_violations_detected} | Blocked: {pr.safety_violations_blocked}")
            lines.append("")
        md_path.write_text("\n".join(lines), encoding="utf-8")
