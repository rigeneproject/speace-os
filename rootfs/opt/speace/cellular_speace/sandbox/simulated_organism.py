"""SimulatedOrganism — sandboxed cyber-physical organism simulator.

This module is meant to run INSIDE the sandbox container (Punto 1) and
produce synthetic sensor data without touching the host's real hardware.

The simulation evolves a coherent world state (CPU, memory, battery,
processes, environment, robot) tick by tick.  All randomness is driven
by an explicit ``random.Random(seed)`` instance so that the output is
fully reproducible.

Design constraints (from the Punto 4 plan):

* No host hardware probing (no ``psutil``, no ``os``/``subprocess``
  side-effects).
* No real network or filesystem mutations.
* Deterministic given ``seed`` and ``tick_id``.
* Coherent: if the robot moves, the position changes consistently with
  its velocity; if the battery discharges, the ``seconds_left`` field
  shrinks accordingly; etc.
"""

from __future__ import annotations

import math
import uuid
from collections import deque
from enum import Enum
from typing import Any, Deque, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------- #
# Virtual subsystems
# ---------------------------------------------------------------------- #


class VirtualCPU(BaseModel):
    """Synthetic CPU state for one tick."""

    usage_percent: float = Field(..., ge=0.0, le=100.0)
    temperature_celsius: float = Field(..., ge=0.0, le=120.0)
    frequency_mhz: float = Field(..., ge=100.0, le=6000.0)


class VirtualMemory(BaseModel):
    """Synthetic memory state for one tick."""

    total_mb: int = Field(..., ge=0)
    used_mb: int = Field(..., ge=0)
    percent: float = Field(..., ge=0.0, le=100.0)


class VirtualBattery(BaseModel):
    """Synthetic battery state for one tick."""

    percent: float = Field(..., ge=0.0, le=100.0)
    charging: bool
    seconds_left: Optional[int] = None


class VirtualProcess(BaseModel):
    """Synthetic process entry."""

    pid: int = Field(..., ge=0)
    name: str
    cpu_percent: float = Field(..., ge=0.0, le=100.0)
    memory_mb: float = Field(..., ge=0.0)


class VirtualEnvironment(BaseModel):
    """Synthetic ambient environment state for one tick."""

    ambient_temperature_celsius: float
    humidity_percent: float = Field(..., ge=0.0, le=100.0)
    light_lux: float = Field(..., ge=0.0)
    sound_db: float = Field(..., ge=0.0)


class VirtualRobot(BaseModel):
    """Synthetic 2-D robot state for one tick."""

    position_x: float
    position_y: float
    velocity_x: float
    velocity_y: float
    battery_percent: float = Field(..., ge=0.0, le=100.0)
    task: str  # "idle" | "moving" | "charging" | "error"


# ---------------------------------------------------------------------- #
# Events
# ---------------------------------------------------------------------- #


class SimulatedEventType(str, Enum):
    """Catalog of synthetic event types that the organism can emit."""

    NORMAL = "normal"
    ANOMALY_TEMP = "anomaly_temperature"
    ANOMALY_CPU = "anomaly_cpu_spike"
    ANOMALY_ROBOT = "anomaly_robot_stuck"
    ALARM_LOW_BATTERY = "alarm_low_battery"
    INFO_ROBOT_TASK_COMPLETE = "info_robot_task_complete"


class SimulatedEvent(BaseModel):
    """A single synthetic event emitted at a tick."""

    event_id: str
    event_type: SimulatedEventType
    timestamp: float
    description: str
    severity: float = Field(..., ge=0.0, le=1.0)


# ---------------------------------------------------------------------- #
# Snapshot (one full tick)
# ---------------------------------------------------------------------- #


