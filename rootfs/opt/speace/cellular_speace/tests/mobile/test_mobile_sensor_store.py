"""Tests for T120-C — Mobile Sensor Store."""

from speace_core.mobile.mobile_sensor_store import MobileSensorStore


def test_store_and_latest():
    store = MobileSensorStore(data_root="data/test_mobile_sensors")
    accepted = store.store("d1", {"battery": 0.85, "network": "wifi"})
    assert "battery" in accepted
    assert "network" in accepted
    latest = store.latest("d1")
    assert len(latest) == 2


def test_latest_filtered():
    store = MobileSensorStore(data_root="data/test_mobile_sensors")
    store.store("d2", {"battery": 0.9})
    store.store("d2", {"accelerometer": [0.1, 0.2, 0.3]})
    bat = store.latest("d2", sensor_type="battery")
    assert len(bat) == 1
    acc = store.latest("d2", sensor_type="accelerometer")
    assert len(acc) == 1


def test_snapshot():
    store = MobileSensorStore(data_root="data/test_mobile_sensors")
    store.store("d3", {"battery": 1.0})
    snap = store.snapshot()
    assert "d3" in snap["devices"]
    assert snap["total_readings"] >= 1
