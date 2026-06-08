"""Registro dei servizi cognitivi gestiti dal coordinatore OS.

Ogni servizio è identificato da un nome canonico e ha uno stato. Il
coordinatore legge/scuote questo registro per sapere cosa sta girando
e cosa no. La sorgente di verità resta il supervisore (``/lib/speace/supervisor.py``);
questo registro ne è lo specchio in-memory.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Optional


class ServiceState(str, enum.Enum):
    """Stato di un servizio gestito dal coordinatore."""

    UNKNOWN = "unknown"
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    FAILED = "failed"
    RESTARTING = "restarting"


# Servizi canonici della distro SPEACE OS.
CANONICAL_SERVICES: tuple[str, ...] = (
    "speace-brain",       # speace_core orchestrator
    "speace-evolution",   # evolution_daemon LiveOrganism
    "speace-agi-team",    # speace_agi_team web server (porta 8686)
    "speace-dashboard",   # monitor FastAPI (porta 8787)
)


@dataclass
class ServiceRecord:
    name: str
    state: ServiceState = ServiceState.UNKNOWN
    pid: Optional[int] = None
    last_change: float = field(default_factory=time.time)
    last_error: str = ""
    restarts: int = 0
    last_heartbeat: float = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "pid": self.pid,
            "last_change": self.last_change,
            "last_error": self.last_error,
            "restarts": self.restarts,
            "last_heartbeat": self.last_heartbeat,
            "uptime_sec": (time.time() - self.last_change) if self.state == ServiceState.RUNNING else 0.0,
        }


class ServiceRegistry:
    """Registro thread-unsafe (è PID 1, single-threaded) dei servizi."""

    def __init__(self) -> None:
        self._records: dict[str, ServiceRecord] = {
            name: ServiceRecord(name=name) for name in CANONICAL_SERVICES
        }

    def all(self) -> list[ServiceRecord]:
        return [self._records[n] for n in CANONICAL_SERVICES]

    def get(self, name: str) -> Optional[ServiceRecord]:
        return self._records.get(name)

    def set_state(self, name: str, state: ServiceState, pid: Optional[int] = None) -> None:
        rec = self._records.get(name)
        if rec is None:
            rec = ServiceRecord(name=name, state=state, pid=pid)
            self._records[name] = rec
            return
        rec.state = state
        if pid is not None:
            rec.pid = pid
        rec.last_change = time.time()
        if state == ServiceState.RUNNING:
            rec.last_heartbeat = time.time()

    def heartbeat(self, name: str) -> None:
        rec = self._records.get(name)
        if rec is not None:
            rec.last_heartbeat = time.time()

    def record_error(self, name: str, error: str) -> None:
        rec = self._records.get(name)
        if rec is not None:
            rec.last_error = error
            rec.state = ServiceState.FAILED
            rec.last_change = time.time()

    def record_restart(self, name: str) -> None:
        rec = self._records.get(name)
        if rec is not None:
            rec.restarts += 1
            rec.state = ServiceState.RESTARTING
            rec.last_change = time.time()

    def snapshot(self) -> dict:
        return {name: self._records[name].to_dict() for name in CANONICAL_SERVICES}
