"""Bridge from SimulatedSnapshot to CyberPhysicalSensorArray's dict format.

The :class:`CyberPhysicalSensorArray` (in
``speace_core.cellular_brain.embodiment.cyber_physical_sensor_array``)
exposes :meth:`read_all`, which returns a JSON-serialisable ``Dict`` with
the following top-level keys:

* ``timestamp``        — ISO-8601 UTC string
* ``cpu``              — usage, frequency, temperature, core counts
* ``memory``           — total/used/free bytes and percent
* ``disk``             — drives list and read/write bytes
* ``network``          — bytes sent/received and connections
* ``process``          — process count, top by CPU, top by memory
* ``power``            — battery percent, plugged, seconds left
* ``temperature``      — CPU/GPU celsius
* ``filesystem``       — recent filesystem events

The function :func:`simulated_to_sensor_array_format` produces a dict
with the same shape from a :class:`SimulatedSnapshot`, so that downstream
code can consume simulated data through the same code path used for real
hardware readings.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from sandbox.simulated_organism import SimulatedSnapshot


_MB_TO_BYTES = 1024 * 1024


def _ts_to_iso(ts: float) -> str:
    """Convert a Unix timestamp to an ISO-8601 UTC string."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _normalize(value: Any, lo: float, hi: float) -> float:
    """Normalize a numeric value into [0, 1] like the real sensor array."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.0
    if hi == lo:
        return 0.0
    return max(0.0, min(1.0, (f - lo) / (hi - lo)))


def simulated_to_sensor_array_format(snapshot: SimulatedSnapshot) -> Dict[str, Any]:
    """Translate a :class:`SimulatedSnapshot` to the format of
    :meth:`CyberPhysicalSensorArray.read_all`.

    The produced dict is suitable for JSON serialisation.  Values that
    have no simulated counterpart (e.g. GPU temperature, real network
    connections) are filled with ``None`` or with small, plausible,
    deterministic placeholder values so that downstream code can rely
    on the schema being complete.
    """
    cpu = snapshot.cpu
    memory = snapshot.memory
    battery = snapshot.battery
    env = snapshot.environment
    robot = snapshot.robot
    tick_id = snapshot.tick_id

    total_bytes = memory.total_mb * _MB_TO_BYTES
    used_bytes = memory.used_mb * _MB_TO_BYTES
    free_bytes = max(0, total_bytes - used_bytes)

    # Deterministic, low-traffic placeholder network stats.  They only
    # need to be present and non-negative.
    net_sent = tick_id * 1024
    net_recv = tick_id * 4096

    # Deterministic placeholder disk: a single virtual drive on "/".
    disk_total = 512 * 1024 * _MB_TO_BYTES
    disk_used = int(disk_total * 0.42)
    disk_free = disk_total - disk_used

    # Top processes by CPU and memory — sorted in the same way the real
    # sensor array does (descending).
    procs = [
        {
            "pid": p.pid,
            "name": p.name,
            "cpu_percent": p.cpu_percent,
            "memory_percent": (
                p.memory_mb / memory.total_mb * 100.0 if memory.total_mb else 0.0
            ),
        }
        for p in snapshot.processes
    ]
    top_by_cpu = sorted(procs, key=lambda x: x["cpu_percent"], reverse=True)[:5]
    top_by_memory = sorted(procs, key=lambda x: x["memory_percent"], reverse=True)[:5]

    return {
        "timestamp": _ts_to_iso(snapshot.timestamp),
        "cpu": {
            "usage_percent": cpu.usage_percent,
            "frequency_mhz": cpu.frequency_mhz,
            "temperature_celsius": cpu.temperature_celsius,
            "core_count_logical": 8,
            "core_count_physical": 4,
            "usage_percent_normalized": _normalize(cpu.usage_percent, 0.0, 100.0),
            "frequency_mhz_normalized": _normalize(cpu.frequency_mhz, 0.0, 5000.0),
            "temperature_celsius_normalized": _normalize(
                cpu.temperature_celsius, 20.0, 100.0
            ),
        },
        "memory": {
            "total_bytes": total_bytes,
            "used_bytes": used_bytes,
            "free_bytes": free_bytes,
            "percent": memory.percent,
            "percent_normalized": _normalize(memory.percent, 0.0, 100.0),
        },
        "disk": {
            "drives": [
                {
                    "device": "/",
                    "mountpoint": "/",
                    "total_bytes": disk_total,
                    "used_bytes": disk_used,
                    "free_bytes": disk_free,
                    "percent": (disk_used / disk_total) * 100.0,
                    "percent_normalized": _normalize(
                        (disk_used / disk_total) * 100.0, 0.0, 100.0
                    ),
                }
            ],
            "read_bytes": tick_id * 2048,
            "write_bytes": tick_id * 1024,
        },
        "network": {
            "bytes_sent": net_sent,
            "bytes_received": net_recv,
            "connections": 1,
            "packets_sent": tick_id * 8,
            "packets_received": tick_id * 12,
        },
        "process": {
            "process_count": len(snapshot.processes),
            "top_by_cpu": top_by_cpu,
            "top_by_memory": top_by_memory,
        },
        "power": {
            "battery_percent": battery.percent,
            "power_plugged": battery.charging,
            "seconds_left": battery.seconds_left,
            "battery_percent_normalized": _normalize(battery.percent, 0.0, 100.0),
        },
        "temperature": {
            "cpu_celsius": cpu.temperature_celsius,
            "gpu_celsius": None,
            "cpu_celsius_normalized": _normalize(
                cpu.temperature_celsius, 20.0, 100.0
            ),
            "gpu_celsius_normalized": 0.0,
        },
        "filesystem": {
            "monitored_path": "/sandbox",
            "duration_seconds": 1,
            "events": [],
            "event_count": 0,
            "ambient_temperature_celsius": env.ambient_temperature_celsius,
            "humidity_percent": env.humidity_percent,
            "light_lux": env.light_lux,
            "sound_db": env.sound_db,
            "robot_position_x": robot.position_x,
            "robot_position_y": robot.position_y,
            "robot_velocity_x": robot.velocity_x,
            "robot_velocity_y": robot.velocity_y,
            "robot_task": robot.task,
            "robot_battery_percent": robot.battery_percent,
            "tick_id": tick_id,
            "world_coherence_score": snapshot.world_coherence_score,
        },
    }


__all__ = ["simulated_to_sensor_array_format"]
