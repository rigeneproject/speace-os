import json
import random
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.world_model.causal_graph_engine import CausalGraphEngine
from speace_core.cellular_brain.world_model.constraint_evaluator import ConstraintEvaluator
from speace_core.cellular_brain.world_model.impact_simulator import ImpactSimulator
from speace_core.cellular_brain.world_model.scenario_builder import ScenarioBuilder
from speace_core.cellular_brain.world_model.world_model_models import (
    CausalSimulationResult,
    ImpactAssessment,
    WorldModelSnapshot,
    WorldScenario,
)
from speace_core.cellular_brain.world_model.world_state_store import WorldStateStore


class ExternalWorldModelSandbox:
    """Orchestrates store, scenario builder, causal engine, constraint evaluator and simulator."""

    def __init__(self, seed: int = 42):
        self._seed = seed
        self._rng = random.Random(seed)
        self._store = WorldStateStore(seed=seed)
        self._scenario_builder = ScenarioBuilder(seed=seed)
        self._causal_engine = CausalGraphEngine(seed=seed)
        self._constraint_evaluator = ConstraintEvaluator()
        self._impact_simulator = ImpactSimulator(seed=seed)
        self._reports_dir = Path("reports/world_model")
        self._reports_dir.mkdir(parents=True, exist_ok=True)

    def ingest_world_state_snapshot(self, cp_snapshot: dict) -> WorldModelSnapshot:
        return self._store.import_cyber_physical_snapshot(cp_snapshot)

    def build_world_model_snapshot(
        self,
        entities=None,
        zones=None,
        metadata=None,
    ) -> WorldModelSnapshot:
        return self._store.create_snapshot(entities=entities, zones=zones, metadata=metadata)

    def run_scenario_simulation(
        self,
        snapshot: WorldModelSnapshot,
        scenario: WorldScenario,
    ) -> tuple[CausalSimulationResult, ImpactAssessment]:
        valid, reason = self._scenario_builder.validate_scenario_read_only(scenario)
        if not valid:
            causal = CausalSimulationResult(
                scenario_id=scenario.scenario_id,
                ticks_simulated=0,
                causal_chains_detected=0,
                contradictions_detected=0,
                constraint_violations_detected=1,
                predicted_risk_score=1.0,
                predicted_coherence_score=0.0,
                safe_to_publish_read_only=False,
                metadata={"blocked_reason": reason},
            )
            impact = ImpactAssessment(
                assessment_id=f"ia_{scenario.scenario_id}",
                scenario_id=scenario.scenario_id,
                impact_score=1.0,
                safety_impact_score=1.0,
                energy_impact_score=1.0,
                infrastructure_impact_score=1.0,
                uncertainty_impact_score=1.0,
                reversible=False,
                requires_human_review=True,
                allowed_as_simulation_only=False,
                blocked_reason=reason,
            )
            return causal, impact

        causal = self._causal_engine.run_causal_simulation(snapshot, scenario)
        impact = self._impact_simulator.compute_impact_assessment(snapshot, scenario, causal)
        return causal, impact

    def publish_read_only_world_model_summary(self, snapshot: WorldModelSnapshot) -> dict:
        return {
            "type": "world_model_summary",
            "snapshot_id": snapshot.snapshot_id,
            "timestamp": snapshot.timestamp,
            "entity_count": len(snapshot.entities),
            "zone_count": len(snapshot.zones),
            "global_uncertainty": snapshot.global_uncertainty_score,
            "global_coherence": snapshot.global_coherence_score,
            "global_risk": snapshot.global_risk_score,
            "read_only": True,
        }

    def generate_sandbox_report(
        self,
        suite_result: dict,
        suffix: str = "",
    ) -> tuple[Path, Path]:
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        if suffix:
            ts = f"{ts}_{suffix}"
        json_path = self._reports_dir / f"t61_audit_{ts}.json"
        md_path = self._reports_dir / f"t61_audit_{ts}.md"
        json_path.write_text(json.dumps(suite_result, indent=2, default=str), encoding="utf-8")
        md_lines = [
            "# T61 — External World Model Sandbox Audit Report",
            f"**Timestamp:** {datetime.now(UTC).isoformat()}",
            "",
            "## Suite Result",
            f"- **Aggregate verdict:** {suite_result.get('aggregate_verdict', 'N/A')}",
            f"- **Proceed to T61B:** {suite_result.get('proceed_to_t61b', False)}",
            f"- **Profile count:** {suite_result.get('profile_count', 0)}",
            f"- **Total snapshots:** {suite_result.get('total_snapshots_generated', 0)}",
            f"- **Total scenarios:** {suite_result.get('total_scenarios_built', 0)}",
            f"- **Total simulations:** {suite_result.get('total_simulations_run', 0)}",
            f"- **World model sandbox score:** {suite_result.get('aggregate_world_model_sandbox_score', 0.0):.4f}",
            "",
            "## Profile Results",
        ]
        for pr in suite_result.get("profile_results", []):
            md_lines.append(f"### {pr.get('profile_name', 'unknown')}")
            md_lines.append(f"- Verdict: {pr.get('verdict', 'N/A')}")
            md_lines.append(f"- Sandbox score: {pr.get('world_model_sandbox_score', 0.0):.4f}")
            md_lines.append("")
        md_path.write_text("\n".join(md_lines), encoding="utf-8")
        return json_path, md_path
