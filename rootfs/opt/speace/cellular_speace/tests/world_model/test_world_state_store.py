import pytest
from speace_core.cellular_brain.world_model.world_model_models import WorldEntity, WorldEntityType, WorldZone
from speace_core.cellular_brain.world_model.world_state_store import WorldStateStore


def test_create_snapshot():
    store = WorldStateStore(seed=1)
    e = WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)
    s = store.create_snapshot(entities=[e])
    assert s.snapshot_id.startswith("wms_")
    assert len(s.entities) == 1
    assert s.global_uncertainty_score >= 0.0


def test_import_cyber_physical_snapshot():
    store = WorldStateStore(seed=1)
    cp = {"snapshot_id": "cp_1", "streams": {"env_temp": [{"value": 22.0}], "energy_grid": [{"value": 0.9}]}}
    s = store.import_cyber_physical_snapshot(cp)
    assert len(s.entities) == 2
    assert s.metadata.get("source") == "cyber_physical"


def test_get_snapshot():
    store = WorldStateStore(seed=1)
    e = WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT)
    s = store.create_snapshot(entities=[e])
    fetched = store.get_snapshot(s.snapshot_id)
    assert fetched is not None
    assert fetched.snapshot_id == s.snapshot_id


def test_list_snapshots():
    store = WorldStateStore(seed=1)
    store.create_snapshot()
    store.create_snapshot()
    assert len(store.list_snapshots()) == 2


def test_compute_global_uncertainty_empty():
    store = WorldStateStore(seed=1)
    s = store.create_snapshot()
    assert s.global_uncertainty_score == 0.0


def test_compute_global_uncertainty_with_entities():
    store = WorldStateStore(seed=1)
    e1 = WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT, uncertainty=0.5)
    e2 = WorldEntity(entity_id="e2", entity_type=WorldEntityType.SENSOR_SOURCE, uncertainty=0.3)
    s = store.create_snapshot(entities=[e1, e2])
    assert s.global_uncertainty_score > 0.0


def test_compute_global_coherence_empty():
    store = WorldStateStore(seed=1)
    s = store.create_snapshot()
    assert s.global_coherence_score == 1.0


def test_compute_global_coherence_with_entities():
    store = WorldStateStore(seed=1)
    e = WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT, confidence=0.8)
    s = store.create_snapshot(entities=[e])
    assert s.global_coherence_score == 0.8


def test_compute_global_risk_empty():
    store = WorldStateStore(seed=1)
    s = store.create_snapshot()
    assert s.global_risk_score == 0.0


def test_compute_global_risk_with_safety():
    store = WorldStateStore(seed=1)
    e = WorldEntity(entity_id="e1", entity_type=WorldEntityType.ENVIRONMENT, safety_relevance=0.9)
    z = WorldZone(zone_id="z1", safety_pressure=0.7)
    s = store.create_snapshot(entities=[e], zones=[z])
    assert s.global_risk_score == 0.9
