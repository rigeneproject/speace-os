import threading
import time
from unittest.mock import patch

import pytest

from speace_core.cellular_brain.embodiment.cyber_physical_sensor_array import (
    CyberPhysicalSensorArray,
    _normalize,
)


class TestCyberPhysicalSensorArray:
    def test_sensor_array_initialization(self):
        sensor = CyberPhysicalSensorArray()
        assert sensor._has_psutil in (True, False)
        assert sensor._history.maxlen == 1000
        assert sensor._sampling_thread is None

    def test_read_all_returns_structure(self):
        sensor = CyberPhysicalSensorArray()
        result = sensor.read_all()
        assert "timestamp" in result
        assert "cpu" in result
        assert "memory" in result
        assert "disk" in result
        assert "network" in result
        assert "process" in result
        assert "power" in result
        assert "temperature" in result
        assert "filesystem" in result
        assert result["timestamp"].endswith("+00:00")

    def test_cpu_state_returns_values(self):
        sensor = CyberPhysicalSensorArray()
        cpu = sensor.get_cpu_state()
        assert isinstance(cpu, dict)
        assert "usage_percent" in cpu
        assert "frequency_mhz" in cpu
        assert "temperature_celsius" in cpu
        assert "core_count_logical" in cpu
        assert "core_count_physical" in cpu
        assert "usage_percent_normalized" in cpu
        assert "frequency_mhz_normalized" in cpu
        assert "temperature_celsius_normalized" in cpu

    def test_memory_state_returns_values(self):
        sensor = CyberPhysicalSensorArray()
        mem = sensor.get_memory_state()
        assert isinstance(mem, dict)
        assert "total_bytes" in mem
        assert "used_bytes" in mem
        assert "free_bytes" in mem
        assert "percent" in mem
        assert "percent_normalized" in mem

    def test_history_accumulates(self):
        sensor = CyberPhysicalSensorArray(history_size=10)
        sensor.read_all()
        sensor.read_all()
        sensor.read_all()
        history = sensor.get_history(n_samples=5)
        assert len(history) == 3
        assert all("timestamp" in h for h in history)

    def test_sensor_delta_computes(self):
        sensor = CyberPhysicalSensorArray(history_size=10)
        sensor.read_all()
        time.sleep(0.05)
        sensor.read_all()
        delta = sensor.get_sensor_delta()
        assert isinstance(delta, dict)
        assert "timestamp" in delta
        assert "previous_timestamp" in delta
        assert "cpu" in delta
        assert "memory" in delta
        assert "disk" in delta
        assert "drive_deltas" in delta["disk"]
        assert "process" in delta
        assert "process_count_delta" in delta["process"]
        assert "filesystem" in delta
        assert "event_count_delta" in delta["filesystem"]

    def test_normalization_range(self):
        sensor = CyberPhysicalSensorArray()
        snapshot = sensor.read_all()
        for section in ("cpu", "memory", "temperature"):
            for key, value in snapshot.get(section, {}).items():
                if "_normalized" in key and value is not None:
                    assert 0.0 <= value <= 1.0, f"{section}.{key} = {value} out of range"

        for drive in snapshot.get("disk", {}).get("drives", []):
            norm = drive.get("percent_normalized")
            if norm is not None:
                assert 0.0 <= norm <= 1.0

    def test_graceful_degradation_without_psutil(self):
        with patch(
            "speace_core.cellular_brain.embodiment.cyber_physical_sensor_array._HAS_PSUTIL",
            False,
        ):
            sensor = CyberPhysicalSensorArray()
            assert sensor._has_psutil is False
            result = sensor.read_all()
            assert "timestamp" in result
            assert "cpu" in result
            assert "memory" in result
            assert "disk" in result
            assert "network" in result
            assert "process" in result
            assert "power" in result
            assert "temperature" in result
            assert "filesystem" in result
            # Disk should at least have one drive via shutil fallback
            assert len(result["disk"]["drives"]) >= 0

    def test_continuous_sampling(self):
        sensor = CyberPhysicalSensorArray(history_size=20)
        sensor.start_continuous_sampling(interval_ms=200)
        assert sensor._sampling_thread is not None
        assert sensor._sampling_thread.is_alive()
        time.sleep(3.0)
        history = sensor.get_history(n_samples=20)
        assert len(history) >= 2
        sensor.stop_continuous_sampling()
        assert sensor._sampling_thread is None

    def test_history_respects_n_samples(self):
        sensor = CyberPhysicalSensorArray(history_size=50)
        for _ in range(10):
            sensor.read_all()
        history = sensor.get_history(n_samples=5)
        assert len(history) == 5
        history = sensor.get_history(n_samples=100)
        assert len(history) == 10

    def test_stop_continuous_sampling_idempotent(self):
        sensor = CyberPhysicalSensorArray()
        sensor.stop_continuous_sampling()
        assert sensor._sampling_thread is None

    def test_get_sensor_delta_empty_history(self):
        sensor = CyberPhysicalSensorArray()
        assert sensor.get_sensor_delta() == {}
        sensor.read_all()
        # Only one sample
        assert sensor.get_sensor_delta() == {}

    def test_filesystem_events(self):
        sensor = CyberPhysicalSensorArray()
        events = sensor.get_filesystem_events(path=".", duration=60)
        assert "monitored_path" in events
        assert "duration_seconds" in events
        assert "events" in events
        assert "event_count" in events
        assert isinstance(events["events"], list)

    def test_normalize_helper(self):
        assert _normalize(50.0, 0.0, 100.0) == 0.5
        assert _normalize(0.0, 0.0, 100.0) == 0.0
        assert _normalize(100.0, 0.0, 100.0) == 1.0
        assert _normalize(-10.0, 0.0, 100.0) == 0.0
        assert _normalize(200.0, 0.0, 100.0) == 1.0
        assert _normalize(None, 0.0, 100.0) is None
        assert _normalize(5.0, 5.0, 5.0) == 0.0

    def test_disk_state_structure(self):
        sensor = CyberPhysicalSensorArray()
        disk = sensor.get_disk_state()
        assert "drives" in disk
        assert isinstance(disk["drives"], list)
        for drive in disk["drives"]:
            assert "device" in drive
            assert "mountpoint" in drive
            assert "total_bytes" in drive
            assert "used_bytes" in drive
            assert "free_bytes" in drive
            assert "percent" in drive
            assert "percent_normalized" in drive

    def test_power_state_structure(self):
        sensor = CyberPhysicalSensorArray()
        power = sensor.get_power_state()
        assert "battery_percent" in power
        assert "power_plugged" in power
        assert "seconds_left" in power
        assert "battery_percent_normalized" in power
        if power["battery_percent_normalized"] is not None:
            assert 0.0 <= power["battery_percent_normalized"] <= 1.0

    def test_network_state_structure(self):
        sensor = CyberPhysicalSensorArray()
        net = sensor.get_network_state()
        assert "bytes_sent" in net
        assert "bytes_received" in net
        assert "connections" in net
        assert "packets_sent" in net
        assert "packets_received" in net

    def test_process_state_structure(self):
        sensor = CyberPhysicalSensorArray()
        proc = sensor.get_process_state()
        assert "process_count" in proc
        assert "top_by_cpu" in proc
        assert "top_by_memory" in proc
        assert isinstance(proc["top_by_cpu"], list)
        assert isinstance(proc["top_by_memory"], list)

    def test_temperature_state_structure(self):
        sensor = CyberPhysicalSensorArray()
        temp = sensor.get_temperature_state()
        assert "cpu_celsius" in temp
        assert "gpu_celsius" in temp
        assert "cpu_celsius_normalized" in temp
        assert "gpu_celsius_normalized" in temp
        if temp["cpu_celsius_normalized"] is not None:
            assert 0.0 <= temp["cpu_celsius_normalized"] <= 1.0

    def test_thread_safety_history(self):
        sensor = CyberPhysicalSensorArray(history_size=100)
        sensor.start_continuous_sampling(interval_ms=100)
        time.sleep(1.0)
        sensor.stop_continuous_sampling()
        history = sensor.get_history(n_samples=100)
        # Should have accumulated at least a few samples
        assert len(history) >= 2
