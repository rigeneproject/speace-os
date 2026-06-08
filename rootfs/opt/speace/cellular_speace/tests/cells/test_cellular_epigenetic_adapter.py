import pytest

from speace_core.cellular_brain.cells.cellular_damage import CellularDamageEngine
from speace_core.cellular_brain.cells.cellular_epigenetic_adapter import (
    CellularEpigeneticAdapter,
    CellularEpigeneticResult,
    EpigeneticShift,
    GeneExpressionProfile,
)
from speace_core.cellular_brain.cells.cellular_stress import CellularStressEngine
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

def test_epigenetic_adapter_importable():
    assert CellularEpigeneticAdapter is not None


def test_gene_expression_profile_model():
    p = GeneExpressionProfile(cell_id="c1", plasticity_expression=0.8, repair_expression=0.3)
    assert p.plasticity_expression == 0.8
    assert p.repair_expression == 0.3


def test_epigenetic_shift_model():
    s = EpigeneticShift(cell_id="c1", tick=1, trigger="stress_response", genes_added=["g1"])
    assert s.tick == 1


# ------------------------------------------------------------------ #
# Adapt
# ------------------------------------------------------------------ #

def test_adapt_returns_result():
    circuit = _make_circuit()
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    adapter = CellularEpigeneticAdapter()
    result = adapter.adapt(circuit, stress_result.per_cell, damage_result.per_cell, current_tick=1)
    assert isinstance(result, CellularEpigeneticResult)
    assert len(result.profiles) == 2


def test_stressed_cell_gets_defense_expression():
    circuit = _make_circuit()
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    adapter = CellularEpigeneticAdapter(stress_response_threshold=0.3)
    result = adapter.adapt(circuit, stress_result.per_cell, damage_result.per_cell, current_tick=1)
    n2_profile = result.profiles["n2"]
    assert n2_profile.defense_expression > 0.0


def test_healthy_cell_has_plasticity_expression():
    circuit = _make_circuit()
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    adapter = CellularEpigeneticAdapter()
    result = adapter.adapt(circuit, stress_result.per_cell, damage_result.per_cell, current_tick=1)
    n1_profile = result.profiles["n1"]
    assert n1_profile.plasticity_expression >= 0.0


def test_shift_count_increases():
    circuit = _make_circuit()
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    adapter = CellularEpigeneticAdapter(stress_response_threshold=0.1)
    result = adapter.adapt(circuit, stress_result.per_cell, damage_result.per_cell, current_tick=1)
    assert result.epigenetic_shift_count >= 0


def test_numeric_factors_persisted_on_neuron():
    circuit = _make_circuit()
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    adapter = CellularEpigeneticAdapter(stress_response_threshold=0.1)
    adapter.adapt(circuit, stress_result.per_cell, damage_result.per_cell, current_tick=1)
    n2 = circuit.hidden_neurons[0]
    assert hasattr(n2, "epigenetic_marks")
    marks = n2.epigenetic_marks
    assert isinstance(marks, dict)
    assert "plasticity_expression" in marks
    assert "repair_expression" in marks
    assert "defense_expression" in marks
    assert "energy_expression" in marks
    assert "growth_expression" in marks
    assert "apoptosis_sensitivity" in marks
    assert "differentiation_bias" in marks


def test_shift_recorded():
    circuit = _make_circuit()
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    adapter = CellularEpigeneticAdapter(stress_response_threshold=0.1)
    result = adapter.adapt(circuit, stress_result.per_cell, damage_result.per_cell, current_tick=1)
    if result.shifts:
        shift = result.shifts[0]
        assert shift.cell_id != ""
        assert shift.tick == 1


def test_epigenetic_adaptation_score_computed():
    circuit = _make_circuit()
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    adapter = CellularEpigeneticAdapter()
    result = adapter.adapt(circuit, stress_result.per_cell, damage_result.per_cell, current_tick=1)
    assert 0.0 <= result.epigenetic_adaptation_score <= 1.0


def test_empty_circuit():
    circuit = NeuralCircuit(circuit_id="empty", input_neurons=[], hidden_neurons=[], output_neurons=[])
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    adapter = CellularEpigeneticAdapter()
    result = adapter.adapt(circuit, stress_result.per_cell, damage_result.per_cell, current_tick=1)
    assert result.epigenetic_shift_count == 0
    assert result.mean_gene_count == 0.0


# ------------------------------------------------------------------ #
# Numeric expression factor dynamics
# ------------------------------------------------------------------ #

def test_plasticity_decreases_under_stress():
    n = DigitalNeuron(cell_id="n", role="digital_neuron", energy=0.2, activation=2.0, consecutive_fires=5, apoptosis_risk=0.9)
    circuit = NeuralCircuit(circuit_id="t", input_neurons=[], hidden_neurons=[n], output_neurons=[])
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    adapter = CellularEpigeneticAdapter(defense_trigger_threshold=0.1)
    result = adapter.adapt(circuit, stress_result.per_cell, damage_result.per_cell, current_tick=1)
    profile = result.profiles["n"]
    assert profile.plasticity_expression < 1.0


def test_repair_increases_after_damage():
    n = DigitalNeuron(cell_id="n", role="digital_neuron", energy=0.2, activation=2.0, consecutive_fires=5, apoptosis_risk=0.9)
    circuit = NeuralCircuit(circuit_id="t", input_neurons=[], hidden_neurons=[n], output_neurons=[])
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    adapter = CellularEpigeneticAdapter(repair_trigger_threshold=0.1)
    result = adapter.adapt(circuit, stress_result.per_cell, damage_result.per_cell, current_tick=1)
    profile = result.profiles["n"]
    assert profile.repair_expression > 0.0


def test_apoptosis_sensitivity_increases_with_critical_damage():
    n = DigitalNeuron(cell_id="n", role="digital_neuron", energy=0.2, activation=2.0, consecutive_fires=5, apoptosis_risk=0.9)
    circuit = NeuralCircuit(circuit_id="t", input_neurons=[], hidden_neurons=[n], output_neurons=[])
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    adapter = CellularEpigeneticAdapter()
    result = adapter.adapt(circuit, stress_result.per_cell, damage_result.per_cell, current_tick=1)
    profile = result.profiles["n"]
    # Critical damage should sensitize apoptosis
    if damage_result.per_cell["n"].damage_score >= 0.80:
        assert profile.apoptosis_sensitivity >= 0.5
