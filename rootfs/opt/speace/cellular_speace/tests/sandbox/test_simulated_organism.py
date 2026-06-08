"""Tests for the SimulatedOrganism simulator (Punto 4).

These tests are deterministic, do not depend on any host hardware, and
should run quickly.  They cover:

* determinism (same seed → same snapshot)
* statistical differences across seeds
* state invariants (coherence, battery drain, robot movement)
* anomaly injection
* ``reset()`` rewind semantics
* the ``simulated_to_sensor_array_format`` bridge
"""

from __future__ import annotations

import pytest

from sandbox import (
    SimulatedEvent,
    SimulatedEventType,
    SimulatedOrganism,
    SimulatedSnapshot,
    simulated_to_sensor_array_format,
    __version__,
)


# ---------------------------------------------------------------------- #
# Sanity / smoke
# ---------------------------------------------------------------------- #


def test_package_version_exposed() -> None:
    assert isinstance(__version__, str) and __version__


def test_tick_returns_snapshot() -> None:
    organism = SimulatedOrganism(seed=1)
    snap = organism.tick()
    assert isinstance(snap, SimulatedSnapshot)
    assert snap.tick_id == 1
    assert snap.cpu.usage_percent >= 0.0
    assert snap.battery.percent <= 100.0


# ---------------------------------------------------------------------- #
# Determinism
# ---------------------------------------------------------------------- #


def test_determinism() -> None:
    a = SimulatedOrganism(seed=123, enable_anomalies=True)
    b = SimulatedOrganism(seed=123, enable_anomalies=True)
    snaps_a = [a.tick() for _ in range(50)]
    snaps_b = [b.tick() for _ in range(50)]
    for sa, sb in zip(snaps_a, snaps_b):
        assert sa.model_dump() == sb.model_dump()


def test_different_seeds() -> None:
    a = SimulatedOrganism(seed=1, enable_anomalies=True)
    b = SimulatedOrganism(seed=2, enable_anomalies=True)
    snaps_a = [a.tick() for _ in range(100)]
    snaps_b = [b.tick() for _ in range(100)]
    # At least one snapshot must differ in CPU usage.
    differ = any(
        sa.cpu.usage_percent != sb.cpu.usage_percent
        for sa, sb in zip(snaps_a, snaps_b)
    )
    assert differ, "Different seeds should produce different sequences"


# ---------------------------------------------------------------------- #
# State invariants
# ---------------------------------------------------------------------- #


def test_state_invariants() -> None:
    organism = SimulatedOrganism(
        seed=7, enable_anomalies=False, anomaly_rate=0.0
    )
    for _ in range(1000):
        snap = organism.tick()
        # Coherence must stay in a sensible range in the no-anomaly regime.
        assert snap.world_coherence_score > 0.7, (
            f"Coherence dropped to {snap.world_coherence_score} under no-anomaly regime"
        )
        # Sanity caps.
        assert 0.0 <= snap.cpu.usage_percent <= 100.0
        assert 0.0 <= snap.battery.percent <= 100.0
        assert 0.0 <= snap.memory.percent <= 100.0
        assert 30.0 <= snap.cpu.temperature_celsius <= 95.0
        # Robot in arena.
        assert -50.0 <= snap.robot.position_x <= 50.0
        assert -50.0 <= snap.robot.position_y <= 50.0


def test_battery_drains() -> None:
    organism = SimulatedOrganism(
        seed=11, enable_anomalies=False, anomaly_rate=0.0, tick_seconds=1.0
    )
    initial = organism.tick()
    for _ in range(1000):
        organism.tick()
    final = organism.get_history(n=1)[0]
    # Battery should have decreased (no charging events in steady state).
    assert final.battery.percent < initial.battery.percent


# ---------------------------------------------------------------------- #
# Anomalies
# ---------------------------------------------------------------------- #


def test_anomaly_injection() -> None:
    # Seed picked so that with anomaly_rate=1.0 we see all anomaly types
    # within a small number of ticks.
    organism = SimulatedOrganism(
        seed=2024, enable_anomalies=True, anomaly_rate=1.0
    )
    anomaly_types_seen = set()
    for _ in range(30):
        snap = organism.tick()
        for ev in snap.events:
            if ev.event_type in (
                SimulatedEventType.ANOMALY_TEMP,
                SimulatedEventType.ANOMALY_CPU,
                SimulatedEventType.ANOMALY_ROBOT,
            ):
                anomaly_types_seen.add(ev.event_type)
    # With rate=1.0 for 30 ticks we must see at least one anomaly.
    assert anomaly_types_seen, "No anomaly was ever generated with rate=1.0"


