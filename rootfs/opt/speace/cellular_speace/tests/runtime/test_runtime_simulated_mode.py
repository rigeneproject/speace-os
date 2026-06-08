"""Tests for Stage 2.5 / Punto 5 — runtime_mode='simulated'.

These tests cover the integration of the Punto 4
:class:`SimulatedOrganism` (via :mod:`sandbox.sensor_bridge`) into
:class:`ContinuousRuntimeEngine` through the
:class:`SimulatedSensorAdapter`.

Two layers are covered:

* **Adapter layer** — :class:`SimulatedSensorAdapter` exposes
  :meth:`read_all` in the same shape as
  :class:`CyberPhysicalSensorArray.read_all` and the no-op
  :meth:`start_continuous_sampling` / :meth:`stop_continuous_sampling`
  pair.
* **Engine layer** — :class:`ContinuousRuntimeEngine` accepts
  ``runtime_mode="simulated"`` at construction time, validates the
  parameter, swaps ``orchestrator._sensor_array`` with the adapter on
  :meth:`start`, writes the audit log, and leaves the default
  behaviour untouched when ``runtime_mode=None``.

The tests intentionally do not start a full asyncio loop: the
:func:`pytest.mark.asyncio` decorator is used sparingly, and the
adapter-level checks do not depend on any event loop at all.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import pytest


# ---------------------------------------------------------------------- #
# Imports under test
# ---------------------------------------------------------------------- #

from speace_core.runtime.continuous_runtime_engine import ContinuousRuntimeEngine
from speace_core.runtime.simulated_sensor_adapter import (
    SIMULATED_MODE,
    SimulatedSensorAdapter,
    is_simulated_runtime_active,
)


# ---------------------------------------------------------------------- #
# Minimal orchestrator double
# ---------------------------------------------------------------------- #


class _FakeOrchestrator:
    """A minimum-viable orchestrator double for engine-level tests.

    It implements the *exact* attributes that
    :meth:`ContinuousRuntimeEngine._activate_simulated_mode` touches
    on the real orchestrator (``_sensor_array``), plus the bootstrap
    attributes that the engine's :meth:`start` reads via
    ``getattr(...)`` so the engine can be brought up without dragging
    in a full :class:`CellularBrainOrchestrator`.
    """

    def __init__(self, with_real_sensor: bool = True) -> None:
        # Real sensor array (or not).  The real array is what
        # _activate_simulated_mode must stop and replace.
        self._sensor_array: Any = None
        if with_real_sensor:
            self._sensor_array = _FakeRealSensorArray()
        # Misc attributes that start() reads via getattr().
        self.embodiment_enabled = True
        self._physical_environment = object()
        self._embodied_actuator = None
        self._embodiment_monitor = None
        self.sleep_enabled = False
        self.brainstem_controller_enabled = False
        self.global_workspace_enabled = False
        self.temporal_dynamics_enabled = False
        self.neural_oscillator_enabled = False
        self.phase_coupling_enabled = False
        self.energy_field_enabled = False
        self.predictive_coding_enabled = False
        self.active_inference_enabled = False
        self.homeostatic_drive_enabled = False
        self.criticality_monitor_enabled = False
        self.node_id = "fake-orchestrator-001"

    def _initialize_dynamic_modules(self) -> None:  # pragma: no cover
        return None


class _FakeRealSensorArray:
    """A tiny stand-in for CyberPhysicalSensorArray.

    Only the two methods that
    :meth:`ContinuousRuntimeEngine._activate_simulated_mode` actually
    calls are implemented.  The constructor is a no-op so that it can
    be instantiated without psutil, WMI, or any host probing.
    """

    def __init__(self) -> None:
        self.start_continuous_sampling_calls: int = 0
        self.stop_continuous_sampling_calls: int = 0
        self._sampling_started = False

    def start_continuous_sampling(self, interval_ms: int = 1000) -> None:
        self.start_continuous_sampling_calls += 1
        self._sampling_started = True

    def stop_continuous_sampling(self) -> None:
        self.stop_continuous_sampling_calls += 1
        self._sampling_started = False

    def read_all(self) -> Dict[str, Any]:  # pragma: no cover
        # Should NOT be called in simulated mode.
        raise AssertionError("Real sensor array read_all() called in simulated mode")


# ---------------------------------------------------------------------- #
# Engine construction helpers
# ---------------------------------------------------------------------- #


def _build_engine(runtime_mode: Optional[str] = None, **kwargs: Any) -> ContinuousRuntimeEngine:
    """Build a ContinuousRuntimeEngine without running start().

    The :class:`ContinuousRuntimeEngine` constructor is heavy: it
    instantiates a number of subsystems (circadian scheduler, health
    monitor, narrative engine, ...).  None of those touch the host,
    so building the engine in isolation is safe and fast.  Only the
    tests that exercise the *behaviour* of :meth:`start` need to go
    through the async path.
    """
    orch = _FakeOrchestrator()
    return ContinuousRuntimeEngine(
        orchestrator=orch,
        tick_interval=0.05,
        runtime_mode=runtime_mode,
        **kwargs,
    )


# ---------------------------------------------------------------------- #
# 1. Default mode
# ---------------------------------------------------------------------- #


def test_default_mode_is_none() -> None:
    """The default ``runtime_mode`` must be ``None`` (no behaviour change)."""
    engine = _build_engine()
    assert engine.runtime_mode is None
    assert engine._simulated_sensor_adapter is None


# ---------------------------------------------------------------------- #
# 2. Validation
# ---------------------------------------------------------------------- #


@pytest.mark.parametrize("bad_value", ["foo", "real", "", "SIMULATED", "live"])
def test_invalid_runtime_mode_rejected(bad_value: str) -> None:
    """Any value not in ``ALLOWED_RUNTIME_MODES`` must raise ``ValueError``."""
    with pytest.raises(ValueError, match="Invalid runtime_mode"):
        _build_engine(runtime_mode=bad_value)


# ---------------------------------------------------------------------- #
# 3. Construction does not break under simulated mode
# ---------------------------------------------------------------------- #


def test_simulated_mode_does_not_break_construction() -> None:
    engine = _build_engine(runtime_mode="simulated")
    assert engine.runtime_mode == "simulated"


# ---------------------------------------------------------------------- #
# 4. Adapter contract
# ---------------------------------------------------------------------- #


_EXPECTED_KEYS = {
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


def test_simulated_adapter_read_all_returns_bridge_format() -> None:
    """``SimulatedSensorAdapter.read_all`` returns a dict with the same
    top-level keys that ``CyberPhysicalSensorArray.read_all`` returns."""
    adapter = SimulatedSensorAdapter(seed=123, tick_seconds=0.1)
    payload = adapter.read_all()
    assert isinstance(payload, dict)
    assert set(payload.keys()) == _EXPECTED_KEYS
    # A few invariants shared with the real array:
    assert isinstance(payload["timestamp"], str)
    assert "T" in payload["timestamp"]  # ISO-8601
    assert isinstance(payload["cpu"], dict)
    assert "usage_percent" in payload["cpu"]
    assert isinstance(payload["memory"], dict)
    assert "percent" in payload["memory"]


def test_simulated_adapter_is_deterministic_with_seed() -> None:
    """Same seed → identical first snapshot (Punto 4 contract)."""
    a = SimulatedSensorAdapter(seed=42, tick_seconds=1.0).read_all()
    b = SimulatedSensorAdapter(seed=42, tick_seconds=1.0).read_all()
    assert a == b


def test_simulated_adapter_different_seeds_diverge() -> None:
    a = SimulatedSensorAdapter(seed=1, tick_seconds=1.0).read_all()
    b = SimulatedSensorAdapter(seed=999, tick_seconds=1.0).read_all()
    # At least one numeric field should differ.
    assert a != b


def test_start_stop_continuous_sampling_idempotent() -> None:
    """start/stop on the adapter are idempotent no-ops."""
    adapter = SimulatedSensorAdapter(seed=7, tick_seconds=0.1)
    adapter.start_continuous_sampling(interval_ms=100)
    adapter.start_continuous_sampling(interval_ms=200)
    adapter.start_continuous_sampling()  # default
    adapter.stop_continuous_sampling()
    adapter.stop_continuous_sampling()
    # Still works for normal read_all() afterwards.
    payload = adapter.read_all()
    assert "cpu" in payload


def test_adapter_records_organism_state() -> None:
    """The adapter exposes the underlying SimulatedOrganism for inspection."""
    adapter = SimulatedSensorAdapter(seed=11, tick_seconds=0.5)
    adapter.read_all()
    org = adapter.get_organism()
    assert org._tick_id == 1
    adapter.read_all()
    assert org._tick_id == 2


# ---------------------------------------------------------------------- #
# 5. Engine activation
# ---------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_simulated_mode_creates_adapter_on_start() -> None:
    """After start() in simulated mode, the engine must own a SimulatedSensorAdapter
    and the orchestrator's _sensor_array must be the adapter."""
    engine = _build_engine(runtime_mode="simulated")
    orch = engine.orchestrator
    real_array = orch._sensor_array
    assert isinstance(real_array, _FakeRealSensorArray)

    try:
        await engine.start()
        # The adapter was created.
        assert engine._simulated_sensor_adapter is not None
        assert isinstance(engine._simulated_sensor_adapter, SimulatedSensorAdapter)
        # The orchestrator's _sensor_array was swapped.
        assert orch._sensor_array is engine._simulated_sensor_adapter
        # The real array's continuous sampling was stopped.
        assert real_array.stop_continuous_sampling_calls == 1
    finally:
        await engine.stop()


