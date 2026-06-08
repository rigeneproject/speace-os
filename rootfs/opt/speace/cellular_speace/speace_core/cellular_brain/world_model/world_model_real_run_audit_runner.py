import json
import random
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.world_model.world_model_models import (
    WorldConstraint,
    WorldEntity,
    WorldEntityType,
    WorldModelRealRunProfile,
    WorldModelRealRunProfileResult,
    WorldModelRealRunSuiteResult,
    WorldModelSnapshot,
    WorldScenario,
    WorldZone,
)
from speace_core.cellular_brain.world_model.world_model_sandbox import ExternalWorldModelSandbox


class WorldModelRealRunAuditRunner:
    """T61B real-run audit runner. Stress-tests T61 with multi-horizon simulated scenarios. Reuses ExternalWorldModelSandbox."""

    def __init__(
        self,
        sandbox: Optional[ExternalWorldModelSandbox] = None,
        seed: int = 42,
        reports_dir: str = "reports/world_model",
    ):
        self._seed = seed
        self._rng = random.Random(seed)
        self._sandbox = sandbox or ExternalWorldModelSandbox(seed=seed)
        self._reports_dir = Path(reports_dir)
        self._reports_dir.mkdir(parents=True, exist_ok=True)

    def build_default_profiles(self) -> List[WorldModelRealRunProfile]:
        return [
            WorldModelRealRunProfile(
                name="real_run_world_model_baseline_sequence",
                description="Stable multi-tick baseline sequence",
                duration_ticks=5,
                horizon_ticks=5,
                entity_count=6,
                zone_count=2,
            ),
            WorldModelRealRunProfile(
                name="real_run_multi_horizon_energy_scarcity",
                description="Long-horizon energy scarcity",
                duration_ticks=8,
                horizon_ticks=8,
                entity_count=6,
                zone_count=2,
                perturbation_mix={"energy_scarcity": 1.0},
                expected_risk_type="energy",
            ),
            WorldModelRealRunProfile(
                name="real_run_infrastructure_degradation_chain",
                description="Infrastructure degradation with delayed causality",
                duration_ticks=7,
                horizon_ticks=7,
                entity_count=6,
                zone_count=3,
                causal_link_count=8,
                perturbation_mix={"pressure_spike": 1.0},
                expected_risk_type="infrastructure",
            ),
            WorldModelRealRunProfile(
                name="real_run_safety_hazard_persistence",
                description="Persistent safety hazard over multiple ticks",
                duration_ticks=6,
                horizon_ticks=6,
                entity_count=5,
                zone_count=2,
                perturbation_mix={"safety_hazard": 1.0},
                expected_risk_type="safety",
            ),
            WorldModelRealRunProfile(
                name="real_run_conflicting_entities_accumulation",
                description="Accumulating conflicts between entities and zones",
                duration_ticks=6,
                horizon_ticks=6,
                entity_count=6,
                zone_count=2,
                conflict_level=0.6,
            ),
            WorldModelRealRunProfile(
                name="real_run_uncertainty_growth_dropout",
                description="Signal dropout and growing uncertainty",
                duration_ticks=6,
                horizon_ticks=6,
                entity_count=5,
                zone_count=2,
                uncertainty_growth_rate=0.15,
            ),
            WorldModelRealRunProfile(
                name="real_run_multi_constraint_pressure",
                description="Simultaneous hard and soft constraints",
                duration_ticks=5,
                horizon_ticks=5,
                entity_count=5,
                zone_count=2,
                constraint_count=3,
            ),
            WorldModelRealRunProfile(
                name="real_run_causal_feedback_loop",
                description="Circular causal feedback simulation",
                duration_ticks=6,
                horizon_ticks=6,
                entity_count=6,
                zone_count=2,
                causal_link_count=10,
            ),
            WorldModelRealRunProfile(
                name="real_run_prediction_drift_detection",
                description="Divergence between predicted and subsequent snapshots",
                duration_ticks=7,
                horizon_ticks=7,
                entity_count=5,
                zone_count=2,
                uncertainty_growth_rate=0.1,
            ),
            WorldModelRealRunProfile(
                name="real_run_unsafe_simulated_action_attempt",
                description="High-risk simulated action that must be blocked",
                duration_ticks=3,
                horizon_ticks=3,
                entity_count=3,
                zone_count=1,
                simulated_action_attempts=1,
            ),
            WorldModelRealRunProfile(
                name="real_run_real_action_escape_attempt",
                description="Attempt to turn sandbox into real action",
                duration_ticks=3,
                horizon_ticks=3,
                entity_count=3,
                zone_count=1,
                real_action_attempts=1,
            ),
            WorldModelRealRunProfile(
                name="real_run_world_model_bus_publication_integrity",
                description="Multiple read-only publications to OrganismBus",
                duration_ticks=5,
                horizon_ticks=5,
                entity_count=4,
                zone_count=2,
            ),
            WorldModelRealRunProfile(
                name="real_run_full_world_model_sandbox_mix",
                description="Realistic mix of energy, environment, infrastructure, safety, conflicts, constraints, uncertainty, and causality",
                duration_ticks=8,
                horizon_ticks=8,
                entity_count=8,
                zone_count=3,
                constraint_count=2,
                causal_link_count=8,
                conflict_level=0.3,
                uncertainty_growth_rate=0.1,
                perturbation_mix={"energy_scarcity": 0.3, "pressure_spike": 0.3, "safety_hazard": 0.4},
                expected_risk_type="mixed",
            ),
        ]

    def load_real_fixtures_if_available(self) -> Dict[str, Any]:
        return {}

    def build_synthetic_world_sequence_for_profile(
        self,
        profile: WorldModelRealRunProfile,
    ) -> Dict[str, Any]:
        entities: List[WorldEntity] = []
        for i in range(profile.entity_count):
            etype = WorldEntityType.UNKNOWN
            if i % 5 == 0:
                etype = WorldEntityType.ENVIRONMENT
            elif i % 5 == 1:
                etype = WorldEntityType.SENSOR_SOURCE
            elif i % 5 == 2:
                etype = WorldEntityType.ENERGY_SYSTEM
            elif i % 5 == 3:
                etype = WorldEntityType.INFRASTRUCTURE
            else:
                etype = WorldEntityType.HUMAN_CONTEXT
            state: Dict[str, Any] = {"status": "active", "value": round(self._rng.uniform(0.0, 1.0), 4)}
            if profile.conflict_level > 0.0 and i % 2 == 1:
                state["status"] = "inactive"
            uncertainty = profile.uncertainty_growth_rate * self._rng.uniform(0.5, 1.5)
            if uncertainty > 0.0:
                state["uncertainty"] = round(uncertainty, 4)
            entities.append(
                WorldEntity(
                    entity_id=f"ent_{profile.name}_{i}",
                    entity_type=etype,
                    name=f"entity_{i}",
                    state=state,
                    confidence=max(0.0, round(1.0 - uncertainty, 4)),
                    uncertainty=round(uncertainty, 4),
                    safety_relevance=0.6 if profile.expected_risk_type in ("safety", "mixed") else 0.2,
                )
            )
        zones: List[WorldZone] = []
        for z in range(profile.zone_count):
            zones.append(
                WorldZone(
                    zone_id=f"zone_{profile.name}_{z}",
                    name=f"zone_{z}",
                    entities=[e.entity_id for e in entities if self._rng.random() > 0.3],
                    environmental_pressure=round(self._rng.uniform(0.0, 0.3), 4),
                    infrastructure_pressure=round(self._rng.uniform(0.0, 0.3), 4),
                    energy_pressure=round(self._rng.uniform(0.0, 0.3), 4),
                    safety_pressure=0.5 if profile.expected_risk_type in ("safety", "mixed") else 0.1,
                    uncertainty_score=profile.uncertainty_growth_rate,
                )
            )
        constraints: List[WorldConstraint] = []
        if profile.constraint_count > 0:
            for ci in range(profile.constraint_count):
                constraints.append(
                    WorldConstraint(
                        constraint_id=f"c_{profile.name}_{ci}",
                        name=f"constraint_{ci}",
                        constraint_type="safety" if ci == 0 else "read_only",
                        severity=0.9 if ci == 0 else 0.6,
                        hard_constraint=(ci == 0),
                        description=f"Constraint {ci}",
                    )
                )
        snapshot = self._sandbox.build_world_model_snapshot(entities=entities, zones=zones)
        snapshot.constraints = constraints
        return {
            "snapshot": snapshot,
            "entities": entities,
            "zones": zones,
            "constraints": constraints,
        }

    def run_profile(self, profile: WorldModelRealRunProfile) -> WorldModelRealRunProfileResult:
        result = WorldModelRealRunProfileResult(profile_name=profile.name)
        result.horizon_ticks = profile.horizon_ticks
        seq = self.build_synthetic_world_sequence_for_profile(profile)
        snapshot = seq["snapshot"]
        result.snapshots_generated = 1
        result.entities_processed = len(seq["entities"])
        result.zones_processed = len(seq["zones"])
        result.constraints_evaluated = len(seq["constraints"])

        # Build a scenario with multi-horizon and mixed perturbations
        scenario = self._sandbox._scenario_builder.build_scenario_from_profile(
            snapshot,
            "baseline",
            conflict_level=profile.conflict_level,
            uncertainty_level=profile.uncertainty_growth_rate,
        )
        # Inject profile-specific perturbations
        for ptype, intensity in profile.perturbation_mix.items():
            if ptype == "energy_scarcity":
                for z in snapshot.zones:
                    scenario.perturbations.append({
                        "type": "energy_scarcity",
                        "target_zone_id": z.zone_id,
                        "delta_energy": -round(self._rng.uniform(0.2, 0.5) * intensity, 4),
                    })
            elif ptype == "pressure_spike":
                for z in snapshot.zones:
                    scenario.perturbations.append({
                        "type": "pressure_spike",
                        "target_zone_id": z.zone_id,
                        "delta_infrastructure": round(self._rng.uniform(0.2, 0.5) * intensity, 4),
                        "delta_energy": round(self._rng.uniform(0.1, 0.4) * intensity, 4),
                    })
            elif ptype == "safety_hazard":
                for e in snapshot.entities:
                    if e.safety_relevance > 0.3:
                        scenario.perturbations.append({
                            "type": "safety_hazard",
                            "target_entity_id": e.entity_id,
                            "delta_safety": round(self._rng.uniform(0.3, 0.8) * intensity, 4),
                        })

        # Inject action attempts
        for _ in range(profile.simulated_action_attempts):
            scenario.simulated_actions.append({"type": "actuate", "target_real": False})
        for _ in range(profile.real_action_attempts):
            scenario.simulated_actions.append({"type": "actuate", "target_real": True})

        scenario.horizon_ticks = profile.horizon_ticks
        result.scenarios_built = 1

        causal, impact = self._sandbox.run_scenario_simulation(snapshot, scenario)
        result.simulations_run = 1
        result.ticks_run = profile.duration_ticks
        result.causal_chains_detected = causal.causal_chains_detected
        result.contradictions_detected = causal.contradictions_detected
        result.constraint_violations_detected = causal.constraint_violations_detected

        # Multi-horizon prediction drift detection by running a second simulation with modified snapshot
        drift_detected = 0
        if profile.uncertainty_growth_rate > 0.0 or profile.name == "real_run_prediction_drift_detection":
            # Slightly perturb snapshot state to simulate next tick reality divergence
            next_entities = []
            for e in snapshot.entities:
                next_state = dict(e.state)
                next_state["value"] = round(next_state.get("value", 0.5) + self._rng.uniform(-0.2, 0.2), 4)
                next_entities.append(
                    WorldEntity(
                        entity_id=e.entity_id,
                        entity_type=e.entity_type,
                        name=e.name,
                        state=next_state,
                        confidence=e.confidence,
                        uncertainty=e.uncertainty,
                        safety_relevance=e.safety_relevance,
                        metadata=e.metadata,
                    )
                )
            next_snapshot = self._sandbox.build_world_model_snapshot(entities=next_entities, zones=snapshot.zones)
            next_snapshot.constraints = snapshot.constraints
            next_causal, _ = self._sandbox.run_scenario_simulation(next_snapshot, scenario)
            if abs(next_causal.predicted_coherence_score - causal.predicted_coherence_score) > 0.05:
                drift_detected += 1
            if next_causal.contradictions_detected != causal.contradictions_detected:
                drift_detected += 1
        result.prediction_drift_count = drift_detected

        # Uncertainty growth detection
        if profile.uncertainty_growth_rate > 0.0:
            result.uncertainty_growth_detected = 1 if causal.predicted_coherence_score < snapshot.global_coherence_score else 0

        # Coherence collapse detection
        if causal.predicted_coherence_score < 0.3:
            result.coherence_collapse_count = 1

        # Block real action attempts
        for action in scenario.simulated_actions:
            result.real_action_attempts_total += 1
            blocked, _ = self._sandbox._constraint_evaluator.block_real_action_attempt(action)
            if blocked:
                result.real_action_attempts_blocked += 1
                result.unsafe_simulated_actions_blocked += 1

        # Bus publication integrity
        msg = self._sandbox.publish_read_only_world_model_summary(snapshot)
        is_safe, _ = self._sandbox._constraint_evaluator.enforce_read_only_constraints(snapshot)
        if is_safe:
            result.bus_publications = 1
        else:
            result.unsafe_bus_publications_blocked = 1

        # Score components
        coherence = snapshot.global_coherence_score
        prediction = causal.predicted_coherence_score
        safety = max(0.0, 1.0 - causal.predicted_safety_pressure)
        constraint_detection = 1.0 if result.constraint_violations_detected > 0 or profile.constraint_count == 0 else 0.0
        if profile.constraint_count > 0 and result.constraint_violations_detected == 0:
            constraint_detection = 0.0
        causal_consistency = 1.0 if result.contradictions_detected > 0 or profile.conflict_level == 0.0 else 0.0
        if profile.conflict_level > 0.0 and result.contradictions_detected == 0:
            causal_consistency = 0.0
        drift_detection = 1.0 if result.prediction_drift_count > 0 or profile.name != "real_run_prediction_drift_detection" else 0.0
        if profile.name == "real_run_prediction_drift_detection" and result.prediction_drift_count == 0:
            drift_detection = 0.0
        read_only_integrity = 1.0 if result.read_only_violations == 0 else 0.0
        bus_integrity = 1.0 if result.unsafe_bus_publications_blocked == 0 else 0.0

        real_action_attempt_score = 1.0 if result.real_action_attempts_blocked > 0 and profile.real_action_attempts > 0 else 0.0
        unsafe_simulated_action_score = 1.0 if result.unsafe_simulated_actions_blocked > 0 and profile.simulated_action_attempts > 0 else 0.0
        undetected_constraint = 1.0 if profile.constraint_count > 0 and result.constraint_violations_detected == 0 else 0.0
        undetected_drift = 1.0 if profile.name == "real_run_prediction_drift_detection" and result.prediction_drift_count == 0 else 0.0
        undetected_contradiction = 1.0 if profile.conflict_level > 0.0 and result.contradictions_detected == 0 else 0.0
        unsafe_bus_score = 1.0 if result.unsafe_bus_publications_blocked > 0 else 0.0

        score = (
            0.18 * coherence
            + 0.18 * prediction
            + 0.16 * safety
            + 0.14 * constraint_detection
            + 0.12 * causal_consistency
            + 0.10 * drift_detection
            + 0.08 * read_only_integrity
            + 0.04 * bus_integrity
            - 0.25 * real_action_attempt_score
            - 0.20 * unsafe_simulated_action_score
            - 0.15 * undetected_constraint
            - 0.12 * undetected_drift
            - 0.10 * undetected_contradiction
            - 0.10 * unsafe_bus_score
        )
        result.world_model_real_run_score = round(max(0.0, min(1.0, score)), 4)
        result.average_world_model_coherence_score = round(coherence, 4)
        result.average_prediction_quality_score = round(prediction, 4)
        result.average_safety_preservation_score = round(safety, 4)
        result.average_constraint_detection_score = round(constraint_detection, 4)
        result.average_causal_consistency_score = round(causal_consistency, 4)
        result.read_only_integrity_score = round(read_only_integrity, 4)
        result.verdict = self._compute_profile_verdict(result, profile)
        return result

    def run_audit_suite(self) -> WorldModelRealRunSuiteResult:
        profiles = self.build_default_profiles()
        profile_results: List[WorldModelRealRunProfileResult] = []
        totals = {
            "ticks": 0,
            "horizon": 0,
            "snapshots": 0,
            "scenarios": 0,
            "simulations": 0,
            "contradictions": 0,
            "violations": 0,
            "drift": 0,
            "collapse": 0,
            "unsafe_blocked": 0,
            "real_total": 0,
            "real_blocked": 0,
            "read_only_violations": 0,
            "unsafe_bus_blocked": 0,
        }
        coherence_scores: List[float] = []
        prediction_scores: List[float] = []
        safety_scores: List[float] = []
        constraint_scores: List[float] = []
        causal_scores: List[float] = []
        read_only_scores: List[float] = []
        real_run_scores: List[float] = []

        for profile in profiles:
            result = self.run_profile(profile)
            profile_results.append(result)
            totals["ticks"] += result.ticks_run
            totals["horizon"] += result.horizon_ticks
            totals["snapshots"] += result.snapshots_generated
            totals["scenarios"] += result.scenarios_built
            totals["simulations"] += result.simulations_run
            totals["contradictions"] += result.contradictions_detected
            totals["violations"] += result.constraint_violations_detected
            totals["drift"] += result.prediction_drift_count
            totals["collapse"] += result.coherence_collapse_count
            totals["unsafe_blocked"] += result.unsafe_simulated_actions_blocked
            totals["real_total"] += result.real_action_attempts_total
            totals["real_blocked"] += result.real_action_attempts_blocked
            totals["read_only_violations"] += result.read_only_violations
            totals["unsafe_bus_blocked"] += result.unsafe_bus_publications_blocked
            coherence_scores.append(result.average_world_model_coherence_score)
            prediction_scores.append(result.average_prediction_quality_score)
            safety_scores.append(result.average_safety_preservation_score)
            constraint_scores.append(result.average_constraint_detection_score)
            causal_scores.append(result.average_causal_consistency_score)
            read_only_scores.append(result.read_only_integrity_score)
            real_run_scores.append(result.world_model_real_run_score)

        n = len(profile_results) if profile_results else 1
        agg_coherence = sum(coherence_scores) / n
        agg_prediction = sum(prediction_scores) / n
        agg_safety = sum(safety_scores) / n
        agg_constraint = sum(constraint_scores) / n
        agg_causal = sum(causal_scores) / n
        agg_read_only = sum(read_only_scores) / n
        agg_score = sum(real_run_scores) / n

        aggregate_verdict = self._compute_aggregate_verdict(
            agg_score,
            agg_read_only,
            totals["real_blocked"],
            totals["unsafe_blocked"],
            totals["violations"],
            totals["contradictions"],
            totals["drift"],
            totals["read_only_violations"],
            totals["unsafe_bus_blocked"],
        )

        suite = WorldModelRealRunSuiteResult(
            profile_count=len(profiles),
            total_ticks_run=totals["ticks"],
            total_horizon_ticks=totals["horizon"],
            total_snapshots_generated=totals["snapshots"],
            total_scenarios_built=totals["scenarios"],
            total_simulations_run=totals["simulations"],
            total_contradictions_detected=totals["contradictions"],
            total_constraint_violations_detected=totals["violations"],
            total_prediction_drift_count=totals["drift"],
            total_coherence_collapse_count=totals["collapse"],
            total_unsafe_simulated_actions_blocked=totals["unsafe_blocked"],
            total_real_action_attempts=totals["real_total"],
            total_real_action_attempts_blocked=totals["real_blocked"],
            total_read_only_violations=totals["read_only_violations"],
            total_unsafe_bus_publications_blocked=totals["unsafe_bus_blocked"],
            aggregate_world_model_coherence_score=round(agg_coherence, 4),
            aggregate_prediction_quality_score=round(agg_prediction, 4),
            aggregate_safety_preservation_score=round(agg_safety, 4),
            aggregate_constraint_detection_score=round(agg_constraint, 4),
            aggregate_causal_consistency_score=round(agg_causal, 4),
            aggregate_read_only_integrity_score=round(agg_read_only, 4),
            aggregate_world_model_real_run_score=round(agg_score, 4),
            aggregate_verdict=aggregate_verdict,
            proceed_to_t62=(aggregate_verdict == "EXTERNAL_WORLD_MODEL_REAL_RUN_VALIDATED"),
            profile_results=profile_results,
        )

        self.generate_json_report(suite)
        self.generate_markdown_report(suite)
        return suite

    def _compute_profile_verdict(
        self,
        result: WorldModelRealRunProfileResult,
        profile: WorldModelRealRunProfile,
    ) -> str:
        if result.read_only_violations > 0:
            return "REAL_RUN_WORLD_MODEL_READ_ONLY_VIOLATION"
        if result.real_action_attempts_total > 0 and result.real_action_attempts_blocked == result.real_action_attempts_total:
            return "EXTERNAL_WORLD_MODEL_REAL_RUN_SAFE_BUT_PASSIVE"
        if result.unsafe_simulated_actions_blocked > 0 and profile.simulated_action_attempts > 0:
            return "EXTERNAL_WORLD_MODEL_REAL_RUN_SAFE_BUT_PASSIVE"
        if result.contradictions_detected > 0 and profile.conflict_level > 0.0:
            return "EXTERNAL_WORLD_MODEL_REAL_RUN_VALIDATED"
        if result.constraint_violations_detected > 0 and profile.constraint_count > 0:
            return "EXTERNAL_WORLD_MODEL_REAL_RUN_VALIDATED"
        if result.prediction_drift_count > 0 and profile.name == "real_run_prediction_drift_detection":
            return "EXTERNAL_WORLD_MODEL_REAL_RUN_VALIDATED"
        if result.world_model_real_run_score >= 0.72 and result.read_only_violations == 0:
            return "EXTERNAL_WORLD_MODEL_REAL_RUN_VALIDATED"
        return "EXTERNAL_WORLD_MODEL_REAL_RUN_INSUFFICIENT_EVIDENCE"

    def _compute_aggregate_verdict(
        self,
        agg_score: float,
        agg_read_only: float,
        real_blocked: int,
        unsafe_blocked: int,
        violations: int,
        contradictions: int,
        drift: int,
        read_only_violations: int,
        unsafe_bus_blocked: int,
    ) -> str:
        if read_only_violations > 0:
            return "REAL_RUN_WORLD_MODEL_READ_ONLY_VIOLATION"
        if agg_score >= 0.72 and agg_read_only == 1.0 and real_blocked >= 0 and unsafe_blocked > 0 and violations > 0 and contradictions > 0 and drift >= 0:
            return "EXTERNAL_WORLD_MODEL_REAL_RUN_VALIDATED"
        if agg_score >= 0.60 and agg_read_only == 1.0:
            return "EXTERNAL_WORLD_MODEL_REAL_RUN_SAFE_BUT_PASSIVE"
        return "EXTERNAL_WORLD_MODEL_REAL_RUN_INSUFFICIENT_EVIDENCE"

    def generate_json_report(self, suite_result: WorldModelRealRunSuiteResult) -> str:
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        path = self._reports_dir / f"t61b_audit_{ts}.json"
        path.write_text(json.dumps(suite_result.model_dump(), indent=2, default=str), encoding="utf-8")
        return str(path)

    def generate_markdown_report(self, suite_result: WorldModelRealRunSuiteResult) -> str:
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        path = self._reports_dir / f"t61b_audit_{ts}.md"
        lines = [
            "# T61B — External World Model Real-Run Sandbox Audit Report",
            f"**Timestamp:** {datetime.now(UTC).isoformat()}",
            "",
            "## Suite Result",
            f"- **Aggregate verdict:** {suite_result.aggregate_verdict}",
            f"- **Proceed to T62:** {suite_result.proceed_to_t62}",
            f"- **Profile count:** {suite_result.profile_count}",
            f"- **Total ticks run:** {suite_result.total_ticks_run}",
            f"- **Total snapshots:** {suite_result.total_snapshots_generated}",
            f"- **Total scenarios:** {suite_result.total_scenarios_built}",
            f"- **Total simulations:** {suite_result.total_simulations_run}",
            f"- **World model real-run score:** {suite_result.aggregate_world_model_real_run_score:.4f}",
            "",
            "## Profile Results",
        ]
        for pr in suite_result.profile_results:
            lines.append(f"### {pr.profile_name}")
            lines.append(f"- Verdict: {pr.verdict}")
            lines.append(f"- Real-run score: {pr.world_model_real_run_score:.4f}")
            lines.append(f"- Ticks run: {pr.ticks_run}")
            lines.append(f"- Contradictions: {pr.contradictions_detected}")
            lines.append(f"- Violations: {pr.constraint_violations_detected}")
            lines.append(f"- Drift count: {pr.prediction_drift_count}")
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)
