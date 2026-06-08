"""Pairing token system for SPEACE bootstrap (T115).

Simple JWT-like tokens without external dependencies.
Used to authorize connection between SPEACE nodes.
No token = no pairing.
"""

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class PairingToken:
    """Generates and verifies pairing tokens for node-to-node authorization."""

    DEFAULT_BASE_PATH: Path = Path("data/node_identity")
    TOKEN_LOG: str = "pairing_tokens.jsonl"

    def __init__(self, secret: Optional[str] = None, base_path: Optional[Path] = None) -> None:
        self._secret = secret or secrets.token_hex(32)
        self.base_path = base_path or self.DEFAULT_BASE_PATH
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._log_path = self.base_path / self.TOKEN_LOG

    # ------------------------------------------------------------------ #
    # Token lifecycle
    # ------------------------------------------------------------------ #

    def generate(
        self,
        source_node: str,
        target_node: str,
        expiry_hours: int = 24,
    ) -> str:
        """Generate a pairing token.

        Returns a URL-safe base64-encoded token containing:
        - source_node, target_node
        - created_at, expires_at
        - HMAC-SHA256 signature
        """
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=expiry_hours)
        payload = {
            "source_node": source_node,
            "target_node": target_node,
            "created_at": now.isoformat(),
            "expires_at": expires.isoformat(),
        }
        payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
        sig = hmac.new(self._secret.encode(), payload_bytes, hashlib.sha256).hexdigest()[:16]
        # JWT-like format: base64(payload).base64(signature)
        b64_payload = base64.urlsafe_b64encode(payload_bytes).decode().rstrip("=")
        b64_sig = base64.urlsafe_b64encode(sig.encode()).decode().rstrip("=")
        token = f"{b64_payload}.{b64_sig}"
        self._log_token(payload, sig)
        return token

    @staticmethod
    def _b64_decode_pad(s: str) -> bytes:
        padding_needed = 4 - len(s) % 4
        if padding_needed != 4:
            s += "=" * padding_needed
        return base64.urlsafe_b64decode(s.encode())

    def verify(self, token: str, expected_target_node: Optional[str] = None) -> Dict[str, Any]:
        """Verify a pairing token.

        Returns the payload dict if valid, raises ValueError otherwise.
        """
        parts = token.split(".")
        if len(parts) != 2:
            raise ValueError("Malformed token")

        try:
            payload_bytes = self._b64_decode_pad(parts[0])
            sig_bytes = self._b64_decode_pad(parts[1])
        except Exception as exc:
            raise ValueError("Invalid token encoding") from exc

        # Verify signature
        expected_sig = hmac.new(
            self._secret.encode(), payload_bytes, hashlib.sha256
        ).hexdigest()[:16]
        if not hmac.compare_digest(expected_sig.encode(), sig_bytes):
            raise ValueError("Invalid token signature")

        # Parse payload
        payload = json.loads(payload_bytes.decode())

        # Check expiry
        expires_at = datetime.fromisoformat(payload["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            raise ValueError("Token expired")

        # Check target node if specified
        if expected_target_node and payload.get("target_node") != expected_target_node:
            raise ValueError("Token not valid for this node")

        return payload

    # ------------------------------------------------------------------ #
    # Logging
    # ------------------------------------------------------------------ #

    def _log_token(self, payload: Dict[str, Any], signature: str) -> None:
        record = {
            "source_node": payload["source_node"],
            "target_node": payload["target_node"],
            "created_at": payload["created_at"],
            "expires_at": payload["expires_at"],
            "signature_prefix": signature[:8],
        }
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def list_tokens(self) -> list:
        """List all logged pairing tokens."""
        if not self._log_path.exists():
            return []
        tokens = []
        with open(self._log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    tokens.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return tokens
