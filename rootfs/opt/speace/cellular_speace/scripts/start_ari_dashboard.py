"""Start the SPEACE ARI Dashboard on port 5699 (T169).

Thin wrapper that imports and runs the Flask server in
``speace_core.monitoring.ari_dashboard_server``.

Environment variables:
    SPEACE_ARI_DASHBOARD_HOST   default 127.0.0.1
    SPEACE_ARI_DASHBOARD_PORT   default 5699

Usage:
    python scripts/start_ari_dashboard.py
    python scripts/start_ari_dashboard.py --port 5699
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make repo importable
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from speace_core.monitoring.ari_dashboard_server import run_server  # noqa: E402


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="SPEACE ARI Dashboard launcher")
    parser.add_argument(
        "--host",
        default=os.environ.get("SPEACE_ARI_DASHBOARD_HOST", "127.0.0.1"),
        help="bind address (default 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("SPEACE_ARI_DASHBOARD_PORT", "5699")),
        help="bind port (default 5699)",
    )
    args = parser.parse_args()

    print(f"[ari-dashboard] starting on http://{args.host}:{args.port}")
    print(f"[ari-dashboard] data root: {_REPO_ROOT / 'data'}")
    run_server(host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