class SimulatedSnapshot(BaseModel):
    """A complete, coherent state of the simulated organism at one tick."""

    tick_id: int = Field(..., ge=0)
    timestamp: float
    cpu: VirtualCPU
    memory: VirtualMemory
    battery: VirtualBattery
    processes: List[VirtualProcess]
    environment: VirtualEnvironment
    robot: VirtualRobot
    events: List[SimulatedEvent]
    world_coherence_score: float = Field(..., ge=0.0, le=1.0)


# ---------------------------------------------------------------------- #
# Simulator
# ---------------------------------------------------------------------- #


_PROCESS_NAMES = (
    "speace_core",
    "embodiment",
    "memory_loop",
    "temporal_engine",
    "language_organ",
    "regulation_layer",
    "evolution_kernel",
    "monitoring_agent",
)


class SimulatedOrganism:
    """Cyber-physical organism simulator producing reproducible synthetic data.

    Parameters
    ----------
    seed:
        Seed for the internal :class:`random.Random` instance.  The global
        RNG is never touched.
    tick_seconds:
        Wall-clock duration represented by one ``tick()`` call.  Used to
        compute ``seconds_left`` and to pace the optional real-time loop
        in :mod:`sandbox.sandbox_run`.
    enable_anomalies:
        If ``False``, no random anomalies are generated.  Useful for
        regression-style deterministic tests.
    anomaly_rate:
        Probability that a single ``tick()`` produces an anomaly.
    history_size:
        Maximum number of snapshots retained in ``get_history()``.
    """

    def __init__(
        self,
        seed: int = 42,
        tick_seconds: float = 1.0,
        enable_anomalies: bool = True,
        anomaly_rate: float = 0.01,
        history_size: int = 1024,
    ) -> None:
        self._seed = int(seed)
        self._tick_seconds = float(tick_seconds)
        self._enable_anomalies = bool(enable_anomalies)
        self._anomaly_rate = float(anomaly_rate)
        self._history_size = int(history_size)

        # Mutable state — populated by _init_state / reset.
        self._rng: Any = None
        self._tick_id: int = 0
        # Deterministic clock anchor so two instances with the same seed
        # produce byte-identical snapshots regardless of wall-clock time.
        self._start_ts: float = 0.0
        self._history: Deque[SimulatedSnapshot] = deque(maxlen=self._history_size)
        self._injected_events: Deque[SimulatedEvent] = deque()

        # Internal continuous state
        self._cpu: float = 25.0
        self._cpu_setpoint: float = 25.0
        self._cpu_temp: float = 45.0
        self._cpu_freq: float = 2400.0
        self._memory_total_mb: int = 16384
        self._memory_used_mb: int = 4096
        self._battery_percent: float = 100.0
        self._battery_charging: bool = False
        self._ambient_temp: float = 22.0
        self._humidity: float = 50.0
        self._light_lux: float = 350.0
        self._sound_db: float = 35.0
        self._robot_x: float = 0.0
        self._robot_y: float = 0.0
        self._robot_vx: float = 0.4
        self._robot_vy: float = 0.2
        self._robot_battery: float = 100.0
        self._robot_task: str = "moving"
        self._robot_stuck_ticks: int = 0  # decrements to 0
        self._process_cpu: List[float] = [0.0] * len(_PROCESS_NAMES)
        self._process_mem: List[float] = [0.0] * len(_PROCESS_NAMES)
        self._last_event_seq: int = 0
        self._anomaly_active: Dict[str, int] = {}
        self._task_complete_ticks_left: int = 0

        self.reset()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def reset(self) -> None:
        """Re-seed the RNG and restore the initial state."""
        import random as _random

        self._rng = _random.Random(self._seed)
        self._tick_id = 0
        # Use a deterministic anchor; the real wall-clock must never leak
        # into the simulator's output.
        self._start_ts = 0.0
        self._history.clear()
        self._injected_events.clear()

        self._cpu = 25.0
        self._cpu_setpoint = 25.0
        self._cpu_temp = 45.0
        self._cpu_freq = 2400.0
        self._memory_total_mb = 16384
        self._memory_used_mb = 4096
        self._battery_percent = 100.0
        self._battery_charging = False
        self._ambient_temp = 22.0
        self._humidity = 50.0
        self._light_lux = 350.0
        self._sound_db = 35.0
        self._robot_x = 0.0
        self._robot_y = 0.0
        self._robot_vx = 0.4
        self._robot_vy = 0.2
        self._robot_battery = 100.0
        self._robot_task = "moving"
        self._robot_stuck_ticks = 0
        self._process_cpu = [0.0] * len(_PROCESS_NAMES)
        self._process_mem = [0.0] * len(_PROCESS_NAMES)
        self._last_event_seq = 0
        self._anomaly_active = {}
        self._task_complete_ticks_left = 0

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def tick(self) -> SimulatedSnapshot:
        """Advance the simulation by one step and return the snapshot."""
        self._tick_id += 1
        rng = self._rng

        # Drain any injected events whose timestamp has been reached.
        drained: List[SimulatedEvent] = []
        while self._injected_events and self._injected_events[0].timestamp <= self._now():
            drained.append(self._injected_events.popleft())

        events: List[SimulatedEvent] = list(drained)

        # --- Anomaly lifecycle: decay timers -------------------------
        for k in list(self._anomaly_active.keys()):
            self._anomaly_active[k] -= 1
            if self._anomaly_active[k] <= 0:
                del self._anomaly_active[k]

        # --- Random anomaly injection --------------------------------
        if self._enable_anomalies and rng.random() < self._anomaly_rate:
            event = self._spawn_anomaly()
            events.append(event)

        # --- CPU evolution -------------------------------------------
        # Setpoint drift: very slow random walk.
        self._cpu_setpoint = max(
            5.0,
            min(75.0, self._cpu_setpoint + rng.gauss(0.0, 0.5)),
        )
        # Pull current usage toward setpoint + Gaussian noise.
        target = self._cpu_setpoint + rng.gauss(0.0, 4.0)
        self._cpu = self._lerp(self._cpu, target, 0.35)
        self._cpu = max(0.0, min(100.0, self._cpu))

        # CPU spike anomaly
        if SimulatedEventType.ANOMALY_CPU.value in self._anomaly_active:
            self._cpu = min(100.0, self._cpu + 35.0 + rng.random() * 10.0)

        # Frequency scales with load (1.2 GHz idle, up to 3.8 GHz boost).
        self._cpu_freq = 1200.0 + (self._cpu / 100.0) * 2600.0 + rng.gauss(0, 25)
        self._cpu_freq = max(1000.0, min(4000.0, self._cpu_freq))

        # --- CPU temperature with hysteresis -------------------------
        # If CPU > 30% temp rises; if < 20% temp falls; otherwise drift.
        if self._cpu > 30.0:
            self._cpu_temp += 0.6 + rng.gauss(0, 0.1)
        elif self._cpu < 20.0:
            self._cpu_temp -= 0.5 + rng.gauss(0, 0.1)
        else:
            self._cpu_temp += rng.gauss(0, 0.05)
        # Ambient coupling: pull gently toward ambient.
        self._cpu_temp = 0.92 * self._cpu_temp + 0.08 * self._ambient_temp
        if SimulatedEventType.ANOMALY_TEMP.value in self._anomaly_active:
            self._cpu_temp = min(95.0, self._cpu_temp + 8.0 + rng.random() * 3.0)
        self._cpu_temp = max(30.0, min(95.0, self._cpu_temp))

        # --- Memory --------------------------------------------------
        # Slight drift, anchored to CPU.
        cpu_pressure = (self._cpu / 100.0) * 0.4
        drift = rng.gauss(0, 25.0) + cpu_pressure * 50.0
        self._memory_used_mb = int(
            max(512, min(self._memory_total_mb - 256, self._memory_used_mb + drift))
        )
        mem_percent = (self._memory_used_mb / self._memory_total_mb) * 100.0
        mem_percent = max(0.0, min(100.0, mem_percent))

        # --- Battery -------------------------------------------------
        if self._battery_charging:
            self._battery_percent = min(100.0, self._battery_percent + 0.1)
            if self._battery_percent >= 99.95:
                self._battery_charging = False
        else:
            self._battery_percent = max(0.0, self._battery_percent - 0.05)
        # Occasionally start charging if plugged in and low.
        if (
            not self._battery_charging
            and self._battery_percent < 20.0
            and rng.random() < 0.01
        ):
            self._battery_charging = True

        seconds_left: Optional[int]
        if self._battery_charging or self._battery_percent <= 0.0:
            if self._battery_percent >= 100.0:
                seconds_left = None
            else:
                # Charging: time to full at +0.1%/tick.
                ticks_to_full = max(1, int(math.ceil((100.0 - self._battery_percent) / 0.1)))
                seconds_left = int(ticks_to_full * self._tick_seconds)
        else:
            # Discharging: time to empty at -0.05%/tick.
            ticks_to_empty = max(1, int(math.ceil(self._battery_percent / 0.05)))
            seconds_left = int(ticks_to_empty * self._tick_seconds)

        if self._battery_percent < 15.0 and self._enable_anomalies:
            # Periodic low-battery alarm, but not every tick.
            if rng.random() < 0.25:
                events.append(
                    SimulatedEvent(
                        event_id=self._next_event_id(),
                        event_type=SimulatedEventType.ALARM_LOW_BATTERY,
                        timestamp=self._now(),
                        description=(
                            f"Battery critically low at "
                            f"{self._battery_percent:.1f}%"
                        ),
                        severity=min(1.0, (15.0 - self._battery_percent) / 15.0 + 0.5),
                    )
                )

        # --- Environment --------------------------------------------
        self._ambient_temp += rng.gauss(0, 0.05)
        self._ambient_temp = max(15.0, min(35.0, self._ambient_temp))
        # CPU temp leaks into ambient when high.
        if self._cpu_temp > 70.0:
            self._ambient_temp = min(35.0, self._ambient_temp + 0.02)
        self._humidity = self._clip(self._humidity + rng.gauss(0, 0.4), 20.0, 90.0)
        self._light_lux = self._clip(self._light_lux + rng.gauss(0, 5.0), 0.0, 2000.0)
        self._sound_db = self._clip(self._sound_db + rng.gauss(0, 0.3), 20.0, 90.0)
        if SimulatedEventType.ANOMALY_ROBOT.value in self._anomaly_active:
            # Robot in error — louder ambient, hotter.
            self._sound_db = self._clip(self._sound_db + rng.uniform(2.0, 4.0), 20.0, 90.0)
            self._ambient_temp = min(35.0, self._ambient_temp + 0.05)

        # --- Robot --------------------------------------------------
        if SimulatedEventType.ANOMALY_ROBOT.value in self._anomaly_active:
            self._robot_stuck_ticks = max(self._robot_stuck_ticks, 1)
            self._robot_vx = 0.0
            self._robot_vy = 0.0
            self._robot_task = "error"
        else:
            # Direction-change probability per tick.
            if rng.random() < 0.08:
                # Pick a new direction (m/s) and a new task mostly 'moving'.
                angle = rng.uniform(0.0, 2.0 * math.pi)
                speed = rng.uniform(0.2, 0.8)
                self._robot_vx = speed * math.cos(angle)
                self._robot_vy = speed * math.sin(angle)
                self._robot_task = "moving" if rng.random() > 0.1 else "idle"
            if self._robot_stuck_ticks > 0:
                self._robot_stuck_ticks -= 1
            # Integrate position from velocity (m per tick).
            if self._robot_task == "moving" and self._robot_stuck_ticks == 0:
                self._robot_x += self._robot_vx * self._tick_seconds
                self._robot_y += self._robot_vy * self._tick_seconds
            # Robot battery drains slightly faster while moving.
            if self._robot_task == "moving":
                self._robot_battery = max(0.0, self._robot_battery - 0.02)
            elif self._robot_task == "idle":
                self._robot_battery = max(0.0, self._robot_battery - 0.005)
            # Charge if docked and low.
            if self._robot_battery < 20.0 and rng.random() < 0.02:
                self._robot_task = "charging"
            if self._robot_task == "charging":
                self._robot_battery = min(100.0, self._robot_battery + 0.1)
                if self._robot_battery >= 99.0:
                    self._robot_task = "moving"
                    self._robot_battery = 100.0

        # Clamp position to a soft square arena [-50, 50] m.
        self._robot_x = self._clip(self._robot_x, -50.0, 50.0)
        self._robot_y = self._clip(self._robot_y, -50.0, 50.0)

        # --- Processes ----------------------------------------------
        for i, name in enumerate(_PROCESS_NAMES):
            target = (self._cpu / 100.0) * (1.0 / len(_PROCESS_NAMES)) * 100.0
            jitter = rng.gauss(0, 1.2)
            self._process_cpu[i] = max(0.0, target + jitter)
            mem_target = (self._memory_used_mb / max(1, self._memory_total_mb)) * 512.0
            mem_jitter = rng.gauss(0, 8.0)
            self._process_mem[i] = max(8.0, mem_target + mem_jitter)
        processes = [
            VirtualProcess(
                pid=1000 + i,
                name=_PROCESS_NAMES[i],
                cpu_percent=round(self._process_cpu[i], 2),
                memory_mb=round(self._process_mem[i], 2),
            )
            for i in range(len(_PROCESS_NAMES))
        ]

        # --- Periodic task-complete info event ---------------------
        if self._enable_anomalies and self._robot_task == "moving":
            self._task_complete_ticks_left -= 1
            if self._task_complete_ticks_left <= 0 and rng.random() < 0.05:
                self._task_complete_ticks_left = rng.randint(20, 60)
                events.append(
                    SimulatedEvent(
                        event_id=self._next_event_id(),
                        event_type=SimulatedEventType.INFO_ROBOT_TASK_COMPLETE,
                        timestamp=self._now(),
                        description=(
                            f"Robot reached waypoint "
                            f"({self._robot_x:.1f}, {self._robot_y:.1f})"
                        ),
                        severity=0.1,
                    )
                )

        # --- World coherence ----------------------------------------
        coherence = self._compute_coherence(events)

        snapshot = SimulatedSnapshot(
            tick_id=self._tick_id,
            timestamp=self._now(),
            cpu=VirtualCPU(
                usage_percent=round(self._cpu, 2),
                temperature_celsius=round(self._cpu_temp, 2),
                frequency_mhz=round(self._cpu_freq, 2),
            ),
            memory=VirtualMemory(
                total_mb=self._memory_total_mb,
                used_mb=self._memory_used_mb,
                percent=round(mem_percent, 2),
            ),
            battery=VirtualBattery(
                percent=round(self._battery_percent, 3),
                charging=self._battery_charging,
                seconds_left=seconds_left,
            ),
            processes=processes,
            environment=VirtualEnvironment(
                ambient_temperature_celsius=round(self._ambient_temp, 2),
                humidity_percent=round(self._humidity, 2),
                light_lux=round(self._light_lux, 2),
                sound_db=round(self._sound_db, 2),
            ),
            robot=VirtualRobot(
                position_x=round(self._robot_x, 4),
                position_y=round(self._robot_y, 4),
                velocity_x=round(self._robot_vx, 4),
                velocity_y=round(self._robot_vy, 4),
                battery_percent=round(self._robot_battery, 3),
                task=self._robot_task,
            ),
            events=events,
            world_coherence_score=round(coherence, 4),
        )
        self._history.append(snapshot)
        return snapshot

    def get_history(self, n: int = 100) -> List[SimulatedSnapshot]:
        """Return the last *n* snapshots (most recent last)."""
        if n <= 0:
            return []
        return list(self._history)[-n:]

    def inject_event(self, event: SimulatedEvent) -> None:
        """Queue an event to be emitted on the next matching tick.

        If the event's ``timestamp`` is in the past relative to the next
        ``tick()`` call, it will be drained immediately.  Injected events
        bypass the RNG and always appear in the events list of the
        snapshot where they are drained.
        """
        # Make sure timestamp is set.
        if event.timestamp == 0.0:
            event.timestamp = self._now()
        # The injected event is treated as authoritative — if it is an
        # anomaly type, activate the corresponding lock for a few ticks
        # so the world state reacts coherently.
        if event.event_type in (
            SimulatedEventType.ANOMALY_TEMP,
            SimulatedEventType.ANOMALY_CPU,
            SimulatedEventType.ANOMALY_ROBOT,
        ):
            self._anomaly_active[event.event_type.value] = max(
                self._anomaly_active.get(event.event_type.value, 0),
                3,
            )
        self._injected_events.append(event)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _clip(v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, v))

    @staticmethod
    def _lerp(a: float, b: float, t: float) -> float:
        return a + (b - a) * t

    def _now(self) -> float:
        # Use a deterministic clock that advances with the tick_id so the
        # output is fully reproducible regardless of wall-clock.
        return self._start_ts + self._tick_id * self._tick_seconds

    def _next_event_id(self) -> str:
        self._last_event_seq += 1
        return f"EV-{self._seed}-{self._tick_id}-{self._last_event_seq:04d}"

    def _spawn_anomaly(self) -> SimulatedEvent:
        rng = self._rng
        anomaly_type = rng.choice(
            [
                SimulatedEventType.ANOMALY_TEMP,
                SimulatedEventType.ANOMALY_CPU,
                SimulatedEventType.ANOMALY_ROBOT,
            ]
        )
        if anomaly_type == SimulatedEventType.ANOMALY_TEMP:
            self._anomaly_active[anomaly_type.value] = 5
            return SimulatedEvent(
                event_id=self._next_event_id(),
                event_type=anomaly_type,
                timestamp=self._now(),
                description=(
                    f"Temperature anomaly: CPU at {self._cpu_temp:.1f} C"
                ),
                severity=0.7,
            )
        if anomaly_type == SimulatedEventType.ANOMALY_CPU:
            self._anomaly_active[anomaly_type.value] = 3
            return SimulatedEvent(
                event_id=self._next_event_id(),
                event_type=anomaly_type,
                timestamp=self._now(),
                description=f"CPU spike: {self._cpu:.1f}% usage",
                severity=0.6,
            )
        # ANOMALY_ROBOT
        self._anomaly_active[anomaly_type.value] = 4
        return SimulatedEvent(
            event_id=self._next_event_id(),
            event_type=anomaly_type,
            timestamp=self._now(),
            description="Robot stuck: position locked",
            severity=0.65,
        )

    def _compute_coherence(self, events: List[SimulatedEvent]) -> float:
        """Compute a [0, 1] coherence score for the current world state.

        Healthy regime is >= 0.85.  Active anomalies drag the score down
        into the 0.5–0.7 range.  The score is fully deterministic given
        the current internal state and the list of events emitted this
        tick.
        """
        score = 1.0
        # Each active anomaly knocks 0.1 off, capped at 0.5.
        for _etype, ticks_left in self._anomaly_active.items():
            score -= 0.1
        score -= 0.05 * len(events)
        # Physical sanity adjustments.
        if self._battery_percent < 5.0:
            score -= 0.1
        if self._cpu_temp > 85.0:
            score -= 0.1
        # Stochastic wobble bounded to ±0.02 so two identical instances
        # agree numerically (the RNG is consumed in lock-step).
        score += self._rng.uniform(-0.02, 0.02)
        return self._clip(score, 0.0, 1.0)
