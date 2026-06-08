"""MobileSensorStore — T120-C: receives and stores mobile sensor data.

Sensors are opt-in per device. Data is stored in-memory with bounded
history and persisted to disk as lightweight JSONL.
"""

import json
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional


@dataclass
class SensorReading:
    device_id: str
    sensor_type: str
    value: Any
    timestamp: float = field(default_factory=time.time)


class MobileSensorStore:
    """Bounded in-memory store for mobile sensor readings."""

    def __init__(self, data_root: str = "data/mobile_sensors", max_per_sensor: int = 1000) -> None:
        self.data_root = Path(data_root)
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.max_per_sensor = max_per_sensor
        self._readings: Dict[str, Deque[Dict[str, Any]]] = {}

    def store(self, device_id: str, sensors: Dict[str, Any]) -> List[str]:
        """Store sensor readings for a device. Returns list of accepted sensor types."""
        accepted: List[str] = []
        key = device_id
        if key not in self._readings:
            self._readings[key] = deque(maxlen=self.max_per_sensor)
        for sensor_type, value in sensors.items():
            reading = {
                "sensor_type": sensor_type,
                "value": value,
                "timestamp": time.time(),
            }
            self._readings[key].append(reading)
            accepted.append(sensor_type)
            # Persist each reading as a lightweight JSONL line
            self._persist(device_id, reading)
        return accepted

    def _persist(self, device_id: str, reading: Dict[str, Any]) -> None:
        path = self.data_root / f"{device_id}.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(reading, ensure_ascii=False) + "\n")

    def latest(self, device_id: str, sensor_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return latest readings for a device, optionally filtered by sensor type."""
        key = device_id
        if key not in self._readings:
            return []
        readings = list(self._readings[key])
        if sensor_type is not None:
            readings = [r for r in readings if r["sensor_type"] == sensor_type]
        return readings[-100:]

    def snapshot(self) -> Dict[str, Any]:
        return {
            "devices": list(self._readings.keys()),
            "total_readings": sum(len(v) for v in self._readings.values()),
        }
