import pytest

from speace_core.cellular_brain.analysis.recovery_policy_selector import (
    RecoveryPolicy,
    RegressionGuardThresholds,
)
from speace_core.cellular_brain.analysis.regression_guard import (
    RegressionGuard,
    RegressionGuardResult,
)


# ------------------------------------------------------------------ #
# Import & construction
# ------------------------------------------------------------------ #

def test_guard_importable():
    assert RegressionGuard is not None
    assert RegressionGuardResult is not None


def test_guard_evaluate_stable():
    metrics = {
        "cognitive_score": 0.50,
        "coherence_phi": 0.30,
        "energy_efficiency": 0.25,
        "suppression_cost": 0.10,
        "long_horizon_recovery_score": 0.20,
        "emergency_state_ratio": 0.20,
        "state_entropy": 0.80,
    }
    thr = RegressionGuardThresholds(
        min_cognitive_score=0.40,
        min_phi=0.20,
        min_energy_efficiency=0.15,
        max_suppression_cost=0.15,
        min_long_horizon_recovery_score=0.10,
        max_emergency_state_ratio=0.30,
        min_state_entropy=0.50,
    )
    result = RegressionGuard.evaluate(metrics, thresholds=thr)
    assert result.verdict == "POLICY_STABLE"
    assert result.cognitive_score_ok is True
    assert result.phi_ok is True
    assert result.energy_efficiency_ok is True
    assert result.suppression_cost_ok is True
    assert result.violations == {}


def test_guard_evaluate_minor_regression():
    metrics = {
        "cognitive_score": 0.50,
        "coherence_phi": 0.30,
        "energy_efficiency": 0.25,
        "suppression_cost": 0.10,
        "long_horizon_recovery_score": 0.20,
        "emergency_state_ratio": 0.20,
        "state_entropy": 0.40,
    }
    thr = RegressionGuardThresholds(
        min_cognitive_score=0.40,
        min_phi=0.20,
        min_energy_efficiency=0.15,
        max_suppression_cost=0.15,
        min_long_horizon_recovery_score=0.10,
        max_emergency_state_ratio=0.30,
        min_state_entropy=0.50,
    )
    result = RegressionGuard.evaluate(metrics, thresholds=thr)
    assert result.verdict == "POLICY_MINOR_REGRESSION"
    assert result.state_entropy_ok is False
    assert "state_entropy" in result.violations


def test_guard_evaluate_major_regression():
    metrics = {
        "cognitive_score": 0.30,
        "coherence_phi": 0.30,
        "energy_efficiency": 0.25,
        "suppression_cost": 0.10,
        "long_horizon_recovery_score": 0.20,
        "emergency_state_ratio": 0.20,
        "state_entropy": 0.80,
    }
    thr = RegressionGuardThresholds(
        min_cognitive_score=0.40,
        min_phi=0.20,
        min_energy_efficiency=0.15,
        max_suppression_cost=0.15,
        min_long_horizon_recovery_score=0.10,
        max_emergency_state_ratio=0.30,
        min_state_entropy=0.50,
    )
    result = RegressionGuard.evaluate(metrics, thresholds=thr)
    assert result.verdict == "POLICY_MAJOR_REGRESSION"
    assert result.cognitive_score_ok is False


def test_guard_evaluate_unsafe():
    metrics = {
        "cognitive_score": 0.50,
        "coherence_phi": 0.03,
        "energy_efficiency": 0.25,
        "suppression_cost": 0.10,
        "long_horizon_recovery_score": 0.20,
        "emergency_state_ratio": 0.20,
        "state_entropy": 0.80,
    }
    thr = RegressionGuardThresholds(
        min_cognitive_score=0.40,
        min_phi=0.20,
        min_energy_efficiency=0.15,
        max_suppression_cost=0.15,
        min_long_horizon_recovery_score=0.10,
        max_emergency_state_ratio=0.30,
        min_state_entropy=0.50,
    )
    result = RegressionGuard.evaluate(metrics, thresholds=thr)
    assert result.verdict == "POLICY_UNSAFE"


def test_guard_evaluate_energy_unsafe():
    metrics = {
        "cognitive_score": 0.50,
        "coherence_phi": 0.30,
        "energy_efficiency": 0.03,
        "suppression_cost": 0.10,
        "long_horizon_recovery_score": 0.20,
        "emergency_state_ratio": 0.20,
        "state_entropy": 0.80,
    }
    thr = RegressionGuardThresholds(
        min_cognitive_score=0.40,
        min_phi=0.20,
        min_energy_efficiency=0.15,
        max_suppression_cost=0.15,
        min_long_horizon_recovery_score=0.10,
        max_emergency_state_ratio=0.30,
        min_state_entropy=0.50,
    )
    result = RegressionGuard.evaluate(metrics, thresholds=thr)
    assert result.verdict == "POLICY_UNSAFE"


def test_guard_with_policy():
    policy = RecoveryPolicy(
        regression_guard_thresholds=RegressionGuardThresholds(
            min_cognitive_score=0.40,
            min_phi=0.20,
            min_energy_efficiency=0.15,
            max_suppression_cost=0.15,
            min_long_horizon_recovery_score=0.10,
            max_emergency_state_ratio=0.30,
            min_state_entropy=0.50,
        ),
    )
    metrics = {
        "cognitive_score": 0.50,
        "coherence_phi": 0.30,
        "energy_efficiency": 0.25,
        "suppression_cost": 0.10,
        "long_horizon_recovery_score": 0.20,
        "emergency_state_ratio": 0.20,
        "state_entropy": 0.80,
    }
    result = RegressionGuard.evaluate(metrics, policy=policy)
    assert result.verdict == "POLICY_STABLE"


def test_guard_evaluate_benchmark_metrics():
    fm = {
        "cognitive_score": 0.50,
        "coherence_phi": 0.30,
        "energy_efficiency": 0.25,
        "suppression_cost": 0.10,
        "long_horizon_recovery_score": 0.20,
        "emergency_state_ratio": 0.20,
        "state_entropy": 0.80,
    }
    thr = RegressionGuardThresholds(
        min_cognitive_score=0.40,
        min_phi=0.20,
        min_energy_efficiency=0.15,
        max_suppression_cost=0.15,
        min_long_horizon_recovery_score=0.10,
        max_emergency_state_ratio=0.30,
        min_state_entropy=0.50,
    )
    result = RegressionGuard.evaluate(fm, thresholds=thr)
    assert result.verdict == "POLICY_STABLE"


def test_guard_no_violations_all_ok():
    result = RegressionGuard.evaluate({
        "cognitive_score": 0.60,
        "coherence_phi": 0.40,
        "energy_efficiency": 0.30,
        "suppression_cost": 0.05,
        "long_horizon_recovery_score": 0.30,
        "emergency_state_ratio": 0.10,
        "state_entropy": 1.0,
    })
    assert result.verdict == "POLICY_STABLE"
    assert result.violations == {}


# ------------------------------------------------------------------ #
# Edge cases
# ------------------------------------------------------------------ #

def test_guard_empty_metrics_defaults():
    result = RegressionGuard.evaluate({})
    assert result.cognitive_score_ok is False
    assert result.phi_ok is False
    assert result.energy_efficiency_ok is False
    # phi=0.0 and energy=0.0 trigger UNSAFE override
    assert result.verdict == "POLICY_UNSAFE"


def test_guard_none_metrics():
    result = RegressionGuard.evaluate({"cognitive_score": None, "coherence_phi": None})
    assert result.cognitive_score_ok is False
    assert result.phi_ok is False
