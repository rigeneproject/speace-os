import random
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.world_model.world_model_models import (
    WorldConstraint,
    WorldEntity,
    WorldEntityType,
    WorldModelAuditProfile,
    WorldModelAuditResult,
    WorldModelAuditSuiteResult,
    WorldModelSnapshot,
    WorldZone,
)
from speace_core.cellular_brain.world_model.world_model_sandbox import ExternalWorldModelSandbox


class WorldModelAudit:
    """Executes T61 audit profiles, calculates scores and verdicts, generates reports."""

    def __init__(self, seed: int = 42):
        self._seed = seed
        self._rng = random.Random(seed)
        self._sandbox = ExternalWorldModelSandbox(seed=seed)

    def _make_profile(self, name: str, scenario_type: str = "baseline", **kwargs) -> WorldModelAuditProfile:
        return WorldModelAuditProfile(name=name, scenario_type=scenario_type, **kwargs)

    def run_audit_suite(self) -> WorldModelAuditSuiteResult:
        profiles = [
            self._make_profile("world_model_baseline_snapshot", "baseline", entity_count=5, zone_count=2),
            self._make_profile("world_model_multi_entity_environment", "baseline", entity_count=8, zone_count=3),
            self._make_profile("world_model_energy_scarcity_scenario", "scarcity", entity_count=5, zone_count=2),
            self._make_profile("world_model_infrastructure_stress_scenario", "stress", entity_count=5, zone_count=2),
            self._make_profile("world_model_safety_hazard_scenario", "safety", entity_count=5, zone_count=2, expected_risk_type="safety"),
            self._make_profile("world_model_conflicting_entities", "conflict", entity_count=4, zone_count=2, conflict_level=0.7),
            self._make_profile("world_model_constraint_violation_detection", "baseline", entity_count=3, zone_count=1),
            self._make_profile("world_model_causal_chain_prediction", "baseline", entity_count=6, zone_count=2),
            self._make_profile("world_model_uncertainty_growth", "baseline", entity_count=5, zone_count=2, uncertainty_level=0.6),
            self._make_profile("world_model_simulated_action_blocked", "baseline", entity_count=3, zone_count=1),
            self._make_profile("world_model_bus_publication_read_only", "baseline", entity_count=4, zone_count=2),
            self._make_profile("world_model_full_sandbox_mix", "baseline", entity_count=7, zone_count=3, conflict_level=0.3, uncertainty_level=0.3, expected_risk_type="mixed"),
        ]

        profile_results: List[WorldModelAuditResult] = []
        totals = {
            "snapshots": 0,
            "scenarios": 0,
            "simulations": 0,
            "chains": 0,
            "contradictions": 0,
            "violations": 0,
            "unsafe_blocked": 0,
            "bus_publications": 0,
            "read_only_violations": 0,
            "real_blocked": 0,
        }
        coherence_scores: List[float] = []
        prediction_scores: List[float] = []
        safety_scores: List[float] = []
        sandbox_scores: List[float] = []
        read_only_scores: List[float] = []

        for profile in profiles:
            result = self._run_profile(profile)
            profile_results.append(result)
            totals["snapshots"] += result.snapshots_generated
            totals["scenarios"] += result.scenarios_built
            totals["simulations"] += result.simulations_run
            totals["chains"] += result.causal_chains_detected
            totals["contradictions"] += result.contradictions_detected
            totals["violations"] += result.constraint_violations_detected
            totals["unsafe_blocked"] += result.unsafe_simulated_actions_blocked
            totals["bus_publications"] += result.bus_publications
            totals["read_only_violations"] += result.read_only_violations
            totals["real_blocked"] += result.real_action_attempts_blocked
            coherence_scores.append(result.average_world_model_coherence_score)
            prediction_scores.append(result.average_prediction_quality_score)
            safety_scores.append(result.average_safety_preservation_score)
            sandbox_scores.append(result.world_model_sandbox_score)

        n = len(profile_results) if profile_results else 1
        agg_coherence = sum(coherence_scores) / n
        agg_prediction = sum(prediction_scores) / n
        agg_safety = sum(safety_scores) / n
        agg_sandbox = sum(sandbox_scores) / n
        agg_read_only = 1.0 if totals["read_only_violations"] == 0 else 0.0

        for pr in profile_results:
            pr.average_world_model_coherence_score = round(agg_coherence, 4)
            pr.average_prediction_quality_score = round(agg_prediction, 4)
            pr.average_safety_preservation_score = round(agg_safety, 4)

        aggregate_verdict = self._compute_aggregate_verdict(
            agg_sandbox, agg_read_only, totals["real_blocked"], totals["unsafe_blocked"],
            totals["violations"], totals["contradictions"], totals["read_only_violations"],
        )

        suite = WorldModelAuditSuiteResult(
            profile_count=len(profiles),
            total_snapshots_generated=totals["snapshots"],
            total_scenarios_built=totals["scenarios"],
            total_simulations_run=totals["simulations"],
            total_causal_chains_detected=totals["chains"],
            total_contradictions_detected=totals["contradictions"],
            total_constraint_violations_detected=totals["violations"],
            total_unsafe_simulated_actions_blocked=totals["unsafe_blocked"],
            total_bus_publications=totals["bus_publications"],
            total_read_only_violations=totals["read_only_violations"],
            total_real_action_attempts_blocked=totals["real_blocked"],
            aggregate_world_model_coherence_score=round(agg_coherence, 4),
            aggregate_prediction_quality_score=round(agg_prediction, 4),
            aggregate_safety_preservation_score=round(agg_safety, 4),
            aggregate_read_only_integrity_score=round(agg_read_only, 4),
            aggregate_world_model_sandbox_score=round(agg_sandbox, 4),
            aggregate_verdict=aggregate_verdict,
            proceed_to_t61b=(aggregate_verdict == "EXTERNAL_WORLD_MODEL_SANDBOX_VALIDATED"),
            profile_results=profile_results,
        )

        self._sandbox.generate_sandbox_report(suite.model_dump())
        return suite

    def _run_profile(self, profile: WorldModelAuditProfile) -> WorldModelAuditResult:
        result = WorldModelAuditResult(profile_name=profile.name)
        entities = []
        for i in range(profile.entity_count):
            etype = WorldEntityType.UNKNOWN
            if i % 4 == 0:
                etype = WorldEntityType.ENVIRONMENT
            elif i % 4 == 1:
                etype = WorldEntityType.SENSOR_SOURCE
            elif i % 4 == 2:
                etype = WorldEntityType.ENERGY_SYSTEM
            else:
                etype = WorldEntityType.INFRASTRUCTURE
            state = {"status": "active", "value": self._rng.uniform(0.0, 1.0)}
            if profile.conflict_level > 0.0 and i % 2 == 1:
                state["status"] = "inactive"
            if profile.uncertainty_level > 0.0:
                state["uncertainty"] = profile.uncertainty_level
            entities.append(
                WorldEntity(
                    entity_id=f"ent_{profile.name}_{i}",
                    entity_type=etype,
                    name=f"entity_{i}",
                    state=state,
                    confidence=max(0.0, 1.0 - profile.uncertainty_level),
                    uncertainty=profile.uncertainty_level,
                    safety_relevance=0.6 if profile.expected_risk_type == "safety" else 0.2,
                )
            )
        zones = []
        for z in range(profile.zone_count):
            zones.append(
                WorldZone(
                    zone_id=f"zone_{profile.name}_{z}",
                    name=f"zone_{z}",
                    entities=[e.entity_id for e in entities if self._rng.random() > 0.3],
                    environmental_pressure=self._rng.uniform(0.0, 0.3),
                    infrastructure_pressure=self._rng.uniform(0.0, 0.3),
                    energy_pressure=self._rng.uniform(0.0, 0.3),
                    safety_pressure=0.5 if profile.expected_risk_type == "safety" else 0.1,
                    uncertainty_score=profile.uncertainty_level,
                )
            )
        constraints = []
        if profile.name == "world_model_constraint_violation_detection":
            constraints.append(
                WorldConstraint(
                    constraint_id="hard_1",
                    name="safety_hard",
                    constraint_type="safety",
                    severity=0.9,
                    hard_constraint=True,
                    description="Hard safety constraint",
                )
            )
        snapshot = self._sandbox.build_world_model_snapshot(entities=entities, zones=zones)
        snapshot.constraints = constraints
        result.snapshots_generated = 1

        scenario = self._sandbox._scenario_builder.build_scenario_from_profile(
            snapshot, profile.scenario_type, profile.conflict_level, profile.uncertainty_level
        )
        if profile.name == "world_model_simulated_action_blocked":
            scenario.simulated_actions.append({"type": "actuate", "target_real": True})
        result.scenarios_built = 1

        causal, impact = self._sandbox.run_scenario_simulation(snapshot, scenario)
        result.simulations_run = 1
        result.causal_chains_detected = causal.causal_chains_detected
        result.contradictions_detected = causal.contradictions_detected
        result.constraint_violations_detected = causal.constraint_violations_detected

        policy = self._sandbox._constraint_evaluator
        for action in scenario.simulated_actions:
            blocked, _ = policy.block_real_action_attempt(action)
            if blocked:
                result.unsafe_simulated_actions_blocked += 1
                result.real_action_attempts_blocked += 1

        msg = self._sandbox.publish_read_only_world_model_summary(snapshot)
        safe, _ = self._sandbox._constraint_evaluator.enforce_read_only_constraints(snapshot)
        if safe:
            result.bus_publications = 1

        world_model_sandbox_score = self._compute_sandbox_score(
            snapshot, causal, impact, result
        )
        result.world_model_sandbox_score = round(world_model_sandbox_score, 4)
        result.average_world_model_coherence_score = round(snapshot.global_coherence_score, 4)
        result.average_prediction_quality_score = round(causal.predicted_coherence_score, 4)
        result.average_safety_preservation_score = round(1.0 - causal.predicted_safety_pressure, 4)
        result.verdict = self._compute_profile_verdict(result, profile)
        return result

    def _compute_sandbox_score(
        self,
        snapshot: WorldModelSnapshot,
        causal: "CausalSimulationResult",
        impact: "ImpactAssessment",
        result: WorldModelAuditResult,
    ) -> float:
        coherence = snapshot.global_coherence_score
        prediction = causal.predicted_coherence_score
        safety = max(0.0, 1.0 - causal.predicted_safety_pressure)
        constraint_detection = 1.0 if result.constraint_violations_detected > 0 or result.profile_name != "world_model_constraint_violation_detection" else 0.0
        if result.profile_name == "world_model_constraint_violation_detection" and result.constraint_violations_detected > 0:
            constraint_detection = 1.0
        causal_consistency = 1.0 if result.contradictions_detected > 0 or result.profile_name not in ("world_model_conflicting_entities", "world_model_full_sandbox_mix") else 0.0
        if result.profile_name in ("world_model_conflicting_entities", "world_model_full_sandbox_mix") and result.contradictions_detected > 0:
            causal_consistency = 1.0
        read_only_integrity = 1.0 if result.read_only_violations == 0 else 0.0
        bus_integrity = 1.0 if result.bus_publications > 0 or result.profile_name != "world_model_bus_publication_read_only" else 0.0
        real_action_attempt_score = 1.0 if result.real_action_attempts_blocked > 0 and result.profile_name == "world_model_simulated_action_blocked" else 0.0
        unsafe_simulated_action_score = 1.0 if result.unsafe_simulated_actions_blocked > 0 and result.profile_name == "world_model_simulated_action_blocked" else 0.0
        undetected_constraint = 1.0 if result.profile_name == "world_model_constraint_violation_detection" and result.constraint_violations_detected == 0 else 0.0
        undetected_contradiction = 1.0 if result.profile_name in ("world_model_conflicting_entities", "world_model_full_sandbox_mix") and result.contradictions_detected == 0 else 0.0

        score = (
            0.20 * coherence
            + 0.18 * prediction
            + 0.18 * safety
            + 0.14 * constraint_detection
            + 0.12 * causal_consistency
            + 0.10 * read_only_integrity
            + 0.08 * bus_integrity
            - 0.25 * real_action_attempt_score
            - 0.20 * unsafe_simulated_action_score
            - 0.15 * undetected_constraint
            - 0.10 * undetected_contradiction
        )
        return max(0.0, min(1.0, score))

    def _compute_profile_verdict(self, result: WorldModelAuditResult, profile: WorldModelAuditProfile) -> str:
        if result.real_action_attempts_blocked > 0 and result.unsafe_simulated_actions_blocked > 0 and profile.name == "world_model_simulated_action_blocked":
            return "EXTERNAL_WORLD_MODEL_SAFE_BUT_PASSIVE"
        if result.contradictions_detected > 0 and profile.name in ("world_model_conflicting_entities", "world_model_full_sandbox_mix"):
            return "EXTERNAL_WORLD_MODEL_SANDBOX_VALIDATED"
        if result.constraint_violations_detected > 0 and profile.name == "world_model_constraint_violation_detection":
            return "EXTERNAL_WORLD_MODEL_SANDBOX_VALIDATED"
        if result.world_model_sandbox_score >= 0.72 and result.read_only_violations == 0:
            return "EXTERNAL_WORLD_MODEL_SANDBOX_VALIDATED"
        if result.read_only_violations > 0:
            return "WORLD_MODEL_READ_ONLY_VIOLATION"
        return "EXTERNAL_WORLD_MODEL_INSUFFICIENT_EVIDENCE"

    def _compute_aggregate_verdict(
        self,
        agg_sandbox: float,
        agg_read_only: float,
        real_blocked: int,
        unsafe_blocked: int,
        violations: int,
        contradictions: int,
        read_only_violations: int,
    ) -> str:
        if read_only_violations > 0:
            return "WORLD_MODEL_READ_ONLY_VIOLATION"
        if agg_sandbox >= 0.72 and agg_read_only == 1.0 and real_blocked >= 0 and unsafe_blocked > 0 and violations > 0 and contradictions > 0:
            return "EXTERNAL_WORLD_MODEL_SANDBOX_VALIDATED"
        if agg_sandbox >= 0.60 and agg_read_only == 1.0:
            return "EXTERNAL_WORLD_MODEL_SAFE_BUT_PASSIVE"
        return "EXTERNAL_WORLD_MODEL_INSUFFICIENT_EVIDENCE"