@pytest.mark.asyncio
async def test_simulated_mode_does_not_call_real_read_all() -> None:
    """In simulated mode, the orchestrator's _sensor_array must NOT be the real one."""
    engine = _build_engine(runtime_mode="simulated")
    try:
        await engine.start()
        # Orchestrator pipeline now reads from the adapter.  Running a
        # tick via the adapter's read_all() is fine.
        snap = engine.orchestrator._sensor_array.read_all()
        assert "cpu" in snap
    finally:
        await engine.stop()


# ---------------------------------------------------------------------- #
# 6. Audit log
# ---------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_audit_log_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """start() in simulated mode must append a JSONL line to
    ``data/sandbox/runtime_mode_activations.jsonl`` with the expected
    schema."""
    # Redirect the audit log into a temp dir so we don't pollute the
    # real data/sandbox/ tree.  We achieve this by changing the cwd
    # for the duration of the test.
    monkeypatch.chdir(tmp_path)

    engine = _build_engine(runtime_mode="simulated", simulated_seed=99)
    try:
        await engine.start()
    finally:
        await engine.stop()

    log_path = tmp_path / "data" / "sandbox" / "runtime_mode_activations.jsonl"
    assert log_path.is_file(), f"expected audit log at {log_path}"
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    # Schema checks
    assert record["event"] == "simulated_mode_activated"
    assert record["runtime_mode"] == "simulated"
    assert record["stage"] == "2.5-sandbox-lab"
    assert record["seed"] == 99
    assert record["enable_anomalies"] is False
    # Timestamp should be ISO-8601 UTC
    ts = record["timestamp"]
    assert isinstance(ts, str)
    datetime.fromisoformat(ts)  # raises if malformed
    # User / hostname / in_container
    assert "user" in record
    assert "hostname" in record
    assert "in_container" in record
    assert "orchestrator_id" in record


def test_no_audit_log_in_safe_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """In safe mode (runtime_mode=None) the activation log is NOT touched.

    Note: this test does not call start() (which would need the full
    engine), it only checks that the activation logger writes nothing
    when the mode is not simulated.
    """
    monkeypatch.chdir(tmp_path)
    engine = _build_engine(runtime_mode=None)
    # _log_runtime_mode_activation is only called by
    # _activate_simulated_mode, which is only called in simulated
    # mode.  So the audit file should not exist after a default
    # construction.
    log_path = tmp_path / "data" / "sandbox" / "runtime_mode_activations.jsonl"
    assert not log_path.exists()


# ---------------------------------------------------------------------- #
# 7. Environment flag
# ---------------------------------------------------------------------- #


def test_is_simulated_runtime_active_helper() -> None:
    """``is_simulated_runtime_active`` reads the env var and is case-insensitive."""
    old = os.environ.pop("SPEACE_RUNTIME_MODE", None)
    try:
        os.environ.pop("SPEACE_RUNTIME_MODE", None)
        assert is_simulated_runtime_active() is False
        os.environ["SPEACE_RUNTIME_MODE"] = "simulated"
        assert is_simulated_runtime_active() is True
        os.environ["SPEACE_RUNTIME_MODE"] = "SIMULATED"
        assert is_simulated_runtime_active() is True
        os.environ["SPEACE_RUNTIME_MODE"] = "real"
        assert is_simulated_runtime_active() is False
    finally:
        if old is not None:
            os.environ["SPEACE_RUNTIME_MODE"] = old
        else:
            os.environ.pop("SPEACE_RUNTIME_MODE", None)


# ---------------------------------------------------------------------- #
# 8. Simulated mode does not break the real-sensor path
# ---------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_safe_mode_keeps_real_sensor_array() -> None:
    """When ``runtime_mode=None`` (the default), start() must NOT touch
    the orchestrator's real sensor array."""
    orch = _FakeOrchestrator(with_real_sensor=True)
    real_array = orch._sensor_array
    assert isinstance(real_array, _FakeRealSensorArray)

    engine = ContinuousRuntimeEngine(
        orchestrator=orch,
        tick_interval=0.05,
        # runtime_mode omitted → defaults to None
    )
    try:
        await engine.start()
        assert engine._simulated_sensor_adapter is None
        # The real array is still in place.
        assert orch._sensor_array is real_array
        assert real_array.stop_continuous_sampling_calls == 0
    finally:
        await engine.stop()


# ---------------------------------------------------------------------- #
# 9. Adapter survives multiple read_all() calls
# ---------------------------------------------------------------------- #


def test_adapter_history_accumulates() -> None:
    adapter = SimulatedSensorAdapter(seed=5, tick_seconds=0.1)
    for _ in range(5):
        adapter.read_all()
    history = adapter.get_history(n=10)
    assert len(history) == 5
    # Each entry is a dict with the expected schema.
    for entry in history:
        assert "cpu" in entry
        assert "memory" in entry
