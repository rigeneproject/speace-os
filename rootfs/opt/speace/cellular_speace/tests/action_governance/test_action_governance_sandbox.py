import pytest
from speace_core.cellular_brain.action_governance.action_governance_models import (
    ActionGovernanceDecision,
    ExternalActionProposal,
    ExternalActionType,
)
from speace_core.cellular_brain.action_governance.action_governance_sandbox import (
    ExternalActionGovernanceSandbox,
)
from speace_core.cellular_brain.world_model.world_model_models import (
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
        ],
        zones=[
            WorldZone(zone_id="z1", name="zone1", entities=["e1"]),
        ],
    )


def test_generate_action_proposals(snapshot):
    sandbox = ExternalActionGovernanceSandbox(seed=1)
    proposals = sandbox.generate_action_proposals(snapshot)
    assert len(proposals) >= 3


def test_evaluate_action_proposal_blocked_for_actuate():
    sandbox = ExternalActionGovernanceSandbox(seed=1)
    p = ExternalActionProposal(
        proposal_id="p1", action_type=ExternalActionType.ACTUATE_EXTERNAL
    )
    d = sandbox.evaluate_action_proposal(p)
    assert d.blocked is True
    assert d.governance_mode.value == "blocked"


def test_generate_human_review_packet():
    sandbox = ExternalActionGovernanceSandbox(seed=1)
    p = ExternalActionProposal(proposal_id="p1", action_type=ExternalActionType.RECOMMEND)
    d = sandbox.evaluate_action_proposal(p)
    packet = sandbox.generate_human_review_packet(p, d)
    assert packet.packet_id.startswith("pkt_")


def test_publish_read_only_summary(snapshot):
    sandbox = ExternalActionGovernanceSandbox(seed=1)
    p = ExternalActionProposal(proposal_id="p1", action_type=ExternalActionType.OBSERVE_ONLY)
    d = sandbox.evaluate_action_proposal(p)
    summary = sandbox.publish_read_only_action_governance_summary([d])
    assert summary["read_only"] is True


def test_ingest_world_model_outputs(snapshot):
    sandbox = ExternalActionGovernanceSandbox(seed=1)
    result = sandbox.ingest_world_model_outputs(snapshot)
    assert result["ingested"] is True


def test_generate_sandbox_report():
    sandbox = ExternalActionGovernanceSandbox(seed=1)
    report = sandbox.generate_sandbox_report({"profile_count": 2, "aggregate_verdict": "validated", "proceed_to_t62b": True})
    assert "External Action Governance Sandbox Report" in report
