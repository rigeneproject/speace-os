"""SPEACE — 24/7 Live Launcher.

Avvia, in un UNICO processo e UNICO event loop persistente:

1.  Il **cervello/organismo** in loop continuo 24/7 (``ContinuousRuntimeEngine``)
    con il campo ILF acceso e cablato su tutti i sottosistemi, un battito
    spontaneo che mantiene i neuroni vivi e il recovery automatico da checkpoint.
2.  Il **team agentico NON-LLM** (``EvolutionDaemon``): cicli periodici di
    auto-miglioramento e auto-riprogettazione (snapshot, benchmark AGI, ARC,
    proposte di refactor/mutazione, fitness, executor bridge, proposte DNA,
    regression review, conflict resolution, rigenerazione del piano di
    ingegneria) — senza alcun LLM.

Perché un launcher dedicato e non ``EvolutionDaemon.run_forever``?
``run_forever`` esegue ``asyncio.run(run_cycle())`` ad ogni ciclo: il loop del
runtime (creato come task di background) verrebbe distrutto alla chiusura
dell'event loop di ogni ciclo. Qui invece teniamo UN solo event loop vivo per
sempre, con il runtime e i cicli del daemon come coroutine concorrenti.

Riavvio dopo spegnimento del PC: rilanciare semplicemente questo launcher. Il
``ContinuousRuntimeEngine`` salva checkpoint periodici (default 300 s) e il
``RecoveryOrchestrator`` ripristina automaticamente l'ultimo checkpoint all'avvio.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
import signal
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s",
)
logger = logging.getLogger("speace.live")


class LiveOrganism:
    """Coordina runtime 24/7 + team agentico non-LLM in un unico event loop."""

    def __init__(
        self,
        cycle_interval_sec: float = 300.0,
        tick_interval: float = 1.0,
        heartbeat_interval: float = 1.5,
        warmup_patterns: int = 40,
        start_dashboards: bool = False,
    ) -> None:
        self.cycle_interval_sec = cycle_interval_sec
        self.tick_interval = tick_interval
        self.heartbeat_interval = heartbeat_interval
        self.warmup_patterns = warmup_patterns
        self.start_dashboards = start_dashboards
        self._stop = asyncio.Event()
        self.orchestrator = None
        self.runtime = None
        self.daemon = None
        self._igniter = None
        self.ans = None  # Autonomic Nervous System

    # ------------------------------------------------------------------ #
    def _request_stop(self, *_: object) -> None:
        logger.info("Arresto richiesto — chiusura ordinata in corso...")
        self._stop.set()

    def install_signal_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        for sig in ("SIGINT", "SIGTERM", "SIGBREAK"):
            s = getattr(signal, sig, None)
            if s is None:
                continue
            try:
                loop.add_signal_handler(s, self._request_stop)
            except (NotImplementedError, RuntimeError, ValueError):
                # Windows: add_signal_handler often unsupported → fallback
                try:
                    signal.signal(s, lambda *_: self._request_stop())
                except (ValueError, OSError):
                    pass

    # ------------------------------------------------------------------ #
    async def _heartbeat(self) -> None:
        """Battito del sistema nervoso autonomo (ANS).

        Non è più uno stimolo casuale esterno: è l'anello autonomo intrinseco
        che legge i segni vitali, attiva i drive (goal engine), genera attività
        cognitiva interna quando non c'è input e applica i riflessi vitali
        (auto-revive) quando energia/attività/coerenza calano.
        """
        while not self._stop.is_set():
            if self.ans is not None:
                try:
                    self.ans.pulse()
                except Exception:  # pragma: no cover - difensivo
                    logger.debug("pulse ANS fallito", exc_info=True)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.heartbeat_interval)
            except asyncio.TimeoutError:
                pass

    async def _evolution_loop(self) -> None:
        """Esegue periodicamente un ciclo del team agentico non-LLM."""
        # Primo ciclo dopo un breve assestamento del cervello
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            pass
        while not self._stop.is_set():
            try:
                result = await self.daemon.run_cycle()
                agi = (
                    result.get("steps", {})
                    .get("benchmark", {})
                    .get("agi_percentage", 0.0)
                )
                logger.info(
                    "Ciclo evolutivo %s completato | AGI%%=%.2f | task=%d | proposte=%d | errori=%d",
                    result.get("cycle_id"),
                    agi,
                    len(result.get("steps", {}).get("tasks", [])),
                    len(result.get("steps", {}).get("refactor_proposals", [])),
                    len(result.get("errors", [])),
                )
            except Exception:  # pragma: no cover - resiliente
                logger.exception("ciclo evolutivo fallito")
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=self.cycle_interval_sec
                )
            except asyncio.TimeoutError:
                pass

    async def _status_loop(self) -> None:
        """Log periodico dello stato vitale dell'organismo."""
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=30.0)
            except asyncio.TimeoutError:
                pass
            if self.orchestrator is None:
                continue
            m = self.orchestrator.latest_metrics
            sci = self.orchestrator.get_systemic_coherence_index()
            fs = self.orchestrator.get_field_state()
            drive = "n/a"
            if self.ans is not None:
                hp = self.ans.drives.get_highest_priority_drive()
                drive = hp[0] if hp else "n/a"
            logger.info(
                "VITALI | tick=%s phi=%.3f energy=%.3f active=%s SCI=%.3f ILF=%.3f drive=%s",
                self.orchestrator.current_tick,
                m.coherence_phi if m else 0.0,
                m.mean_energy if m else 0.0,
                m.active_neurons if m else 0,
                sci,
                fs.ilf_value if fs else 0.0,
                drive,
            )

    # ------------------------------------------------------------------ #
    async def run(self) -> None:
        from evolution_daemon.config import DaemonConfig
        from evolution_daemon.daemon import EvolutionDaemon
        from speace_core.bootstrap.ignition import OrganismIgnition
        from speace_core.runtime.continuous_runtime_engine import (
            ContinuousRuntimeEngine,
        )

        loop = asyncio.get_running_loop()
        self.install_signal_handlers(loop)

        # 1) Accendi l'organismo (ILF on + regolazione globale).
        logger.info("Accensione organismo (ILF on)...")
        self._igniter = OrganismIgnition(warmup_patterns=self.warmup_patterns, sustain_ticks=0)
        self.orchestrator = self._igniter.build()

        # Sistema Nervoso Autonomo: attività intrinseca + riflessi vitali.
        # + Memoria causale + Epigenetica + Loop adattativo.
        from speace_core.cellular_brain.autonomic import (
            AutonomicNervousSystem,
            CausalAdaptationLoop,
            CausalMemory,
        )
        from speace_core.epigenetics import EpigeneticTagsManager

        self._epigenetics = EpigeneticTagsManager()
        self._causal_memory = CausalMemory(max_window=100)
        self._causal_adaptation = CausalAdaptationLoop(
            causal_memory=self._causal_memory,
            epigenetics=self._epigenetics,
            adaptation_interval=10,
        )
        self.ans = AutonomicNervousSystem(
            self.orchestrator,
            causal_memory=self._causal_memory,
            causal_adaptation_loop=self._causal_adaptation,
        )

        # 2) Team agentico non-LLM, riusando l'orchestratore vivo.
        cfg = DaemonConfig.from_env()
        cfg.cycle_interval_sec = self.cycle_interval_sec
        self.daemon = EvolutionDaemon(cfg)
        self.daemon._orchestrator = self.orchestrator

        # 3) Runtime continuo 24/7 (recovery automatico da checkpoint).
        self.runtime = ContinuousRuntimeEngine(
            orchestrator=self.orchestrator,
            tick_interval=self.tick_interval,
        )
        self.daemon._runtime = self.runtime
        start_info = await self.runtime.start()
        logger.info(
            "Runtime avviato: stato=%s recovery=%s",
            start_info.get("state"),
            start_info.get("recovery", {}).get("status"),
        )
        logger.info(start_info.get("resume_narrative", ""))

        # 4) Cabla il campo ILF DOPO start() (che reinizializza il field
        #    integrator) per registrare l'intero organismo, non solo il cervello.
        n_sub = self._igniter.wire_field()
        logger.info("Campo ILF cablato su %d sottosistemi.", n_sub)

        # 5) Dashboard opzionali del daemon.
        if self.start_dashboards:
            try:
                ports = self.daemon.start_dashboards()
                logger.info("Dashboard daemon attive su %s", ports)
            except Exception:
                logger.warning("Avvio dashboard fallito", exc_info=True)

        logger.info(
            "SPEACE VIVO 24/7 — cervello in loop + team non-LLM ogni %.0fs. "
            "Ctrl+C per arresto ordinato.",
            self.cycle_interval_sec,
        )

        # 6) Esegui concorrentemente: heartbeat, cicli evolutivi, status.
        tasks = [
            asyncio.create_task(self._heartbeat(), name="heartbeat"),
            asyncio.create_task(self._evolution_loop(), name="evolution"),
            asyncio.create_task(self._status_loop(), name="status"),
        ]
        await self._stop.wait()

        # 7) Arresto ordinato: ferma cicli, salva checkpoint, halt runtime.
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        try:
            await self.runtime.halt()
            await self.runtime.stop()
        except Exception:
            logger.warning("Halt runtime con avvisi", exc_info=True)
        if self.start_dashboards and self.daemon is not None:
            self.daemon.stop_dashboards()
        logger.info("Organismo arrestato in modo sicuro. Checkpoint salvato.")


def main(argv: Optional[list] = None) -> None:
    parser = argparse.ArgumentParser(
        description="SPEACE — avvia cervello/organismo 24/7 + team agentico non-LLM"
    )
    parser.add_argument(
        "--cycle-interval", type=float, default=300.0,
        help="Secondi tra i cicli del team evolutivo non-LLM (default 300)",
    )
    parser.add_argument(
        "--tick-interval", type=float, default=1.0,
        help="Secondi tra i tick del cervello (default 1.0)",
    )
    parser.add_argument(
        "--dashboards", action="store_true",
        help="Avvia anche le dashboard web del daemon",
    )
    args = parser.parse_args(argv)

    live = LiveOrganism(
        cycle_interval_sec=args.cycle_interval,
        tick_interval=args.tick_interval,
        start_dashboards=args.dashboards,
    )
    try:
        asyncio.run(live.run())
    except KeyboardInterrupt:
        logger.info("Interrotto da tastiera.")


if __name__ == "__main__":
    main()
