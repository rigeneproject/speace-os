import pytest

from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regions.region_plasticity_trigger import (
    RegionPlasticityTrigger,
    RegionActivationTrace,
    RegionPlasticityTriggerResult,
)
from speace_core.cellular_brain.regions.region_signal_router import RegionSignal, RegionRoutingResult


@pytest.fixture
def trigger():
    return RegionPlasticityTrigger(
        trigger_mode="hybrid",
        min_soft_activation=0.03,
        min_routed_signal=0.001,
        temporal_window=2,
        history_depth=5,
    )


@pytest.fixture
def circuit():
    n1 = DigitalNeuron(cell_id="n1", role="digital_neuron", threshold=0.5)
    n1.region = "sensory"
    n2 = DigitalNeuron(cell_id="n2", role="digital_neuron", threshold=0.5)
    n2.region = "hippocampus"
    n3 = DigitalNeuron(cell_id="n3", role="digital_neuron", threshold=0.5)
    n3.region = "prefrontal"
    return NeuralCircuit(
        circuit_id="test",
        input_neurons=[n1],
        hidden_neurons=[n2],
        output_neurons=[n3],
    )


# ---------------------------------------------------------------------------
# 1. RegionPlasticityTrigger importabile
# ---------------------------------------------------------------------------

def test_trigger_importable():
    assert RegionPlasticityTrigger is not None
    assert RegionActivationTrace is not None
    assert RegionPlasticityTriggerResult is not None


# ---------------------------------------------------------------------------
# 2. compute_soft_activation rileva attivazioni deboli
# ---------------------------------------------------------------------------

def test_compute_soft_activation_detects_weak(trigger, circuit):
    circuit.input_neurons[0].activation = 0.1
    score = trigger.compute_soft_region_activation("sensory", circuit)
    assert score > 0.0


def test_compute_soft_activation_zero_when_empty(trigger, circuit):
    assert trigger.compute_soft_region_activation("nonexistent", circuit) == 0.0


# ---------------------------------------------------------------------------
# 3. capture_region_trace crea traccia con routed_input
# ---------------------------------------------------------------------------

def test_capture_region_trace(trigger, circuit):
    circuit.input_neurons[0].activation = 0.1
    trace = trigger.capture_region_trace("sensory", circuit, tick_id=1, routed_input_strength=0.05)
    assert trace.region_id == "sensory"
    assert trace.tick_id == 1
    assert trace.soft_activation > 0.0
    assert trace.routed_input_strength == 0.05


# ---------------------------------------------------------------------------
# 4. routing_aware_trigger scatta con delivered_signals > 0
# ---------------------------------------------------------------------------

def test_routing_aware_trigger(trigger, circuit):
    routing = RegionRoutingResult(
        signals=[
            RegionSignal(
                source_region_id="sensory",
                target_region_id="hippocampus",
                signal_strength=0.05,
                pathway_strength=0.5,
                delivered=True,
            )
        ]
    )
    result = trigger.evaluate_pathway_trigger(
        "sensory", "hippocampus", None, circuit, routing, tick=1
    )
    assert result.triggered is True
    assert "routing_aware" in result.trigger_type


# ---------------------------------------------------------------------------
# 5. temporal_correlation_trigger rileva source(t) → target(t+1)
# ---------------------------------------------------------------------------

def test_temporal_correlation_trigger(trigger, circuit):
    # Tick 1: source active
    circuit.input_neurons[0].activation = 0.2
    circuit.hidden_neurons[0].activation = 0.0
    trigger.capture_region_trace("sensory", circuit, tick_id=1)
    trigger.capture_region_trace("hippocampus", circuit, tick_id=1)

    # Tick 2: target becomes active
    circuit.input_neurons[0].activation = 0.0
    circuit.hidden_neurons[0].activation = 0.2
    result = trigger.evaluate_pathway_trigger(
        "sensory", "hippocampus", None, circuit, None, tick=2
    )
    assert result.triggered is True
    assert result.delta_tick is not None


# ---------------------------------------------------------------------------
# 6. hybrid_trigger scatta quando almeno un criterio è vero
# ---------------------------------------------------------------------------

