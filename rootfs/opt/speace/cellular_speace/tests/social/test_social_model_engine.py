"""Tests for SocialModelEngine."""

import pytest

from speace_core.cellular_brain.social.social_model_engine import AgentType, SocialModelEngine


@pytest.fixture
def engine():
    return SocialModelEngine()


def test_register_agent(engine):
    engine.register_agent("alice", AgentType.HUMAN, initial_beliefs={"weather": "sunny"})
    assert "alice" in engine.agents
    assert engine.agents["alice"].agent_type == AgentType.HUMAN
    assert engine.agents["alice"].beliefs == {"weather": "sunny"}


def test_register_agent_with_string_type(engine):
    engine.register_agent("bob", "service", initial_goals=["uptime", "latency"])
    assert engine.agents["bob"].agent_type == AgentType.SERVICE
    assert engine.agents["bob"].goals == ["uptime", "latency"]


def test_observe_action_updates_predictions(engine):
    engine.register_agent("alice", AgentType.HUMAN)
    engine.observe_action("alice", "greet", "hello")
    engine.observe_action("alice", "greet", "hello")
    engine.observe_action("alice", "ignore", "silent")
    preds = engine.agents["alice"].predicted_actions
    assert "greet" in preds
    assert "ignore" in preds
    assert pytest.approx(preds["greet"]) == 2 / 3


def test_predict_next_action(engine):
    engine.register_agent("alice", AgentType.HUMAN)
    engine.observe_action("alice", "run", "fast")
    engine.observe_action("alice", "run", "fast")
    engine.observe_action("alice", "walk", "slow")
    action, conf = engine.predict_next_action("alice")
    assert action == "run"
    assert conf == pytest.approx(2 / 3)


def test_predict_next_action_no_history(engine):
    engine.register_agent("alice", AgentType.HUMAN)
    action, conf = engine.predict_next_action("alice")
    assert action == "unknown"
    assert conf == 0.0


def test_infer_goal(engine):
    engine.register_agent("alice", AgentType.HUMAN, initial_goals=["speed", "safety"])
    engine.observe_action("alice", "run", "speed achieved")
    engine.observe_action("alice", "run", "speed achieved")
    inferred = engine.infer_goal("alice")
    assert inferred == "speed"


def test_infer_goal_no_history(engine):
    engine.register_agent("alice", AgentType.HUMAN, initial_goals=["speed"])
    assert engine.infer_goal("alice") is None


def test_infer_goal_no_goals(engine):
    engine.register_agent("alice", AgentType.HUMAN)
    engine.observe_action("alice", "run", "fast")
    assert engine.infer_goal("alice") is None


def test_update_trust_cooperation(engine):
    engine.register_agent("alice", AgentType.HUMAN)
    engine.update_trust("alice", "cooperation")
    assert engine.agents["alice"].trust_score == pytest.approx(0.6)
    engine.update_trust("alice", "cooperation")
    assert engine.agents["alice"].trust_score == pytest.approx(0.7)


def test_update_trust_defection(engine):
    engine.register_agent("alice", AgentType.HUMAN)
    engine.update_trust("alice", "defection")
    assert engine.agents["alice"].trust_score == pytest.approx(0.3)
    engine.update_trust("alice", "defection")
    assert engine.agents["alice"].trust_score == pytest.approx(0.1)
    engine.update_trust("alice", "defection")
    assert engine.agents["alice"].trust_score == pytest.approx(0.0)


def test_update_trust_neutral(engine):
    engine.register_agent("alice", AgentType.HUMAN)
    engine.update_trust("alice", "neutral")
    assert engine.agents["alice"].trust_score == pytest.approx(0.5)


def test_get_agent_summary(engine):
    engine.register_agent("alice", AgentType.HUMAN, initial_beliefs={"x": 1}, initial_goals=["g1"])
    summary = engine.get_agent_summary("alice")
    assert "alice" in summary
    assert "human" in summary
    assert "Trust: 0.50" in summary
    assert "g1" in summary


def test_get_agent_summary_missing(engine):
    assert engine.get_agent_summary("nobody") == "No model for agent nobody"


def test_get_all_agent_summaries(engine):
    engine.register_agent("alice", AgentType.HUMAN)
    engine.register_agent("bob", AgentType.SERVICE)
    summaries = engine.get_all_agent_summaries()
    assert set(summaries.keys()) == {"alice", "bob"}
    assert "human" in summaries["alice"]
    assert "service" in summaries["bob"]


def test_set_nested_belief(engine):
    engine.register_agent("alice", AgentType.HUMAN)
    engine.set_nested_belief("alice", "it_is_raining", 0.8)
    assert engine.agents["alice"].nested_beliefs["it_is_raining"] == 0.8
    assert engine.agents["alice"].nested_belief_confidence == pytest.approx(0.8)


def test_set_nested_belief_multiple(engine):
    engine.register_agent("alice", AgentType.HUMAN)
    engine.set_nested_belief("alice", "it_is_raining", 0.8)
    engine.set_nested_belief("alice", "sun_is_shining", 0.4)
    assert engine.agents["alice"].nested_belief_confidence == pytest.approx(0.6)


def test_get_theory_of_mind(engine):
    engine.register_agent("alice", AgentType.HUMAN)
    engine.set_nested_belief("alice", "it_is_raining", 0.9)
    tom = engine.get_theory_of_mind("alice")
    assert tom["agent_id"] == "alice"
    assert tom["nested_beliefs"] == {"it_is_raining": 0.9}
    assert tom["overall_confidence"] == pytest.approx(0.9)


def test_observe_action_unregistered_agent_raises(engine):
    with pytest.raises(ValueError, match="not registered"):
        engine.observe_action("ghost", "jump", "high")


def test_predict_next_action_unregistered_agent_raises(engine):
    with pytest.raises(ValueError, match="not registered"):
        engine.predict_next_action("ghost")


def test_infer_goal_unregistered_agent_raises(engine):
    with pytest.raises(ValueError, match="not registered"):
        engine.infer_goal("ghost")


def test_update_trust_unregistered_agent_raises(engine):
    with pytest.raises(ValueError, match="not registered"):
        engine.update_trust("ghost", "cooperation")


def test_set_nested_belief_unregistered_agent_raises(engine):
    with pytest.raises(ValueError, match="not registered"):
        engine.set_nested_belief("ghost", "x", 1.0)


def test_get_theory_of_mind_unregistered_agent_raises(engine):
    with pytest.raises(ValueError, match="not registered"):
        engine.get_theory_of_mind("ghost")
