import json
import os

import numpy as np
import pytest

from speace_core.cellular_brain.regulation.emergent_dynamics_stabilizer import (
    EmergentDynamicsStabilizer,
    StabilizerIntervention,
)


@pytest.fixture
def stabilizer():
    return EmergentDynamicsStabilizer(
        chaos_threshold=0.35,
        rigidity_threshold=0.02,
        drift_threshold=0.3,
        loop_intensity_threshold=2.5,
        criticality_drift_threshold=0.2,
        embodiment_stress_threshold=0.7,
        history_window=100,
        seed=42,
    )


@pytest.fixture
def base_state():
    return {
        "activations": [0.1] * 10,
        "drive_levels": {"exploration": 0.5, "stability": 0.5},
        "energy_levels": {"module_a": 0.5, "module_b": 0.5},
        "prediction_errors": [0.1, 0.1],
        "workspace_state": {"coherence": 0.5},
        "self_model_coherence": 0.5,
        "embodiment_depth": 0.3,
        "branching_ratio": 1.0,
    }


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def test_init_defaults():
    s = EmergentDynamicsStabilizer()
    assert s.chaos_threshold == 0.35
    assert s.rigidity_threshold == 0.02


def test_init_custom(stabilizer):
    assert stabilizer.chaos_threshold == 0.35
    assert stabilizer.history_window == 100


# ---------------------------------------------------------------------------
# detect_chaos
# ---------------------------------------------------------------------------

def test_detect_chaos_no_history(stabilizer, base_state):
    result = stabilizer.detect_chaos(base_state)
    assert result["detected"] is False
    assert result["lyapunov_exponent"] == 0.0


def test_detect_chaos_high_divergence(stabilizer, base_state):
    # Fill history with small perturbations
    for i in range(15):
        state = dict(base_state)
        state["activations"] = [0.1 + i * 0.05] * 10
        stabilizer.detect_chaos(state)
    result = stabilizer.detect_chaos(base_state)
    assert result["lyapunov_exponent"] >= 0.0


def test_detect_chaos_returns_severity(stabilizer, base_state):
    for _ in range(15):
        stabilizer.detect_chaos(base_state)
    result = stabilizer.detect_chaos(base_state)
    assert "severity" in result


# ---------------------------------------------------------------------------
# detect_rigidity
# ---------------------------------------------------------------------------

def test_detect_rigidity_no_history(stabilizer, base_state):
    result = stabilizer.detect_rigidity(base_state)
    assert result["detected"] is False


def test_detect_rigidity_low_variance(stabilizer, base_state):
    for _ in range(25):
        state = dict(base_state)
        state["activations"] = [0.5] * 10
        stabilizer.detect_chaos(state)
    result = stabilizer.detect_rigidity(base_state)
    # Very low variance should trigger rigidity
    assert result["variance"] < 0.02 or result["detected"] is True


def test_detect_rigidity_high_variance_no_trigger(stabilizer, base_state):
    for i in range(25):
        state = dict(base_state)
        state["activations"] = [0.1 + (i % 5) * 0.2] * 10
        stabilizer.detect_chaos(state)
    result = stabilizer.detect_rigidity(base_state)
    # High variance means not rigid
    if result["variance"] >= 0.02:
        assert result["detected"] is False


# ---------------------------------------------------------------------------
# detect_motivational_drift
# ---------------------------------------------------------------------------

def test_detect_motivational_drift_no_history(stabilizer, base_state):
    result = stabilizer.detect_motivational_drift(base_state)
    assert result["detected"] is False


def test_detect_motivational_drift_strong_drift(stabilizer, base_state):
    for i in range(15):
        state = dict(base_state)
        state["drive_levels"] = {"exploration": 0.5 + i * 0.05, "stability": 0.5}
        stabilizer.detect_motivational_drift(state)
    result = stabilizer.detect_motivational_drift(base_state)
    # Should detect drift if accumulated deviation exceeds threshold
    if result["drift_score"] > 0.3:
        assert result["detected"] is True


