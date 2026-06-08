"""Node identity manager for SPEACE bootstrap (T115).

Generates unique, persistent node identities. No two nodes share
the same identity. Machine-bound but privacy-preserving.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class NodeIdentityManager:
    """Manages creation and persistence of a SPEACE node identity."""

    DEFAULT_BASE_PATH: Path = Path("data/node_identity")
    CONFIG_FILE: str = "config.json"

    def __init__(self, base_path: Optional[Path] = None) -> None:
        self.base_path = base_path or self.DEFAULT_BASE_PATH
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._config_path = self.base_path / self.CONFIG_FILE

    # ------------------------------------------------------------------ #
    # Identity generation
    # ------------------------------------------------------------------ #

    def generate_node_id(self) -> str:
        """Generate a unique node identifier.

        Combines a random UUID4 with a partial machine-bound hash
        to ensure uniqueness while preserving privacy.
        """
        random_part = uuid.uuid4().hex[:16]
        machine_part = self._machine_fingerprint()[:8]
        return f"speace-{random_part}-{machine_part}"

    def _machine_fingerprint(self) -> str:
        """Create a privacy-preserving machine fingerprint.

        Uses platform node name hashed with a fixed salt.
        The raw name is never stored; only the hash is used.
        """
        import hashlib
        import platform

        raw = platform.node().encode("utf-8", errors="ignore")
        salt = b"speace_seed_v0_2026"
        return hashlib.sha256(raw + salt).hexdigest()[:16]

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def load(self) -> Optional[Dict[str, Any]]:
        """Load existing node identity config."""
        if not self._config_path.exists():
            return None
        with open(self._config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save(
        self,
        node_id: str,
        bootstrap_version: str,
        paired_nodes: Optional[list] = None,
        trust_level: float = 0.1,
    ) -> Dict[str, Any]:
        """Save node identity config."""
        config = {
            "node_id": node_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "bootstrap_version": bootstrap_version,
            "paired_nodes": paired_nodes or [],
            "trust_level": trust_level,
            "safe_mode": True,
            "localhost_only": True,
        }
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return config

    def ensure_identity(self, bootstrap_version: str = "0.1.0") -> Dict[str, Any]:
        """Load or create a node identity."""
        existing = self.load()
        if existing is not None:
            return existing
        node_id = self.generate_node_id()
        return self.save(node_id, bootstrap_version)
