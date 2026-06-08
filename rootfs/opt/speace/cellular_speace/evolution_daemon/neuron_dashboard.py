"""Neuron/synapse dashboard (port 5697 default).

Endpoints:
  GET /api/health
  GET /api/neurons
  GET /api/synapses
  GET /api/activation_matrix
  GET /
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from flask import Flask, jsonify, request, send_from_directory
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Flask is required: pip install flask>=3.0"
    ) from exc


# --------------------------------------------------------------------------- #
# Bootstrap
# --------------------------------------------------------------------------- #
_start_time = time.time()
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DATA_ROOT = _REPO_ROOT / "data"
_MORPHO_DIR = _DATA_ROOT / "morphological_memory"

_static_folder = str(_REPO_ROOT / "evolution_daemon" / "static_neurons")
_path_for_static = Path(_static_folder)
_path_for_static.mkdir(parents=True, exist_ok=True)
_index_path = _path_for_static / "index.html"
if not _index_path.exists():
    _index_path.write_text(
        """<!doctype html><html><head><title>SPEACE Neuron Dashboard</title></head>
<body><h1>SPEACE Neuron Dashboard (port 5697)</h1>
<ul>
  <li><a href='/api/health'>/api/health</a></li>
  <li><a href='/api/neurons'>/api/neurons</a></li>
  <li><a href='/api/synapses'>/api/synapses</a></li>
  <li><a href='/api/activation_matrix'>/api/activation_matrix</a></li>
</ul></body></html>""",
        encoding="utf-8",
    )

app = Flask(__name__, static_folder=_static_folder, static_url_path="/static")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _read_jsonl(path: Path, limit: Optional[int] = None) -> List[Dict[str, Any]]:
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
                if limit and len(out) >= limit:
                    break
    except OSError:
        return []
    return out


def _latest_snapshot() -> Dict[str, Any]:
    snaps = _read_jsonl(_MORPHO_DIR / "snapshots.jsonl", limit=1)
    return snaps[-1] if snaps else {}


def _activation_matrix(limit: int = 30) -> Dict[str, Any]:
    """Build a (neurons x ticks) matrix from snapshots.

    If no real distribution is available, return a stub.
    """
    snaps = _read_jsonl(_MORPHO_DIR / "snapshots.jsonl", limit=limit)
    if not snaps:
        return {"ticks": [], "series": [], "source": "missing"}
    series: List[List[float]] = []
    for s in snaps:
        dist = s.get("activation_distribution") or []
        series.append([float(x) for x in dist])
    ticks = [int(s.get("tick", i)) for i, s in enumerate(snaps)]
    return {"ticks": ticks, "series": series, "source": "morphological_snapshot"}


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
            "service": "evolution_daemon.neuron_dashboard",
        }
    )


@app.route("/api/neurons")
def neurons() -> Any:
    snap = _latest_snapshot()
    history = _read_jsonl(_MORPHO_DIR / "snapshots.jsonl", limit=50)
    counts = [int(s.get("neuron_count", 0)) for s in history]
    return jsonify(
        {
            "current": {
                "neuron_count": int(snap.get("neuron_count", 0)),
                "active_neuron_count": int(snap.get("active_neuron_count", 0)),
            },
            "history": {
                "neuron_count": [
                    {"tick": s.get("tick", i), "value": int(s.get("neuron_count", 0))}
                    for i, s in enumerate(history)
                ],
                "stats": {
                    "mean": statistics.fmean(counts) if counts else 0.0,
                    "stdev": statistics.pstdev(counts) if len(counts) > 1 else 0.0,
                    "min": min(counts) if counts else 0,
                    "max": max(counts) if counts else 0,
                },
            },
        }
    )


@app.route("/api/synapses")
def synapses() -> Any:
    snap = _latest_snapshot()
    history = _read_jsonl(_MORPHO_DIR / "snapshots.jsonl", limit=50)
    counts = [int(s.get("synapse_count", 0)) for s in history]
    active_counts = [int(s.get("active_synapse_count", 0)) for s in history]
    return jsonify(
        {
            "current": {
                "synapse_count": int(snap.get("synapse_count", 0)),
                "active_synapse_count": int(snap.get("active_synapse_count", 0)),
                "pruned_synapse_count": int(snap.get("pruned_synapse_count", 0)),
            },
            "history": {
                "synapse_count": [
                    {"tick": s.get("tick", i), "value": int(s.get("synapse_count", 0))}
                    for i, s in enumerate(history)
                ],
                "active_synapse_count": [
                    {"tick": s.get("tick", i), "value": int(s.get("active_synapse_count", 0))}
                    for i, s in enumerate(history)
                ],
                "stats": {
                    "mean_total": statistics.fmean(counts) if counts else 0.0,
                    "mean_active": statistics.fmean(active_counts) if active_counts else 0.0,
                },
            },
        }
    )


@app.route("/api/activation_matrix")
def activation_matrix() -> Any:
    try:
        limit = int(request.args.get("limit", 30))
    except ValueError:
        limit = 30
    return jsonify(_activation_matrix(limit=limit))


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
def run_server(host: str = "127.0.0.1", port: int = 5697) -> None:
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5697)
    args = parser.parse_args()
    run_server(args.host, args.port)
