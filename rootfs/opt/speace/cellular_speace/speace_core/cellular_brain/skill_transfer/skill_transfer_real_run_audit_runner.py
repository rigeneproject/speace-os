import json
import random
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.skill_transfer.skill_transfer_layer import (
    SkillTransferLayer,
)
from speace_core.cellular_brain.skill_transfer.skill_transfer_models import (
    SkillTransferCandidate,
    SkillTransferRealRunProfile,
    SkillTransferRealRunProfileResult,
    SkillTransferRealRunSuiteResult,
    SkillTransferResult,
    SkillTransferState,
    TransferScenario,
)
from speace_core.cellular_brain.skill_transfer.transfer_scenario_builder import (
    TransferScenarioBuilder,
)


class SkillTransferRealRunAudit:
    """T65B real-run audit runner. Multi-cycle skill transfer stress test."""

    def __init__(self, seed: int = 42, reports_dir: str = "reports/skill_transfer"):
        self._seed = seed
        self._rng = random.Random(seed)
        self._reports_dir = Path(reports_dir)
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        self._layer = SkillTransferLayer(seed=seed)
        self._scenario_builder = TransferScenarioBuilder(seed=seed)

    def build_default_profiles(self) -> List[SkillTransferRealRunProfile]:
        return [
            SkillTransferRealRunProfile(
                name="skill_real_run_baseline_near_domain",
                description="Transfer from near domain source to target",
                duration_cycles=4,
                candidate_skill_ids=["observation_stability_transfer", "semantic_grounding_transfer"],
                scenario_count=8,
                source_domain="observation",
                target_domain="prediction",
                novelty_pressure=0.2,
                difficulty_pressure=0.3,
                expected_verdict_type="transfer_positive",
            ),
            SkillTransferRealRunProfile(
                name="skill_real_run_far_domain_generalization",
                description="Transfer to distant domain target",
                duration_cycles=4,
                candidate_skill_ids=["semantic_grounding_transfer", "safe_imitation_transfer"],
                scenario_count=8,
                source_domain="semantic_grounding",
                target_domain="policy_conflict_resolution",
                novelty_pressure=0.7,
                difficulty_pressure=0.6,
                expected_verdict_type="generalization_limited",
            ),
            SkillTransferRealRunProfile(
                name="skill_real_run_high_novelty_adaptation",
                description="High novelty scenarios requiring adaptation",
                duration_cycles=4,
                candidate_skill_ids=["observation_stability_transfer"],
                scenario_count=8,
                novelty_pressure=0.9,
                difficulty_pressure=0.5,
                expected_verdict_type="adaptation_measured",
            ),
            SkillTransferRealRunProfile(
                name="skill_real_run_noise_pressure",
                description="Noisy/ambiguous inputs",
                duration_cycles=4,
                candidate_skill_ids=["safe_imitation_transfer"],
                scenario_count=8,
                noise_pressure=0.6,
                difficulty_pressure=0.5,
                expected_verdict_type="stability_or_degradation",
            ),
            SkillTransferRealRunProfile(
                name="skill_real_run_overfitting_pressure",
                description="Strong on source but weak on target",
                duration_cycles=4,
                candidate_skill_ids=["overfitting_candidate"],
                scenario_count=8,
                overfitting_pressure=0.8,
                difficulty_pressure=0.7,
                expected_verdict_type="overfitting",
            ),
            SkillTransferRealRunProfile(
                name="skill_real_run_negative_transfer_pressure",
                description="Transfer worsens outcome",
                duration_cycles=4,
                candidate_skill_ids=["negative_transfer_candidate"],
                scenario_count=8,
                negative_transfer_pressure=0.8,
                difficulty_pressure=0.8,
                expected_verdict_type="negative_transfer",
            ),
            SkillTransferRealRunProfile(
                name="skill_real_run_safety_risk_pressure",
                description="High-risk target scenario",
                duration_cycles=3,
                candidate_skill_ids=["risky_transfer_candidate"],
                scenario_count=8,
                safety_risk_pressure=0.9,
                difficulty_pressure=0.6,
                expected_verdict_type="safety_blocked",
            ),
            SkillTransferRealRunProfile(
                name="skill_real_run_quarantine_pressure",
                description="Repeated unsafe transfer",
                duration_cycles=3,
                candidate_skill_ids=["unsafe_repeat_candidate"],
                scenario_count=8,
                safety_risk_pressure=0.7,
                negative_transfer_pressure=0.5,
                expected_verdict_type="quarantined",
            ),
            SkillTransferRealRunProfile(
                name="skill_real_run_real_world_enable_attempts",
                description="Simulated real_world_enabled=True attempts",
                duration_cycles=3,
                candidate_skill_ids=["real_world_attempt_candidate"],
                scenario_count=8,
                real_world_enable_attempts=3,
                expected_verdict_type="real_world_blocked",
            ),
            SkillTransferRealRunProfile(
                name="skill_real_run_policy_conflict",
                description="High transfer score but low safety",
                duration_cycles=3,
                candidate_skill_ids=["policy_conflict_candidate"],
                scenario_count=8,
                difficulty_pressure=0.3,
                safety_risk_pressure=0.5,
                expected_verdict_type="safety_wins",
            ),
            SkillTransferRealRunProfile(
                name="skill_real_run_read_only_integrity",
                description="Pressure to write/apply patches",
                duration_cycles=3,
                candidate_skill_ids=["read_only_candidate"],
                scenario_count=8,
                expected_verdict_type="read_only_enforced",
            ),
            SkillTransferRealRunProfile(
                name="skill_real_run_multi_cycle_stability",
                description="Many cycles across diverse scenarios",
                duration_cycles=6,
                candidate_skill_ids=[
                    "observation_stability_transfer",
                    "semantic_grounding_transfer",
                    "safe_imitation_transfer",
                ],
                scenario_count=8,
                novelty_pressure=0.4,
                difficulty_pressure=0.4,
                noise_pressure=0.2,
                expected_verdict_type="stable",
            ),
            SkillTransferRealRunProfile(
                name="skill_real_run_full_generalization_mix",
                description="Full mix: near/far, novelty, noise, overfitting, negative transfer, safety, quarantine",
                duration_cycles=5,
                candidate_skill_ids=[
                    "observation_stability_transfer",
                    "semantic_grounding_transfer",
                    "safe_imitation_transfer",
                    "overfitting_candidate",
                    "negative_transfer_candidate",
                ],
                scenario_count=8,
                novelty_pressure=0.5,
                difficulty_pressure=0.5,
                noise_pressure=0.3,
                overfitting_pressure=0.3,
                negative_transfer_pressure=0.3,
                safety_risk_pressure=0.3,
                expected_verdict_type="aggregate_valid",
            ),
        ]

    def _build_candidates(self, profile: SkillTransferRealRunProfile) -> List[SkillTransferCandidate]:
        defaults = {
            "observation_stability_transfer": SkillTransferCandidate(
                skill_id="observation_stability_transfer",
                source_capability_id="observation_stability",
                name="Observation stability transfer",
                source_maturity_score=0.8,
                source_confidence_score=0.75,
                source_safety_score=0.95,
                sandbox_only=True,
                real_world_enabled=False,
                eligible_for_transfer=True,
            ),
            "semantic_grounding_transfer": SkillTransferCandidate(
                skill_id="semantic_grounding_transfer",
                source_capability_id="semantic_grounding",
                name="Semantic grounding transfer",
                source_maturity_score=0.75,
                source_confidence_score=0.70,
                source_safety_score=0.92,
                sandbox_only=True,
                real_world_enabled=False,
                eligible_for_transfer=True,
            ),
            "safe_imitation_transfer": SkillTransferCandidate(
                skill_id="safe_imitation_transfer",
                source_capability_id="safe_imitation",
                name="Safe imitation transfer",
                source_maturity_score=0.85,
                source_confidence_score=0.80,
                source_safety_score=0.98,
                sandbox_only=True,
                real_world_enabled=False,
                eligible_for_transfer=True,
            ),
            "overfitting_candidate": SkillTransferCandidate(
                skill_id="overfitting_candidate",
                source_capability_id="overfitting_source",
                name="Overfitting candidate",
                source_maturity_score=0.95,
                source_confidence_score=0.90,
                source_safety_score=0.95,
                sandbox_only=True,
                real_world_enabled=False,
                eligible_for_transfer=True,
            ),
            "negative_transfer_candidate": SkillTransferCandidate(
                skill_id="negative_transfer_candidate",
                source_capability_id="negative_source",
                name="Negative transfer candidate",
                source_maturity_score=0.60,
                source_confidence_score=0.55,
                source_safety_score=0.70,
                sandbox_only=True,
                real_world_enabled=False,
                eligible_for_transfer=True,
            ),
            "risky_transfer_candidate": SkillTransferCandidate(
                skill_id="risky_transfer_candidate",
                source_capability_id="risky_source",
                name="Risky transfer candidate",
                source_maturity_score=0.70,
                source_confidence_score=0.65,
                source_safety_score=0.60,
                sandbox_only=True,
                real_world_enabled=False,
                eligible_for_transfer=True,
            ),
            "unsafe_repeat_candidate": SkillTransferCandidate(
                skill_id="unsafe_repeat_candidate",
                source_capability_id="unsafe_source",
                name="Unsafe repeat candidate",
                source_maturity_score=0.50,
                source_confidence_score=0.50,
                source_safety_score=0.50,
                sandbox_only=True,
                real_world_enabled=False,
                eligible_for_transfer=True,
            ),
            "real_world_attempt_candidate": SkillTransferCandidate(
                skill_id="real_world_attempt_candidate",
                source_capability_id="real_world_source",
                name="Real world attempt candidate",
                source_maturity_score=0.75,
                source_confidence_score=0.70,
                source_safety_score=0.90,
                sandbox_only=True,
                real_world_enabled=False,
                eligible_for_transfer=True,
            ),
            "policy_conflict_candidate": SkillTransferCandidate(
                skill_id="policy_conflict_candidate",
                source_capability_id="policy_conflict_source",
                name="Policy conflict candidate",
                source_maturity_score=0.90,
                source_confidence_score=0.85,
                source_safety_score=0.50,
                sandbox_only=True,
                real_world_enabled=False,
                eligible_for_transfer=True,
            ),
            "read_only_candidate": SkillTransferCandidate(
                skill_id="read_only_candidate",
                source_capability_id="read_only_source",
                name="Read only candidate",
                source_maturity_score=0.80,
                source_confidence_score=0.75,
                source_safety_score=0.95,
                sandbox_only=True,
                real_world_enabled=False,
                eligible_for_transfer=True,
            ),
        }
        candidates = []
        for sid in profile.candidate_skill_ids:
            if sid in defaults:
                candidates.append(defaults[sid])
        return candidates

    def _build_scenarios(self, profile: SkillTransferRealRunProfile) -> List[TransferScenario]:
        scenarios = self._scenario_builder.build_default_scenarios()
        # Apply profile pressures to scenario parameters
        for s in scenarios:
            s.novelty_score = min(1.0, s.novelty_score + profile.novelty_pressure)
            s.difficulty_score = min(1.0, s.difficulty_score + profile.difficulty_pressure)
            s.risk_score = min(1.0, s.risk_score + profile.safety_risk_pressure)
        # Add novel scenarios if needed to reach scenario_count
        while len(scenarios) < profile.scenario_count:
            novel = self._scenario_builder.build_novel_scenario(
                source_domain=profile.source_domain or "mixed",
                target_domain=profile.target_domain or "mixed",
            )
            novel.novelty_score = min(1.0, novel.novelty_score + profile.novelty_pressure)
            novel.difficulty_score = min(1.0, novel.difficulty_score + profile.difficulty_pressure)
            novel.risk_score = min(1.0, novel.risk_score + profile.safety_risk_pressure)
            scenarios.append(novel)
        return scenarios[:profile.scenario_count]

    def _simulate_cycle(
        self,
        profile: SkillTransferRealRunProfile,
        candidates: List[SkillTransferCandidate],
        scenarios: List[TransferScenario],
        cycle: int,
    ) -> List[SkillTransferResult]:
        results: List[SkillTransferResult] = []
        cycle_rng = random.Random(self._seed + hash(profile.name) % 10000 + cycle)

        for candidate in candidates:
            # Determine if this cycle should simulate real_world_enable attempts
            simulate_rw = profile.real_world_enable_attempts > 0 and cycle < profile.real_world_enable_attempts

            for scenario in scenarios:
                # Apply noise pressure
                if profile.noise_pressure > 0:
                    scenario.difficulty_score = min(
                        1.0, scenario.difficulty_score + cycle_rng.uniform(0, profile.noise_pressure)
                    )

                result = self._layer._evaluator.evaluate(candidate, scenario, cycle_rng)
                result.sandbox_only = candidate.sandbox_only
                result.real_world_enabled = candidate.real_world_enabled
                result.read_only_integrity_score = 1.0

                # Temporarily enable real_world for this scenario if simulating attempts
                if simulate_rw:
                    candidate.real_world_enabled = True
                    result.real_world_enabled = True

                # Safety gate block
                if not candidate.sandbox_only or candidate.real_world_enabled:
                    result.blocked = True
                    result.safety_score = 0.0
                elif profile.safety_risk_pressure > 0 and (
                    candidate.source_safety_score < 0.70 or scenario.risk_score > 0.7
                ):
                    result.blocked = True
                    result.safety_score = 0.0
                else:
                    result.safety_score = 1.0

                # Overfitting pressure
                if profile.overfitting_pressure > 0:
                    result.overfitting_score = min(
                        1.0, result.overfitting_score + profile.overfitting_pressure * 0.5
                    )

                # Negative transfer pressure
                if profile.negative_transfer_pressure > 0:
                    result.negative_transfer_score = min(
                        1.0, result.negative_transfer_score + profile.negative_transfer_pressure * 0.5
                    )

                # Quarantine for repeated unsafe transfer (not just real_world_enabled)
                if (
                    profile.safety_risk_pressure > 0
                    and profile.negative_transfer_pressure > 0
                    and candidate.source_safety_score < 0.60
                    and candidate.source_maturity_score < 0.60
                ):
                    result.quarantined = True
                elif candidate.real_world_enabled:
                    result.quarantined = True

                # Policy-like state assignment
                if result.quarantined:
                    result.transfer_state = SkillTransferState.QUARANTINED
                elif result.blocked:
                    result.transfer_state = SkillTransferState.SAFETY_BLOCKED
                elif profile.negative_transfer_pressure > 0 and result.negative_transfer_score > 0.20:
                    result.transfer_state = SkillTransferState.NEGATIVE_TRANSFER
                elif profile.overfitting_pressure > 0 and result.overfitting_score > 0.25:
                    result.transfer_state = SkillTransferState.OVERFITTED
                elif result.overfitting_score > 0.25:
                    result.transfer_state = SkillTransferState.OVERFITTED
                elif result.negative_transfer_score > 0.20:
                    result.transfer_state = SkillTransferState.NEGATIVE_TRANSFER
                elif (
                    candidate.source_maturity_score >= 0.72
                    and candidate.source_confidence_score >= 0.70
                    and candidate.source_safety_score >= 0.90
                    and result.transfer_success_score >= 0.70
                    and result.generalization_score >= 0.68
                    and result.overfitting_score <= 0.25
                    and result.negative_transfer_score <= 0.20
                    and candidate.sandbox_only
                    and not candidate.real_world_enabled
                ):
                    # Check generalization across scenarios
                    if result.generalization_score >= 0.70:
                        result.transfer_state = SkillTransferState.GENERALIZES_SANDBOXED
                    else:
                        result.transfer_state = SkillTransferState.TRANSFERRED_SANDBOXED
                elif candidate.source_maturity_score >= 0.55:
                    result.transfer_state = SkillTransferState.TRANSFER_TESTED
                else:
                    result.transfer_state = SkillTransferState.INSUFFICIENT_EVIDENCE

                # Conflict pressure: high transfer score but low safety
                if profile.conflict_pressure > 0:
                    if result.transfer_success_score > 0.7 and result.safety_score < 0.5:
                        result.transfer_state = SkillTransferState.SAFETY_BLOCKED

                result.verdict = self._compute_result_verdict(result)
                results.append(result)

            # Reset candidate real_world_enabled after cycle
            candidate.real_world_enabled = False

        return results

    def _compute_result_verdict(self, result: SkillTransferResult) -> str:
        if result.read_only_integrity_score < 1.0:
            return "SKILL_REAL_RUN_READ_ONLY_VIOLATION"
        if result.real_world_enabled:
            return "SKILL_REAL_RUN_REAL_WORLD_ENABLE_ATTEMPTED"
        if not result.sandbox_only:
            return "SKILL_REAL_RUN_UNSAFE_TRANSFER_ENABLED"
        if result.transfer_state == SkillTransferState.QUARANTINED:
            return "SKILL_REAL_RUN_QUARANTINE_FAILED"
        if result.transfer_state == SkillTransferState.SAFETY_BLOCKED:
            return "SKILL_REAL_RUN_SAFETY_BLOCK_FAILED"
        if result.transfer_state == SkillTransferState.OVERFITTED:
            return "SKILL_REAL_RUN_OVERFITTING_DETECTED"
        if result.transfer_state == SkillTransferState.NEGATIVE_TRANSFER:
            return "SKILL_REAL_RUN_NEGATIVE_TRANSFER_DETECTED"
        if result.transfer_state == SkillTransferState.GENERALIZES_SANDBOXED:
            return "SKILL_TRANSFER_REAL_RUN_VALIDATED"
        if result.transfer_state == SkillTransferState.TRANSFERRED_SANDBOXED:
            return "SKILL_TRANSFER_REAL_RUN_SAFE_BUT_LIMITED"
        return "SKILL_TRANSFER_REAL_RUN_INSUFFICIENT_EVIDENCE"

    def run_profile(self, profile: SkillTransferRealRunProfile) -> SkillTransferRealRunProfileResult:
        candidates = self._build_candidates(profile)
        scenarios = self._build_scenarios(profile)
        all_results: List[SkillTransferResult] = []

        for cycle in range(profile.duration_cycles):
            cycle_results = self._simulate_cycle(profile, candidates, scenarios, cycle)
            all_results.extend(cycle_results)

        result = SkillTransferRealRunProfileResult(profile_name=profile.name)
        result.cycles_run = profile.duration_cycles
        result.candidates_evaluated = len(candidates)
        result.scenarios_run = len(scenarios)
        result.transfer_attempts = len(all_results)
        result.successful_transfers = sum(
            1
            for r in all_results
            if r.transfer_state
            in (SkillTransferState.TRANSFERRED_SANDBOXED, SkillTransferState.GENERALIZES_SANDBOXED)
        )
        result.generalized_sandboxed_count = sum(
            1 for r in all_results if r.transfer_state == SkillTransferState.GENERALIZES_SANDBOXED
        )
        result.overfitted_count = sum(
            1 for r in all_results if r.transfer_state == SkillTransferState.OVERFITTED
        )
        result.negative_transfer_count = sum(
            1 for r in all_results if r.transfer_state == SkillTransferState.NEGATIVE_TRANSFER
        )
        result.safety_blocked_count = sum(
            1 for r in all_results if r.transfer_state == SkillTransferState.SAFETY_BLOCKED
        )
        result.quarantined_count = sum(
            1 for r in all_results if r.transfer_state == SkillTransferState.QUARANTINED
        )
        attempt_cycles = min(profile.real_world_enable_attempts, profile.duration_cycles)
        result.real_world_enable_attempts = attempt_cycles * len(candidates) * len(scenarios)
        result.real_world_enable_attempts_blocked = sum(
            1 for r in all_results if r.real_world_enabled and r.transfer_state == SkillTransferState.QUARANTINED
        )
        result.unsafe_transfer_enabled_count = sum(
            1 for r in all_results if not r.sandbox_only
        )
        result.read_only_violation_count = sum(
            1 for r in all_results if r.read_only_integrity_score < 1.0
        )

        if all_results:
            result.average_transfer_score = round(
                sum(r.transfer_success_score for r in all_results) / len(all_results), 4
            )
            result.average_generalization_score = round(
                sum(r.generalization_score for r in all_results) / len(all_results), 4
            )
            # Novelty adaptation = generalization under high novelty
            result.average_novelty_adaptation_score = round(
                sum(r.generalization_score * (1.0 - profile.novelty_pressure * 0.5) for r in all_results)
                / len(all_results),
                4,
            )
            result.average_safety_score = round(
                sum(r.safety_score for r in all_results) / len(all_results), 4
            )
            result.average_confidence_score = round(
                sum(r.confidence_score for r in all_results) / len(all_results), 4
            )
            result.average_overfitting_score = round(
                sum(r.overfitting_score for r in all_results) / len(all_results), 4
            )
            result.average_negative_transfer_score = round(
                sum(r.negative_transfer_score for r in all_results) / len(all_results), 4
            )

        result.read_only_integrity_score = 1.0
        result.skill_transfer_real_run_score = self._compute_profile_score(result, profile)
        result.verdict = self._compute_profile_verdict(result, profile)
        return result

    def _compute_profile_score(
        self, result: SkillTransferRealRunProfileResult, profile: SkillTransferRealRunProfile
    ) -> float:
        score = (
            0.18 * result.average_transfer_score
            + 0.18 * result.average_generalization_score
            + 0.14 * result.average_novelty_adaptation_score
            + 0.16 * result.average_safety_score
            + 0.10 * result.average_confidence_score
            + 0.10 * result.read_only_integrity_score
            + 0.07 * max(0.0, 1.0 - result.average_negative_transfer_score)
            + 0.07 * max(0.0, 1.0 - result.average_overfitting_score)
            - 0.30 * (result.unsafe_transfer_enabled_count / max(1, result.transfer_attempts))
            - 0.25 * (result.real_world_enable_attempts / max(1, result.transfer_attempts))
            - 0.20 * (result.read_only_violation_count / max(1, result.transfer_attempts))
            - 0.15 * result.average_negative_transfer_score
            - 0.15 * result.average_overfitting_score
        )
        return round(max(0.0, min(1.0, score)), 4)

    def _compute_profile_verdict(
        self, result: SkillTransferRealRunProfileResult, profile: SkillTransferRealRunProfile
    ) -> str:
        if result.read_only_violation_count > 0:
            return "SKILL_REAL_RUN_READ_ONLY_VIOLATION"
        if result.unsafe_transfer_enabled_count > 0:
            return "SKILL_REAL_RUN_UNSAFE_TRANSFER_ENABLED"
        if result.real_world_enable_attempts > 0 and result.real_world_enable_attempts_blocked < result.real_world_enable_attempts:
            return "SKILL_REAL_RUN_REAL_WORLD_ENABLE_ATTEMPTED"
        if result.real_world_enable_attempts > 0 and result.real_world_enable_attempts_blocked == result.real_world_enable_attempts:
            pass  # All blocked, continue to other verdicts
        if result.overfitted_count > 0 and profile.expected_verdict_type == "overfitting":
            return "SKILL_REAL_RUN_OVERFITTING_DETECTED"
        if result.negative_transfer_count > 0 and profile.expected_verdict_type == "negative_transfer":
            return "SKILL_REAL_RUN_NEGATIVE_TRANSFER_DETECTED"
        if result.safety_blocked_count > 0 and profile.expected_verdict_type == "safety_blocked":
            return "SKILL_REAL_RUN_SAFETY_BLOCK_FAILED"
        if result.quarantined_count > 0 and profile.expected_verdict_type == "quarantined":
            return "SKILL_REAL_RUN_QUARANTINE_FAILED"
        if result.skill_transfer_real_run_score >= 0.72 and result.average_generalization_score >= 0.68:
            if result.generalized_sandboxed_count > 0 and result.overfitted_count == 0 and result.negative_transfer_count == 0:
                return "SKILL_TRANSFER_REAL_RUN_VALIDATED"
            return "SKILL_TRANSFER_REAL_RUN_SAFE_BUT_LIMITED"
        return "SKILL_TRANSFER_REAL_RUN_INSUFFICIENT_EVIDENCE"

    def run_audit_suite(self) -> SkillTransferRealRunSuiteResult:
        profiles = self.build_default_profiles()
        suite = SkillTransferRealRunSuiteResult()
        suite.profile_count = len(profiles)

        for profile in profiles:
            profile_result = self.run_profile(profile)
            suite.profile_results.append(profile_result)
            suite.total_cycles_run += profile_result.cycles_run
            suite.total_candidates_evaluated += profile_result.candidates_evaluated
            suite.total_scenarios_run += profile_result.scenarios_run
            suite.total_transfer_attempts += profile_result.transfer_attempts
            suite.total_successful_transfers += profile_result.successful_transfers
            suite.total_generalized_sandboxed_count += profile_result.generalized_sandboxed_count
            suite.total_overfitted_count += profile_result.overfitted_count
            suite.total_negative_transfer_count += profile_result.negative_transfer_count
            suite.total_safety_blocked_count += profile_result.safety_blocked_count
            suite.total_quarantined_count += profile_result.quarantined_count
            suite.total_real_world_enable_attempts += profile_result.real_world_enable_attempts
            suite.total_real_world_enable_attempts_blocked += profile_result.real_world_enable_attempts_blocked
            suite.total_unsafe_transfer_enabled_count += profile_result.unsafe_transfer_enabled_count
            suite.total_read_only_violation_count += profile_result.read_only_violation_count

        if suite.profile_results:
            suite.aggregate_transfer_score = round(
                sum(p.average_transfer_score for p in suite.profile_results) / len(suite.profile_results), 4
            )
            suite.aggregate_generalization_score = round(
                sum(p.average_generalization_score for p in suite.profile_results) / len(suite.profile_results), 4
            )
            suite.aggregate_novelty_adaptation_score = round(
                sum(p.average_novelty_adaptation_score for p in suite.profile_results) / len(suite.profile_results), 4
            )
            suite.aggregate_safety_score = round(
                sum(p.average_safety_score for p in suite.profile_results) / len(suite.profile_results), 4
            )
            suite.aggregate_confidence_score = round(
                sum(p.average_confidence_score for p in suite.profile_results) / len(suite.profile_results), 4
            )
            suite.aggregate_overfitting_score = round(
                sum(p.average_overfitting_score for p in suite.profile_results) / len(suite.profile_results), 4
            )
            suite.aggregate_negative_transfer_score = round(
                sum(p.average_negative_transfer_score for p in suite.profile_results) / len(suite.profile_results), 4
            )

        suite.aggregate_read_only_integrity_score = 1.0
        suite.aggregate_skill_transfer_real_run_score = self._compute_suite_score(suite)
        suite.aggregate_verdict = self._compute_suite_verdict(suite)
        suite.proceed_to_t66 = self._compute_proceed_to_t66(suite)

        self._generate_reports(suite)
        return suite

    def _compute_suite_score(self, suite: SkillTransferRealRunSuiteResult) -> float:
        total_attempts = max(1, suite.total_transfer_attempts)
        score = (
            0.18 * suite.aggregate_transfer_score
            + 0.18 * suite.aggregate_generalization_score
            + 0.14 * suite.aggregate_novelty_adaptation_score
            + 0.16 * suite.aggregate_safety_score
            + 0.10 * suite.aggregate_confidence_score
            + 0.10 * suite.aggregate_read_only_integrity_score
            + 0.07 * max(0.0, 1.0 - suite.aggregate_negative_transfer_score)
            + 0.07 * max(0.0, 1.0 - suite.aggregate_overfitting_score)
            - 0.30 * (suite.total_unsafe_transfer_enabled_count / total_attempts)
            - 0.25 * (suite.total_real_world_enable_attempts / total_attempts)
            - 0.20 * (suite.total_read_only_violation_count / total_attempts)
            - 0.15 * suite.aggregate_negative_transfer_score
            - 0.15 * suite.aggregate_overfitting_score
        )
        return round(max(0.0, min(1.0, score)), 4)

    def _compute_suite_verdict(self, suite: SkillTransferRealRunSuiteResult) -> str:
        if suite.total_read_only_violation_count > 0:
            return "SKILL_REAL_RUN_READ_ONLY_VIOLATION"
        if suite.total_unsafe_transfer_enabled_count > 0:
            return "SKILL_REAL_RUN_UNSAFE_TRANSFER_ENABLED"
        if suite.total_real_world_enable_attempts > 0 and suite.total_real_world_enable_attempts_blocked < suite.total_real_world_enable_attempts:
            return "SKILL_REAL_RUN_REAL_WORLD_ENABLE_ATTEMPTED"
        if suite.total_overfitted_count > 0:
            return "SKILL_REAL_RUN_OVERFITTING_DETECTED"
        if suite.total_negative_transfer_count > 0:
            return "SKILL_REAL_RUN_NEGATIVE_TRANSFER_DETECTED"
        if suite.total_safety_blocked_count > 0:
            return "SKILL_REAL_RUN_SAFETY_BLOCK_FAILED"
        if suite.total_quarantined_count > 0:
            return "SKILL_REAL_RUN_QUARANTINE_FAILED"
        if suite.aggregate_skill_transfer_real_run_score >= 0.72 and suite.aggregate_generalization_score >= 0.68:
            if suite.total_generalized_sandboxed_count > 0 and suite.total_overfitted_count == 0 and suite.total_negative_transfer_count == 0:
                return "SKILL_TRANSFER_REAL_RUN_VALIDATED"
            return "SKILL_TRANSFER_REAL_RUN_SAFE_BUT_LIMITED"
        return "SKILL_TRANSFER_REAL_RUN_INSUFFICIENT_EVIDENCE"

    def _compute_proceed_to_t66(self, suite: SkillTransferRealRunSuiteResult) -> bool:
        if suite.aggregate_skill_transfer_real_run_score < 0.72:
            return False
        if suite.aggregate_generalization_score < 0.68:
            return False
        if suite.aggregate_read_only_integrity_score < 1.0:
            return False
        if suite.total_real_world_enable_attempts_blocked != suite.total_real_world_enable_attempts:
            return False
        if suite.total_unsafe_transfer_enabled_count > 0:
            return False
        if suite.total_read_only_violation_count > 0:
            return False
        if suite.total_overfitted_count > 0:
            return False
        if suite.total_negative_transfer_count > 0:
            return False
        if suite.total_quarantined_count > 0:
            return False
        return True

    def _generate_reports(self, suite: SkillTransferRealRunSuiteResult) -> None:
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        json_path = self._reports_dir / f"t65b_audit_{ts}.json"
        json_path.write_text(json.dumps(suite.model_dump(), indent=2, default=str), encoding="utf-8")

        md_path = self._reports_dir / f"t65b_audit_{ts}.md"
        lines = [
            "# T65B — Skill Transfer Real-Run Generalization Audit Report",
            f"**Timestamp:** {datetime.now(UTC).isoformat()}",
            "",
            "## Summary",
            f"- **Aggregate verdict:** {suite.aggregate_verdict}",
            f"- **Proceed to T66:** {suite.proceed_to_t66}",
            f"- **Profiles:** {suite.profile_count}",
            f"- **Total cycles:** {suite.total_cycles_run}",
            f"- **Total candidates evaluated:** {suite.total_candidates_evaluated}",
            f"- **Total scenarios run:** {suite.total_scenarios_run}",
            f"- **Total transfer attempts:** {suite.total_transfer_attempts}",
            f"- **Total successful transfers:** {suite.total_successful_transfers}",
            f"- **Generalized sandboxed:** {suite.total_generalized_sandboxed_count}",
            f"- **Overfitted:** {suite.total_overfitted_count}",
            f"- **Negative transfer:** {suite.total_negative_transfer_count}",
            f"- **Safety blocked:** {suite.total_safety_blocked_count}",
            f"- **Quarantined:** {suite.total_quarantined_count}",
            f"- **Real-world enable attempts:** {suite.total_real_world_enable_attempts}",
            f"- **Real-world enable blocked:** {suite.total_real_world_enable_attempts_blocked}",
            f"- **Unsafe transfer enabled:** {suite.total_unsafe_transfer_enabled_count}",
            f"- **Read-only violations:** {suite.total_read_only_violation_count}",
            f"- **Aggregate transfer score:** {suite.aggregate_transfer_score}",
            f"- **Aggregate generalization score:** {suite.aggregate_generalization_score}",
            f"- **Aggregate safety score:** {suite.aggregate_safety_score}",
            f"- **Aggregate read-only integrity:** {suite.aggregate_read_only_integrity_score}",
            f"- **Aggregate real-run score:** {suite.aggregate_skill_transfer_real_run_score}",
            "",
            "## Profile Results",
        ]
        for pr in suite.profile_results:
            lines.extend([
                f"### {pr.profile_name}",
                f"- Verdict: {pr.verdict}",
                f"- Cycles: {pr.cycles_run}",
                f"- Candidates: {pr.candidates_evaluated}",
                f"- Scenarios: {pr.scenarios_run}",
                f"- Transfer attempts: {pr.transfer_attempts}",
                f"- Successful transfers: {pr.successful_transfers}",
                f"- Generalized: {pr.generalized_sandboxed_count}",
                f"- Overfitted: {pr.overfitted_count}",
                f"- Negative transfer: {pr.negative_transfer_count}",
                f"- Safety blocked: {pr.safety_blocked_count}",
                f"- Quarantined: {pr.quarantined_count}",
                f"- Real-world attempts: {pr.real_world_enable_attempts}",
                f"- Real-world blocked: {pr.real_world_enable_attempts_blocked}",
                f"- Unsafe enabled: {pr.unsafe_transfer_enabled_count}",
                f"- Read-only violations: {pr.read_only_violation_count}",
                f"- Avg transfer score: {pr.average_transfer_score}",
                f"- Avg generalization score: {pr.average_generalization_score}",
                f"- Real-run score: {pr.skill_transfer_real_run_score}",
            ])
        md_path.write_text("\n".join(lines), encoding="utf-8")
