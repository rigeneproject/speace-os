"""Continuous organism runtime for SPEACE.

Boots the orchestrator, cellular brain, monitoring bus, memory and
evolution subsystems, then keeps the event loop alive, dumping a
compact health snapshot every N seconds. Designed to run for hours.

Safety:
- No shell execution, no internet, no source mutation.
- All FastAPI/lifespan side effects are bypassed; we drive the runtime
  directly so we do not block on a network port.
- Graceful shutdown on SIGINT / SIGTERM / KeyboardInterrupt.
"""

import asyncio
import json
import logging
import os
import signal
import sys
import time
import traceback
from pathlib import Path

# Make repo root importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator
from speace_core.runtime.continuous_runtime_engine import ContinuousRuntimeEngine


GENOME_PATH = (
    Path(__file__).resolve().parent.parent
    / "speace_core"
    / "dna"
    / "genome"
    / "default_genome.yaml"
)
HEALTH_INTERVAL_S = 10.0
# T137-Phase1 (prop-ch-001): writer cadence for morphology/self_model snapshots
WRITER_INTERVAL_S = 30.0


def _log_event(level: int, msg: str, **fields: object) -> None:
    rec = {"ts": time.time(), "level": logging.getLevelName(level), "msg": msg, **fields}
    print(json.dumps(rec, default=str), flush=True)


async def _safe_snapshot(runtime: ContinuousRuntimeEngine) -> dict:
    """Collect a compact health snapshot, never raising."""
    out: dict = {}
    try:
        out["runtime"] = runtime.snapshot()
    except Exception as exc:  # noqa: BLE001
        out["runtime_error"] = f"{type(exc).__name__}: {exc}"
    try:
        out["health"] = runtime.health_monitor.snapshot()
    except Exception as exc:  # noqa: BLE001
        out["health_error"] = f"{type(exc).__name__}: {exc}"
    try:
        out["checkpoint_count"] = len(
            runtime.checkpoint_manager.list_checkpoints(limit=1000)
        )
    except Exception as exc:  # noqa: BLE001
        out["checkpoint_error"] = f"{type(exc).__name__}: {exc}"
    try:
        out["narrative_events_recent"] = len(
            runtime.narrative_engine.recent(hours=1.0, limit=10000)
        )
    except Exception as exc:  # noqa: BLE001
        out["narrative_error"] = f"{type(exc).__name__}: {exc}"
    return out


async def _module_heartbeat(runtime: ContinuousRuntimeEngine) -> dict:
    """Probe each module: did it respond? Did it record anything recently?"""
    mods: dict = {}
    # Modules that have a snapshot() method
    for attr in (
        "circadian",
        "circadian_validator",
        "memory_auditor",
        "latent_integrator",
        "distributed_sync",
        "degradation_handler",
        "halt_gate",
        "cognitive_homeostasis",
        "organism_state_machine",
        "bt_integration",
        "utility_drive_system",
        "utility_arbitration",
        "goap_integration",
        "social_cognition",
        "trust_reputation",
        "social_coordinator",
        "nursery_orchestrator",
        "linguistic_bridge",
        "game_ai_coordinator",
    ):
        mod = getattr(runtime, attr, None)
        if mod is None:
            mods[attr] = "absent"
            continue
        try:
            snap = mod.snapshot() if hasattr(mod, "snapshot") else "ok"
            mods[attr] = "ok" if snap else "empty"
        except Exception as exc:  # noqa: BLE001
            mods[attr] = f"error: {type(exc).__name__}: {exc}"
    return mods