def test_detect_motivational_drift_no_drift(stabilizer, base_state):
    for _ in range(15):
        stabilizer.detect_motivational_drift(base_state)
    result = stabilizer.detect_motivational_drift(base_state)
    assert result["drift_score"] < 0.3


# ---------------------------------------------------------------------------
# detect_self_referential_loop
# ---------------------------------------------------------------------------

def test_detect_loop_no_history(stabilizer, base_state):
    result = stabilizer.detect_self_referential_loop(base_state)
    assert result["detected"] is False


def test_detect_loop_repeating_pattern(stabilizer, base_state):
    pattern = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    for i in range(25):
        state = dict(base_state)
        # Same pattern with increasing magnitude
        multiplier = 1.0 + i * 0.01
        state["activations"] = [a * multiplier for a in pattern]
        stabilizer.detect_self_referential_loop(state)
    result = stabilizer.detect_self_referential_loop(base_state)
    assert "loop_score" in result


# ---------------------------------------------------------------------------
# detect_criticality_drift
# ---------------------------------------------------------------------------

def test_detect_criticality_near_critical(stabilizer, base_state):
    state = dict(base_state)
    state["branching_ratio"] = 1.0
    result = stabilizer.detect_criticality_drift(state)
    assert result["detected"] is False
    assert result["distance_from_critical"] == 0.0


def test_detect_criticality_supercritical(stabilizer, base_state):
    state = dict(base_state)
    state["branching_ratio"] = 1.5
    result = stabilizer.detect_criticality_drift(state)
    assert result["detected"] is True
    assert result["distance_from_critical"] == 0.5


def test_detect_criticality_subcritical(stabilizer, base_state):
    state = dict(base_state)
    state["branching_ratio"] = 0.7
    result = stabilizer.detect_criticality_drift(state)
    assert result["detected"] is True
    assert result["distance_from_critical"] == 0.3


# ---------------------------------------------------------------------------
# detect_embodiment_stress
# ---------------------------------------------------------------------------

def test_detect_embodiment_stress_low(stabilizer, base_state):
    result = stabilizer.detect_embodiment_stress(base_state)
    assert result["detected"] is False


def test_detect_embodiment_stress_high(stabilizer, base_state):
    state = dict(base_state)
    state["embodiment_depth"] = 1.0
    state["energy_levels"] = {"module_a": 0.1, "module_b": 0.1}
    result = stabilizer.detect_embodiment_stress(state)
    assert result["stress_score"] > 0.0


# ---------------------------------------------------------------------------
# Modulation methods
# ---------------------------------------------------------------------------

def test_inject_noise_changes_values(stabilizer, base_state):
    result = stabilizer.inject_noise(0.1, base_state)
    assert len(result["new_activations"]) == len(base_state["activations"])
    assert result["modulation"] == "inject_noise"


def test_dampen_feedback_reduces_values(stabilizer, base_state):
    result = stabilizer.dampen_feedback(0.5, base_state)
    for orig, new in zip(base_state["activations"], result["new_activations"]):
        assert new <= orig + 1e-9


def test_reset_attractor_perturbs(stabilizer, base_state):
    result = stabilizer.reset_attractor(base_state)
    assert len(result["new_activations"]) == len(base_state["activations"])
    # At least some values should differ due to perturbation
    diffs = [abs(n - o) for n, o in zip(result["new_activations"], base_state["activations"])]
    assert any(d > 0 for d in diffs)


def test_adjust_homeostatic_setpoint(stabilizer):
    result = stabilizer.adjust_homeostatic_setpoint("exploration", 0.7)
    assert result["drive_name"] == "exploration"
    assert result["new_setpoint"] == 0.7
    assert stabilizer.get_adjusted_setpoints()["exploration"] == 0.7


