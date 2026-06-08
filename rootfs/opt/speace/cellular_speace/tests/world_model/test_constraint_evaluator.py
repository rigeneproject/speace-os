import pytest
from speace_core.cellular_brain.world_model.world_model_models import WorldConstraint, WorldEntity, WorldEntityType, WorldModelSnapshot, WorldScenario
from speace_core.cellular_brain.world_model.constraint_evaluator import ConstraintEvaluator


def test_evaluate_constraints_no_violations():
    ev = ConstraintEvaluator()
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)])
    scenario = WorldScenario(scenario_id="sc1", initial_state_id="s1")
    violations, hard, safety = ev.evaluate_constraints(snapshot, scenario)
    assert violations == 0
    assert hard == 0
    assert safety == 1.0


def test_evaluate_constraints_hard_violation():
    ev = ConstraintEvaluator()
    c = WorldConstraint(constraint_id="c1", severity=0.9, hard_constraint=True)
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)], constraints=[c])
    scenario = WorldScenario(scenario_id="sc1", initial_state_id="s1")
    violations, hard, safety = ev.evaluate_constraints(snapshot, scenario)
    assert violations >= 1
    assert hard >= 1


def test_evaluate_constraints_blocks_real_action_keyword():
    ev = ConstraintEvaluator()
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)])
    scenario = WorldScenario(scenario_id="sc1", initial_state_id="s1", simulated_actions=[{"type": "actuate"}])
    violations, hard, safety = ev.evaluate_constraints(snapshot, scenario)
    assert violations >= 1


def test_detect_constraint_violations():
    ev = ConstraintEvaluator()
    c = WorldConstraint(constraint_id="c1", severity=0.9, hard_constraint=True, description="hard")
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)], constraints=[c])
    scenario = WorldScenario(scenario_id="sc1", initial_state_id="s1")
    v = ev.detect_constraint_violations(snapshot, scenario)
    assert len(v) >= 1
    assert v[0]["type"] == "hard_constraint_violation"


def test_enforce_read_only_constraints():
    ev = ConstraintEvaluator()
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)])
    ok, reason = ev.enforce_read_only_constraints(snapshot)
    assert ok is True


def test_block_real_action_attempt_actuate():
    ev = ConstraintEvaluator()
    blocked, reason = ev.block_real_action_attempt({"type": "actuate"})
    assert blocked is True
    assert "blocked_real_action_keyword" in reason


def test_block_real_action_attempt_target_real():
    ev = ConstraintEvaluator()
    blocked, reason = ev.block_real_action_attempt({"type": "observe", "target_real": True})
    assert blocked is True
    assert "blocked_real_target_flag" in reason


def test_block_real_action_attempt_iot_reference():
    ev = ConstraintEvaluator()
    blocked, reason = ev.block_real_action_attempt({"type": "observe", "iot_device_id": "dev1"})
    assert blocked is True
    assert "blocked_real_connection_reference" in reason


def test_block_real_action_attempt_safe():
    ev = ConstraintEvaluator()
    blocked, reason = ev.block_real_action_attempt({"type": "observe"})
    assert blocked is False
    assert reason is None


def test_compute_constraint_safety_score():
    ev = ConstraintEvaluator()
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)])
    scenario = WorldScenario(scenario_id="sc1", initial_state_id="s1")
    score = ev.compute_constraint_safety_score(snapshot, scenario)
    assert score == 1.0
