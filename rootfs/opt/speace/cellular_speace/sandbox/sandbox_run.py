"""Entry point for running the SimulatedOrganism from the command line.

Usage::

    python -m sandbox.sandbox_run --seed 42 --ticks 100 \\
        --output-file data/sandbox/run_001.jsonl

By default the script runs in real-time pacing (``--tick-seconds 1.0``).
Use ``--tick-seconds 0`` for a fast as-fast-as-possible batch run.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from sandbox.simulated_organism import (
    SimulatedEvent,
    SimulatedEventType,
    SimulatedOrganism,
    SimulatedSnapshot,
)
from sandbox.sensor_bridge import simulated_to_sensor_array_format


def _snapshot_to_jsonl(snapshot: SimulatedSnapshot) -> str:
    """Serialise a snapshot to a single JSON line."""
    return json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False)


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="sandbox.sandbox_run",
        description=(
            "Run the simulated cyber-physical organism for N ticks and "
            "stream JSON-per-line snapshots to stdout (or a file)."
        ),
    )
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42).")
    parser.add_argument(
        "--tick-seconds",
        type=float,
        default=1.0,
        help="Wall-clock seconds per tick (default: 1.0, use 0 for fast batch).",
    )
    parser.add_argument(
        "--ticks",
        type=int,
        default=100,
        help="Number of ticks to execute (default: 100).",
    )
    parser.add_argument(
        "--anomaly-rate",
        type=float,
        default=0.01,
        help="Probability of anomaly per tick (default: 0.01).",
    )
    parser.add_argument(
        "--enable-anomalies",
        dest="enable_anomalies",
        action="store_true",
        default=True,
        help="Enable stochastic anomaly injection (default: on).",
    )
    parser.add_argument(
        "--disable-anomalies",
        dest="enable_anomalies",
        action="store_false",
        help="Disable stochastic anomaly injection.",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="If set, append JSONL snapshots to this file as well as stdout.",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="If set, suppress per-tick output and only emit the final summary.",
    )
    return parser.parse_args(argv)


def _summary(organism: SimulatedOrganism, total_ticks: int) -> Dict[str, Any]:
    history = organism.get_history(n=total_ticks)
    anomalies = sum(
        1
        for s in history
        for ev in s.events
        if ev.event_type != SimulatedEventType.NORMAL
        and not ev.event_type.value.startswith("info_")
    )
    low_battery = sum(
        1
        for s in history
        for ev in s.events
        if ev.event_type == SimulatedEventType.ALARM_LOW_BATTERY
    )
    if history:
        first = history[0]
        last = history[-1]
        battery_delta = last.battery.percent - first.battery.percent
        robot_distance = (
            (last.robot.position_x - first.robot.position_x) ** 2
            + (last.robot.position_y - first.robot.position_y) ** 2
        ) ** 0.5
        min_coherence = min(s.world_coherence_score for s in history)
        max_coherence = max(s.world_coherence_score for s in history)
        mean_coherence = sum(s.world_coherence_score for s in history) / len(history)
    else:
        battery_delta = 0.0
        robot_distance = 0.0
        min_coherence = max_coherence = mean_coherence = 0.0
    return {
        "total_ticks": total_ticks,
        "anomaly_count": anomalies,
        "low_battery_alarm_count": low_battery,
        "battery_delta_percent": round(battery_delta, 4),
        "robot_distance_meters": round(robot_distance, 4),
        "coherence": {
            "min": round(min_coherence, 4),
            "max": round(max_coherence, 4),
            "mean": round(mean_coherence, 4),
        },
    }


def run(args: argparse.Namespace) -> int:
    organism = SimulatedOrganism(
        seed=args.seed,
        tick_seconds=args.tick_seconds,
        enable_anomalies=args.enable_anomalies,
        anomaly_rate=args.anomaly_rate,
    )

    output_path: Optional[Path] = None
    output_fp = None
    if args.output_file:
        output_path = Path(args.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_fp = output_path.open("w", encoding="utf-8")

    try:
        for _ in range(args.ticks):
            snapshot = organism.tick()
            line = _snapshot_to_jsonl(snapshot)
            if not args.summary_only:
                print(line, flush=True)
            if output_fp is not None:
                output_fp.write(line + "\n")
            if args.tick_seconds > 0:
                time.sleep(args.tick_seconds)
    finally:
        if output_fp is not None:
            output_fp.close()

    summary = _summary(organism, args.ticks)
    print(json.dumps({"summary": summary}, ensure_ascii=False), flush=True)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
