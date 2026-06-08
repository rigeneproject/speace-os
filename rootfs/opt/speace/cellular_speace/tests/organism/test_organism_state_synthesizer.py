import pytest

from speace_core.cellular_brain.organism import OrganismState, OrganismStateSynthesizer


def test_state_synthesizer_computes_global_health():
    synth = OrganismStateSynthesizer()
    metrics = {"subsystem_health_scores": [0.8, 0.9, 1.0]}
    score = synth.compute_global_health_score(metrics)
    assert 0.89 <= score <= 0.91


def test_state_synthesizer_computes_recovery_pressure():
    synth = OrganismStateSynthesizer()
    metrics = {"recovery_load": 0.3, "repair_count": 5}
    pressure = synth.compute_recovery_pressure(metrics)
    assert pressure == 0.55


def test_state_synthesizer_computes_evolutionary_pressure():
    synth = OrganismStateSynthesizer()
    metrics = {"evolutionary_cost": 0.4, "mutation_rate": 0.3}
    pressure = synth.compute_evolutionary_pressure(metrics)
    assert pressure == 0.7


def test_state_synthesizer_detects_conflicts():
    synth = OrganismStateSynthesizer()
    state = OrganismState(recovery_pressure=0.6, evolutionary_pressure=0.6)
    conflicts = synth.detect_state_conflicts(state)
    assert "recovery_evolution_conflict" in conflicts


def test_state_synthesizer_detects_safety_mismatch():
    synth = OrganismStateSynthesizer()
    state = OrganismState(safety_risk_score=0.6, global_health_score=0.9)
    conflicts = synth.detect_state_conflicts(state)
    assert "safety_health_mismatch" in conflicts


def test_state_synthesizer_detects_evolution_under_critical():
    synth = OrganismStateSynthesizer()
    state = OrganismState(metabolic_mode="critical", evolutionary_pressure=0.4)
    conflicts = synth.detect_state_conflicts(state)
    assert "evolution_under_critical_metabolism" in conflicts


def test_synthesize_state_sets_fields():
    synth = OrganismStateSynthesizer()
    metrics = {
        "metabolic_mode": "stress",
        "global_energy_reserve": 0.5,
        "active_subsystems": ["safety", "metabolism"],
        "degraded_subsystems": ["evo"],
    }
    state = synth.synthesize_state(metrics, tick=3)
    assert state.tick == 3
    assert state.metabolic_mode == "stress"
    assert state.global_energy_reserve == 0.5
    assert "safety" in state.active_subsystems
    assert "evo" in state.degraded_subsystems
