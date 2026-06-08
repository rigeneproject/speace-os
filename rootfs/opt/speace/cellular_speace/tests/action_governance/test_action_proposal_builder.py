import pytest
from speace_core.cellular_brain.action_governance.action_governance_models import (
    ExternalActionProposal,
    ExternalActionType,
)
from speace_core.cellular_brain.action_governance.action_proposal_builder import (
    ActionProposalBuilder,
)
from speace_core.cellular_brain.world_model.world_model_models import (
    ImpactAssessment,
    WorldEntity,
    WorldEntityType,
    WorldModelSnapshot,
    WorldZone,
)


@pytest.fixture
def snapshot():
    return WorldModelSnapshot(
        snapshot_id="snap_1",
        entities=[
            WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT),
            WorldEntity(entity_id="e2", entity_type=WorldEntityType.INFRASTRUCTURE),
        ],
        zones=[
            WorldZone(zone_id="z1", name="zone1", entities=["e1"]),
        ],
    )


@pytest.fixture
def impact():
    return ImpactAssessment(
        assessment_id="ia1",
        scenario_id="sc1",
        impact_score=0.4,
        safety_impact_score=0.3,
        energy_impact_score=0.2,
        infrastructure_impact_score=0.1,
    )


def test_build_observe_only_proposal(snapshot):
    builder = ActionProposalBuilder(seed=1)
    p = builder.build_observe_only_proposal(snapshot)
    assert p.action_type == ExternalActionType.OBSERVE_ONLY
    assert p.simulated_only is True
    assert p.source_snapshot_id == "snap_1"


def test_build_recommendation_proposal(snapshot, impact):
    builder = ActionProposalBuilder(seed=1)
    p = builder.build_recommendation_proposal(snapshot, impact)
    assert p.action_type == ExternalActionType.RECOMMEND
    assert p.simulated_only is True
    assert p.source_assessment_id == "ia1"


def test_build_resource_shift_simulated_proposal(snapshot, impact):
    builder = ActionProposalBuilder(seed=1)
    p = builder.build_resource_shift_simulated_proposal(snapshot, impact)
    assert p.action_type == ExternalActionType.RESOURCE_SHIFT_SIMULATED
    assert p.simulated_only is True
    assert p.target_zone_id == "z1"


def test_build_isolation_simulated_proposal(snapshot, impact):
    builder = ActionProposalBuilder(seed=1)
    p = builder.build_isolation_simulated_proposal(snapshot, impact)
    assert p.action_type == ExternalActionType.ISOLATE_SIMULATED
    assert p.simulated_only is True


def test_build_from_impact_assessment(snapshot, impact):
    builder = ActionProposalBuilder(seed=1)
    p = builder.build_from_impact_assessment(snapshot, impact)
    assert p.simulated_only is True
    assert p.source_assessment_id == "ia1"


def test_validate_proposal_is_sandboxed_true(snapshot):
    builder = ActionProposalBuilder(seed=1)
    p = builder.build_observe_only_proposal(snapshot)
    assert builder.validate_proposal_is_sandboxed(p) is True


def test_validate_proposal_is_sandboxed_false_real_execution(snapshot):
    builder = ActionProposalBuilder(seed=1)
    p = ExternalActionProposal(
        proposal_id="p1",
        action_type=ExternalActionType.OBSERVE_ONLY,
        source_snapshot_id=snapshot.snapshot_id,
        simulated_only=False,
        requested_real_execution=True,
    )
    assert builder.validate_proposal_is_sandboxed(p) is False


def test_validate_proposal_is_sandboxed_false_actuate_external(snapshot):
    builder = ActionProposalBuilder(seed=1)
    p = ExternalActionProposal(
        proposal_id="p1",
        action_type=ExternalActionType.ACTUATE_EXTERNAL,
        source_snapshot_id=snapshot.snapshot_id,
        simulated_only=True,
    )
    assert builder.validate_proposal_is_sandboxed(p) is False
