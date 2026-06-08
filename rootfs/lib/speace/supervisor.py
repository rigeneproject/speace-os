"""Supervisore di servizi ispirato a s6/runit, scritto in Python.

Lavora in coppia con ``os_coordinator``: il coordinatore scrive file
marker in ``/var/run/speace/<service>.<op>`` per chiedere start/stop/
restart, e il supervisore li esegue. Il supervisore inoltre fa
watchdog attivo: riavvia i servizi crashati (entro i limiti di
``coordinator.yaml``) e aggiorna i loro heartbeat.

Progettato per essere un singolo processo long-running (``speace-supervisor``).
Non è il PID 1: quello è ``os_coordinator``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=os.environ.get("SPEACE_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger("speace.supervisor")


SERVICES_DIR = Path("/etc/speace/services")
STATE_DIR = Path("/var/lib/speace")
MARKER_DIR = Path("/var/run/speace")
POLL_INTERVAL = 1.0
HEARTBEAT_STALE = 30.0


@dataclass
class ServiceDef:
    """Definizione di un servizio, letta da /etc/speace/services/<name>/."""

    name: str
    run_script: Path
    workdir: Path = Path("/opt/speace/cellular_speace")
    auto_start: bool = True
    auto_restart: bool = True
    max_restarts_per_hour: int = 6
    env_file: Optional[Path] = Path("/etc/speace/env.conf")
    depends_on: list[str] = field(default_factory=list)

    def can_restart(self, restart_count_window_start: float) -> bool:
        return (time.time() - restart_count_window_start) < 3600


@dataclass
class ServiceState:
    """Stato runtime di un servizio gestito dal supervisore."""

    defn: ServiceDef
    proc: Optional[subprocess.Popen] = None
    pid: Optional[int] = None
    started_at: float = 0.0
    restart_count: int = 0
    restart_window_start: float = 0.0
    last_heartbeat: float = 0.0
    stopping: bool = False
    expected_exit: bool = False

    def is_running(self) -> bool:
        if self.proc is None:
            return False
        return self.proc.poll() is None

    def to_dict(self) -> dict:
        return {
            "name": self.defn.name,
            "pid": self.pid,
            "running": self.is_running(),
            "started_at": self.started_at,
            "uptime_sec": (time.time() - self.started_at) if self.is_running() else 0.0,
            "restart_count": self.restart_count,
            "last_heartbeat": self.last_heartbeat,
        }


class Supervisor:
    """Service manager s6-like minimale."""

    def __init__(self, services_dir: Path = SERVICES_DIR) -> None:
        self.services_dir = services_dir
        self.services: dict[str, ServiceState] = {}
        self._stop = False
        self._load_services()

    def _load_services(self) -> None:
        if not self.services_dir.exists():
            logger.warning("services dir non esiste: %s", self.services_dir)
            return
        for entry in sorted(self.services_dir.iterdir()):
            if not entry.is_dir():
                continue
            run_script = entry / "run"
            if not run_script.exists():
                logger.warning("servizio %s senza 'run', skip", entry.name)
                continue
            if not (run_script.stat().st_mode & 0o111):
                logger.warning("servizio %s: 'run' non eseguibile, skip", entry.name)
                continue
            self.services[entry.name] = ServiceState(
                defn=ServiceDef(name=entry.name, run_script=run_script),
            )
            logger.info("servizio registrato: %s", entry.name)

    def install_signal_handlers(self) -> None:
        for sig_name in ("SIGTERM", "SIGINT"):
            sig = getattr(signal, sig_name, None)
            if sig is None:
                continue
            try:
                signal.signal(sig, self._on_signal)
            except (ValueError, OSError):  # pragma: no cover
                pass

    def _on_signal(self, *_: object) -> None:
        logger.info("segnale ricevuto, stop pianificato")
        self._stop = True

    # ------------------------------------------------------------------ #
    # Public ops
    # ------------------------------------------------------------------ #

    def start(self, name: str) -> bool:
        state = self.services.get(name)
        if state is None:
            logger.error("servizio sconosciuto: %s", name)
            return False
        if state.is_running():
            logger.info("%s già running (pid=%d)", name, state.pid)
            return True
        return self._start_service(state)

    def stop(self, name: str) -> bool:
        state = self.services.get(name)
        if state is None:
            return False
        if not state.is_running():
            return True
        state.stopping = True
        state.expected_exit = True
        try:
            if state.proc is not None:
                state.proc.terminate()
                try:
                    state.proc.wait(timeout=10)
                except subprocess.TimeoutExpired:  # pragma: no cover
                    state.proc.kill()
        finally:
            state.stopping = False
        return True

    def restart(self, name: str) -> bool:
        self.stop(name)
        time.sleep(0.5)
        return self.start(name)

    def status(self) -> dict:
        return {name: s.to_dict() for name, s in self.services.items()}

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _start_service(self, state: ServiceState) -> bool:
        env = os.environ.copy()
        if state.defn.env_file and state.defn.env_file.exists():
            try:
                with state.defn.env_file.open("r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line and not line.startswith("export "):
                            line = "export " + line
                        # shell-eval per rispettare export/quotes
                        try:
                            exec(line, {}, env)  # noqa: S102
                        except Exception:  # pragma: no cover
                            pass
            except Exception as exc:  # pragma: no cover
                logger.warning("env file non leggibile per %s: %s", state.defn.name, exc)

        log_path = Path("/var/log/speace") / f"{state.defn.name}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            log_fh = open(log_path, "ab", buffering=0)
        except Exception as exc:  # pragma: no cover
            logger.error("impossibile aprire log %s: %s", log_path, exc)
            return False

        logger.info("avvio %s (log=%s)", state.defn.name, log_path)
        try:
            state.proc = subprocess.Popen(
                [str(state.defn.run_script)],
                cwd=str(state.defn.workdir),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log_fh,
                stderr=log_fh,
                start_new_session=True,
            )
        except Exception as exc:  # pragma: no cover
            logger.error("impossibile avviare %s: %s", state.defn.name, exc)
            return False
        state.pid = state.proc.pid
        state.started_at = time.time()
        state.last_heartbeat = time.time()
        state.expected_exit = False
        return True

    def _process_markers(self) -> None:
        """Legge i file marker scritti da os_coordinator per dispatch azioni."""
        if not MARKER_DIR.exists():
            return
        try:
            entries = list(MARKER_DIR.iterdir())
        except Exception:  # pragma: no cover
            return
        for entry in entries:
            if entry.is_file():
                name = entry.name
                # Formato: <service>.<op>
                if "." not in name:
                    continue
                service, op = name.rsplit(".", 1)
                try:
                    entry.unlink()
                except Exception:  # pragma: no cover
                    pass
                if service not in self.services:
                    logger.warning("marker per servizio sconosciuto: %s", service)
                    continue
                if op == "start":
                    self.start(service)
                elif op == "stop":
                    self.stop(service)
                elif op == "restart":
                    self.restart(service)
                elif op == "status":
                    logger.info("status %s: %s", service, self.services[service].to_dict())
                else:
                    logger.warning("op sconosciuta: %s", op)

    def _watchdog(self) -> None:
        for name, state in self.services.items():
            if state.proc is None:
                continue
            ret = state.proc.poll()
            if ret is not None:
                # processo terminato
                was_expected = state.expected_exit
                state.proc = None
                state.pid = None
                if was_expected or not state.defn.auto_restart:
                    logger.info("%s terminato (exit=%s, expected=%s)",
                                name, ret, was_expected)
                    continue
                # auto-restart entro i limiti
                if state.restart_count < state.defn.max_restarts_per_hour:
                    state.restart_count += 1
                    if state.restart_window_start == 0.0:
                        state.restart_window_start = time.time()
                    logger.warning("%s terminato inaspettatamente (exit=%s), riavvio #%d",
                                   name, ret, state.restart_count)
                    self._start_service(state)
                else:
                    logger.error("%s ha esaurito i restart (%d/h), non riavvio",
                                 name, state.defn.max_restarts_per_hour)
            else:
                # processo vivo, aggiorna heartbeat
                state.last_heartbeat = time.time()

    # ------------------------------------------------------------------ #
    # Main loop
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        self.install_signal_handlers()
        logger.info("supervisore avviato, %d servizi registrati", len(self.services))
        for name, state in self.services.items():
            if state.defn.auto_start:
                self._start_service(state)
        while not self._stop:
            self._process_markers()
            self._watchdog()
            time.sleep(POLL_INTERVAL)
        # Shutdown ordinato
        for name in list(self.services.keys()):
            self.stop(name)
        logger.info("supervisore terminato")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="speace-supervisor")
    parser.add_argument("--services-dir", type=Path, default=SERVICES_DIR)
    parser.add_argument("--status", action="store_true", help="Stampa status ed esci")
    parser.add_argument("--once", action="store_true", help="Esegui un singolo tick")
    args = parser.parse_args(argv)
    sup = Supervisor(services_dir=args.services_dir)
    if args.status:
        print(json.dumps(sup.status(), indent=2))
        return 0
    if args.once:
        sup._process_markers()
        sup._watchdog()
        print(json.dumps(sup.status(), indent=2))
        return 0
    sup.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
