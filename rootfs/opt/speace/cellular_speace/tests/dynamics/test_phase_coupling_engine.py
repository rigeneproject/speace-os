import math

import pytest

from speace_core.cellular_brain.dynamics.phase_coupling_engine import PhaseCouplingEngine


@pytest.fixture
def engine():
    return PhaseCouplingEngine(default_coupling_strength=1.0)


def test_register_oscillator(engine):
    engine.register_oscillator("o1", freq=10.0, initial_phase=0.0)
    assert "o1" in engine.list_oscillators()
    assert engine.get_phase("o1") == pytest.approx(0.0)


def test_phase_wrap_on_registration(engine):
    engine.register_oscillator("o1", freq=10.0, initial_phase=3.0 * math.pi)
    assert engine.get_phase("o1") == pytest.approx(math.pi, abs=1e-12)


def test_step_advances_free_oscillator(engine):
    engine.register_oscillator("o1", freq=10.0, initial_phase=0.0)
    dt = 0.01
    engine.step(dt)
    expected = (2.0 * math.pi * 10.0) * dt
    assert engine.get_phase("o1") == pytest.approx(expected % (2.0 * math.pi))


def test_coupling_pulls_towards_synchrony(engine):
    # Two oscillators with same frequency but different phases
    engine.register_oscillator("a", freq=10.0, initial_phase=0.0)
    engine.register_oscillator("b", freq=10.0, initial_phase=math.pi / 2.0)
    dt = 0.05
    for _ in range(50):
        engine.step(dt)
    # Strong coupling should pull them close together
    diff = engine.get_phase_difference("a", "b")
    assert abs(diff) < 0.5


def test_order_parameter_zero_for_incoherent(engine):
    # Two oscillators pi apart should give low order parameter
    engine.register_oscillator("a", freq=10.0, initial_phase=0.0)
    engine.register_oscillator("b", freq=10.0, initial_phase=math.pi)
    r = engine.get_order_parameter()
    assert r == pytest.approx(0.0, abs=1e-6)


def test_order_parameter_one_for_synchrony(engine):
    engine.register_oscillator("a", freq=10.0, initial_phase=0.0)
    engine.register_oscillator("b", freq=10.0, initial_phase=0.0)
    r = engine.get_order_parameter()
    assert r == pytest.approx(1.0, abs=1e-6)


def test_order_parameter_increases_with_coupling(engine):
    engine.register_oscillator("a", freq=10.0, initial_phase=0.0)
    engine.register_oscillator("b", freq=10.0, initial_phase=1.0)
    r_before = engine.get_order_parameter()
    for _ in range(100):
        engine.step(0.01)
    r_after = engine.get_order_parameter()
    assert r_after > r_before


def test_pairwise_coupling_overrides_default(engine):
    engine = PhaseCouplingEngine(default_coupling_strength=0.0)
    engine.register_oscillator("a", freq=10.0, initial_phase=0.0)
    engine.register_oscillator("b", freq=10.0, initial_phase=math.pi / 2.0)
    # Bidirectional strong coupling overrides the default 0.0
    engine.set_coupling("a", "b", strength=5.0)
    engine.set_coupling("b", "a", strength=5.0)
    dt = 0.01
    for _ in range(200):
        engine.step(dt)
    diff = engine.get_phase_difference("a", "b")
    # With strong bidirectional coupling, they should synchronize
    assert abs(diff) < 0.5


def test_get_coupling_returns_default_when_not_set(engine):
    engine.register_oscillator("a", freq=10.0)
    engine.register_oscillator("b", freq=10.0)
    assert engine.get_coupling("a", "b") == pytest.approx(1.0)


def test_get_coupling_returns_explicit_value(engine):
    engine.register_oscillator("a", freq=10.0)
    engine.register_oscillator("b", freq=10.0)
    engine.set_coupling("a", "b", 3.5)
    assert engine.get_coupling("a", "b") == pytest.approx(3.5)


def test_unregister_removes_oscillator_and_edges(engine):
    engine.register_oscillator("a", freq=10.0)
    engine.register_oscillator("b", freq=10.0)
    engine.set_coupling("a", "b", 2.0)
    engine.unregister_oscillator("a")
    assert "a" not in engine.list_oscillators()
    # edge should be pruned
    assert engine.get_coupling("a", "b") == pytest.approx(1.0)


def test_phase_difference_wrapping(engine):
    engine.register_oscillator("a", freq=10.0, initial_phase=0.1)
    engine.register_oscillator("b", freq=10.0, initial_phase=2.0 * math.pi - 0.1)
    diff = engine.get_phase_difference("a", "b")
    # difference should be wrapped to [-pi, pi]
    assert diff == pytest.approx(0.2, abs=1e-6)


def test_empty_engine_order_parameter(engine):
    assert engine.get_order_parameter() == pytest.approx(0.0)


def test_empty_engine_step_does_not_crash(engine):
    engine.step(0.01)


def test_three_oscillator_synchrony(engine):
    engine.register_oscillator("a", freq=10.0, initial_phase=0.0)
    engine.register_oscillator("b", freq=10.0, initial_phase=math.pi / 3.0)
    engine.register_oscillator("c", freq=10.0, initial_phase=2.0 * math.pi / 3.0)
    for _ in range(200):
        engine.step(0.01)
    r = engine.get_order_parameter()
    assert r > 0.9


def test_set_coupling_unknown_source_raises(engine):
    engine.register_oscillator("b", freq=10.0)
    with pytest.raises(KeyError):
        engine.set_coupling("a", "b", 1.0)


def test_set_coupling_unknown_target_raises(engine):
    engine.register_oscillator("a", freq=10.0)
    with pytest.raises(KeyError):
        engine.set_coupling("a", "b", 1.0)
