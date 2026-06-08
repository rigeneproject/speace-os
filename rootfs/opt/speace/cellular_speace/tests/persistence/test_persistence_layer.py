import uuid
import tempfile
from pathlib import Path

from speace_core.persistence.persistent_object import (
    PersistentObject,
    CellSnapshot,
    SynapseSnapshot,
    SystemStateSnapshot,
)
from speace_core.persistence.persistent_store import PersistentStore
from speace_core.persistence.object_persistence_layer import ObjectPersistenceLayer


class _DummyNeuron:
    def __init__(self, cell_id="n1", role="sensory", energy=0.8, state="active",
                 activation=0.5, threshold=0.5, plasticity_rate=0.01, region_id="r1"):
        self.cell_id = cell_id
        self.role = role
        self.energy = energy
        self.state = state
        self.activation = activation
        self.threshold = threshold
        self.plasticity_rate = plasticity_rate
        self.region_id = region_id
        class FakeEpigenome:
            def __init__(self):
                self.active_genes = ["gene_a", "gene_b"]
        self.epigenome = FakeEpigenome()


class _DummySynapse:
    def __init__(self, source_id="n1", target_id="n2", weight=0.5, trust=0.7,
                 state="active", plasticity_rate=0.01):
        self.source_id = source_id
        self.target_id = target_id
        self.weight = weight
        self.trust = trust
        self.state = state
        self.plasticity_rate = plasticity_rate


class _DummyMetrics:
    def __init__(self):
        self.coherence_phi = 0.42
        self.mean_energy = 0.75
        self.active_neurons = 10
        self.pruned_synapses = 2


def test_persistent_object_creation():
    obj = PersistentObject(object_type="test_type")
    assert obj.persistent_id is not None
    assert uuid.UUID(obj.persistent_id)
    assert obj.object_type == "test_type"
    assert obj.tick == 0
    assert obj.deleted is False


def test_cell_snapshot_creation():
    cell = CellSnapshot(
        cell_id="n1", role="sensory", energy=0.9, state="active",
        activation=0.5, threshold=0.5, plasticity_rate=0.01, region_id="r1",
        tick=42,
    )
    assert cell.object_type == "cell"
    assert cell.cell_id == "n1"
    assert cell.energy == 0.9
    assert cell.tick == 42


def test_synapse_snapshot_creation():
    syn = SynapseSnapshot(
        source_id="n1", target_id="n2", weight=0.8, trust=0.6,
        state="active", plasticity_rate=0.01, tick=42,
    )
    assert syn.object_type == "synapse"
    assert syn.source_id == "n1"
    assert syn.target_id == "n2"
    assert syn.weight == 0.8


def test_system_state_snapshot_creation():
    state = SystemStateSnapshot(
        coherence_phi=0.42, mean_energy=0.75, active_neurons=10,
        synapse_count=100, pruned_synapses=2, tick=42,
    )
    assert state.object_type == "system_state"
    assert state.coherence_phi == 0.42


def test_persistent_store_put_get():
    with tempfile.TemporaryDirectory() as tmp:
        store = PersistentStore(PersistentObject, "test_store", data_dir=tmp)
        obj = PersistentObject(object_type="test")
        pid = store.put(obj)
        retrieved = store.get(pid)
        assert retrieved is not None
        assert retrieved.persistent_id == pid
        assert retrieved.object_type == "test"


def test_persistent_store_delete():
    with tempfile.TemporaryDirectory() as tmp:
        store = PersistentStore(PersistentObject, "test_store", data_dir=tmp)
        obj = PersistentObject(object_type="test")
        pid = store.put(obj)
        assert store.get(pid) is not None
        assert store.delete(pid) is True
        assert store.get(pid) is None
        assert store.delete(pid) is False


def test_persistent_store_query():
    with tempfile.TemporaryDirectory() as tmp:
        store = PersistentStore(PersistentObject, "test_store", data_dir=tmp)
        for i in range(5):
            obj = PersistentObject(object_type="type_a", tick=i)
            store.put(obj)
        for i in range(3):
            obj = PersistentObject(object_type="type_b", tick=i + 10)
            store.put(obj)
        type_a = store.query(object_type="type_a")
        assert len(type_a) == 5
        type_b = store.query(object_type="type_b")
        assert len(type_b) == 3
        filtered = store.query(tick_min=2, tick_max=4)
        assert len(filtered) == 3
        assert all(o.tick >= 2 for o in filtered)
        assert all(o.tick <= 4 for o in filtered)


