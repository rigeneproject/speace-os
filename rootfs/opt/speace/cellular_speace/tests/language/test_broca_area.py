import pytest

from speace_core.cellular_brain.language.broca_area import DigitalBrocaArea


@pytest.fixture
def broca():
    return DigitalBrocaArea(cpg_period=2, decay_rate=0.1, min_activation=0.2)


def test_activate_sequence_loads_tokens(broca):
    broca.activate_sequence(["hello", "world"])
    assert broca.sequence == ["hello", "world"]
    assert broca.is_active is True


def test_next_token_returns_none_when_empty(broca):
    assert broca.next_token() is None
    assert broca.is_active is False


def test_next_token_emits_on_cpg_beat(broca):
    broca.activate_sequence(["the", "quick", "brown"])
    # cpg_period=2, min_activation=0.2
    # tick 1: no beat
    assert broca.next_token() is None
    # tick 2: beat, activation becomes 0.5 >= 0.2
    assert broca.next_token() == "the"
    # tick 3: no beat
    assert broca.next_token() is None
    # tick 4: beat, next token
    assert broca.next_token() == "quick"


def test_next_token_exhausts_sequence(broca):
    broca.activate_sequence(["a"])
    broca.next_token()  # tick 1 -> None
    assert broca.next_token() == "a"  # tick 2
    assert broca.next_token() is None
    assert broca.is_active is False


def test_reset_sequence_restarts_production(broca):
    broca.activate_sequence(["x", "y"])
    broca.next_token()  # tick 1 -> None
    broca.next_token()  # tick 2 -> "x"
    broca.reset_sequence()
    assert broca.remaining == ["x", "y"]
    assert broca.next_token() is None  # tick 1 after reset
    assert broca.next_token() == "x"  # tick 2 after reset


def test_pause_and_resume(broca):
    broca.activate_sequence(["stop", "go"])
    broca.pause()
    assert broca.next_token() is None
    broca.resume()
    assert broca.next_token() is None
    assert broca.next_token() == "stop"


def test_remaining_property_updates(broca):
    broca.activate_sequence(["one", "two", "three"])
    assert broca.remaining == ["one", "two", "three"]
    broca.next_token()
    broca.next_token()
    assert broca.remaining == ["two", "three"]


def test_get_production_state_shape(broca):
    broca.activate_sequence(["alpha"])
    state = broca.get_production_state()
    assert "tick_counter" in state
    assert "current_index" in state
    assert "paused" in state
    assert "tokens" in state
    assert len(state["tokens"]) == 1


def test_sequence_property_is_immutable(broca):
    broca.activate_sequence(["a", "b"])
    seq = broca.sequence
    seq.append("c")
    assert broca.sequence == ["a", "b"]
