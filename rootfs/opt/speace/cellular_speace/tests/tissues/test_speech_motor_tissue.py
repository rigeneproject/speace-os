import pytest

from speace_core.cellular_brain.tissues.speech_motor_tissue import SpeechMotorTissue, ArticulationEvent


@pytest.fixture
def tissue():
    return SpeechMotorTissue(
        energy_budget=1.0,
        articulation_cost=0.1,
        jitter_sigma=0.01,
    )


def test_articulate_returns_event(tissue):
    event = tissue.articulate("hello")
    assert isinstance(event, ArticulationEvent)
    assert event.token == "hello"
    assert event.energy_cost > 0.0


def test_articulate_deducts_energy(tissue):
    before = tissue.energy_budget
    tissue.articulate("a")
    assert tissue.energy_budget < before


def test_articulate_fatigue_returns_none(tissue):
    # Budget = 1.0, cost = 0.1 => 10 tokens max
    for i in range(10):
        assert tissue.articulate(f"t{i}") is not None
    assert tissue.is_fatigued is True
    assert tissue.articulate("overflow") is None


def test_get_output_buffer(tissue):
    tissue.articulate("one")
    tissue.articulate("two")
    buf = tissue.get_output_buffer()
    assert len(buf) == 2
    assert buf[0].token == "one"
    assert buf[1].token == "two"


def test_clear_buffer(tissue):
    tissue.articulate("x")
    tissue.clear_buffer()
    assert tissue.get_output_buffer() == []
    assert tissue.energy_budget < 1.0  # energy not restored


def test_reset(tissue):
    tissue.articulate("x")
    tissue.reset()
    assert tissue.get_output_buffer() == []
    assert tissue.energy_budget == 1.0
    assert tissue._tick_counter == 0


def test_recover_energy(tissue):
    tissue.articulate("x")
    tissue.articulate("y")
    before = tissue.energy_budget
    tissue.recover_energy(amount=0.2)
    assert tissue.energy_budget == pytest.approx(before + 0.2, abs=1e-9)
    assert tissue.energy_budget <= 1.0


def test_recover_energy_caps_at_one(tissue):
    tissue.recover_energy(amount=5.0)
    assert tissue.energy_budget == 1.0


def test_buffer_tokens_property(tissue):
    tissue.articulate("alpha")
    tissue.articulate("beta")
    assert tissue.buffer_tokens == ["alpha", "beta"]


def test_jitter_scales_with_token_length(tissue):
    short = tissue.articulate("a")
    long = tissue.articulate("abcdefghij")
    assert long.jitter > short.jitter


def test_timestamp_increments(tissue):
    e1 = tissue.articulate("first")
    e2 = tissue.articulate("second")
    assert e2.timestamp > e1.timestamp


def test_is_fatigued_false_initially(tissue):
    assert tissue.is_fatigued is False
