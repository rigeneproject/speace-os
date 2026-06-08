import pytest
from speace_core.orchestrator import CellularBrainOrchestrator
from speace_core.dna.models import SharedGenome


@pytest.fixture
def orch():
    genome = SharedGenome()
    return CellularBrainOrchestrator.build_mvp(genome)


def test_orchestrator_flag_disabled_by_default(orch):
    assert orch.external_action_governance_enabled is False


def test_get_external_action_governance_sandbox(orch):
    sandbox = orch.get_external_action_governance_sandbox()
    assert sandbox is not None


def test_generate_external_action_proposals_disabled(orch):
    result = orch.generate_external_action_proposals([])
    assert result.get("error") == "external_action_governance_disabled"


def test_evaluate_external_action_proposal_disabled(orch):
    result = orch.evaluate_external_action_proposal({})
    assert result.get("error") == "external_action_governance_disabled"


@pytest.mark.asyncio
async def test_run_external_action_governance_audit_disabled(orch):
    result = await orch.run_external_action_governance_audit()
    assert result is None


@pytest.mark.asyncio
async def test_run_external_action_governance_audit_enabled(orch):
    orch.external_action_governance_enabled = True
    result = await orch.run_external_action_governance_audit()
    assert result is not None
    assert "aggregate_verdict" in result
    assert "proceed_to_t62b" in result


def test_t62_does_not_apply_architecture_patch(orch):
    assert orch.architecture_patch_execution_enabled is False


def test_t62_does_not_enable_self_improvement(orch):
    assert orch.self_improvement_enabled is False


def test_t62_does_not_connect_to_real_iot(orch):
    assert orch.cyber_physical_assimilation_enabled is False


def test_t62_not_inserted_into_tick_loop(orch):
    assert orch.external_action_governance_enabled is False


def test_benchmark_metrics_t62_present(orch):
    from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import BenchmarkMetrics
    metrics = BenchmarkMetrics()
    assert hasattr(metrics, "action_governance_audit_count")
    assert hasattr(metrics, "external_action_governance_sandbox_score")
    assert hasattr(metrics, "proceed_to_t62b_score")


def test_morphological_events_t62_present():
    from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
    assert hasattr(MorphologyEventType, "ACTION_GOVERNANCE_AUDIT_STARTED")
    assert hasattr(MorphologyEventType, "ACTION_REAL_EXECUTION_ATTEMPT_BLOCKED")
