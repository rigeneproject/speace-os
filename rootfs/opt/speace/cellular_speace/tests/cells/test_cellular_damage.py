import pytest

from speace_core.cellular_brain.cells.cellular_damage import (
    CellularDamageEngine,
    CellularDamageResult,
    CellularDamageState,
)
from speace_core.cellular_brain.cells.cellular_stress import CellularStressEngine, CellularStressResult
from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _make_circuit():
    n1 = DigitalNeuron(cell_id="n1", role="digital_neuron", energy=1.0, activation=0.0, consecutive_fires=0, apoptosis_risk=0.0)
    n2 = DigitalNeuron(cell_id="n2", role="digital_neuron", energy=0.2, activation=2.0, consecutive_fires=5, apoptosis_risk=0.9)
    circuit = NeuralCircuit(circuit_id="test", input_neurons=[n1], hidden_neurons=[n2], output_neurons=[])
    return circuit


# ------------------------------------------------------------------ #
# Import & construction
# ------------------------------------------------------------------ #

def test_damage_engine_importable():
    assert CellularDamageEngine is not None


def test_damage_state_model():
    d = CellularDamageState(cell_id="c1", damage_score=0.3, level="reversible")
    assert d.level == "reversible"


# ------------------------------------------------------------------ #
# Evaluation
# ------------------------------------------------------------------ #

def test_evaluate_returns_result():
    circuit = _make_circuit()
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    result = damage_engine.evaluate(circuit, stress_result)
    assert isinstance(result, CellularDamageResult)
    assert len(result.per_cell) == 2


def test_damage_correlates_with_stress():
    circuit = _make_circuit()
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    result = damage_engine.evaluate(circuit, stress_result)
    assert result.per_cell["n2"].damage_score >= result.per_cell["n1"].damage_score


def test_damage_accumulates_over_ticks():
    circuit = _make_circuit()
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    r1 = damage_engine.evaluate(circuit, stress_result)
    r2 = damage_engine.evaluate(circuit, stress_result, previous_damage=r1.per_cell)
    assert r2.per_cell["n2"].damage_score >= r1.per_cell["n2"].damage_score
    assert r2.per_cell["n2"].cumulative_stress >= r1.per_cell["n2"].cumulative_stress


def test_empty_circuit():
    circuit = NeuralCircuit(circuit_id="empty", input_neurons=[], hidden_neurons=[], output_neurons=[])
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    result = damage_engine.evaluate(circuit, stress_result)
    assert result.mean_damage == 0.0


# ------------------------------------------------------------------ #
# Levels
# ------------------------------------------------------------------ #

def test_level_none_for_healthy():
    n = DigitalNeuron(cell_id="n", role="digital_neuron", energy=1.0, activation=0.0, consecutive_fires=0, apoptosis_risk=0.0)
    circuit = NeuralCircuit(circuit_id="t", input_neurons=[n], hidden_neurons=[], output_neurons=[])
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    result = damage_engine.evaluate(circuit, stress_result)
    assert result.per_cell["n"].level == "none"


def test_level_classifications():
    engine = CellularDamageEngine(
        reversible_threshold=0.20,
        functional_threshold=0.40,
        structural_threshold=0.60,
        critical_threshold=0.80,
    )
    assert engine.reversible_threshold == 0.20
    assert engine.functional_threshold == 0.40


# ------------------------------------------------------------------ #
# Granular damage fields
# ------------------------------------------------------------------ #

def test_granular_damage_fields_present():
    circuit = _make_circuit()
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    result = damage_engine.evaluate(circuit, stress_result)
    for state in result.per_cell.values():
        assert hasattr(state, "reversible_damage")
        assert hasattr(state, "functional_damage")
        assert hasattr(state, "structural_damage")
        assert hasattr(state, "critical_damage")
        total = state.reversible_damage + state.functional_damage + state.structural_damage + state.critical_damage
        assert abs(total - state.damage_score) < 1e-6
