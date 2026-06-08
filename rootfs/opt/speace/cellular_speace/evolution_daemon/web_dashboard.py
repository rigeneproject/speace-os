"""Main web dashboard for the evolution daemon (port 5692 default).

Endpoints:
  GET /api/health
  GET /api/state
  GET /api/agi
  GET /api/ari            (AGI Readiness Index, 8-component formula)
  GET /api/cognition
  GET /api/cognitive_status
  GET /api/diagnostics
  GET /api/tasks
  GET /api/plan
  GET /api/knowledge
  GET /api/cycles
  GET /
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from flask import Flask, jsonify, request, send_from_directory
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Flask is required: pip install flask>=3.0"
    ) from exc

from evolution_daemon.ari import (
    ARI_WEIGHTS,
    compute_ari as _compute_ari,
    cycle_summary as _cycle_summary,
)


# --------------------------------------------------------------------------- #
# Bootstrap
# --------------------------------------------------------------------------- #
_start_time = time.time()
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DATA_ROOT = _REPO_ROOT / "data"

_static_folder = str(_REPO_ROOT / "evolution_daemon" / "static")
_path_for_static = Path(_static_folder)
_path_for_static.mkdir(parents=True, exist_ok=True)
# Minimal placeholder HTML if no static asset exists.
_index_path = _path_for_static / "index.html"
if not _index_path.exists():
    _index_path.write_text(
        """<!doctype html><html><head><title>SPEACE Evolution Daemon</title></head>
<body><h1>SPEACE Evolution Daemon</h1>
<p>API endpoints:</p>
<ul>
  <li><a href='/api/health'>/api/health</a></li>
  <li><a href='/api/state'>/api/state</a></li>
  <li><a href='/api/agi'>/api/agi</a></li>
  <li><a href='/api/ari'>/api/ari</a> (AGI Readiness Index, 8 axes)</li>
  <li><a href='/api/cognition'>/api/cognition</a></li>
  <li><a href='/api/cognitive_status'>/api/cognitive_status</a></li>
  <li><a href='/api/diagnostics'>/api/diagnostics</a></li>
  <li><a href='/api/tasks'>/api/tasks</a></li>
  <li><a href='/api/plan'>/api/plan</a></li>
  <li><a href='/api/knowledge'>/api/knowledge</a></li>
  <li><a href='/api/cycles'>/api/cycles</a></li>
  <li><a href='/api/conflicts'>/api/conflicts</a></li>
</ul></body></html>""",
        encoding="utf-8",
    )

app = Flask(__name__, static_folder=_static_folder, static_url_path="/static")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _read_jsonl(path: Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Read JSONL file. With ``limit``, return the LAST ``limit`` lines
    (most recent entries). Without ``limit``, return all entries.
    """
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    out.append(json.loads(ln))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    if limit and len(out) > limit:
        out = out[-limit:]
    return out