def test_anomaly_disabled_emits_none() -> None:
    organism = SimulatedOrganism(
        seed=99, enable_anomalies=False, anomaly_rate=1.0
    )
    for _ in range(50):
        snap = organism.tick()
        for ev in snap.events:
            assert ev.event_type == SimulatedEventType.NORMAL
            assert ev.severity == 0.0


# ---------------------------------------------------------------------- #
# Reset
# ---------------------------------------------------------------------- #


def test_reset() -> None:
    a = SimulatedOrganism(seed=2026)
    for _ in range(20):
        a.tick()
    a.reset()
    b = SimulatedOrganism(seed=2026)
    for _ in range(20):
        sa = a.tick()
        sb = b.tick()
        assert sa.model_dump() == sb.model_dump()


# ---------------------------------------------------------------------- #
# Sensor bridge
# ---------------------------------------------------------------------- #


def test_sensor_bridge_format() -> None:
    organism = SimulatedOrganism(seed=5)
    snap = organism.tick()
    out = simulated_to_sensor_array_format(snap)
    expected_top_keys = {
        "timestamp",
        "cpu",
        "memory",
        "disk",
        "network",
        "process",
        "power",
        "temperature",
        "filesystem",
    }
    assert expected_top_keys.issubset(out.keys())
    # Sub-keys
    assert {"usage_percent", "frequency_mhz", "temperature_celsius"}.issubset(
        out["cpu"].keys()
    )
    assert {"total_bytes", "used_bytes", "free_bytes", "percent"}.issubset(
        out["memory"].keys()
    )
    assert {"drives", "read_bytes", "write_bytes"}.issubset(out["disk"].keys())
    assert {"bytes_sent", "bytes_received", "connections"}.issubset(
        out["network"].keys()
    )
    assert {"process_count", "top_by_cpu", "top_by_memory"}.issubset(
        out["process"].keys()
    )
    assert {"battery_percent", "power_plugged", "seconds_left"}.issubset(
        out["power"].keys()
    )
    assert {"cpu_celsius", "gpu_celsius"}.issubset(out["temperature"].keys())
    # Sanity: total >= used + free (modulo rounding).
    assert (
        out["memory"]["total_bytes"]
        >= out["memory"]["used_bytes"]
    )


# ---------------------------------------------------------------------- #
# Robot motion
# ---------------------------------------------------------------------- #


def test_robot_moves() -> None:
    organism = SimulatedOrganism(
        seed=13, enable_anomalies=False, anomaly_rate=0.0, tick_seconds=1.0
    )
    initial = organism.tick()
    for _ in range(200):
        organism.tick()
    final = organism.get_history(n=1)[0]
    moved_x = abs(final.robot.position_x - initial.robot.position_x)
    moved_y = abs(final.robot.position_y - initial.robot.position_y)
    assert (moved_x + moved_y) > 0.0, (
        "Robot did not move in 200 non-anomalous ticks"
    )


def test_robot_can_be_stuck() -> None:
    organism = SimulatedOrganism(
        seed=42, enable_anomalies=False, anomaly_rate=0.0, tick_seconds=1.0
    )
    # Warm up so the robot is moving.
    for _ in range(20):
        organism.tick()
    pre_stuck = organism.get_history(n=1)[0]
    # Inject a robot-stuck anomaly and tick once.
    organism.inject_event(
        SimulatedEvent(
            event_id="EV-injected-robot",
            event_type=SimulatedEventType.ANOMALY_ROBOT,
            timestamp=0.0,  # drained immediately
            description="Injected robot-stuck",
            severity=0.65,
        )
    )
    stuck_snap = organism.tick()
    # Position must be locked.
    assert (
        stuck_snap.robot.position_x == pre_stuck.robot.position_x
    ), "Robot x position changed while ANOMALY_ROBOT was active"
    assert (
        stuck_snap.robot.position_y == pre_stuck.robot.position_y
    ), "Robot y position changed while ANOMALY_ROBOT was active"
    assert stuck_snap.robot.task == "error"
    assert stuck_snap.robot.velocity_x == 0.0
    assert stuck_snap.robot.velocity_y == 0.0


# ---------------------------------------------------------------------- #
# History
# ---------------------------------------------------------------------- #


def test_history_window() -> None:
    organism = SimulatedOrganism(seed=3, history_size=10)
    for _ in range(25):
        organism.tick()
    history = organism.get_history(n=100)
    assert len(history) == 10
    # tick_id is strictly increasing
    for prev, nxt in zip(history, history[1:]):
        assert nxt.tick_id == prev.tick_id + 1
