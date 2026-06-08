#!/usr/bin/env python
"""Start SPEACE Secure Web Gateway (T121/T122/T123/T125).

Usage:
    python scripts/start_web_gateway.py
    python scripts/start_web_gateway.py --port 8000 --host 127.0.0.1
"""

import argparse
import sys

try:
    import uvicorn
except ImportError as exc:  # pragma: no cover
    print("[ERROR] uvicorn is not installed.")
    print("Install with: pip install uvicorn[standard] fastapi")
    sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Start SPEACE Web Gateway")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (dev only)")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
    args = parser.parse_args()

    print(f"[INFO] Starting SPEACE Web Gateway on http://{args.host}:{args.port}")
    print(f"[INFO] Dashboard: http://{args.host}:{args.port}/dashboard")
    print(f"[INFO] Health:    http://{args.host}:{args.port}/health")
    print(f"[INFO] Press Ctrl+C to stop")

    uvicorn.run(
        "speace_core.web_gateway.gateway_api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
