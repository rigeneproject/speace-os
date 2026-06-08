import pytest

from speace_core.cellular_brain.cells.auditory_neuron import AuditoryNeuron
from speace_core.cellular_brain.cells.broca_neuron import BrocaNeuron
from speace_core.cellular_brain.cells.wernicke_neuron import WernickeNeuron
from speace_core.cellular_brain.cells.semantic_pointer_neuron import SemanticPointerNeuron
from speace_core.cellular_brain.base.digital_signal import DigitalSignal


@pytest.mark.asyncio
async def test_auditory_neuron_phoneme_sensitivity():
    n = AuditoryNeuron(cell_id="a1", role="auditory_neuron", targets=["t1"])
    n.energy = 1.0
    signal = DigitalSignal(source="s", target="a1", strength=0.5, meaning="phoneme")
    await n.receive(signal)
    assert n.activation == 0.5 * n.phoneme_sensitivity


@pytest.mark.asyncio
async def test_auditory_neuron_tick():
    n = AuditoryNeuron(cell_id="a1", role="auditory_neuron", targets=["t1"])
    n.energy = 1.0
    n.activation = 1.0
    signals = await n.tick()
    assert len(signals) == 1
    assert signals[0].meaning == "auditory_token"
    assert n.activation == 0.0


@pytest.mark.asyncio
async def test_broca_neuron_sequence_buffer():
    n = BrocaNeuron(cell_id="b1", role="broca_neuron", targets=["t1"])
    n.energy = 1.0
    signal = DigitalSignal(
        source="s", target="b1", strength=1.0, meaning="semantic_pointer", payload="hello"
    )
    await n.receive(signal)
    assert "hello" in n.sequence_buffer


@pytest.mark.asyncio
async def test_broca_neuron_production():
    n = BrocaNeuron(cell_id="b1", role="broca_neuron", targets=["t1"])
    n.energy = 1.0
    n.activation = 1.0
    n.sequence_buffer = ["the", "cat"]
    signals = await n.tick()
    assert len(signals) == 1
    assert signals[0].meaning == "symbolic_production"
    assert signals[0].payload == ["the", "cat"]
    assert n.sequence_buffer == []


@pytest.mark.asyncio
async def test_wernicke_neuron_context_window():
    n = WernickeNeuron(cell_id="w1", role="wernicke_neuron", targets=["t1"])
    n.energy = 1.0
    signal = DigitalSignal(
        source="s", target="w1", strength=0.5, meaning="symbolic_label", payload="dog"
    )
    await n.receive(signal)
    assert "dog" in n.context_window


@pytest.mark.asyncio
async def test_wernicke_neuron_comprehension():
    n = WernickeNeuron(cell_id="w1", role="wernicke_neuron", targets=["t1"])
    n.energy = 1.0
    n.activation = 1.0
    n.semantic_field = "animals"
    signals = await n.tick()
    assert len(signals) == 1
    assert signals[0].meaning == "comprehended_symbol"
    assert signals[0].payload == "animals"


@pytest.mark.asyncio
async def test_semantic_pointer_neuron_binding():
    n = SemanticPointerNeuron(cell_id="sp1", role="semantic_pointer_neuron", targets=["t1"])
    n.energy = 1.0
    signal = DigitalSignal(
        source="s",
        target="sp1",
        strength=0.5,
        meaning="ground_symbol",
        payload={"symbol": "cat", "assembly_id": "asm_1"},
    )
    await n.receive(signal)
    assert n.symbol == "cat"
    assert n.assembly_id == "asm_1"
    assert n.binding_strength > 0.0


@pytest.mark.asyncio
async def test_semantic_pointer_neuron_tick():
    n = SemanticPointerNeuron(cell_id="sp1", role="semantic_pointer_neuron", targets=["t1"])
    n.energy = 1.0
    n.symbol = "cat"
    n.assembly_id = "asm_1"
    n.binding_strength = 0.8
    n.activation = 1.0
    signals = await n.tick()
    assert len(signals) == 1
    assert signals[0].meaning == "semantic_pointer"
    assert signals[0].payload["symbol"] == "cat"
    assert signals[0].payload["assembly_id"] == "asm_1"
    assert signals[0].strength == 1.0 * 0.8


def test_auditory_neuron_defaults():
    n = AuditoryNeuron(cell_id="a1", role="auditory_neuron")
    assert n.cell_type == "auditory_neuron"
    assert n.phoneme_sensitivity == 0.7
    assert n.temporal_window == 3


def test_broca_neuron_defaults():
    n = BrocaNeuron(cell_id="b1", role="broca_neuron")
    assert n.cell_type == "broca_neuron"
    assert n.sequence_buffer == []
    assert n.production_readiness == 0.0


def test_wernicke_neuron_defaults():
    n = WernickeNeuron(cell_id="w1", role="wernicke_neuron")
    assert n.cell_type == "wernicke_neuron"
    assert n.comprehension_strength == 0.6
    assert n.context_window == []


def test_semantic_pointer_neuron_defaults():
    n = SemanticPointerNeuron(cell_id="sp1", role="semantic_pointer_neuron")
    assert n.cell_type == "semantic_pointer_neuron"
    assert n.symbol is None
    assert n.assembly_id is None
    assert n.binding_strength == 0.0