def test_hybrid_trigger_soft_activation(trigger, circuit):
    circuit.input_neurons[0].activation = 0.05
    result = trigger.evaluate_pathway_trigger(
        "sensory", "hippocampus", None, circuit, None, tick=1
    )
    assert result.triggered is True
    assert "soft_activation" in result.trigger_type


# ---------------------------------------------------------------------------
# 7. hard_spike_original conserva comportamento T23
# ---------------------------------------------------------------------------

def test_hard_spike_trigger_no_soft_signal(trigger, circuit):
    hard = RegionPlasticityTrigger(trigger_mode="hard_spike")
    # Weak activation should not trigger hard_spike
    circuit.input_neurons[0].activation = 0.1
    result = hard.evaluate_pathway_trigger(
        "sensory", "hippocampus", None, circuit, None, tick=1
    )
    assert result.triggered is False


def test_hard_spike_trigger_with_strong_signal(trigger, circuit):
    hard = RegionPlasticityTrigger(trigger_mode="hard_spike")
    circuit.input_neurons[0].activation = 1.0
    result = hard.evaluate_pathway_trigger(
        "sensory", "hippocampus", None, circuit, None, tick=1
    )
    assert result.triggered is True
    assert result.trigger_type == "hard_spike"


# ---------------------------------------------------------------------------
# 8. trigger produce LTP raccomandato su pathway source→target
# ---------------------------------------------------------------------------

def test_trigger_recommends_ltp(trigger, circuit):
    routing = RegionRoutingResult(
        signals=[
            RegionSignal(
                source_region_id="sensory",
                target_region_id="hippocampus",
                signal_strength=0.05,
                pathway_strength=0.5,
                delivered=True,
            )
        ]
    )
    result = trigger.evaluate_pathway_trigger(
        "sensory", "hippocampus", None, circuit, routing, tick=1
    )
    assert result.recommended_update == "ltp"


# ---------------------------------------------------------------------------
# 9. trigger produce LTD quando target precede source
# ---------------------------------------------------------------------------

def test_trigger_recommends_ltd(trigger, circuit):
    # Tick 1: target active first
    circuit.hidden_neurons[0].activation = 0.2
    circuit.input_neurons[0].activation = 0.0
    trigger.capture_region_trace("hippocampus", circuit, tick_id=1)
    trigger.capture_region_trace("sensory", circuit, tick_id=1)

    # Tick 2: source becomes active
    circuit.hidden_neurons[0].activation = 0.0
    circuit.input_neurons[0].activation = 0.2
    result = trigger.evaluate_pathway_trigger(
        "sensory", "hippocampus", None, circuit, None, tick=2
    )
    assert result.triggered is True
    assert result.recommended_update == "ltd"


# ---------------------------------------------------------------------------
# 10. eventi REGION_PLASTICITY_TRIGGERED registrati
# ---------------------------------------------------------------------------

def test_events_recorded(trigger, circuit):
    mem = MorphologicalMemory()
    routing = RegionRoutingResult(
        signals=[
            RegionSignal(
                source_region_id="sensory",
                target_region_id="hippocampus",
                signal_strength=0.05,
                pathway_strength=0.5,
                delivered=True,
            )
        ]
    )
    trigger.evaluate_pathway_trigger(
        "sensory", "hippocampus", None, circuit, routing, tick=1, memory=mem
    )
    types = [e.event_type for e in mem.events]
    assert MorphologyEventType.REGION_PLASTICITY_TRIGGERED in types


# ---------------------------------------------------------------------------
# 11. eventi REGION_PLASTICITY_TRIGGER_SKIPPED quando non attivo
# ---------------------------------------------------------------------------

def test_skip_event_recorded(trigger, circuit):
    mem = MorphologicalMemory()
    # No activation, no routing
    result = trigger.evaluate_pathway_trigger(
        "sensory", "hippocampus", None, circuit, None, tick=1, memory=mem
    )
    assert result.triggered is False
    types = [e.event_type for e in mem.events]
    assert MorphologyEventType.REGION_PLASTICITY_TRIGGER_SKIPPED in types


# ---------------------------------------------------------------------------
# 12. clear_history resets state
# ---------------------------------------------------------------------------

def test_clear_history(trigger, circuit):
    trigger.capture_region_trace("sensory", circuit, tick_id=1)
    assert "sensory" in trigger._activation_history
    trigger.clear_history()
    assert not trigger._activation_history
