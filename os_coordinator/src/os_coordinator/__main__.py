"""Entry point: ``python -m os_coordinator`` avvia il PID 1 cognitivo.

CLI:
    speace-os-coordinator                # avvia in modalità PID 1
    speace-os-coordinator --dry-run      # modalità test, nessun effetto reale
    speace-os-coordinator --offline      # non consulta Ollama Cloud
    speace-os-coordinator --status       # stampa stato corrente e esce
    speace-os-coordinator --phase BOOT   # imposta la fase iniziale
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from os_coordinator.agentic_brain import AgenticBrain
from os_coordinator.coordinator import CoordinatorConfig, OSCoordinator
from os_coordinator.phases import Phase
from os_coordinator.service_registry import ServiceRegistry


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=os.environ.get("SPEACE_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )
    parser = argparse.ArgumentParser(
        prog="speace-os-coordinator",
        description="Coordinatore cognitivo del sistema operativo SPEACE OS",
    )
    parser.add_argument("--config", type=Path, default=CoordinatorConfig.config_path,
                        help="Percorso a coordinator.yaml")
    parser.add_argument("--dry-run", action="store_true",
                        help="Non eseguire azioni reali sul sistema")
    parser.add_argument("--offline", action="store_true",
                        help="Non consultare Ollama Cloud (usa decisioni di default)")
    parser.add_argument("--status", action="store_true",
                        help="Stampa lo stato corrente e esci")
    parser.add_argument("--phase", type=str, default="BOOT",
                        choices=[p.value for p in Phase],
                        help="Fase iniziale")
    parser.add_argument("--once", action="store_true",
                        help="Esegui un singolo tick ed esci (per test)")
    parser.add_argument("--log-file", type=Path, default=None,
                        help="File di log (default: stderr)")
    args = parser.parse_args(argv)

    if args.log_file:
        handler = logging.FileHandler(args.log_file, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s | %(message)s"))
        logging.getLogger().addHandler(handler)

    cfg = CoordinatorConfig(
        config_path=args.config,
        dry_run=args.dry_run,
        offline=args.offline,
    )
    coord = OSCoordinator(
        config=cfg,
        brain=AgenticBrain(offline=args.offline),
        registry=ServiceRegistry(),
    )
    # Forza la fase iniziale (in run normale parte da BOOT).
    if args.phase != Phase.BOOT.value:
        coord.state.transition(Phase(args.phase), reason="CLI override")

    if args.status:
        print(json.dumps(coord.status(), indent=2, default=str))
        return 0

    if args.once:
        # Singolo tick: utile per test/sviluppo.
        asyncio.run(coord._tick())
        print(json.dumps(coord.status(), indent=2, default=str))
        return 0

    try:
        asyncio.run(coord.run())
    except KeyboardInterrupt:
        coord.request_stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
