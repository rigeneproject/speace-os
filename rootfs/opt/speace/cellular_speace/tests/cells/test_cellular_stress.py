import pytest

from speace_core.cellular_brain.cells.cellular_stress import (
    CellularStressEngine,
    CellularStressResult,
    CellularStressState,
)
from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _make_circuit_with_stressed_neurons():
    n1 = DigitalNeuron(cell_id="n1", role="digital_neuron", energy=1.0, activation=0.0, consecutive_fires=0, apoptosis_risk=0.0)
    n2 = DigitalNeuron(cell_id="n2", role="digital_neuron", energy=0.3, activation=1.8, consecutive_fires=5, apoptosis_risk=0.8)
    n3 = DigitalNeuron(cell_id="n3", role="digital_neuron", energy=0.5, activation=0.5, consecutive_fires=2, apoptosis_risk=0.2)
    circuit = NeuralCircuit(
        circuit_id="test",
        input_neurons=[n1],
        hidden_neurons=[n2, n3],
        output_neurons=[],
    )
    return circuit


# ------------------------------------------------------------------ #
# Import & construction
# ------------------------------------------------------------------ #

def test_stress_engine_importable():
    assert CellularStressEngine is not None


def test_stress_state_model():
    s = CellularStressState(cell_id="c1", stress_score=0.5, level="high")
    assert s.cell_id == "c1"
    assert s.stress_score == 0.5
    assert s.level == "high"


# ------------------------------------------------------------------ #
# Evaluation
# ------------------------------------------------------------------ #

def test_evaluate_returns_result():
    circuit = _make_circuit_with_stressed_neurons()
    engine = CellularStressEngine()
    result = engine.evaluate(circuit)
    assert isinstance(result, CellularStressResult)
    assert len(result.per_cell) == 3


def test_stress_levels_ordered():
    circuit = _make_circuit_with_stressed_neurons()
    engine = CellularStressEngine()
    result = engine.evaluate(circuit)
    n1 = result.per_cell["n1"]
    n2 = result.per_cell["n2"]
    assert n2.stress_score > n1.stress_score


def test_mean_and_max_stress():
    circuit = _make_circuit_with_stressed_neurons()
    engine = CellularStressEngine()
    result = engine.evaluate(circuit)
    assert result.mean_stress > 0.0
    assert result.max_stress >= result.mean_stress


def test_critical_count():
    circuit = _make_circuit_with_stressed_neurons()
    engine = CellularStressEngine(critical_threshold=0.7)
    result = engine.evaluate(circuit)
    assert result.critical_count >= 0


def test_low_energy_increases_stress():
    n = DigitalNeuron(cell_id="n_low", role="digital_neuron", energy=0.1, activation=0.0, consecutive_fires=0, apoptosis_risk=0.0)
    circuit = NeuralCircuit(circuit_id="t", input_neurons=[n], hidden_neurons=[], output_neurons=[])
    engine = CellularStressEngine()
    result = engine.evaluate(circuit)
    assert result.per_cell["n_low"].stress_score > 0.0
    assert result.per_cell["n_low"].energy_stress > 0.0


def test_high_firing_increases_stress():
    n = DigitalNeuron(cell_id="n_fire", role="digital_neuron", energy=1.0, activation=0.0, consecutive_fires=5, apoptosis_risk=0.0)
    circuit = NeuralCircuit(circuit_id="t", input_neurons=[n], hidden_neurons=[], output_neurons=[])
    engine = CellularStressEngine()
    result = engine.evaluate(circuit)
    assert result.per_cell["n_fire"].firing_rate_contribution > 0.0


def test_empty_circuit():
    circuit = NeuralCircuit(circuit_id="empty", input_neurons=[], hidden_neurons=[], output_neurons=[])
    engine = CellularStressEngine()
    result = engine.evaluate(circuit)
    assert result.mean_stress == 0.0
    assert result.max_stress == 0.0


# ------------------------------------------------------------------ #
# Thresholds T42B
# ------------------------------------------------------------------ #

def test_level_normal_for_healthy():
    n = DigitalNeuron(cell_id="n", role="digital_neuron", energy=1.0, activation=0.0, consecutive_fires=0, apoptosis_risk=0.0)
    circuit = NeuralCircuit(circuit_id="t", input_neurons=[n], hidden_neurons=[], output_neurons=[])
    engine = CellularStressEngine()
    result = engine.evaluate(circuit)
    assert result.per_cell["n"].level == "normal"


def test_level_elevated():
    n = DigitalNeuron(cell_id="n", role="digital_neuron", energy=0.5, activation=1.0, consecutive_fires=2, apoptosis_risk=0.3)
    circuit = NeuralCircuit(circuit_id="t", input_neurons=[n], hidden_neurons=[], output_neurons=[])
    engine = CellularStressEngine()
    result = engine.evaluate(circuit)
    assert result.per_cell["n"].level in ("elevated", "high", "critical")


def test_granular_stress_fields_present():
    n = DigitalNeuron(cell_id="n", role="digital_neuron", energy=0.5, activation=1.0, consecutive_fires=2, apoptosis_risk=0.3)
    n.targets = ["a"] * 5
    n.error_history = [0.1] * 3
    circuit = NeuralCircuit(circuit_id="t", input_neurons=[n], hidden_neurons=[], output_neurons=[])
    engine = CellularStressEngine()
    result = engine.evaluate(circuit)
    s = result.per_cell["n"]
    assert s.activation_stress >= 0.0
    assert s.energy_stress >= 0.0
    assert s.synaptic_stress >= 0.0
    assert s.routing_stress >= 0.0
    assert s.plasticity_stress >= 0.0
    assert s.confidence_stress >= 0.0
