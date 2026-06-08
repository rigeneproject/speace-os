"""Package verifier for SPEACE bootstrap (T115).

Ensures downloaded packages match an allowlist of known-good hashes.
No package is installed without hash verification.
"""

import hashlib
from pathlib import Path
from typing import Dict, List, Optional


class HashAllowlist:
    """Maintains a list of approved commit/package hashes."""

    DEFAULT_ALLOWLIST: Dict[str, List[str]] = {
        "https://github.com/rigeneproject/cellular_speace": [],
    }

    def __init__(self, entries: Optional[Dict[str, List[str]]] = None) -> None:
        src = entries if entries is not None else self.DEFAULT_ALLOWLIST
        self._entries = {k: list(v) for k, v in src.items()}

    def add_hash(self, repo: str, commit_hash: str) -> None:
        """Register an approved hash for a repo."""
        self._entries.setdefault(repo, [])
        if commit_hash not in self._entries[repo]:
            self._entries[repo].append(commit_hash)

    def is_approved(self, repo: str, commit_hash: str) -> bool:
        """Check if a hash is in the allowlist."""
        if repo not in self._entries:
            return False
        # Support both full and short (7-char) hashes
        allowed = self._entries[repo]
        return any(
            commit_hash == h or commit_hash.startswith(h) or h.startswith(commit_hash)
            for h in allowed
        )

    def repo_allowed(self, repo: str) -> bool:
        """Check if a repo URL is in the allowlist."""
        return repo in self._entries


class PackageVerifier:
    """Verifies package integrity via SHA-256 hash."""

    def __init__(self, allowlist: Optional[HashAllowlist] = None) -> None:
        self.allowlist = allowlist or HashAllowlist()

    def compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 of a file."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def compute_bytes_hash(self, data: bytes) -> str:
        """Compute SHA-256 of raw bytes."""
        return hashlib.sha256(data).hexdigest()

    def verify_repo_hash(self, repo: str, commit_hash: str) -> bool:
        """Check if a repo+commit pair is approved."""
        if not self.allowlist.repo_allowed(repo):
            return False
        return self.allowlist.is_approved(repo, commit_hash)

    def verify_file(self, file_path: Path, expected_hash: str) -> bool:
        """Check if a file matches an expected hash."""
        actual = self.compute_file_hash(file_path)
        return actual.lower() == expected_hash.lower()