def test_persistent_store_count():
    with tempfile.TemporaryDirectory() as tmp:
        store = PersistentStore(PersistentObject, "test_store", data_dir=tmp)
        assert store.count() == 0
        store.put(PersistentObject(object_type="a"))
        store.put(PersistentObject(object_type="b"))
        assert store.count() == 2
        assert store.count(object_type="a") == 1


def test_persistent_store_compaction():
    with tempfile.TemporaryDirectory() as tmp:
        store = PersistentStore(
            PersistentObject, "test_store", data_dir=tmp, compaction_interval=3
        )
        ids = []
        for i in range(5):
            obj = PersistentObject(object_type="test", tick=i)
            pid = store.put(obj)
            ids.append(pid)
        store.delete(ids[0])
        store.delete(ids[1])
        store._compact()
        assert store.count() == 3
        assert store.get(ids[0]) is None
        assert store.get(ids[2]) is not None


def test_persistent_store_load():
    with tempfile.TemporaryDirectory() as tmp:
        store = PersistentStore(PersistentObject, "test_store", data_dir=tmp)
        ids = []
        for i in range(3):
            obj = PersistentObject(object_type="test", tick=i)
            pid = store.put(obj)
            ids.append(pid)
        store2 = PersistentStore(PersistentObject, "test_store", data_dir=tmp)
        assert store2.count() == 3
        for pid in ids:
            assert store2.get(pid) is not None


def test_object_persistence_layer_create():
    with tempfile.TemporaryDirectory() as tmp:
        layer = ObjectPersistenceLayer(data_dir=tmp)
        assert layer.has_store("cells")
        assert layer.has_store("synapses")
        assert layer.has_store("system_state")
        assert not layer.has_store("nonexistent")


def test_object_persistence_layer_put_get():
    with tempfile.TemporaryDirectory() as tmp:
        layer = ObjectPersistenceLayer(data_dir=tmp)
        cell = CellSnapshot(cell_id="n1", role="sensory", tick=1)
        pid = layer.put("cells", cell)
        assert pid is not None
        retrieved = layer.get("cells", pid)
        assert retrieved is not None
        assert retrieved.cell_id == "n1"


def test_object_persistence_layer_snapshot_circuit():
    with tempfile.TemporaryDirectory() as tmp:
        layer = ObjectPersistenceLayer(data_dir=tmp)
        neurons = [
            _DummyNeuron("n1", "sensory"),
            _DummyNeuron("n2", "interneuron"),
        ]
        synapses = [
            _DummySynapse("n1", "n2"),
        ]
        metrics = _DummyMetrics()
        counts = layer.snapshot_circuit(neurons, synapses, tick=42, metrics=metrics)
        assert counts["cells"] == 2
        assert counts["synapses"] == 1
        assert layer.count("cells") == 2
        assert layer.count("synapses") == 1
        assert layer.count("system_state") == 1


def test_object_persistence_layer_load():
    with tempfile.TemporaryDirectory() as tmp:
        layer = ObjectPersistenceLayer(data_dir=tmp)
        cell = CellSnapshot(cell_id="n1", role="sensory", tick=1)
        layer.put("cells", cell)
        stats_before = layer.get_stats()
        assert stats_before["cells"]["alive_count"] == 1
        layer2 = ObjectPersistenceLayer(data_dir=tmp)
        counts = layer2.load_all()
        assert counts.get("cells", 0) == 1
        cells = layer2.list_all("cells")
        assert len(cells) == 1
        assert cells[0].cell_id == "n1"


def test_persistent_store_snapshot_bulk():
    with tempfile.TemporaryDirectory() as tmp:
        store = PersistentStore(CellSnapshot, "cells", data_dir=tmp)
        cells = [
            CellSnapshot(cell_id=f"n{i}", role="sensory", tick=1) for i in range(10)
        ]
        written = store.snapshot(cells)
        assert written == 10
        assert store.count() == 10


def test_delete_nonexistent_returns_false():
    with tempfile.TemporaryDirectory() as tmp:
        store = PersistentStore(PersistentObject, "test_store", data_dir=tmp)
        assert store.delete("nonexistent") is False


def test_get_nonexistent_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        store = PersistentStore(PersistentObject, "test_store", data_dir=tmp)
        assert store.get("nonexistent") is None


def test_list_all_empty_store():
    with tempfile.TemporaryDirectory() as tmp:
        store = PersistentStore(PersistentObject, "test_store", data_dir=tmp)
        assert store.list_all() == []


def test_query_with_predicate():
    with tempfile.TemporaryDirectory() as tmp:
        store = PersistentStore(PersistentObject, "test_store", data_dir=tmp)
        for i in range(5):
            obj = PersistentObject(object_type="test", tick=i)
            store.put(obj)
        results = store.query(predicate=lambda o: o.tick % 2 == 0)
        assert len(results) == 3
