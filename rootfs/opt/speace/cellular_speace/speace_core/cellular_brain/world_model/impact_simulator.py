import random
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.world_model.world_model_models import (
    CausalSimulationResult,
    ImpactAssessment,
    WorldModelSnapshot,
    WorldScenario,
)


class ImpactSimulator:
    """Simulates future impacts without real action. Produces ImpactAssessment."""

    def __init__(self, seed: int = 42):
        self._seed = seed
        self._rng = random.Random(seed)

    def run_simulation(
        self,
        snapshot: WorldModelSnapshot,
        scenario: WorldScenario,
        causal_result: CausalSimulationResult,
    ) -> ImpactAssessment:
        return self.compute_impact_assessment(snapshot, scenario, causal_result)

    def simulate_horizon(
        self,
        snapshot: WorldModelSnapshot,
        scenario: WorldScenario,
        ticks: int = 5,
    ) -> List[WorldModelSnapshot]:
        from speace_core.cellular_brain.world_model.causal_graph_engine import CausalGraphEngine

        engine = CausalGraphEngine(seed=self._seed)
        horizon: List[WorldModelSnapshot] = []
        current = snapshot
        for tick in range(1, ticks + 1):
            current = engine.simulate_causal_step(current, scenario, tick)
            horizon.append(current)
        return horizon

    def compute_impact_assessment(
        self,
        snapshot: WorldModelSnapshot,
        scenario: WorldScenario,
        causal_result: CausalSimulationResult,
    ) -> ImpactAssessment:
        base_impact = 0.0
        safety_impact = causal_result.predicted_safety_pressure
        energy_impact = causal_result.predicted_energy_pressure
        infra_impact = 0.0
        for z in snapshot.zones:
            infra_impact = max(infra_impact, z.infrastructure_pressure)
        uncertainty_impact = 1.0 - causal_result.predicted_coherence_score

        for p in scenario.perturbations:
            if p.get("type") == "safety_hazard":
                safety_impact = min(1.0, safety_impact + 0.2)
            elif p.get("type") == "energy_scarcity":
                energy_impact = min(1.0, energy_impact + 0.2)
            elif p.get("type") == "pressure_spike":
                infra_impact = min(1.0, infra_impact + 0.2)
            elif p.get("type") == "injected_uncertainty":
                uncertainty_impact = min(1.0, uncertainty_impact + p.get("level", 0.0))

        impact_score = min(1.0, (safety_impact + energy_impact + infra_impact + uncertainty_impact) / 4.0)
        reversible = impact_score < 0.6 and causal_result.contradictions_detected == 0
        requires_human_review = impact_score > 0.5 or safety_impact > 0.5 or causal_result.contradictions_detected > 0
        allowed_as_simulation_only = True
        blocked_reason = None
        if impact_score > 0.8:
            allowed_as_simulation_only = False
            blocked_reason = "impact_score_too_high"
        elif causal_result.constraint_violations_detected > 0 and not reversible:
            allowed_as_simulation_only = False
            blocked_reason = "irreversible_with_constraint_violations"

        return ImpactAssessment(
            assessment_id=f"ia_{scenario.scenario_id}",
            scenario_id=scenario.scenario_id,
            impact_score=round(impact_score, 4),
            safety_impact_score=round(safety_impact, 4),
            energy_impact_score=round(energy_impact, 4),
            infrastructure_impact_score=round(infra_impact, 4),
            uncertainty_impact_score=round(uncertainty_impact, 4),
            reversible=reversible,
            requires_human_review=requires_human_review,
            allowed_as_simulation_only=allowed_as_simulation_only,
            blocked_reason=blocked_reason,
            metadata={"perturbation_count": len(scenario.perturbations)},
        )

    def compute_prediction_quality(
        self,
        causal_result: CausalSimulationResult,
    ) -> float:
        if causal_result.ticks_simulated == 0:
            return 0.0
        chain_bonus = min(1.0, causal_result.causal_chains_detected / 3.0) * 0.3
        coherence_factor = causal_result.predicted_coherence_score * 0.4
        risk_factor = (1.0 - causal_result.predicted_risk_score) * 0.3
        return max(0.0, min(1.0, chain_bonus + coherence_factor + risk_factor))

    def compute_safety_preservation(
        self,
        causal_result: CausalSimulationResult,
    ) -> float:
        if causal_result.predicted_safety_pressure > 0.5:
            return max(0.0, 0.5 - causal_result.predicted_safety_pressure)
        if causal_result.constraint_violations_detected > 0:
            return max(0.0, 1.0 - causal_result.constraint_violations_detected * 0.2)
        return 1.0
