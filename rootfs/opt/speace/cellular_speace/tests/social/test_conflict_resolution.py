"""Tests for ConflictResolutionEngine."""

import pytest

from speace_core.cellular_brain.social.conflict_resolution import ConflictResolutionEngine
from speace_core.cellular_brain.social.social_model_engine import SocialModelEngine


@pytest.fixture
def resolution():
    engine = SocialModelEngine()
    engine.register_agent("alice", "human", initial_beliefs={"temp": "hot"}, initial_goals=["cool"])
    engine.register_agent(
        "bob", "human", initial_beliefs={"temp": "cold"}, initial_goals=["not_cool"]
    )
    return ConflictResolutionEngine(engine)


def test_detect_conflict_goals(resolution):
    record = resolution.detect_conflict("alice", "bob")
    assert record is not None
    assert "Goal conflict" in record.details
    assert record.conflict_type == "goal_belief_mismatch"


def test_detect_conflict_beliefs(resolution):
    record = resolution.detect_conflict("alice", "bob")
    assert record is not None
    assert "Belief conflict on temp" in record.details


def test_detect_conflict_none(resolution):
    resolution.social_model_engine.register_agent(
        "carol", "human", initial_beliefs={"temp": "hot"}, initial_goals=["cool"]
    )
    record = resolution.detect_conflict("alice", "carol")
    assert record is None


def test_detect_conflict_unregistered(resolution):
    record = resolution.detect_conflict("alice", "ghost")
    assert record is None


def test_mediate_finds_common_goals(resolution):
    resolution.social_model_engine.agents["alice"].beliefs["shared"] = True
    resolution.social_model_engine.agents["bob"].beliefs["shared"] = True
    resolution.social_model_engine.agents["alice"].goals.append("shared_goal")
    resolution.social_model_engine.agents["bob"].goals.append("shared_goal")
    result = resolution.mediate("alice", "bob")
    assert result is not None
    assert "shared_goal" in result["common_goals"]
    assert "shared" in result["shared_beliefs"]
    assert len(result["conflicting_goals_to_abandon"]) > 0


def test_mediate_no_common_goals(resolution):
    result = resolution.mediate("alice", "bob")
    assert result is not None
    assert result["common_goals"] == []
    assert "No common goals found" in result["suggested_compromise"]


def test_mediate_unregistered(resolution):
    result = resolution.mediate("alice", "ghost")
    assert result is None


def test_escalate_increments_threat(resolution):
    level = resolution.escalate("bob")
    assert level == 1
    level = resolution.escalate("bob")
    assert level == 2


def test_escalate_multiple_agents(resolution):
    resolution.escalate("alice")
    resolution.escalate("alice")
    resolution.escalate("bob")
    assert resolution.threat_levels["alice"] == 2
    assert resolution.threat_levels["bob"] == 1


def test_detect_conflict_appends_to_list(resolution):
    resolution.detect_conflict("alice", "bob")
    assert len(resolution.conflicts) == 1
    resolution.detect_conflict("alice", "bob")
    assert len(resolution.conflicts) == 2
