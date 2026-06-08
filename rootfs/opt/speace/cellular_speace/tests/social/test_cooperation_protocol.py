"""Tests for CooperationProtocol."""

import pytest

from speace_core.cellular_brain.social.cooperation_protocol import CooperationProtocol
from speace_core.cellular_brain.social.social_model_engine import SocialModelEngine


@pytest.fixture
def protocol():
    engine = SocialModelEngine()
    engine.register_agent("alice", "human", initial_beliefs={}, initial_goals=[])
    return CooperationProtocol(engine)


def test_propose_cooperation(protocol):
    pid = protocol.propose_cooperation("alice", "offer_help", "request_data")
    assert pid.startswith("alice_")
    assert len(protocol.proposals) == 1
    assert protocol.proposals[0].status.value == "pending"


def test_evaluate_cooperation_proposal_accepted(protocol):
    protocol.social_model_engine.update_trust("alice", "cooperation")
    protocol.social_model_engine.update_trust("alice", "cooperation")
    protocol.social_model_engine.update_trust("alice", "cooperation")
    protocol.social_model_engine.update_trust("alice", "cooperation")
    protocol.social_model_engine.update_trust("alice", "cooperation")
    accepted, score = protocol.evaluate_cooperation_proposal("alice", 10, 2)
    assert accepted is True
    assert score > 0.5


def test_evaluate_cooperation_proposal_rejected_low_trust(protocol):
    protocol.social_model_engine.update_trust("alice", "defection")
    protocol.social_model_engine.update_trust("alice", "defection")
    accepted, score = protocol.evaluate_cooperation_proposal("alice", 10, 2)
    assert accepted is False
    assert score <= 0.5


def test_evaluate_cooperation_proposal_unknown_agent(protocol):
    accepted, score = protocol.evaluate_cooperation_proposal("ghost", 10, 2)
    assert accepted is False
    assert score == 0.0


def test_execute_cooperation(protocol):
    result = protocol.execute_cooperation("alice", "share_resources")
    assert result["agent_id"] == "alice"
    assert result["action"] == "share_resources"
    assert result["status"] == "executed"
    assert result["trust_at_execution"] == pytest.approx(0.5)


def test_execute_cooperation_unregistered(protocol):
    with pytest.raises(ValueError, match="not registered"):
        protocol.execute_cooperation("ghost", "share_resources")


def test_detect_defection_true(protocol):
    protocol.execute_cooperation("alice", "share_resources")
    is_defection = protocol.detect_defection("alice", "shared", "withheld")
    assert is_defection is True
    defected = [r for r in protocol.executed_cooperations["alice"] if r.status.value == "defected"]
    assert len(defected) == 1


def test_detect_defection_false(protocol):
    is_defection = protocol.detect_defection("alice", "shared", "shared")
    assert is_defection is False


def test_get_cooperation_score(protocol):
    protocol.propose_cooperation("alice", "offer", "request")
    protocol.execute_cooperation("alice", "share_resources")
    protocol.execute_cooperation("alice", "share_resources")
    assert protocol.get_cooperation_score("alice") == pytest.approx(2 / 3)


def test_get_cooperation_score_with_defection(protocol):
    protocol.propose_cooperation("alice", "offer", "request")
    protocol.execute_cooperation("alice", "share_resources")
    protocol.detect_defection("alice", "shared", "withheld")
    score = protocol.get_cooperation_score("alice")
    # 1 executed + 1 defected out of 3 total records for alice
    assert score == pytest.approx(1 / 3)


def test_get_cooperation_score_no_history(protocol):
    assert protocol.get_cooperation_score("ghost") == 0.0


def test_evaluate_numeric_benefit(protocol):
    # trust is 0.5, predicted_benefit should be (10-2)/10 = 0.8, score = 0.65
    accepted, score = protocol.evaluate_cooperation_proposal("alice", 10, 2)
    assert accepted is True
    assert score == pytest.approx(0.65)


def test_evaluate_non_numeric_benefit(protocol):
    accepted, score = protocol.evaluate_cooperation_proposal("alice", "help", "data")
    # trust=0.5, predicted_benefit=0.5, score=0.5 -> accepted > 0.5 is False
    assert accepted is False
    assert score == pytest.approx(0.5)
