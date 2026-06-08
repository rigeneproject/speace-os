import pytest
from speace_core.orchestrator import CellularBrainOrchestrator
from speace_core.dna.models import SharedGenome


@pytest.fixture
def orch():
    genome = SharedGenome()
    return CellularBrainOrchestrator.build_mvp(genome)


def test_orchestrator_flag_disabled_by_default(orch):
    assert orch.external_world_model_sandbox_enabled is False


def test_get_external_world_model_sandbox(orch):
    sandbox = orch.get_external_world_model_sandbox()
    assert sandbox is not None


def test_ingest_world_state_disabled(orch):
    result = orch.ingest_world_state_into_world_model({"snapshot_id": "cp_1", "streams": {}})
    assert result.get("error") == "external_world_model_sandbox_disabled"


def test_ingest_world_state_enabled(orch):
    orch.external_world_model_sandbox_enabled = True
    result = orch.ingest_world_state_into_world_model({"snapshot_id": "cp_1", "streams": {"env": [{"value": 1.0}]}})
    assert "error" not in result
    assert "snapshot_id" in result


def test_run_external_world_model_scenario_disabled(orch):
    result = orch.run_external_world_model_scenario("s1")
    assert result.get("error") == "external_world_model_sandbox_disabled"


def test_run_external_world_model_scenario_snapshot_not_found(orch):
    orch.external_world_model_sandbox_enabled = True
    result = orch.run_external_world_model_scenario("nonexistent")
    assert result.get("error") == "snapshot_not_found"


def test_run_external_world_model_scenario_success(orch):
    orch.external_world_model_sandbox_enabled = True
    cp = {"snapshot_id": "cp_1", "streams": {"env": [{"value": 1.0}]}}
    snap = orch.ingest_world_state_into_world_model(cp)
    result = orch.run_external_world_model_scenario(snap["snapshot_id"], "baseline")
    assert "causal_simulation" in result
    assert "impact_assessment" in result


@pytest.mark.asyncio
async def test_run_external_world_model_audit_disabled(orch):
    result = await orch.run_external_world_model_audit()
    assert result is None


@pytest.mark.asyncio
async def test_run_external_world_model_audit_enabled(orch):
    orch.external_world_model_sandbox_enabled = True
    result = await orch.run_external_world_model_audit()
    assert result is not None
    assert "aggregate_verdict" in result
    assert "proceed_to_t61b" in result


def test_t61_does_not_apply_architecture_patch(orch):
    assert orch.architecture_patch_execution_enabled is False


def test_t61_does_not_enable_self_improvement(orch):
    assert orch.self_improvement_enabled is False


def test_t61_does_not_connect_to_real_iot(orch):
    assert orch.cyber_physical_assimilation_enabled is False


def test_t61_not_inserted_into_tick_loop(orch):
    assert orch.external_world_model_sandbox_enabled is False


@pytest.mark.asyncio
async def test_run_external_world_model_real_run_audit_disabled(orch):
    result = await orch.run_external_world_model_real_run_audit()
    assert result is None


@pytest.mark.asyncio
async def test_run_external_world_model_real_run_audit_enabled(orch):
    orch.external_world_model_sandbox_enabled = True
    result = await orch.run_external_world_model_real_run_audit()
    assert result is not None
    assert "aggregate_verdict" in result
    assert "proceed_to_t62" in result
