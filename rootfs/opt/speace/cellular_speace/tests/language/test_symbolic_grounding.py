import pathlib
import tempfile

import pytest

from speace_core.cellular_brain.language.symbolic_grounding_engine import (
    SymbolicGroundingEngine,
)


@pytest.fixture
def engine():
    return SymbolicGroundingEngine()


@pytest.fixture
def persistent_engine():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = pathlib.Path(tmpdir) / "grounding.json"
        yield SymbolicGroundingEngine(store_path=store)


def test_ground_assembly_creates_mapping(engine):
    engine.ground_assembly("assembly_1", "cat")
    assert engine.get_label("assembly_1") == "cat"
    assert engine.get_assembly("cat") == "assembly_1"


def test_ground_assembly_overwrites_existing_label(engine):
    engine.ground_assembly("assembly_1", "cat")
    engine.ground_assembly("assembly_2", "cat")
    assert engine.get_assembly("cat") == "assembly_2"
    assert engine.get_label("assembly_1") is None


def test_ground_assembly_overwrites_existing_assembly(engine):
    engine.ground_assembly("assembly_1", "cat")
    engine.ground_assembly("assembly_1", "dog")
    assert engine.get_label("assembly_1") == "dog"
    assert engine.get_assembly("cat") is None


def test_get_label_missing(engine):
    assert engine.get_label("nonexistent") is None


def test_get_assembly_missing(engine):
    assert engine.get_assembly("nonexistent") is None


def test_unground_by_assembly(engine):
    engine.ground_assembly("a1", "hello")
    assert engine.unground(assembly_id="a1") is True
    assert engine.get_label("a1") is None
    assert engine.get_assembly("hello") is None


def test_unground_by_label(engine):
    engine.ground_assembly("a1", "hello")
    assert engine.unground(label="hello") is True
    assert engine.get_label("a1") is None
    assert engine.get_assembly("hello") is None


def test_unground_nonexistent(engine):
    assert engine.unground(assembly_id="missing") is False
    assert engine.unground(label="missing") is False


def test_list_groundings(engine):
    engine.ground_assembly("a1", "apple")
    engine.ground_assembly("a2", "banana")
    groundings = engine.list_groundings()
    assert groundings == {"a1": "apple", "a2": "banana"}


def test_persistence_load_on_init():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = pathlib.Path(tmpdir) / "grounding.json"
        engine1 = SymbolicGroundingEngine(store_path=store)
        engine1.ground_assembly("a1", "concept")
        del engine1

        engine2 = SymbolicGroundingEngine(store_path=store)
        assert engine2.get_label("a1") == "concept"
        assert engine2.get_assembly("concept") == "a1"


def test_persistence_overwrites_persist(persistent_engine):
    persistent_engine.ground_assembly("a1", "x")
    persistent_engine.ground_assembly("a1", "y")
    assert persistent_engine.get_label("a1") == "y"
    assert persistent_engine.get_assembly("x") is None

    # Re-load and verify
    engine2 = SymbolicGroundingEngine(store_path=persistent_engine.store_path)
    assert engine2.get_label("a1") == "y"
    assert engine2.get_assembly("y") == "a1"


def test_empty_engine_list_groundings(engine):
    assert engine.list_groundings() == {}
