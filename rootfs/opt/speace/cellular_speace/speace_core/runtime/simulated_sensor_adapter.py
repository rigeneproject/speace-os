"""SimulatedSensorAdapter — adapter for ContinuousRuntimeEngine Punto 5.

This adapter implements the subset of :class:`CyberPhysicalSensorArray`
that the :class:`CellularBrainOrchestrator` actually calls inside its
tick pipeline:

* :meth:`read_all`  — returns a dict with the same shape that
  :meth:`CyberPhysicalSensorArray.read_all` produces
  (timestamp, cpu, memory, disk, network, process, power, temperature,
  filesystem).
* :meth:`start_continuous_sampling` / :meth:`stop_continuous_sampling`
  — no-ops.  The orchestrator and the runtime engine both expect these
  methods to exist; the simulator produces data synchronously inside
  :meth:`read_all` instead of pushing it in a background thread.

The adapter is **the** integration point between the Punto 4
:class:`SimulatedOrganism` and the production orchestrator pipeline
(``self._sensor_array.read_all()``).  It is enabled only when the
runtime is started with ``runtime_mode="simulated"``; the orchestrator
keeps its normal, real-sensor path in every other mode.

Design constraints (preserved from the Punto 4 plan and from the user
mandate):

* No real hardware probing (no psutil, no WMI, no /proc).
* No network calls, no filesystem mutations.
* Deterministic given ``seed`` and ``tick_id`` (delegated to
  :class:`SimulatedOrganism`).
* Safe-mode default: importing this module is a no-op for the
  orchestrator; it is wired in only by
  :class:`ContinuousRuntimeEngine._activate_simulated_mode`.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, Optional

from sandbox.sensor_bridge import simulated_to_sensor_array_format
from sandbox.simulated_organism import SimulatedOrganism, SimulatedSnapshot


_logger = logging.getLogger(__name__)


# Default registry of orchestrator attributes that the adapter can
# transparently replace.  Kept as a module-level constant so tests can
# assert on it without poking into private internals.
SIMULATED_MODE = "simulated"


class SimulatedSensorAdapter:
    """Adapter that exposes :class:`SimulatedOrganism` as a
    :class:`CyberPhysicalSensorArray` for the orchestrator pipeline.

    Parameters
    ----------
    seed:
        Seed for the deterministic simulator (see Punto 4).
    tick_seconds:
        Wall-clock duration represented by one ``tick()`` call.  Used by
        the simulator to compute ``seconds_left`` and timestamps.
    enable_anomalies:
        If ``True``, the simulator may inject random anomalies.  Set
        to ``False`` for deterministic regression tests.
    anomaly_rate:
        Probability that a single ``tick()`` produces a random anomaly.
    history_size:
        Maximum number of snapshots retained inside the simulator
        (forwarded to :class:`SimulatedOrganism`).
    orchestrator:
        Optional reference to the orchestrator owning this adapter.  If
        provided, the adapter can be queried by other runtime
        components; if not, the adapter is fully usable in isolation.
    """

    def __init__(
        self,
        seed: int = 42,
        tick_seconds: float = 1.0,
        enable_anomalies: bool = False,
        anomaly_rate: float = 0.01,
        history_size: int = 1024,
        orchestrator: Optional[Any] = None,
    ) -> None:
        self._seed = int(seed)
        self._tick_seconds = float(tick_seconds)
        self._enable_anomalies = bool(enable_anomalies)
        self._anomaly_rate = float(anomaly_rate)
        self._orchestrator = orchestrator

        # Mutable state for the background-sampling no-op (matches the
        # shape of CyberPhysicalSensorArray so that downstream code
        # does not crash if it ever inspects it).
        self._sampling_thread: Optional[threading.Thread] = None
        self._interval_ms: int = 1000
        self._stop_event: threading.Event = threading.Event()
        self._lock: threading.Lock = threading.Lock()
        self._history: list = []
        self._max_history: int = 256

        # The deterministic simulator.  Constructed eagerly so the
        # first read_all() is reproducible.
        self._organism = SimulatedOrganism(
            seed=self._seed,
            tick_seconds=self._tick_seconds,
            enable_anomalies=self._enable_anomalies,
            anomaly_rate=self._anomaly_rate,
            history_size=history_size,
        )

        _logger.info(
            "SimulatedSensorAdapter created (seed=%d, tick_seconds=%.3f, "
            "enable_anomalies=%s, anomaly_rate=%.4f)",
            self._seed,
            self._tick_seconds,
            self._enable_anomalies,
            self._anomaly_rate,
        )

    # ------------------------------------------------------------------ #
    # Public, orchestrator-facing API
    # ------------------------------------------------------------------ #

    def read_all(self) -> Dict[str, Any]:
        """Return one fresh simulated snapshot in
        :class:`CyberPhysicalSensorArray` format.

        The produced dict has the same top-level keys as
        :meth:`CyberPhysicalSensorArray.read_all`:

        ``timestamp``, ``cpu``, ``memory``, ``disk``, ``network``,
        ``process``, ``power``, ``temperature``, ``filesystem``.
        """
        snapshot: SimulatedSnapshot = self._organism.tick()
        payload: Dict[str, Any] = simulated_to_sensor_array_format(snapshot)
        with self._lock:
            self._history.append(payload)
            if len(self._history) > self._max_history:
                # drop oldest
                del self._history[: len(self._history) - self._max_history]
        return payload

    def start_continuous_sampling(self, interval_ms: int = 1000) -> None:
        """No-op kept for API compatibility with
        :meth:`CyberPhysicalSensorArray.start_continuous_sampling`.

        The simulator is invoked synchronously inside :meth:`read_all`;
        no background thread is required.  The method exists so that
        callers like ``orchestrator._init_embodiment_if_needed`` can
        invoke it without checking the runtime mode.
        """
        self._interval_ms = max(100, int(interval_ms))
        # Mark the no-op as "started" so repeated calls are idempotent,
        # mirroring the real sensor array's contract.
        return None

    def stop_continuous_sampling(self) -> None:
        """No-op kept for API compatibility with
        :meth:`CyberPhysicalSensorArray.stop_continuous_sampling`."""
        # If a sampling thread were ever spawned in the future, this is
        # where it would be stopped.  Today the adapter is fully
        # synchronous, so this is a no-op.
        return None

    # ------------------------------------------------------------------ #
    # Introspection helpers
    # ------------------------------------------------------------------ #

    def get_organism(self) -> SimulatedOrganism:
        """Return the underlying :class:`SimulatedOrganism` instance.

        Useful for tests and for the audit log: it allows callers to
        query the current simulated state without re-ticking the
        simulator.
        """
        return self._organism

    def get_history(self, n: int = 10) -> list:
        """Return the last ``n`` produced snapshots (most recent last)."""
        with self._lock:
            return list(self._history[-n:])

    @property
    def seed(self) -> int:
        return self._seed

    @property
    def tick_seconds(self) -> float:
        return self._tick_seconds

    @property
    def runtime_mode(self) -> str:
        """Always returns ``"simulated"`` (the adapter's whole point)."""
        return SIMULATED_MODE


# ---------------------------------------------------------------------- #
# Module-level helpers
# ---------------------------------------------------------------------- #


def is_simulated_runtime_active() -> bool:
    """Return ``True`` when the runtime is configured for simulated mode.

    The runtime engine sets the ``SPEACE_RUNTIME_MODE`` environment
    variable in :meth:`ContinuousRuntimeEngine._activate_simulated_mode`
    so that downstream code (third-party libraries, log filters, audit
    hooks) can detect the mode without importing the engine itself.
    """
    return os.environ.get("SPEACE_RUNTIME_MODE", "").lower() == SIMULATED_MODE


__all__ = [
    "SimulatedSensorAdapter",
    "SIMULATED_MODE",
    "is_simulated_runtime_active",
]
