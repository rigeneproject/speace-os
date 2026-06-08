"""Coordinatore OS — il cuore del PID 1.

Macchina a stati che orchestra l'avvio, la supervisione e lo spegnimento
dei servizi cognitivi. È progettato per girare come PID 1 dentro al
contenitore initramfs/rootfs della distro, ma funziona anche come
programma utente in ``--dry-run`` mode per test e sviluppo.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from os_coordinator.agentic_brain import AgenticBrain, AgenticDecision
from os_coordinator.health import HealthReport, check_health
from os_coordinator.phases import Phase, can_transition
from os_coordinator.policy import plan_actions
from os_coordinator.service_registry import ServiceRegistry, ServiceState
from os_coordinator.state_machine import StateMachine

logger = logging.getLogger("os_coordinator")


DEFAULT_CONFIG_PATH = Path("/etc/speace/coordinator.yaml")


@dataclass
class CoordinatorConfig:
    """Configurazione del coordinatore OS."""

    config_path: Path = DEFAULT_CONFIG_PATH
    services_dir: Path = Path("/etc/speace/services")
    state_dir: Path = Path("/var/lib/speace")
    log_dir: Path = Path("/var/log/speace")
    heartbeat_interval_sec: float = 5.0
    cognition_tick_sec: float = 30.0
    idle_tick_sec: float = 10.0
    ai_consult_every_n_ticks: int = 6  # in IDLE, chiedi all'AI ogni N tick
    dry_run: bool = False
    offline: bool = False

    def load_yaml(self) -> dict:
        """Carica coordinator.yaml se esiste. Ritorna {} altrimenti."""
        if not self.config_path.exists():
            return {}
        try:
            import yaml  # type: ignore
        except ImportError:
            return {}
        try:
            with self.config_path.open("r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            if not isinstance(data, dict):
                return {}
            return data
        except Exception as exc:  # pragma: no cover
            logger.warning("impossibile leggere %s: %s", self.config_path, exc)
            return {}


class OSCoordinator:
    """Coordinatore OS cognitivo. Singolo loop asyncio, single-thread."""

    def __init__(
        self,
        config: Optional[CoordinatorConfig] = None,
        brain: Optional[AgenticBrain] = None,
        registry: Optional[ServiceRegistry] = None,
    ) -> None:
        self.config = config or CoordinatorConfig()
        self.brain = brain or AgenticBrain(offline=self.config.offline)
        self.registry = registry or ServiceRegistry()
        self.state = StateMachine(initial=Phase.BOOT)
        self._stop = asyncio.Event()
        self._tick_count: int = 0
        self._decisions_log: list[AgenticDecision] = []
        self._start_time: float = time.time()

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def run(self) -> None:
        """Loop principale del coordinatore."""
        logger.info("OSCoordinator avviato in fase %s", self.state.current.value)
        self._install_signal_handlers()
        while not self.state.in_(Phase.SHUTDOWN):
            try:
                await self._tick()
            except Exception:  # pragma: no cover - resiliente
                logger.exception("errore in _tick, continuo")
            await asyncio.sleep(self._tick_interval())
        logger.info("OSCoordinator terminato in fase %s", self.state.current.value)

    def _install_signal_handlers(self) -> None:
        """SIGTERM/SIGINT → SHUTDOWN. Solo se non siamo PID 1 (init ha i suoi handler)."""
        if os.getpid() == 1:
            return
        for sig_name in ("SIGTERM", "SIGINT"):
            sig = getattr(signal, sig_name, None)
            if sig is None:
                continue
            try:
                asyncio.get_running_loop().add_signal_handler(sig, self.request_stop)
            except (NotImplementedError, RuntimeError):  # pragma: no cover
                pass

    def request_stop(self) -> None:
        logger.info("richiesta di stop ricevuta")
        self._stop.set()

    def _tick_interval(self) -> float:
        phase = self.state.current
        if phase in (Phase.BOOT, Phase.IGNITION, Phase.SHUTDOWN):
            return 0.1
        if phase == Phase.COGNITION:
            return self.config.cognition_tick_sec
        return self.config.idle_tick_sec

    async def _tick(self) -> None:
        self._tick_count += 1
        phase = self.state.current
        if phase == Phase.BOOT:
            await self._phase_boot()
        elif phase == Phase.IGNITION:
            await self._phase_ignition()
        elif phase == Phase.COGNITION:
            await self._phase_cognition()
        elif phase == Phase.IDLE:
            await self._phase_idle()
        elif phase == Phase.INTERVENTION:
            await self._phase_intervention()
        # SHUTDOWN è gestito a parte

    # ------------------------------------------------------------------ #
    # Phases
    # ------------------------------------------------------------------ #

    async def _phase_boot(self) -> None:
        logger.info("[BOOT] montaggio proc/sys/dev e lettura os-release")
        if self.config.dry_run:
            logger.info("[BOOT] dry-run: skip montaggi reali")
        else:
            self._try_mount("proc", "/proc", "proc", 0)
            self._try_mount("sys", "/sys", "sysfs", 0)
            self._try_mount("dev", "/dev", "devtmpfs", 0)
            self._try_mount("tmpfs", "/run", "tmpfs", 0)
            self._try_mount("tmpfs", "/tmp", "tmpfs", 0)
        self._ensure_dirs()
        self._log_os_release()
        self.state.transition(Phase.IGNITION, reason="boot completato")

    async def _phase_ignition(self) -> None:
        logger.info("[IGNITION] caricamento config e validazione installazione")
        cfg_yaml = self.config.load_yaml()
        logger.info("[IGNITION] config caricata: %d chiavi", len(cfg_yaml))
        # Verifica esistenza dei servizi canonici.
        for name in self.registry.snapshot():
            rec = self.registry.get(name)
            if rec and self.config.services_dir.joinpath(name).exists():
                self.registry.set_state(name, ServiceState.STOPPED)
        if self.config.dry_run:
            logger.info("[IGNITION] dry-run: non avvio servizi reali")
        self.state.transition(Phase.COGNITION, reason="ignition completata")

    async def _phase_cognition(self) -> None:
        """L'AI produce il piano di avvio iniziale dei servizi cognitivi."""
        logger.info("[COGNITION] consulto l'agentic AI per il piano di avvio")
        context = self._build_context(extra={
            "stage": "initial_startup",
            "available_services": self.registry.snapshot(),
        })
        decision = self.brain.decide(context)
        self._decisions_log.append(decision)
        logger.info("[COGNITION] decisione AI: %s (urgency=%s)",
                    decision.phase_decision, decision.urgency)
        if decision.phase_decision == "SHUTDOWN":
            self.state.transition(Phase.SHUTDOWN, reason=f"AI: {decision.reasoning}")
            return
        await self._execute_decision(decision)
        self.state.transition(Phase.IDLE, reason="avvio cognitivo completato")

    async def _phase_idle(self) -> None:
        """Heartbeat + consulto AI a frequenza ridotta."""
        # Aggiorna heartbeat di tutti i servizi RUNNING.
        for rec in self.registry.all():
            if rec.state == ServiceState.RUNNING:
                self.registry.heartbeat(rec.name)
        if self._tick_count % self.config.ai_consult_every_n_ticks == 0:
            health = check_health(self.registry)
            if not health.healthy:
                self.state.transition(Phase.INTERVENTION,
                                      reason="; ".join(health.notes[:2]) or "health degraded")
                return
            context = self._build_context(extra={
                "stage": "idle_supervision",
                "tick": self._tick_count,
                "uptime_sec": time.time() - self._start_time,
            })
            decision = self.brain.decide(context)
            self._decisions_log.append(decision)
            if decision.phase_decision in ("INTERVENE", "SHUTDOWN", "START_SERVICES"):
                self.state.transition(Phase.INTERVENTION,
                                      reason=decision.reasoning or decision.phase_decision)
                return
        # In IDLE resta fino a SHUTDOWN esplicito.

    async def _phase_intervention(self) -> None:
        """L'AI ha chiesto un intervento: esegui le azioni e torna in IDLE."""
        logger.info("[INTERVENTION] azione correttiva richiesta")
        # Prendi l'ultima decisione non vuota come "corrente".
        decision = self._decisions_log[-1] if self._decisions_log else AgenticDecision(
            phase_decision="IDLE", actions=[], reasoning="no decision", urgency="low",
        )
        if decision.phase_decision == "SHUTDOWN":
            self.state.transition(Phase.SHUTDOWN, reason=decision.reasoning)
            return
        await self._execute_decision(decision)
        self.state.transition(Phase.IDLE, reason="intervento completato")

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _ensure_dirs(self) -> None:
        for d in (self.config.state_dir, self.config.log_dir, Path("/var/lib/speace/coordinator")):
            try:
                d.mkdir(parents=True, exist_ok=True)
            except Exception:  # pragma: no cover
                pass

    def _log_os_release(self) -> None:
        rel = Path("/etc/os-release")
        if not rel.exists():
            return
        try:
            text = rel.read_text(encoding="utf-8")
            for line in text.splitlines():
                if line.startswith(("NAME=", "VERSION=", "ID=")):
                    logger.info("[BOOT] %s", line)
        except Exception:  # pragma: no cover
            pass

    def _try_mount(self, _name: str, target: str, fstype: str, _flags: int) -> None:
        """Tenta un mount; non fatale in dry-run o se già montato."""
        if self.config.dry_run:
            return
        try:
            import os as _os
            _os.makedirs(target, exist_ok=True)
        except Exception:  # pragma: no cover
            pass
        # Implementazione reale delegata al supervisore/init: qui è no-op.

    def _build_context(self, extra: Optional[dict] = None) -> dict:
        ctx = {
            "hostname": _safe_hostname(),
            "phase": self.state.current.value,
            "tick": self._tick_count,
            "uptime_sec": time.time() - self._start_time,
            "registry": self.registry.snapshot(),
            "state_machine": self.state.snapshot(),
            "coordinator_config": {
                "offline": self.config.offline,
                "dry_run": self.config.dry_run,
            },
        }
        if extra:
            ctx.update(extra)
        return ctx

    async def _execute_decision(self, decision: AgenticDecision) -> None:
        actions = plan_actions(decision, self.registry)
        for action in actions:
            if not action.accepted:
                logger.warning("azione rifiutata: %s/%s (%s)",
                               action.service, action.op, action.reason)
                continue
            await self._dispatch(action.service, action.op)

    async def _dispatch(self, service: str, op: str) -> None:
        """Dispatch sincronizzato con il supervisore di servizi.

        In modalità dry-run, simula l'azione. In modalità normale,
        delega al supervisore (``/lib/speace/supervisor.py``).
        """
        if self.config.dry_run:
            logger.info("[dispatch] dry-run: %s/%s", service, op)
            if op == "start":
                self.registry.set_state(service, ServiceState.RUNNING, pid=os.getpid())
            elif op == "stop":
                self.registry.set_state(service, ServiceState.STOPPED)
            elif op == "restart":
                self.registry.record_restart(service)
                self.registry.set_state(service, ServiceState.RUNNING, pid=os.getpid())
            elif op == "status":
                logger.info("[dispatch] status: %s", self.registry.get(service).to_dict())
            return

        # Implementazione reale: scrivi un file marker che il supervisore monitora.
        # (Il supervisore è un processo separato, vedi /lib/speace/supervisor.py.)
        marker = Path(f"/var/run/speace/{service}.{op}")
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(str(time.time()), encoding="utf-8")
            if op == "start":
                self.registry.set_state(service, ServiceState.RUNNING)
            elif op == "stop":
                self.registry.set_state(service, ServiceState.STOPPED)
            elif op == "restart":
                self.registry.record_restart(service)
                self.registry.set_state(service, ServiceState.RUNNING)
        except Exception as exc:  # pragma: no cover
            self.registry.record_error(service, str(exc))

    def shutdown(self) -> None:
        """Avvia shutdown ordinato. Bloccante."""
        logger.info("shutdown richiesto")
        if not can_transition(self.state.current, Phase.SHUTDOWN):
            logger.warning("transizione a SHUTDOWN non permessa da %s", self.state.current.value)
            return
        self.state.transition(Phase.SHUTDOWN, reason="richiesta shutdown")

    def status(self) -> dict:
        """Stato corrente serializzabile per /status e debug."""
        return {
            "version": "0.1.0-cos",
            "uptime_sec": time.time() - self._start_time,
            "phase": self.state.current.value,
            "phase_time_sec": self.state.time_in_current(),
            "tick": self._tick_count,
            "registry": self.registry.snapshot(),
            "state_machine": self.state.snapshot(),
            "brain": self.brain.describe(),
            "decisions_count": len(self._decisions_log),
            "dry_run": self.config.dry_run,
        }


def _safe_hostname() -> str:
    try:
        import socket
        return socket.gethostname()
    except Exception:  # pragma: no cover
        return "speace-os"
