import pytest

from speace_core.cellular_brain.cells.cellular_damage import CellularDamageEngine
from speace_core.cellular_brain.cells.cellular_repair_engine import (
    CellularRepairEngine,
    CellularRepairResult,
    RepairAction,
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

def test_repair_engine_importable():
    assert CellularRepairEngine is not None


def test_repair_action_model():
    a = RepairAction(cell_id="c1", action="restore_energy", success=True, energy_cost=0.05, damage_before=0.3, damage_after=0.0)
    assert a.success is True


# ------------------------------------------------------------------ #
# Run
# ------------------------------------------------------------------ #

def test_run_returns_result():
    circuit = _make_circuit()
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    repair_engine = CellularRepairEngine()
    result = repair_engine.run(circuit, damage_result.per_cell)
    assert isinstance(result, CellularRepairResult)


def test_repair_reduces_damage():
    circuit = _make_circuit()
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    repair_engine = CellularRepairEngine()
    result = repair_engine.run(circuit, damage_result.per_cell)
    for action in result.actions:
        if action.success and action.action != "no_damage":
            assert action.damage_after <= action.damage_before


def test_repair_costs_energy():
    circuit = _make_circuit()
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    repair_engine = CellularRepairEngine()
    result = repair_engine.run(circuit, damage_result.per_cell)
    assert result.total_energy_cost >= 0.0


def test_success_and_failure_rates_computed():
    circuit = _make_circuit()
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    repair_engine = CellularRepairEngine()
    result = repair_engine.run(circuit, damage_result.per_cell)
    assert 0.0 <= result.repair_success_rate <= 1.0
    assert 0.0 <= result.repair_failure_rate <= 1.0
    if result.actions:
        assert abs(result.repair_success_rate + result.repair_failure_rate - 1.0) < 1e-6


def test_max_repairs_per_cycle_respected():
    circuit = _make_circuit()
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    repair_engine = CellularRepairEngine(max_repairs_per_cycle=1)
    result = repair_engine.run(circuit, damage_result.per_cell)
    assert len(result.actions) <= 1


def test_no_damage_no_action():
    n = DigitalNeuron(cell_id="n", role="digital_neuron", energy=1.0)
    circuit = NeuralCircuit(circuit_id="t", input_neurons=[n], hidden_neurons=[], output_neurons=[])
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    repair_engine = CellularRepairEngine()
    result = repair_engine.run(circuit, damage_result.per_cell)
    assert len(result.actions) >= 1


def test_low_energy_blocks_repair():
    n = DigitalNeuron(cell_id="n", role="digital_neuron", energy=0.05, activation=2.0, consecutive_fires=5, apoptosis_risk=0.9)
    circuit = NeuralCircuit(circuit_id="t", input_neurons=[], hidden_neurons=[n], output_neurons=[])
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    repair_engine = CellularRepairEngine(min_energy_to_repair=0.20)
    result = repair_engine.run(circuit, damage_result.per_cell)
    for action in result.actions:
        if action.action != "no_damage" and action.damage_before > 0:
            assert action.success is False


def test_repair_action_names_are_specific():
    n = DigitalNeuron(cell_id="n", role="digital_neuron", energy=0.2, activation=2.0, consecutive_fires=5, apoptosis_risk=0.9)
    circuit = NeuralCircuit(circuit_id="t", input_neurons=[], hidden_neurons=[n], output_neurons=[])
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    repair_engine = CellularRepairEngine()
    result = repair_engine.run(circuit, damage_result.per_cell)
    for action in result.actions:
        if action.action != "no_damage":
            assert action.action in (
                "restore_energy", "lower_activation", "reset_refractory_state",
                "repair_synaptic_weights", "restore_threshold", "reduce_plasticity", "request_glial_support",
            )


def test_repair_events_emitted():
    from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
    n = DigitalNeuron(cell_id="n", role="digital_neuron", energy=0.2, activation=2.0, consecutive_fires=5, apoptosis_risk=0.9)
    circuit = NeuralCircuit(circuit_id="t", input_neurons=[], hidden_neurons=[n], output_neurons=[])
    circuit.memory = MorphologicalMemory()
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    repair_engine = CellularRepairEngine()
    repair_engine.run(circuit, damage_result.per_cell, memory=circuit.memory)
    events = circuit.memory.events
    assert any(e.event_type.value.startswith("cellular_repair") for e in events)
