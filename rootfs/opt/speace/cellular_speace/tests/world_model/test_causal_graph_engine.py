import pytest
from speace_core.cellular_brain.world_model.world_model_models import WorldEntity, WorldEntityType, WorldModelSnapshot, WorldScenario, WorldZone
from speace_core.cellular_brain.world_model.causal_graph_engine import CausalGraphEngine


@pytest.fixture
def three_entity_snapshot():
    e1 = WorldEntity(entity_id="a", entity_type=WorldEntityType.ENVIRONMENT, state={"x": 1.0})
    e2 = WorldEntity(entity_id="b", entity_type=WorldEntityType.INFRASTRUCTURE, state={"x": 0.5})
    e3 = WorldEntity(entity_id="c", entity_type=WorldEntityType.ENERGY_SYSTEM, state={"x": 0.8})
    return WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[e1, e2, e3])


def test_build_causal_graph(three_entity_snapshot):
    engine = CausalGraphEngine(seed=1)
    links = engine.build_causal_graph(three_entity_snapshot)
    assert len(links) >= 1
    for l in links:
        assert l.source_entity_id != l.target_entity_id


def test_evaluate_causal_links_uses_existing(three_entity_snapshot):
    engine = CausalGraphEngine(seed=1)
    three_entity_snapshot.causal_links = engine.build_causal_graph(three_entity_snapshot)
    links = engine.evaluate_causal_links(three_entity_snapshot)
    assert len(links) == len(three_entity_snapshot.causal_links)


def test_detect_causal_chains(three_entity_snapshot):
    engine = CausalGraphEngine(seed=1)
    links = engine.build_causal_graph(three_entity_snapshot)
    chains = engine.detect_causal_chains(links)
    assert isinstance(chains, list)


def test_detect_contradictions(three_entity_snapshot):
    engine = CausalGraphEngine(seed=1)
    three_entity_snapshot.entities[0].state["status"] = "active"
    three_entity_snapshot.entities[1].state["status"] = "inactive"
    contradictions = engine.detect_contradictions(three_entity_snapshot)
    assert len(contradictions) >= 1


def test_detect_contradictions_numeric():
    e1 = WorldEntity(entity_id="a", entity_type=WorldEntityType.ENVIRONMENT, state={"temp": 30.0})
    e2 = WorldEntity(entity_id="b", entity_type=WorldEntityType.ENVIRONMENT, state={"temp": 20.0})
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[e1, e2])
    engine = CausalGraphEngine(seed=1)
    contradictions = engine.detect_contradictions(snapshot)
    assert len(contradictions) >= 1


def test_simulate_causal_step():
    engine = CausalGraphEngine(seed=1)
    e = WorldEntity(entity_id="a", entity_type=WorldEntityType.ENVIRONMENT, state={"status": "active"})
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[e])
    scenario = WorldScenario(scenario_id="sc1", initial_state_id="s1", perturbations=[{"type": "safety_hazard", "target_entity_id": "a", "delta_safety": 0.3}])
    next_snap = engine.simulate_causal_step(snapshot, scenario, tick=1)
    assert next_snap.snapshot_id == "s1_tick1"
    assert next_snap.metadata.get("simulated_tick") == 1


def test_run_causal_simulation():
    engine = CausalGraphEngine(seed=1)
    e = WorldEntity(entity_id="a", entity_type=WorldEntityType.ENVIRONMENT, state={"status": "active"})
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[e])
    scenario = WorldScenario(scenario_id="sc1", initial_state_id="s1", horizon_ticks=3)
    result = engine.run_causal_simulation(snapshot, scenario)
    assert result.scenario_id == "sc1"
    assert result.ticks_simulated == 3
    assert result.predicted_coherence_score <= 1.0


def test_run_causal_simulation_with_constraints():
    from speace_core.cellular_brain.world_model.world_model_models import WorldConstraint
    engine = CausalGraphEngine(seed=1)
    e = WorldEntity(entity_id="a", entity_type=WorldEntityType.ENVIRONMENT, state={"status": "active"})
    c = WorldConstraint(constraint_id="c1", constraint_type="safety", severity=0.9, hard_constraint=True)
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[e], constraints=[c])
    scenario = WorldScenario(scenario_id="sc1", initial_state_id="s1", horizon_ticks=2)
    result = engine.run_causal_simulation(snapshot, scenario)
    assert result.constraint_violations_detected >= 1
    assert result.safe_to_publish_read_only is False