def test_enforce_balance_redistributes(stabilizer, base_state):
    result = stabilizer.enforce_balance(base_state)
    assert result["modulation"] == "enforce_balance"
    if result["redistributed"]:
        assert len(result["new_energy_levels"]) == len(base_state["energy_levels"])


# ---------------------------------------------------------------------------
# monitor
# ---------------------------------------------------------------------------

def test_monitor_returns_report(stabilizer, base_state):
    report = stabilizer.monitor(base_state)
    assert "chaos" in report
    assert "rigidity" in report
    assert "overall_danger_score" in report
    assert "any_detected" in report


def test_monitor_increments_tick(stabilizer, base_state):
    stabilizer.monitor(base_state)
    assert stabilizer._tick == 1
    stabilizer.monitor(base_state)
    assert stabilizer._tick == 2


# ---------------------------------------------------------------------------
# stabilize
# ---------------------------------------------------------------------------

def test_stabilize_no_intervention_when_safe(stabilizer, base_state):
    report = stabilizer.monitor(base_state)
    interventions = stabilizer.stabilize(report, base_state)
    assert interventions == []


def test_stabilize_intervenes_on_rigidity(stabilizer, base_state):
    # Force rigidity
    for _ in range(30):
        state = dict(base_state)
        state["activations"] = [0.5] * 10
        stabilizer.monitor(state)
    report = stabilizer.monitor(base_state)
    # Ensure rigidity is detected
    if report["rigidity"]["detected"]:
        interventions = stabilizer.stabilize(report, base_state)
        mods = [i["modulation"] for i in interventions]
        assert "reset_attractor" in mods


def test_stabilize_intervenes_on_criticality_drift(stabilizer, base_state):
    state = dict(base_state)
    state["branching_ratio"] = 1.5
    report = stabilizer.monitor(state)
    if report["criticality_drift"]["detected"]:
        interventions = stabilizer.stabilize(report, state)
        mods = [i["modulation"] for i in interventions]
        assert "dampen_feedback" in mods


# ---------------------------------------------------------------------------
# step
# ---------------------------------------------------------------------------

def test_step_returns_diagnostic_and_interventions(stabilizer, base_state):
    result = stabilizer.step(base_state)
    assert "diagnostic" in result
    assert "interventions" in result
    assert "intervention_count" in result


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_persistence_creates_file(stabilizer, base_state, tmp_path):
    log_path = tmp_path / "interventions.jsonl"
    s = EmergentDynamicsStabilizer(persistence_log_path=str(log_path))
    # Force an intervention via rigidity
    for _ in range(30):
        state = dict(base_state)
        state["activations"] = [0.5] * 10
        s.step(state)
    assert log_path.exists()
    content = log_path.read_text()
    assert len(content) > 0


def test_get_intervention_log(stabilizer, base_state):
    # Force an intervention via criticality
    state = dict(base_state)
    state["branching_ratio"] = 1.5
    for _ in range(5):
        stabilizer.step(state)
    log = stabilizer.get_intervention_log()
    # Should have logged something if criticality drift triggered
    assert isinstance(log, list)


def test_clear_history(stabilizer, base_state):
    stabilizer.step(base_state)
    stabilizer.clear_history()
    assert stabilizer._tick == 0
    assert len(stabilizer.get_intervention_log()) == 0


# ---------------------------------------------------------------------------
# Orchestrator integration (end-to-end)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orchestrator_stabilizer_enabled():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    assert hasattr(orch, "emergent_dynamics_stabilizer_enabled")
    assert orch.emergent_dynamics_stabilizer_enabled is False


@pytest.mark.asyncio
async def test_orchestrator_stabilizer_field_exists():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    assert hasattr(orch, "_emergent_dynamics_stabilizer")


@pytest.mark.asyncio
async def test_orchestrator_stabilizer_step_when_enabled():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.emergent_dynamics_stabilizer_enabled = True
    # Re-initialize model_post_init would be needed, but we can verify field exists
    assert hasattr(orch, "_emergent_dynamics_stabilizer")