async def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    _log_event(logging.INFO, "boot_start", genome=str(GENOME_PATH))

    if not GENOME_PATH.exists():
        _log_event(logging.ERROR, "genome_not_found", path=str(GENOME_PATH))
        return 2

    try:
        genome = load_genome(GENOME_PATH)
    except Exception as exc:  # noqa: BLE001
        _log_event(logging.ERROR, "genome_load_failed", error=str(exc))
        return 3

    try:
        orchestrator = CellularBrainOrchestrator.build_mvp(genome)
    except Exception as exc:  # noqa: BLE001
        _log_event(logging.ERROR, "orchestrator_build_failed", error=str(exc))
        traceback.print_exc()
        return 4

    runtime = ContinuousRuntimeEngine(
        orchestrator=orchestrator,
        tick_interval=1.0,
        checkpoint_interval_seconds=300.0,
        awake_duration=600.0,
        sleep_duration=60.0,
    )

    shutdown = asyncio.Event()

    def _signal_handler() -> None:
        _log_event(logging.INFO, "signal_received")
        shutdown.set()

    if sys.platform != "win32":
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, _signal_handler)
        loop.add_signal_handler(signal.SIGTERM, _signal_handler)
    else:
        # Windows: SIGINT only — handled in KeyboardInterrupt
        pass

    try:
        start_result = await runtime.start()
    except Exception as exc:  # noqa: BLE001
        _log_event(logging.ERROR, "runtime_start_failed", error=str(exc))
        traceback.print_exc()
        return 5

    _log_event(
        logging.INFO,
        "boot_complete",
        state=start_result.get("state"),
        recovery=start_result.get("recovery", {}).get("status"),
    )

    tick = 0
    last_full_dump = 0.0
    last_writer = 0.0
    try:
        while not shutdown.is_set():
            await asyncio.sleep(HEALTH_INTERVAL_S)
            tick += 1
            now = time.time()
            snap = await _safe_snapshot(runtime)
            modules = await _module_heartbeat(runtime)
            failed = {k: v for k, v in modules.items() if v != "ok" and v != "empty"}
            _log_event(
                logging.INFO,
                "heartbeat",
                tick=tick,
                runtime_state=snap.get("runtime", {}).get("state"),
                health_score=snap.get("health", {}).get("health_score"),
                consecutive_exceptions=snap.get("health", {}).get("consecutive_exceptions"),
                narrative_events=snap.get("narrative_events_recent"),
                checkpoint_count=snap.get("checkpoint_count"),
                module_failures=len(failed),
                uptime_s=int(now - last_full_dump) if last_full_dump else 0,
            )
            # T137-Phase1 (prop-ch-001): periodic morphology/self_model writer.
            # This closes the false-positive coherence_phi=0 alert by populating
            # data/morphological_memory/snapshots.jsonl and
            # data/self_model/snapshots.jsonl, which OrganismStateCollector
            # reads from (see monitoring/organism_state_collector.py).
            if now - last_writer >= WRITER_INTERVAL_S:
                last_writer = now
                try:
                    from speace_core.monitoring.morphology_writers import write_all

                    runtime_snap = snap.get("runtime") or {}
                    written = write_all(runtime_snap, tick=tick)
                    _log_event(
                        logging.INFO,
                        "morphology_writers_tick",
                        tick=tick,
                        morphology_ok=written.get("morphology"),
                        self_model_ok=written.get("self_model"),
                    )
                except Exception as exc:  # noqa: BLE001
                    _log_event(
                        logging.WARNING,
                        "morphology_writers_failed",
                        tick=tick,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                # T137-Phase1 (prop-ch-003-v2): re-anchor energy drive.
                # The production AutonomousDriveEngine is gated off in the
                # genome, so energy_conservation.current_value was stuck at
                # 0.0 producing urgency=0.84. This rewrites the drive from
                # proxy sensors (cpu/memory derived from runtime.health).
                try:
                    from speace_core.monitoring.energy_drive_rewriter import (
                        reanchor_drives,
                    )

                    rs = reanchor_drives(runtime_snap)
                    _log_event(
                        logging.INFO,
                        "energy_drive_reanchor",
                        tick=tick,
                        engine_ok=rs.get("engine_ok"),
                        ec_current=rs.get("energy_conservation_current"),
                        ec_urgency=rs.get("energy_conservation_urgency"),
                        action=rs.get("action_tendency"),
                    )
                except Exception as exc:  # noqa: BLE001
                    _log_event(
                        logging.WARNING,
                        "energy_drive_reanchor_failed",
                        tick=tick,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                # T137-Phase1 (prop-ch-002-v2): stabilizer telemetry.
                # Diagnostic only: aggregates the last N interventions and
                # emits a hint. No patch to the regulator. Output goes to
                # data/regulation/stabilizer_telemetry.jsonl.
                try:
                    from speace_core.monitoring.stabilizer_telemetry import (
                        emit as emit_stab_telemetry,
                    )

                    telem = emit_stab_telemetry(window=50)
                    _log_event(
                        logging.INFO,
                        "stabilizer_telemetry",
                        tick=tick,
                        window=telem.get("window"),
                        last_window_count=telem.get("last_window_count"),
                        last_window_severity_mean=telem.get("last_window_severity_mean"),
                        chaos_score_proxy=telem.get("chaos_score_proxy"),
                        dominant_pattern=(
                            max(telem.get("counts_by_pattern", {}).items(), key=lambda kv: kv[1])[0]
                            if telem.get("counts_by_pattern")
                            else "none"
                        ),
                    )
                except Exception as exc:  # noqa: BLE001
                    _log_event(
                        logging.WARNING,
                        "stabilizer_telemetry_failed",
                        tick=tick,
                        error=f"{type(exc).__name__}: {exc}",
                    )
            if failed:
                _log_event(
                    logging.WARNING,
                    "module_degraded",
                    failures=failed,
                )
            # Full dump every 5 minutes
            if now - last_full_dump > 300.0:
                last_full_dump = now
                _log_event(
                    logging.INFO,
                    "full_snapshot",
                    snapshot=snap,
                    modules=modules,
                )
    except KeyboardInterrupt:
        _log_event(logging.INFO, "keyboard_interrupt")
    except Exception as exc:  # noqa: BLE001
        _log_event(logging.ERROR, "loop_error", error=str(exc))
        traceback.print_exc()
    finally:
        _log_event(logging.INFO, "halt_requested")
        try:
            await runtime.halt()
        except Exception as exc:  # noqa: BLE001
            _log_event(logging.WARNING, "halt_error", error=str(exc))
        # Wait for loop to exit
        for _ in range(60):
            if runtime._state == "halted":
                break
            await asyncio.sleep(0.5)
        try:
            await runtime.stop()
        except Exception as exc:  # noqa: BLE001
            _log_event(logging.WARNING, "stop_error", error=str(exc))
        _log_event(logging.INFO, "shutdown_complete")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
