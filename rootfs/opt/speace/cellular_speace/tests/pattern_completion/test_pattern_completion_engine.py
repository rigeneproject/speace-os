import pytest

from speace_core.cellular_brain.pattern_completion.pattern_completion_engine import (
    PatternCompletionEngine,
)


def test_store_and_complete():
    engine = PatternCompletionEngine(dim=4)
    patterns = [
        [1.0, 1.0, -1.0, -1.0],
        [-1.0, -1.0, 1.0, 1.0],
    ]
    engine.store_patterns(patterns)
    partial = [1.0, 1.0, 0.0, 0.0]
    completed = engine.complete_pattern(partial, steps=5)
    assert completed == [1.0, 1.0, -1.0, -1.0]


def test_store_invalid_dimension():
    engine = PatternCompletionEngine(dim=3)
    with pytest.raises(ValueError):
        engine.store_pattern([1.0, 1.0])


def test_complete_invalid_dimension():
    engine = PatternCompletionEngine(dim=3)
    with pytest.raises(ValueError):
        engine.complete_pattern([1.0, 1.0])


def test_energy_decreases_or_stays():
    engine = PatternCompletionEngine(dim=4)
    patterns = [
        [1.0, 1.0, -1.0, -1.0],
    ]
    engine.store_patterns(patterns)
    state = [1.0, -1.0, -1.0, 1.0]
    e_before = engine.energy(state)
    state_after = engine.complete_pattern(state, steps=1)
    e_after = engine.energy(state_after)
    assert e_after <= e_before


def test_missing_value_initialization():
    engine = PatternCompletionEngine(dim=4)
    patterns = [
        [1.0, 1.0, -1.0, -1.0],
    ]
    engine.store_patterns(patterns)
    partial = [1.0, 1.0, 0.0, 0.0]
    completed = engine.complete_pattern(partial, steps=5, missing_value=0.0)
    assert len(completed) == 4
