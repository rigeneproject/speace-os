"""Start SPEACE runtime programmatically for local testing."""

import asyncio
import json
import logging
import signal
import sys
from pathlib import Path

from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator
from speace_core.runtime.continuous_runtime_engine import ContinuousRuntimeEngine

_logger = logging.getLogger("start_runtime")


async def main():
    genome_path = Path(__file__).resolve().parent.parent / "speace_core" / "dna" / "genome" / "default_genome.yaml"
    genome = load_genome(genome_path)
    orchestrator = CellularBrainOrchestrator.build_mvp(genome)

    # Auto-start VFS index and system assimilation if enabled
    genome_sa = getattr(genome, "system_assimilation", None)
    if genome_sa is not None and getattr(genome_sa, "enable_vfs", False):
        vfs_info = getattr(orchestrator, "_last_vfs_index", None)
        if vfs_info:
            print(json.dumps({"vfs_index": vfs_info}, indent=2, default=str))
            _logger.info("VFS indexed %s entries at startup", vfs_info.get("indexed"))
    if genome_sa is not None and getattr(genome_sa, "enable_assimilation", False):
        assim_info = getattr(orchestrator, "_last_assimilation_report", None)
        if assim_info:
            snap = {
                "hostname": assim_info.system_info.hostname,
                "os": f"{assim_info.system_info.os_platform} {assim_info.system_info.os_release}",
                "admin": assim_info.system_info.is_admin,
                "processes": assim_info.process_count,
                "services": assim_info.service_count,
                "devices": assim_info.device_count,
                "storage": [
                    {"device": d.get("device_id", "unknown") if isinstance(d, dict) else d.device_id,
                     "size_gb": round((d.get("size_bytes", 0) if isinstance(d, dict) else d.size_bytes) / (1024**3), 1),
                     "free_gb": round((d.get("free_bytes", 0) if isinstance(d, dict) else d.free_bytes) / (1024**3), 1)}
                    for d in assim_info.storage_devices
                ],
            }
            print(json.dumps({"system_assimilation": snap}, indent=2, default=str))
            _logger.info("System assimilated: %s processes, %s services", assim_info.process_count, assim_info.service_count)

    runtime = ContinuousRuntimeEngine(orchestrator=orchestrator)
    result = await runtime.start()
    print(json.dumps({"status": "started", "runtime_state": result}, indent=2, default=str))

    shutdown_event = asyncio.Event()

    def _on_signal(*_):
        shutdown_event.set()

    if sys.platform != "win32":
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, _on_signal)
        loop.add_signal_handler(signal.SIGTERM, _on_signal)
    else:
        # Windows: signals are coarse; rely on KeyboardInterrupt
        pass

    tick_counter = 0
    try:
        while not shutdown_event.is_set():
            await asyncio.sleep(5)
            tick_counter += 1
            snap = runtime.snapshot()
            print(json.dumps({"status": "snapshot", "tick": tick_counter, "snapshot": snap}, indent=2, default=str))
    except KeyboardInterrupt:
        print(json.dumps({"status": "shutting_down", "reason": "keyboard_interrupt"}, indent=2))
    finally:
        await runtime.pause()
        print(json.dumps({"status": "paused"}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
