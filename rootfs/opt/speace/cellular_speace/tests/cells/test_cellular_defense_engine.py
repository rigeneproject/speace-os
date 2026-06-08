import pytest

from speace_core.cellular_brain.cells.cellular_damage import CellularDamageEngine
from speace_core.cellular_brain.cells.cellular_defense_engine import (
    CellularDefenseEngine,
    CellularDefenseResult,
    DefenseAction,
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
    n3 = DigitalNeuron(cell_id="n3", role="digital_neuron", energy=0.5, activation=1.0, consecutive_fires=3, apoptosis_risk=0.4)
    circuit = NeuralCircuit(circuit_id="test", input_neurons=[n1], hidden_neurons=[n2, n3], output_neurons=[])
    return circuit


# ------------------------------------------------------------------ #
# Import & construction
# ------------------------------------------------------------------ #

def test_defense_engine_importable():
    assert CellularDefenseEngine is not None


def test_defense_action_model():
    a = DefenseAction(cell_id="c1", action="snooze", applied=True, reason="stress_threshold")
    assert a.applied is True


# ------------------------------------------------------------------ #
# Run
# ------------------------------------------------------------------ #

def test_run_returns_result():
    circuit = _make_circuit()
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    defense_engine = CellularDefenseEngine()
    result = defense_engine.run(circuit, stress_result.per_cell, damage_result.per_cell)
    assert isinstance(result, CellularDefenseResult)


def test_defense_activations_only_when_threshold_met():
    circuit = _make_circuit()
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    defense_engine = CellularDefenseEngine(
        quarantine_stress_threshold=0.99,
        quarantine_damage_threshold=0.99,
        firewall_stress_threshold=0.99,
        snooze_stress_threshold=0.99,
        routing_block_stress_threshold=0.99,
        plasticity_lock_stress_threshold=0.99,
        input_filter_stress_threshold=0.99,
        immune_alert_damage_threshold=0.99,
    )
    result = defense_engine.run(circuit, stress_result.per_cell, damage_result.per_cell)
    assert result.defense_activation_count == 0


def test_snooze_applied_for_high_stress():
    n = DigitalNeuron(cell_id="n", role="digital_neuron", energy=0.2, activation=2.0, consecutive_fires=5, apoptosis_risk=0.9)
    circuit = NeuralCircuit(circuit_id="t", input_neurons=[], hidden_neurons=[n], output_neurons=[])
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    defense_engine = CellularDefenseEngine(
        snooze_stress_threshold=0.3,
        firewall_stress_threshold=1.0,
        quarantine_stress_threshold=1.0,
        quarantine_damage_threshold=1.0,
        routing_block_stress_threshold=1.0,
        plasticity_lock_stress_threshold=1.0,
        input_filter_stress_threshold=1.0,
        immune_alert_damage_threshold=1.0,
    )
    result = defense_engine.run(circuit, stress_result.per_cell, damage_result.per_cell)
    assert result.snooze_count >= 1


def test_max_defenses_per_cycle_respected():
    circuit = _make_circuit()
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    defense_engine = CellularDefenseEngine(max_defenses_per_cycle=1)
    result = defense_engine.run(circuit, stress_result.per_cell, damage_result.per_cell)
    assert result.defense_activation_count <= 1


def test_protected_neurons_skipped():
    n = DigitalNeuron(cell_id="n_in", role="digital_neuron", energy=0.1, activation=2.0, consecutive_fires=5, apoptosis_risk=0.9)
    n.is_critical = True
    circuit = NeuralCircuit(circuit_id="t", input_neurons=[n], hidden_neurons=[], output_neurons=[])
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    defense_engine = CellularDefenseEngine(snooze_stress_threshold=0.1)
    result = defense_engine.run(circuit, stress_result.per_cell, damage_result.per_cell)
    actions_for_n = [a for a in result.actions if a.cell_id == "n_in"]
    assert len(actions_for_n) == 0


def test_io_neurons_protected():
    n = DigitalNeuron(cell_id="n_out", role="digital_neuron", energy=0.1, activation=2.0, consecutive_fires=5, apoptosis_risk=0.9)
    n.neuron_role = "output"
    circuit = NeuralCircuit(circuit_id="t", input_neurons=[], hidden_neurons=[], output_neurons=[n])
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    defense_engine = CellularDefenseEngine(snooze_stress_threshold=0.1)
    result = defense_engine.run(circuit, stress_result.per_cell, damage_result.per_cell)
    actions_for_n = [a for a in result.actions if a.cell_id == "n_out"]
    assert len(actions_for_n) == 0


def test_quarantine_clears_targets():
    n = DigitalNeuron(cell_id="n", role="digital_neuron", energy=0.1, activation=2.0, consecutive_fires=5, apoptosis_risk=0.9)
    n.targets = ["t1", "t2"]
    circuit = NeuralCircuit(circuit_id="t", input_neurons=[], hidden_neurons=[n], output_neurons=[])
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    defense_engine = CellularDefenseEngine(
        quarantine_stress_threshold=0.1,
        quarantine_damage_threshold=0.1,
    )
    result = defense_engine.run(circuit, stress_result.per_cell, damage_result.per_cell)
    if result.quarantined_count > 0:
        assert n.targets == []


def test_firewall_clears_targets():
    n = DigitalNeuron(cell_id="n", role="digital_neuron", energy=0.1, activation=2.0, consecutive_fires=5, apoptosis_risk=0.9)
    n.targets = ["t1", "t2"]
    circuit = NeuralCircuit(circuit_id="t", input_neurons=[], hidden_neurons=[n], output_neurons=[])
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    defense_engine = CellularDefenseEngine(
        firewall_stress_threshold=0.1,
        quarantine_stress_threshold=1.0,
        quarantine_damage_threshold=1.0,
    )
    result = defense_engine.run(circuit, stress_result.per_cell, damage_result.per_cell)
    if result.firewall_count > 0:
        assert n.targets == []


# ------------------------------------------------------------------ #
# T42B new defense actions
# ------------------------------------------------------------------ #

def test_plasticity_lock_applied():
    n = DigitalNeuron(cell_id="n", role="digital_neuron", energy=0.2, activation=2.0, consecutive_fires=5, apoptosis_risk=0.9)
    circuit = NeuralCircuit(circuit_id="t", input_neurons=[], hidden_neurons=[n], output_neurons=[])
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    defense_engine = CellularDefenseEngine(
        plasticity_lock_stress_threshold=0.1,
        quarantine_stress_threshold=1.0,
        quarantine_damage_threshold=1.0,
        firewall_stress_threshold=1.0,
    )
    result = defense_engine.run(circuit, stress_result.per_cell, damage_result.per_cell)
    assert result.plasticity_lock_count >= 1


def test_immune_alert_on_critical_damage():
    n = DigitalNeuron(cell_id="n", role="digital_neuron", energy=0.2, activation=2.0, consecutive_fires=5, apoptosis_risk=0.9)
    circuit = NeuralCircuit(circuit_id="t", input_neurons=[], hidden_neurons=[n], output_neurons=[])
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    defense_engine = CellularDefenseEngine(
        immune_alert_damage_threshold=0.1,
        quarantine_stress_threshold=1.0,
        quarantine_damage_threshold=1.0,
    )
    result = defense_engine.run(circuit, stress_result.per_cell, damage_result.per_cell)
    assert result.immune_alert_count >= 1


def test_quarantine_event_type():
    from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
    n = DigitalNeuron(cell_id="n", role="digital_neuron", energy=0.1, activation=2.0, consecutive_fires=5, apoptosis_risk=0.9)
    circuit = NeuralCircuit(circuit_id="t", input_neurons=[], hidden_neurons=[n], output_neurons=[])
    circuit.memory = MorphologicalMemory()
    stress_engine = CellularStressEngine()
    stress_result = stress_engine.evaluate(circuit)
    damage_engine = CellularDamageEngine()
    damage_result = damage_engine.evaluate(circuit, stress_result)
    defense_engine = CellularDefenseEngine(
        quarantine_stress_threshold=0.1,
        quarantine_damage_threshold=0.1,
    )
    defense_engine.run(circuit, stress_result.per_cell, damage_result.per_cell, memory=circuit.memory)
    events = circuit.memory.events
    assert any(e.event_type.value == "cell_quarantined" for e in events)
