"""Sandbox simulation package for the cyber-physical organism.

This package is meant to run INSIDE the sandbox container of Punto 1
and produce synthetic sensor data without touching the host's real
hardware.  It exposes a single, focused API:

* :class:`SimulatedOrganism` — the simulator itself.
* :class:`SimulatedSnapshot`, :class:`SimulatedEvent`, ... — the data
  models.
* :func:`simulated_to_sensor_array_format` — bridge to the real
  :class:`CyberPhysicalSensorArray` output schema.
"""

from __future__ import annotations

from sandbox.sensor_bridge import simulated_to_sensor_array_format
from sandbox.simulated_organism import (
    SimulatedEvent,
    SimulatedEventType,
    SimulatedOrganism,
    SimulatedSnapshot,
    VirtualBattery,
    VirtualCPU,
    VirtualEnvironment,
    VirtualMemory,
    VirtualProcess,
    VirtualRobot,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "SimulatedOrganism",
    "SimulatedSnapshot",
    "SimulatedEvent",
    "SimulatedEventType",
    "VirtualCPU",
    "VirtualMemory",
    "VirtualBattery",
    "VirtualProcess",
    "VirtualEnvironment",
    "VirtualRobot",
    "simulated_to_sensor_array_format",
]
