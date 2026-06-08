"""SPEACE Seed Engine — Minimal Authorized Bootstrap Unit (T115).

Orchestrates the safe installation of SPEACE on a new device.
Manual authorization required. No autonomous replication.
"""

import json
import logging
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from speace_core.bootstrap.node_identity import NodeIdentityManager
from speace_core.bootstrap.pairing_token import PairingToken
from speace_core.bootstrap.verifier import HashAllowlist, PackageVerifier

logger = logging.getLogger("speace.seed")


class SeedEngine:
    """Bootstraps a new SPEACE node from a minimal seed."""

    DEFAULT_REPO: str = "https://github.com/rigeneproject/cellular_speace"
    DEFAULT_BRANCH: str = "main"
    MIN_PYTHON_VERSION: tuple = (3, 12)

    def __init__(
        self,
        repo: Optional[str] = None,
        branch: str = DEFAULT_BRANCH,
        target_dir: Optional[Path] = None,
        pairing_token: Optional[str] = None,
        allowlist: Optional[HashAllowlist] = None,
    ) -> None:
        self.repo = repo or self.DEFAULT_REPO
        self.branch = branch
        self.target_dir = target_dir or Path(".")
        self.pairing_token_str = pairing_token
        self.allowlist = allowlist or HashAllowlist()
        self.verifier = PackageVerifier(self.allowlist)
        self.identity_manager = NodeIdentityManager()
        self.token_engine = PairingToken()
        self._bootstrap_version: str = "0.1.0"

    # ------------------------------------------------------------------ #
    # Environment checks
    # ------------------------------------------------------------------ #

    def verify_environment(self) -> Dict[str, Any]:
        """Check prerequisites: Python version, git, pip."""
        errors: List[str] = []
        warnings: List[str] = []

        # Python version
        if sys.version_info < self.MIN_PYTHON_VERSION:
            errors.append(
                f"Python {self.MIN_PYTHON_VERSION[0]}.{self.MIN_PYTHON_VERSION[1]}+ required, "
                f"found {sys.version_info.major}.{sys.version_info.minor}"
            )

        # git
        git_path = self._which("git")
        if git_path is None:
            errors.append("git is required but not found in PATH")

        # pip
        pip_path = self._which("pip") or self._which("pip3")
        if pip_path is None:
            errors.append("pip is required but not found in PATH")

        return {
            "ok": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "git_path": git_path,
            "pip_path": pip_path,
        }

    @staticmethod
    def _which(cmd: str) -> Optional[str]:
        """Cross-platform `which`."""
        for path in os.environ.get("PATH", "").split(os.pathsep):
            full = Path(path) / cmd
            if full.exists():
                return str(full)
            # Windows
            for ext in (".exe", ".cmd", ".bat"):
                full_ext = Path(path) / (cmd + ext)
                if full_ext.exists():
                    return str(full_ext)
        return None

    # ------------------------------------------------------------------ #
    # Download
    # ------------------------------------------------------------------ #

    def download_repo(self) -> Path:
        """Clone the SPEACE repo into target_dir.

        Returns the path to the cloned directory.
        """
        if not self.allowlist.repo_allowed(self.repo):
            raise RuntimeError(
                f"Repo '{self.repo}' is not in the allowlist. "
                "Only authorized repositories may be used."
            )

        clone_path = self.target_dir / "cellular_speace"
        if clone_path.exists():
            raise RuntimeError(f"Target directory already exists: {clone_path}")

        logger.info("Cloning %s (branch: %s) into %s", self.repo, self.branch, clone_path)
        subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", self.branch, self.repo, str(clone_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        return clone_path

    def get_commit_hash(self, clone_path: Path) -> str:
        """Read the current commit hash from the cloned repo."""
        result = subprocess.run(
            ["git", "-C", str(clone_path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    # ------------------------------------------------------------------ #
    # Verification
    # ------------------------------------------------------------------ #

    def verify_package(self, clone_path: Path) -> bool:
        """Verify the cloned package against the hash allowlist.

        If the allowlist is empty for this repo, logs a warning but
        allows installation (first-time bootstrap scenario).
        """
        commit_hash = self.get_commit_hash(clone_path)
        approved_hashes = self.allowlist._entries.get(self.repo, [])
        if not approved_hashes:
            logger.warning(
                "No approved hashes in allowlist for %s. "
                "Commit %s will be trusted on first bootstrap.",
                self.repo,
                commit_hash,
            )
            # Auto-approve this hash for future verification
            self.allowlist.add_hash(self.repo, commit_hash)
            return True

        if self.verifier.verify_repo_hash(self.repo, commit_hash):
            logger.info("Commit %s verified against allowlist.", commit_hash)
            return True

        raise RuntimeError(
            f"Hash verification failed for commit {commit_hash}. "
            "The package may have been tampered with. Aborting."
        )

    # ------------------------------------------------------------------ #
    # Installation
    # ------------------------------------------------------------------ #

    def install_dependencies(self, clone_path: Path) -> None:
        """Install SPEACE in editable mode."""
        pip = self._which("pip") or self._which("pip3") or "pip"
        logger.info("Installing SPEACE from %s...", clone_path)
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", str(clone_path)],
            check=True,
        )

    # ------------------------------------------------------------------ #
    # Identity
    # ------------------------------------------------------------------ #

    def generate_node_identity(self) -> Dict[str, Any]:
        """Create or load node identity."""
        identity = self.identity_manager.ensure_identity(
            bootstrap_version=self._bootstrap_version
        )
        logger.info("Node identity: %s", identity["node_id"])
        return identity

    def register_in_distributed_kernel(self, identity: Dict[str, Any]) -> None:
        """Register the new node in the distributed identity kernel."""
        try:
            from speace_core.cellular_brain.distributed.distributed_identity_kernel import (
                DistributedIdentityKernel,
            )

            kernel = DistributedIdentityKernel(node_id=identity["node_id"])
            # Self-register with low initial trust
            kernel.register_node(
                node_id=identity["node_id"],
                address="127.0.0.1",  # safe default
                initial_trust=identity.get("trust_level", 0.1),
            )
            logger.info("Node registered in distributed identity kernel.")
        except ImportError:
            logger.warning("DistributedIdentityKernel not available; skipping registration.")

    # ------------------------------------------------------------------ #
    # Pairing
    # ------------------------------------------------------------------ #

    def verify_pairing_token(self, identity: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Verify an external pairing token if provided."""
        if not self.pairing_token_str:
            return None
        try:
            payload = self.token_engine.verify(
                self.pairing_token_str, expected_target_node=identity["node_id"]
            )
            logger.info("Pairing token verified for source node %s", payload["source_node"])
            return payload
        except ValueError as exc:
            logger.error("Pairing token verification failed: %s", exc)
            raise RuntimeError(f"Invalid pairing token: {exc}") from exc

    def generate_pairing_token(self, identity: Dict[str, Any], target_node: str) -> str:
        """Generate a pairing token to share with another node."""
        token = self.token_engine.generate(
            source_node=identity["node_id"],
            target_node=target_node,
            expiry_hours=24,
        )
        logger.info("Generated pairing token for target %s", target_node)
        return token

    # ------------------------------------------------------------------ #
    # Launch
    # ------------------------------------------------------------------ #

    def launch_safe_mode(self) -> None:
        """Start SPEACE in safe mode (monitoring only, localhost)."""
        logger.info("Launching SPEACE in safe mode...")
        # Safe mode = speace monitor (no runtime, no autonomous actions)
        # We do not auto-launch here; we just log instructions.
        # The user should run `speace monitor` manually.
        logger.info(
            "Bootstrap complete. To start SPEACE safely, run:\n"
            "  speace monitor\n"
            "This starts the organismic dashboard on http://127.0.0.1:8787"
        )

    # ------------------------------------------------------------------ #
    # Orchestration
    # ------------------------------------------------------------------ #

    def bootstrap(self, skip_confirm: bool = False) -> Dict[str, Any]:
        """Run the full bootstrap pipeline.

        Returns a summary dict with all generated artifacts.
        """
        # Environment
        env = self.verify_environment()
        if not env["ok"]:
            return {"status": "failed", "stage": "environment", "errors": env["errors"]}

        # Confirm
        if not skip_confirm:
            print("=" * 64)
            print("SPEACE Minimal Authorized Bootstrap Unit (T115)")
            print("=" * 64)
            print(f"Repository : {self.repo}")
            print(f"Branch     : {self.branch}")
            print(f"Target     : {self.target_dir.resolve()}")
            print(f"Pairing    : {'Yes' if self.pairing_token_str else 'No'}")
            print()
            print("WARNING: This will download and install SPEACE from the internet.")
            print("No autonomous replication will occur.")
            print()
            answer = input("Proceed? [y/N]: ").strip().lower()
            if answer not in ("y", "yes"):
                return {"status": "aborted", "reason": "user_declined"}

        # Download
        clone_path = self.download_repo()

        # Verify
        self.verify_package(clone_path)

        # Install
        self.install_dependencies(clone_path)

        # Identity
        identity = self.generate_node_identity()

        # Pairing
        pairing_info = self.verify_pairing_token(identity)

        # Distributed registration
        self.register_in_distributed_kernel(identity)

        # Safe mode launch instructions
        self.launch_safe_mode()

        return {
            "status": "success",
            "clone_path": str(clone_path),
            "node_id": identity["node_id"],
            "bootstrap_version": self._bootstrap_version,
            "pairing_verified": pairing_info is not None,
        }
