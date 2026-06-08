"""SPEACE AGI Team — Entry point to launch the agent management system."""

import sys
import argparse


def main():
    parser = argparse.ArgumentParser(
        description="SPEACE AGI Team — Agentic AI per l'evoluzione di SPEACE verso AGI"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host per il server web")
    parser.add_argument("--port", type=int, default=8686, help="Porta per il server web")
    parser.add_argument("--no-web", action="store_true", help="Modalità solo CLI, senza server web")
    args = parser.parse_args()

    if args.no_web:
        print("Modalità CLI non ancora implementata. Usa --port per il server web.")
        sys.exit(0)

    from speace_agi_team.web_server import run_server
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
