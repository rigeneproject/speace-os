"""Start the SPEACE evolution daemon.

Usage:
  python scripts/start_evolution_daemon.py            # run forever
  python scripts/start_evolution_daemon.py --once     # one cycle, exit
  python scripts/start_evolution_daemon.py --no-dashboards
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Make `evolution_daemon` importable when running from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evolution_daemon.config import DaemonConfig
from evolution_daemon.daemon import EvolutionDaemon


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run a single cycle and exit")
    parser.add_argument("--no-dashboards", action="store_true", help="Skip launching dashboards")
    parser.add_argument("--cycle-interval", type=float, default=None, help="Override cycle interval (s)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = DaemonConfig.from_env()
    if args.cycle_interval is not None:
        config.cycle_interval_sec = float(args.cycle_interval)
    daemon = EvolutionDaemon(config=config)

    if args.once:
        result = asyncio.run(daemon.run_cycle())
        print(json.dumps(result, indent=2, default=str)[:8000])
        if not args.no_dashboards:
            ports = daemon.start_dashboards()
            print(f"dashboards: {ports}")
        return

    if not args.no_dashboards:
        ports = daemon.start_dashboards()
        print(f"dashboards: {ports}")
    daemon.run_forever()


if __name__ == "__main__":
    main()
