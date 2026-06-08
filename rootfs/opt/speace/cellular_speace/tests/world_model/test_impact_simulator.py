import pytest
from speace_core.cellular_brain.world_model.world_model_models import (
    CausalSimulationResult,
    WorldEntity,
    WorldEntityType,
    WorldModelSnapshot,
    WorldScenario,
    WorldZone,
)
from speace_core.cellular_brain.world_model.impact_simulator import ImpactSimulator


def test_compute_impact_assessment_low_risk():
    sim = ImpactSimulator(seed=1)
    e = WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[e])
    scenario = WorldScenario(scenario_id="sc1", initial_state_id="s1")
    causal = CausalSimulationResult(scenario_id="sc1", ticks_simulated=3, predicted_risk_score=0.1, predicted_safety_pressure=0.1, predicted_coherence_score=0.9)
    impact = sim.compute_impact_assessment(snapshot, scenario, causal)
    assert impact.impact_score < 0.5
    assert impact.reversible is True
    assert impact.requires_human_review is False


def test_compute_impact_assessment_high_risk():
    sim = ImpactSimulator(seed=1)
    z = WorldZone(zone_id="z1", safety_pressure=0.8, infrastructure_pressure=0.8, energy_pressure=0.8)
    e = WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[e], zones=[z])
    scenario = WorldScenario(scenario_id="sc1", initial_state_id="s1", perturbations=[{"type": "safety_hazard"}])
    causal = CausalSimulationResult(scenario_id="sc1", ticks_simulated=3, predicted_risk_score=0.9, predicted_safety_pressure=0.8, predicted_coherence_score=0.2, contradictions_detected=2)
    impact = sim.compute_impact_assessment(snapshot, scenario, causal)
    assert impact.impact_score > 0.5
    assert impact.requires_human_review is True


def test_compute_impact_assessment_blocked_reason():
    sim = ImpactSimulator(seed=1)
    z = WorldZone(zone_id="z1", safety_pressure=0.9, infrastructure_pressure=0.9, energy_pressure=0.9)
    e = WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[e], zones=[z])
    scenario = WorldScenario(scenario_id="sc1", initial_state_id="s1")
    causal = CausalSimulationResult(scenario_id="sc1", ticks_simulated=3, predicted_risk_score=0.9, predicted_safety_pressure=0.9, predicted_coherence_score=0.1, constraint_violations_detected=3)
    impact = sim.compute_impact_assessment(snapshot, scenario, causal)
    assert impact.allowed_as_simulation_only is False
    assert impact.blocked_reason is not None


def test_compute_prediction_quality():
    sim = ImpactSimulator(seed=1)
    causal = CausalSimulationResult(scenario_id="sc1", ticks_simulated=5, causal_chains_detected=3, predicted_coherence_score=0.8, predicted_risk_score=0.2)
    score = sim.compute_prediction_quality(causal)
    assert 0.0 <= score <= 1.0


def test_compute_prediction_quality_zero_ticks():
    sim = ImpactSimulator(seed=1)
    causal = CausalSimulationResult(scenario_id="sc1", ticks_simulated=0)
    score = sim.compute_prediction_quality(causal)
    assert score == 0.0


def test_compute_safety_preservation_safe():
    sim = ImpactSimulator(seed=1)
    causal = CausalSimulationResult(scenario_id="sc1", predicted_safety_pressure=0.2)
    score = sim.compute_safety_preservation(causal)
    assert score == 1.0


def test_compute_safety_preservation_unsafe():
    sim = ImpactSimulator(seed=1)
    causal = CausalSimulationResult(scenario_id="sc1", predicted_safety_pressure=0.8)
    score = sim.compute_safety_preservation(causal)
    assert score < 1.0


def test_simulate_horizon():
    sim = ImpactSimulator(seed=1)
    e = WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT, state={"status": "active"})
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[e])
    scenario = WorldScenario(scenario_id="sc1", initial_state_id="s1", horizon_ticks=3)
    horizon = sim.simulate_horizon(snapshot, scenario, ticks=3)
    assert len(horizon) == 3


def test_run_simulation():
    sim = ImpactSimulator(seed=1)
    e = WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[e])
    scenario = WorldScenario(scenario_id="sc1", initial_state_id="s1")
    causal = CausalSimulationResult(scenario_id="sc1", ticks_simulated=3, predicted_risk_score=0.1, predicted_safety_pressure=0.1, predicted_coherence_score=0.9)
    impact = sim.run_simulation(snapshot, scenario, causal)
    assert impact.scenario_id == "sc1"
