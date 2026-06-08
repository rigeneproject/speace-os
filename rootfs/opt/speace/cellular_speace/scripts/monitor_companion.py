"""Lightweight monitoring companion for the continuous runtime.

This is a separate process that reads the runtime state by:
1. Discovering the running python process and watching it
2. Serving a tiny HTTP endpoint on port 8001 with runtime vitals

It does NOT touch the runtime — pure observer. Safe to run in
parallel with continuous_organism.py.
"""

import json
import os
import sys
import time
from pathlib import Path

# Make repo importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from fastapi import FastAPI
    import uvicorn
except ImportError:
    print("[ERROR] fastapi/uvicorn not installed. Skipping companion.", flush=True)
    sys.exit(0)


DATA_ROOT = Path("data")


def _latest_jsonl(path: Path) -> dict:
    """Read last line of a JSONL file and return it as a dict, or empty dict."""
    try:
        if not path.exists():
            return {}
        # Read last 8KB to get the most recent record
        size = path.stat().st_size
        with path.open("rb") as f:
            f.seek(max(0, size - 8192))
            chunk = f.read().decode("utf-8", errors="replace")
        last = [ln for ln in chunk.splitlines() if ln.strip()][-1] if chunk else ""
        if not last:
            return {}
        return json.loads(last)
    except Exception:
        return {}


app = FastAPI(title="SPEACE Runtime Monitor", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "ts": time.time()}


@app.get("/runtime/snapshot")
def runtime_snapshot() -> dict:
    """Return latest cached runtime state from data/ JSONL files.

    This is a *companion* snapshot — the full live state is inside the
    ContinuousRuntimeEngine process. We expose a best-effort view
    from on-disk artifacts (narrative, audit, etc.) plus process
    health inferred from data timestamps.
    """
    out: dict = {"ts": time.time()}

    # Latest narrative event
    narrative_dir = DATA_ROOT / "narrative"
    latest_event = {}
    if narrative_dir.exists():
        for p in narrative_dir.glob("*.jsonl"):
            rec = _latest_jsonl(p)
            if rec and rec.get("timestamp", 0) > latest_event.get("timestamp", 0):
                latest_event = rec
    out["latest_narrative_event"] = latest_event

    # Memory audit latest
    out["memory_audit"] = _latest_jsonl(DATA_ROOT / "runtime" / "memory_leak_audit.jsonl")

    # Checkpoint count
    cp_dir = Path("data/runtime/checkpoints")
    if cp_dir.exists():
        cps = sorted(cp_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        out["checkpoint_count"] = len(cps)
        out["latest_checkpoint"] = str(cps[0]) if cps else None
        out["latest_checkpoint_mtime"] = cps[0].stat().st_mtime if cps else None
    else:
        out["checkpoint_count"] = 0
        out["latest_checkpoint"] = None
        out["latest_checkpoint_mtime"] = None

    # Latest runtime snapshot
    snap_path = Path("data/runtime/latest_snapshot.json")
    if snap_path.exists():
        try:
            out["latest_snapshot_mtime"] = snap_path.stat().st_mtime
            out["latest_snapshot_size"] = snap_path.stat().st_size
        except Exception:
            pass

    # Find the runtime process
    try:
        import psutil
        procs = []
        for proc in psutil.process_iter(["pid", "name", "cmdline", "create_time", "memory_info"]):
            try:
                cmd = " ".join(proc.info.get("cmdline") or [])
                if "continuous_organism" in cmd and "monitor_companion" not in cmd:
                    procs.append({
                        "pid": proc.info["pid"],
                        "uptime_s": int(time.time() - proc.info["create_time"]),
                        "rss_mb": round(proc.info["memory_info"].rss / (1024 * 1024), 1),
                        "cmd_short": cmd[:200],
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        out["runtime_processes"] = procs
    except ImportError:
        out["runtime_processes"] = "psutil_unavailable"

    return out


@app.get("/runtime/processes")
def runtime_processes() -> dict:
    """List all python processes with CPU and memory."""
    try:
        import psutil
        procs = []
        for proc in psutil.process_iter(
            ["pid", "name", "cmdline", "cpu_percent", "memory_info", "create_time"]
        ):
            try:
                if proc.info["name"] and "python" in proc.info["name"].lower():
                    procs.append({
                        "pid": proc.info["pid"],
                        "uptime_s": int(time.time() - proc.info["create_time"]),
                        "cpu_pct": proc.info["cpu_percent"],
                        "rss_mb": round(proc.info["memory_info"].rss / (1024 * 1024), 1),
                        "cmd_short": " ".join(proc.info["cmdline"] or [])[:200],
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return {"processes": procs, "ts": time.time()}
    except ImportError:
        return {"processes": [], "ts": time.time(), "error": "psutil_unavailable"}


if __name__ == "__main__":
    port = int(os.environ.get("SPEACE_COMPANION_PORT", "8001"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
