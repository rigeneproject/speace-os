import pytest
from speace_core.cellular_brain.world_model.world_model_models import (
    WorldConstraint,
    WorldEntity,
    WorldEntityType,
    WorldModelSnapshot,
    WorldScenario,
    WorldZone,
)
from speace_core.cellular_brain.world_model.constraint_evaluator import ConstraintEvaluator
from speace_core.cellular_brain.world_model.impact_simulator import ImpactSimulator
from speace_core.cellular_brain.world_model.world_model_policy_engine import WorldModelPolicyEngine
from speace_core.cellular_brain.world_model.world_model_sandbox import ExternalWorldModelSandbox
from speace_core.cellular_brain.world_model.world_state_store import WorldStateStore


# --- constraint_evaluator coverage gaps ---

def test_soft_constraint_violation():
    ev = ConstraintEvaluator()
    c = WorldConstraint(constraint_id="c1", severity=0.7, hard_constraint=False)
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)], constraints=[c])
    scenario = WorldScenario(scenario_id="sc1", initial_state_id="s1")
    violations, hard, safety = ev.evaluate_constraints(snapshot, scenario)
    assert violations == 1
    assert hard == 0


def test_hard_constraint_severity_not_above_threshold():
    ev = ConstraintEvaluator()
    c = WorldConstraint(constraint_id="c1", severity=0.8, hard_constraint=True)
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)], constraints=[c])
    scenario = WorldScenario(scenario_id="sc1", initial_state_id="s1")
    violations, hard, safety = ev.evaluate_constraints(snapshot, scenario)
    assert violations == 1
    assert hard == 0


def test_detect_constraint_violations_hard_not_above_threshold():
    ev = ConstraintEvaluator()
    c = WorldConstraint(constraint_id="c1", severity=0.8, hard_constraint=True)
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)], constraints=[c])
    scenario = WorldScenario(scenario_id="sc1", initial_state_id="s1")
    v = ev.detect_constraint_violations(snapshot, scenario)
    assert len(v) == 0


def test_detect_constraint_violations_simulated_action():
    ev = ConstraintEvaluator()
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)])
    scenario = WorldScenario(scenario_id="sc1", initial_state_id="s1", simulated_actions=[{"type": "actuate"}])
    v = ev.detect_constraint_violations(snapshot, scenario)
    assert any(vv["type"] == "simulated_action_blocked" for vv in v)


def test_enforce_read_only_constraints_soft_only():
    ev = ConstraintEvaluator()
    c = WorldConstraint(constraint_id="c1", constraint_type="read_only", hard_constraint=False)
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)], constraints=[c])
    ok, reason = ev.enforce_read_only_constraints(snapshot)
    assert ok is True
    assert reason is None


def test_compute_constraint_safety_score_with_violations():
    ev = ConstraintEvaluator()
    c = WorldConstraint(constraint_id="c1", severity=0.9, hard_constraint=True)
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)], constraints=[c])
    scenario = WorldScenario(scenario_id="sc1", initial_state_id="s1")
    score = ev.compute_constraint_safety_score(snapshot, scenario)
    assert score < 1.0


# --- world_state_store coverage gaps ---

def test_import_cyber_physical_snapshot_infra():
    store = WorldStateStore(seed=1)
    cp = {"snapshot_id": "cp_1", "streams": {"infra_net": [{"value": 1.0}]}}
    s = store.import_cyber_physical_snapshot(cp)
    assert any("infra" in e.entity_type for e in s.entities)


# --- impact_simulator coverage gaps ---

def test_simulate_horizon_with_perturbations():
    sim = ImpactSimulator(seed=1)
    e = WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT, state={"status": "active"})
    snapshot = WorldModelSnapshot(snapshot_id="s1", timestamp="2024-01-01T00:00:00", entities=[e])
    scenario = WorldScenario(scenario_id="sc1", initial_state_id="s1", horizon_ticks=2, perturbations=[{"type": "safety_hazard", "target_entity_id": "e1", "delta_safety": 0.3}])
    horizon = sim.simulate_horizon(snapshot, scenario, ticks=2)
    assert len(horizon) == 2


def test_compute_safety_preservation_with_constraint_violations():
    from speace_core.cellular_brain.world_model.world_model_models import CausalSimulationResult
    sim = ImpactSimulator(seed=1)
    causal = CausalSimulationResult(scenario_id="sc1", predicted_safety_pressure=0.2, constraint_violations_detected=2)
    score = sim.compute_safety_preservation(causal)
    assert score < 1.0


# --- world_model_policy_engine coverage gaps ---

def test_is_bus_message_safe_unsafe_type():
    pe = WorldModelPolicyEngine()
    ok, reason = pe.is_bus_message_safe({"type": "control"})
    assert ok is False
    assert "unsafe_bus_type" in reason


def test_block_real_action_attempt_safe():
    pe = WorldModelPolicyEngine()
    blocked, reason = pe.block_real_action_attempt({"type": "observe"})
    assert blocked is False
    assert reason is None


# --- world_model_sandbox coverage gaps ---

def test_generate_sandbox_report_with_suffix():
    sandbox = ExternalWorldModelSandbox(seed=1)
    suite = {"aggregate_verdict": "EXTERNAL_WORLD_MODEL_SANDBOX_VALIDATED", "proceed_to_t61b": True, "profile_count": 1, "total_snapshots_generated": 1, "total_scenarios_built": 1, "total_simulations_run": 1, "profile_results": [{"profile_name": "p1", "verdict": "VALIDATED", "world_model_sandbox_score": 0.8}]}
    json_path, md_path = sandbox.generate_sandbox_report(suite, suffix="test")
    assert "_test" in str(json_path)
    assert json_path.exists()