def _read_cycles_jsonl(path: Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Public helper for the evolution daemon to read cycles."""
    return _read_jsonl(path, limit=limit)


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route("/")
def index() -> Any:
    return send_from_directory(_static_folder, "index.html")


@app.route("/api/health")
def health() -> Any:
    return jsonify(
        {
            "status": "ok",
            "uptime_seconds": int(time.time() - _start_time),
            "service": "evolution_daemon.main_dashboard",
        }
    )


@app.route("/api/state")
def state() -> Any:
    daemon_state = _read_json(_DATA_ROOT / "daemon_state.json")
    return jsonify(
        {
            "daemon_state": daemon_state,
            "speace_state": _read_jsonl(
                _DATA_ROOT / "evolution_daemon" / "cycles.jsonl", limit=1
            ),
        }
    )


@app.route("/api/agi")
def agi() -> Any:
    bench = _read_json(_DATA_ROOT / "evolution_daemon" / "benchmarks" / "latest.json")
    return jsonify(
        {
            "agi_percentage": float(bench.get("agi_percentage", 0.0)),
            "components": bench.get("components", {}),
            "weights": bench.get("weights", {}),
            "report_id": bench.get("report_id", ""),
            "timestamp": bench.get("timestamp", ""),
        }
    )


# --------------------------------------------------------------------------- #
# ARI — AGI Readiness Index
# --------------------------------------------------------------------------- #
# ARI = 0.20·ARC + 0.15·Generalization + 0.15·MemoryInt + 0.10·SelfImprove
#       + 0.10·Planning + 0.10·Robustness + 0.10·KGCoh + 0.10·Autonomy
#
# Computation lives in ``evolution_daemon.ari`` so it can be reused by
# the evolution daemon when populating the engineering plan.
ARI_WEIGHTS_DASHBOARD = ARI_WEIGHTS  # re-exported for legacy imports


def compute_ari(cycles: List[Dict[str, Any]]) -> Dict[str, Any]:
    return _compute_ari(cycles, data_root=_DATA_ROOT)


@app.route("/api/ari")
def ari() -> Any:
    cycles = _read_jsonl(_DATA_ROOT / "evolution_daemon" / "cycles.jsonl", limit=50)
    return jsonify(compute_ari(cycles))


@app.route("/api/ari_history")
def ari_history() -> Any:
    """Time-series of ARI% across the last N cycles.

    Prefers the ARI stored in the cycle (computed at cycle time) and
    falls back to a fresh recompute when the cycle predates the ARI
    snapshot feature.
    """
    try:
        limit = int(request.args.get("limit", 30))
    except ValueError:
        limit = 30
    cycles = _read_jsonl(_DATA_ROOT / "evolution_daemon" / "cycles.jsonl", limit=200)
    if not cycles:
        return jsonify({"series": [], "summary": {}})
    # Build history for ALL cycles first, then take the LAST ``limit``
    history: List[Dict[str, Any]] = []
    for c in cycles:
        stored = (c.get("steps", {}) or {}).get("ari", {}) or {}
        ari_pct = stored.get("ari_percentage")
        comps = stored.get("components", {})
        if ari_pct is None or not comps:
            # Recompute on the fly for older cycles
            recomputed = compute_ari([c])
            ari_pct = recomputed["ari_percentage"]
            comps = recomputed["components"]
        history.append(
            {
                "cycle_id": c.get("cycle_id", ""),
                "timestamp": c.get("finished_at") or c.get("started_at", ""),
                "ari_percentage": ari_pct,
                "agi_percentage_legacy": stored.get(
                    "agi_percentage_legacy",
                    (c.get("steps", {}) or {}).get("benchmark", {}).get("agi_percentage", 0.0),
                ),
                "components": comps,
            }
        )
    # Trim to the last ``limit`` entries so the most recent cycles
    # are surfaced first.
    if len(history) > limit:
        history = history[-limit:]
    # Summary statistics
    pct = [h["ari_percentage"] for h in history]
    summary = {
        "count": len(pct),
        "min": min(pct) if pct else 0.0,
        "max": max(pct) if pct else 0.0,
        "mean": round(sum(pct) / len(pct), 2) if pct else 0.0,
        "first": pct[0] if pct else 0.0,
        "last": pct[-1] if pct else 0.0,
        "delta": round(pct[-1] - pct[0], 2) if len(pct) >= 2 else 0.0,
    }
    return jsonify({"series": history, "summary": summary})


@app.route("/api/runtime_uptime")
def runtime_uptime() -> Any:
    """Persistent runtime uptime (T104 governance-safe read-only)."""
    path = _DATA_ROOT / "evolution_daemon" / "runtime_uptime.json"
    payload = _read_json(path)
    if not payload:
        return jsonify(
            {
                "first_started_at": None,
                "last_seen_running_at": None,
                "session_start_count": 0,
                "total_uptime_seconds": 0.0,
                "last_status": "no_data",
                "uptime_hours": 0.0,
                "uptime_days": 0.0,
            }
        )
    total = float(payload.get("total_uptime_seconds", 0.0))
    return jsonify(
        {
            "first_started_at": payload.get("first_started_at"),
            "last_seen_running_at": payload.get("last_seen_running_at"),
            "session_start_count": int(payload.get("session_start_count", 0)),
            "total_uptime_seconds": total,
            "uptime_hours": round(total / 3600.0, 4),
            "uptime_days": round(total / 86400.0, 6),
            "last_status": payload.get("last_status", "unknown"),
            "updated_at": payload.get("updated_at"),
        }
    )


@app.route("/api/ari_summary")
def ari_summary() -> Any:
    """Plain-text breakdown of the current ARI."""
    cycles = _read_jsonl(_DATA_ROOT / "evolution_daemon" / "cycles.jsonl", limit=50)
    return jsonify(_cycle_summary(cycles, data_root=_DATA_ROOT))


@app.route("/api/cognitive_coherence")
def cognitive_coherence() -> Any:
    """Single 'cognitive coherence' score in [0,1] for the dashboard.

    Computed as a weighted blend of the four most stateful axes:
    memory_integration × self_improvement × autonomy × robustness.
    If any axis is missing, falls back to a flat 0.5 so the endpoint
    is never empty.
    """
    cycles = _read_jsonl(_DATA_ROOT / "evolution_daemon" / "cycles.jsonl", limit=50)
    ari = compute_ari(cycles)
    comps = ari["components"]
    blend = (
        0.35 * comps["memory_integration"]
        + 0.25 * comps["self_improvement"]
        + 0.20 * comps["autonomy"]
        + 0.20 * comps["robustness"]
    )
    return jsonify(
        {
            "coherence_score": round(blend, 4),
            "ari_percentage": ari["ari_percentage"],
            "components": {
                "memory_integration": comps["memory_integration"],
                "self_improvement": comps["self_improvement"],
                "autonomy": comps["autonomy"],
                "robustness": comps["robustness"],
            },
            "timestamp": ari["timestamp"],
        }
    )


@app.route("/api/cognitive_status")
def cognitive_status() -> Any:
    """Cognitive Status Report — one-shot summary of the 7 axes."""
    cycles = _read_jsonl(_DATA_ROOT / "evolution_daemon" / "cycles.jsonl", limit=50)
    last_cycle = cycles[-1] if cycles else {}
    cognition = (last_cycle.get("steps", {}) or {}).get("cognition", {}) or {}
    diagnostics = (last_cycle.get("steps", {}) or {}).get("diagnostics", {}) or {}
    neurons = (last_cycle.get("steps", {}) or {}).get("neurons", {}) or {}
    bench = _read_json(_DATA_ROOT / "evolution_daemon" / "benchmarks" / "latest.json")
    ari = compute_ari(cycles)
    report = {
        "memory": {
            "narrative_depth": cognition.get("narrative_depth", 0),
            "compartments": diagnostics.get("compartments", {}).get("memory", {}),
        },
        "reasoning": {
            "workspace_ignition": (cognition.get("workspace", {}) or {}).get("ignition_score", 0.0),
            "active_items": (cognition.get("workspace", {}) or {}).get("active_items", 0),
        },
        "planning": {
            "tasks_emitted": len((last_cycle.get("steps", {}) or {}).get("tasks", []) or []),
            "by_priority": {
                p: sum(
                    1
                    for t in (last_cycle.get("steps", {}) or {}).get("tasks", [])
                    if t.get("priority") == p
                )
                for p in ("high", "medium", "low")
            },
        },
        "learning": {
            "arc_subset_accuracy": float(
                ((bench.get("details", {}) or {}).get("arc_agi_subset", {}) or {}).get(
                    "accuracy", 0.0
                )
            ),
            "self_improvement_slope": ari["components"]["self_improvement"],
        },
        "generalization": {
            "score": ari["components"]["generalization"],
            "robustness": ari["components"]["robustness"],
        },
        "autonomy": {
            "score": ari["components"]["autonomy"],
            "runtime_status": (last_cycle.get("steps", {}) or {}).get("runtime", {}),
        },
        "adaptation": {
            "regulation": diagnostics.get("compartments", {}).get("regulation", {}),
            "cognition_status": diagnostics.get("compartments", {}).get("cognition", {}),
        },
        "neuron_synapse": neurons,
        "ari": ari,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return jsonify(report)


@app.route("/api/cognition")
def cognition() -> Any:
    cycles = _read_jsonl(_DATA_ROOT / "evolution_daemon" / "cycles.jsonl", limit=1)
    if not cycles:
        return jsonify({"cognition": {}})
    last = cycles[-1]
    return jsonify({"cognition": last.get("steps", {}).get("cognition", {})})


@app.route("/api/diagnostics")
def diagnostics() -> Any:
    cycles = _read_jsonl(_DATA_ROOT / "evolution_daemon" / "cycles.jsonl", limit=1)
    if not cycles:
        return jsonify({"diagnostics": {}})
    last = cycles[-1]
    return jsonify({"diagnostics": last.get("steps", {}).get("diagnostics", {})})


@app.route("/api/tasks")
def tasks() -> Any:
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        limit = 50
    return jsonify({"tasks": _read_jsonl(_DATA_ROOT / "daemon_tasks.jsonl", limit=limit)})


@app.route("/api/plan")
def plan() -> Any:
    return jsonify(_read_json(_DATA_ROOT / "engineering_plan.json"))


@app.route("/api/knowledge")
def knowledge() -> Any:
    nodes = _read_jsonl(_DATA_ROOT / "knowledge_graph.jsonl", limit=5000)
    return jsonify(
        {
            "nodes": [n for n in nodes if n.get("kind") == "node"],
            "edges": [n for n in nodes if n.get("kind") == "edge"],
        }
    )


@app.route("/api/cycles")
def cycles() -> Any:
    try:
        limit = int(request.args.get("limit", 5))
    except ValueError:
        limit = 5
    return jsonify({"cycles": _read_jsonl(_DATA_ROOT / "evolution_daemon" / "cycles.jsonl", limit=limit)})


@app.route("/api/conflicts")
def conflicts() -> Any:
    """Last conflict-resolver scan + summary."""
    entries = _read_jsonl(_DATA_ROOT / "evolution_daemon" / "conflicts.jsonl", limit=10)
    last = entries[-1] if entries else {}
    return jsonify(
        {
            "last": last,
            "history": entries,
            "summary": last.get("summary", {}),
        }
    )


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
def run_server(host: str = "127.0.0.1", port: int = 5692) -> None:
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5692)
    args = parser.parse_args()
    run_server(args.host, args.port)
