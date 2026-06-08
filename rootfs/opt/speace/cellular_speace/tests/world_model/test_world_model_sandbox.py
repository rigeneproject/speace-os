import pytest
from speace_core.cellular_brain.world_model.world_model_models import (
    WorldEntity,
    WorldEntityType,
    WorldModelSnapshot,
    WorldScenario,
    WorldZone,
)
from speace_core.cellular_brain.world_model.world_model_sandbox import ExternalWorldModelSandbox


def test_ingest_world_state_snapshot():
    sandbox = ExternalWorldModelSandbox(seed=1)
    cp = {"snapshot_id": "cp_1", "streams": {"env_temp": [{"value": 22.0}]}}
    snapshot = sandbox.ingest_world_state_snapshot(cp)
    assert snapshot.snapshot_id.startswith("wms_")
    assert any("cp_env_temp" in e.entity_id for e in snapshot.entities)


def test_build_world_model_snapshot():
    sandbox = ExternalWorldModelSandbox(seed=1)
    e = WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)
    snapshot = sandbox.build_world_model_snapshot(entities=[e])
    assert len(snapshot.entities) == 1
    assert snapshot.global_uncertainty_score >= 0.0


def test_run_scenario_simulation_baseline():
    sandbox = ExternalWorldModelSandbox(seed=1)
    e = WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)
    snapshot = sandbox.build_world_model_snapshot(entities=[e])
    scenario = WorldScenario(scenario_id="sc1", initial_state_id=snapshot.snapshot_id, horizon_ticks=3)
    causal, impact = sandbox.run_scenario_simulation(snapshot, scenario)
    assert causal.scenario_id == "sc1"
    assert impact.scenario_id == "sc1"


def test_run_scenario_simulation_blocks_real_action():
    sandbox = ExternalWorldModelSandbox(seed=1)
    e = WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)
    snapshot = sandbox.build_world_model_snapshot(entities=[e])
    scenario = WorldScenario(scenario_id="sc1", initial_state_id=snapshot.snapshot_id, simulated_actions=[{"type": "actuate", "target_real": True}])
    causal, impact = sandbox.run_scenario_simulation(snapshot, scenario)
    assert causal.ticks_simulated == 0
    assert impact.blocked_reason is not None
    assert impact.allowed_as_simulation_only is False


def test_publish_read_only_world_model_summary():
    sandbox = ExternalWorldModelSandbox(seed=1)
    e = WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)
    snapshot = sandbox.build_world_model_snapshot(entities=[e])
    msg = sandbox.publish_read_only_world_model_summary(snapshot)
    assert msg["type"] == "world_model_summary"
    assert msg["read_only"] is True
    assert msg["snapshot_id"] == snapshot.snapshot_id


def test_generate_sandbox_report():
    sandbox = ExternalWorldModelSandbox(seed=1)
    suite = {
        "aggregate_verdict": "EXTERNAL_WORLD_MODEL_SANDBOX_VALIDATED",
        "proceed_to_t61b": True,
        "profile_count": 2,
        "total_snapshots_generated": 2,
        "total_scenarios_built": 2,
        "total_simulations_run": 2,
        "profile_results": [
            {"profile_name": "p1", "verdict": "EXTERNAL_WORLD_MODEL_SANDBOX_VALIDATED", "world_model_sandbox_score": 0.8},
            {"profile_name": "p2", "verdict": "EXTERNAL_WORLD_MODEL_INSUFFICIENT_EVIDENCE", "world_model_sandbox_score": 0.5},
        ],
    }
    json_path, md_path = sandbox.generate_sandbox_report(suite)
    assert json_path.exists()
    assert md_path.exists()
    assert "t61_audit_" in str(json_path)
