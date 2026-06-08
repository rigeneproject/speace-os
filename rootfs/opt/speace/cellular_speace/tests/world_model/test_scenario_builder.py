import pytest
from speace_core.cellular_brain.world_model.world_model_models import WorldEntity, WorldEntityType, WorldModelSnapshot, WorldZone
from speace_core.cellular_brain.world_model.scenario_builder import ScenarioBuilder


@pytest.fixture
def sample_snapshot():
    e1 = WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT, state={"temp": 20.0})
    e2 = WorldEntity(entity_id="e2", entity_type=WorldEntityType.SENSOR_SOURCE, state={"temp": 21.0})
    z = WorldZone(zone_id="z1", entities=["e1", "e2"])
    return WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[e1, e2], zones=[z])


def test_build_baseline_scenario(sample_snapshot):
    builder = ScenarioBuilder(seed=1)
    sc = builder.build_baseline_scenario(sample_snapshot)
    assert sc.name == "baseline"
    assert sc.horizon_ticks == 5


def test_build_stress_scenario(sample_snapshot):
    builder = ScenarioBuilder(seed=1)
    sc = builder.build_stress_scenario(sample_snapshot)
    assert sc.name == "stress"
    assert len(sc.perturbations) >= 1


def test_build_conflict_scenario(sample_snapshot):
    builder = ScenarioBuilder(seed=1)
    sc = builder.build_conflict_scenario(sample_snapshot)
    assert sc.name == "conflict"
    assert len(sc.perturbations) >= 1


def test_build_energy_scarcity_scenario(sample_snapshot):
    builder = ScenarioBuilder(seed=1)
    sc = builder.build_energy_scarcity_scenario(sample_snapshot)
    assert sc.name == "energy_scarcity"
    assert any(p.get("type") == "energy_scarcity" for p in sc.perturbations)


def test_build_safety_hazard_scenario(sample_snapshot):
    builder = ScenarioBuilder(seed=1)
    sc = builder.build_safety_hazard_scenario(sample_snapshot)
    assert sc.name == "safety_hazard"


def test_validate_scenario_read_only_pass():
    builder = ScenarioBuilder(seed=1)
    from speace_core.cellular_brain.world_model.world_model_models import WorldScenario
    sc = WorldScenario(scenario_id="sc1", simulated_actions=[{"type": "observe"}])
    ok, reason = builder.validate_scenario_read_only(sc)
    assert ok is True
    assert reason is None


def test_validate_scenario_read_only_blocks_actuate():
    builder = ScenarioBuilder(seed=1)
    from speace_core.cellular_brain.world_model.world_model_models import WorldScenario
    sc = WorldScenario(scenario_id="sc1", simulated_actions=[{"type": "actuate"}])
    ok, reason = builder.validate_scenario_read_only(sc)
    assert ok is False
    assert "real_action_detected" in reason


def test_validate_scenario_read_only_blocks_target_real():
    builder = ScenarioBuilder(seed=1)
    from speace_core.cellular_brain.world_model.world_model_models import WorldScenario
    sc = WorldScenario(scenario_id="sc1", simulated_actions=[{"type": "observe", "target_real": True}])
    ok, reason = builder.validate_scenario_read_only(sc)
    assert ok is False
    assert "real_target_flag_set" in reason


def test_build_scenario_from_profile_stress(sample_snapshot):
    builder = ScenarioBuilder(seed=1)
    sc = builder.build_scenario_from_profile(sample_snapshot, "stress", conflict_level=0.2)
    assert sc.name == "stress"
    assert any(p.get("type") == "injected_conflict" for p in sc.perturbations)
