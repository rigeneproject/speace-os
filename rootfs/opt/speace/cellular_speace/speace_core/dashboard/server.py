"""SPEACE organismic web dashboard server."""

import time
from pathlib import Path

from speace_core.cli import SPEACE_VERSION

try:
    from flask import Flask, jsonify, request, send_from_directory
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Flask is not installed.\n"
        "Install it with:  pip install \"speace-core[dashboard]\"\n"
        "or:               pip install flask>=3.0"
    ) from exc

from speace_core.dashboard.state_reader import DashboardStateReader

# --------------------------------------------------------------------------- #
# Bootstrap
# --------------------------------------------------------------------------- #
_start_time = time.time()
_state_reader = DashboardStateReader(data_root="data")

# Resolve static folder relative to this file
_static_folder = str(Path(__file__).resolve().parent / "static")
app = Flask(__name__, static_folder=_static_folder, static_url_path="/static")
app.config["JSON_SORT_KEYS"] = False

# --------------------------------------------------------------------------- #
# API — read-only
# --------------------------------------------------------------------------- #


@app.route("/api/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "uptime_seconds": int(time.time() - _start_time),
            "speace_version": SPEACE_VERSION,
        }
    )


@app.route("/api/state")
def state():
    return jsonify(_state_reader.get_current_state())


@app.route("/api/history")
def history():
    metric = request.args.get("metric", "coherence_phi")
    try:
        limit = int(request.args.get("limit", 100))
    except ValueError:
        limit = 100
    return jsonify(_state_reader.get_history(metric=metric, limit=limit))


@app.route("/api/logs")
def logs():
    return jsonify(_state_reader.get_logs(limit=20))


# --------------------------------------------------------------------------- #
# Frontend
# --------------------------------------------------------------------------- #


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    app.run(host=host, port=port)


if __name__ == "__main__":
    run_server()
