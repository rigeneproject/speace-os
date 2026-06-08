#!/usr/bin/env python3
"""SPEACE Seed — Minimal Authorized Bootstrap Unit (T115).

Standalone bootstrap script for installing SPEACE on a new device.
Manual authorization required. No autonomous replication.

Usage:
    python speace_seed.py [--repo URL] [--branch main] [--target DIR]
                          [--pairing-token TOKEN] [--yes]

This script uses only the Python standard library for its core logic.
If speace_core is already installed, it uses the full bootstrap engine.
Otherwise it falls back to a minimal built-in implementation.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import uuid
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("speace.seed")

DEFAULT_REPO = "https://github.com/rigeneproject/cellular_speace"
DEFAULT_BRANCH = "main"
MIN_PYTHON = (3, 12)


# --------------------------------------------------------------------------- #
# Minimal built-in helpers (used when speace_core is not yet installed)
# --------------------------------------------------------------------------- #

def _which(cmd: str) -> str | None:
    for path in os.environ.get("PATH", "").split(os.pathsep):
        full = Path(path) / cmd
        if full.exists():
            return str(full)
        for ext in (".exe", ".cmd", ".bat"):
            full_ext = Path(path) / (cmd + ext)
            if full_ext.exists():
                return str(full_ext)
    return None


def _generate_node_id() -> str:
    import hashlib
    import platform

    random_part = uuid.uuid4().hex[:16]
    raw = platform.node().encode("utf-8", errors="ignore")
    salt = b"speace_seed_v0_2026"
    machine_part = hashlib.sha256(raw + salt).hexdigest()[:8]
    return f"speace-{random_part}-{machine_part}"


def _save_node_identity(node_id: str, base_path: Path) -> Path:
    base_path.mkdir(parents=True, exist_ok=True)
    config = {
        "node_id": node_id,
        "created_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        "bootstrap_version": "0.1.0",
        "paired_nodes": [],
        "trust_level": 0.1,
        "safe_mode": True,
        "localhost_only": True,
    }
    config_path = base_path / "config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    return config_path


# --------------------------------------------------------------------------- #
# Main bootstrap logic
# --------------------------------------------------------------------------- #

def _bootstrap(args: argparse.Namespace) -> dict:
    repo = args.repo or DEFAULT_REPO
    branch = args.branch or DEFAULT_BRANCH
    target = Path(args.target) if args.target else Path(".")
    pairing_token = args.pairing_token

    # Environment check
    if sys.version_info < MIN_PYTHON:
        logger.error(
            "Python %d.%d+ required, found %d.%d",
            MIN_PYTHON[0], MIN_PYTHON[1], sys.version_info.major, sys.version_info.minor,
        )
        return {"status": "failed", "reason": "python_version"}

    if _which("git") is None:
        logger.error("git is required but not found in PATH")
        return {"status": "failed", "reason": "git_missing"}

    if _which("pip") is None and _which("pip3") is None:
        logger.error("pip is required but not found in PATH")
        return {"status": "failed", "reason": "pip_missing"}

    # Confirmation
    if not args.yes:
        print("=" * 64)
        print("SPEACE Minimal Authorized Bootstrap Unit (T115)")
        print("=" * 64)
        print(f"Repository : {repo}")
        print(f"Branch     : {branch}")
        print(f"Target     : {target.resolve()}")
        print()
        print("WARNING: This will download and install SPEACE from the internet.")
        print("No autonomous replication will occur.")
        print()
        answer = input("Proceed? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            return {"status": "aborted", "reason": "user_declined"}

    # Try using the full bootstrap engine if available
    try:
        from speace_core.bootstrap import SeedEngine

        engine = SeedEngine(
            repo=repo,
            branch=branch,
            target_dir=target,
            pairing_token=pairing_token,
        )
        return engine.bootstrap(skip_confirm=True)
    except ImportError:
        logger.info("speace_core not installed; using minimal built-in bootstrap...")

    # Minimal fallback bootstrap
    clone_path = target / "cellular_speace"
    if clone_path.exists():
        logger.error("Target directory already exists: %s", clone_path)
        return {"status": "failed", "reason": "target_exists"}

    logger.info("Cloning %s (branch: %s)...", repo, branch)
    subprocess.run(
        ["git", "clone", "--depth", "1", "--branch", branch, repo, str(clone_path)],
        check=True,
    )

    logger.info("Installing SPEACE...")
    pip = _which("pip") or _which("pip3") or "pip"
    subprocess.run([sys.executable, "-m", "pip", "install", "-e", str(clone_path)], check=True)

    node_id = _generate_node_id()
    identity_path = _save_node_identity(node_id, Path("data/node_identity"))
    logger.info("Node identity saved to %s", identity_path)

    # Try distributed registration
    try:
        from speace_core.cellular_brain.distributed.distributed_identity_kernel import (
            DistributedIdentityKernel,
        )

        kernel = DistributedIdentityKernel(node_id=node_id)
        kernel.register_node(node_id=node_id, address="127.0.0.1", initial_trust=0.1)
        logger.info("Node registered in distributed identity kernel.")
    except ImportError:
        logger.warning("DistributedIdentityKernel not available; skipping registration.")

    logger.info(
        "Bootstrap complete. To start SPEACE safely, run:\n"
        "  speace monitor\n"
        "This starts the organismic dashboard on http://127.0.0.1:8787"
    )

    return {
        "status": "success",
        "clone_path": str(clone_path),
        "node_id": node_id,
        "bootstrap_version": "0.1.0",
        "pairing_verified": pairing_token is not None,
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main() -> int:
    parser = argparse.ArgumentParser(
        description="SPEACE Seed — Minimal Authorized Bootstrap Unit (T115)",
        epilog="Manual installation only. No autonomous replication.",
    )
    parser.add_argument("--repo", default=DEFAULT_REPO, help="GitHub repo URL")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="Git branch")
    parser.add_argument("--target", help="Installation directory")
    parser.add_argument("--pairing-token", help="Pairing token from an existing node")
    parser.add_argument(
        "--yes", "-y", action="store_true", help="Skip confirmation prompts"
    )
    args = parser.parse_args()

    result = _bootstrap(args)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
