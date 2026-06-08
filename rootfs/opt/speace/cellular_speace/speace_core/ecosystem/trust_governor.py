"""TrustGovernor — T131-C: trust scoring and adversarial detection for ecosystem sources."""

import hashlib
import time
from typing import Any, Dict, List, Optional, Set


class TrustGovernor:
    """Manages trust scores, permissions, rate limits, and sandbox validation.

    T131-C adds:
    - Origin verification (signature/checksum)
    - Sandboxing validation (dangerous payload detection)
    - Permission gates (source capability tracking)
    - Rate limiting per source (sliding window)
    - Identity validation (token checking)

    Rules:
    - New sources start at 0.5
    - Successful observation: +0.05 (capped at 1.0)
    - Timeout / error: -0.1 (floor at 0.0)
    - Trust < 0.2: source auto-deactivated
    """

    _DANGEROUS_PATTERNS: Set[str] = {
        "__import__", "eval(", "exec(", "compile(", "os.system",
        "subprocess.call", "subprocess.Popen", "shell=True",
        "import os", "import subprocess", "import sys",
        "<script>", "javascript:", "onclick=", "onerror=",
    }

    def __init__(
        self,
        success_delta: float = 0.05,
        failure_delta: float = -0.1,
        min_active_trust: float = 0.2,
        rate_limit_window_seconds: float = 60.0,
        rate_limit_max_requests: int = 100,
    ) -> None:
        self.success_delta = success_delta
        self.failure_delta = failure_delta
        self.min_active_trust = min_active_trust
        self.rate_limit_window = rate_limit_window_seconds
        self.rate_limit_max = rate_limit_max_requests
        self._permissions: Dict[str, Set[str]] = {}
        self._identities: Dict[str, str] = {}
        self._rate_log: Dict[str, List[float]] = {}

    def evaluate_observation(self, current_trust: float, status: str) -> float:
        """Return updated trust score after an observation."""
        if status in ("ok",):
            return min(1.0, current_trust + self.success_delta)
        if status in ("timeout", "error", "blocked"):
            return max(0.0, current_trust + self.failure_delta)
        return current_trust

    def should_block(self, trust_score: float) -> bool:
        """True if source should be blocked."""
        return trust_score < self.min_active_trust

    # ------------------------------------------------------------------ #
    # T131-C: Sandboxing
    # ------------------------------------------------------------------ #

    def validate_sandbox(self, payload: Any) -> bool:
        """Return False if payload contains dangerous patterns."""
        text = str(payload).lower()
        for pattern in self._DANGEROUS_PATTERNS:
            if pattern.lower() in text:
                return False
        return True

    # ------------------------------------------------------------------ #
    # T131-C: Origin verification
    # ------------------------------------------------------------------ #

    def verify_origin(self, payload: Any, expected_hash: Optional[str] = None) -> bool:
        """Verify payload integrity via SHA-256 hash if expected_hash provided."""
        if expected_hash is None:
            return True
        text = str(payload)
        actual = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return actual == expected_hash

    # ------------------------------------------------------------------ #
    # T131-C: Permission gates
    # ------------------------------------------------------------------ #

    def grant_permission(self, source_id: str, action: str) -> None:
        """Grant an action permission to a source."""
        self._permissions.setdefault(source_id, set()).add(action)

    def revoke_permission(self, source_id: str, action: str) -> None:
        """Revoke an action permission from a source."""
        self._permissions.get(source_id, set()).discard(action)

    def check_permission(self, source_id: str, action: str) -> bool:
        """Check if a source has permission for an action."""
        return action in self._permissions.get(source_id, set())

    def list_permissions(self, source_id: str) -> List[str]:
        """List all permissions for a source."""
        return list(self._permissions.get(source_id, set()))

    # ------------------------------------------------------------------ #
    # T131-C: Rate limiting
    # ------------------------------------------------------------------ #

    def check_rate(self, source_id: str) -> bool:
        """Return True if source is within rate limit."""
        now = time.time()
        log = self._rate_log.get(source_id, [])
        cutoff = now - self.rate_limit_window
        log = [t for t in log if t > cutoff]
        self._rate_log[source_id] = log
        return len(log) < self.rate_limit_max

    def record_request(self, source_id: str) -> None:
        """Record a request timestamp for rate limiting."""
        self._rate_log.setdefault(source_id, []).append(time.time())

    def rate_status(self, source_id: str) -> Dict[str, Any]:
        """Return current rate limit status for a source."""
        now = time.time()
        log = self._rate_log.get(source_id, [])
        cutoff = now - self.rate_limit_window
        log = [t for t in log if t > cutoff]
        return {
            "window_seconds": self.rate_limit_window,
            "max_requests": self.rate_limit_max,
            "current_requests": len(log),
            "remaining": max(0, self.rate_limit_max - len(log)),
        }

    # ------------------------------------------------------------------ #
    # T131-C: Identity validation
    # ------------------------------------------------------------------ #

    def register_identity(self, source_id: str, token: str) -> None:
        """Register an identity token for a source."""
        self._identities[source_id] = token

    def validate_identity(self, source_id: str, token: str) -> bool:
        """Validate source identity token."""
        return self._identities.get(source_id) == token

    def has_identity(self, source_id: str) -> bool:
        """Check if a source has a registered identity."""
        return source_id in self._identities

    # ------------------------------------------------------------------ #
    # Anomaly detection
    # ------------------------------------------------------------------ #

    def assess_anomaly(self, observations: List[Dict[str, Any]]) -> Optional[str]:
        """Lightweight anomaly detection on observation history.

        Returns: 'spam' | 'manipulation' | 'overload' | None
        """
        if len(observations) < 3:
            return None
        # Detect spam: very high frequency
        times = [obs["timestamp"] for obs in observations]
        diffs = [times[i + 1] - times[i] for i in range(len(times) - 1)]
        avg_interval = sum(diffs) / len(diffs) if diffs else 1.0
        if avg_interval < 1.0:
            return "spam"

        # Detect manipulation: payload size oscillates wildly
        sizes = [len(str(obs.get("raw_payload", {}))) for obs in observations]
        if len(sizes) > 2:
            mean_size = sum(sizes) / len(sizes)
            variance = sum((s - mean_size) ** 2 for s in sizes) / len(sizes)
            if variance > (mean_size ** 2) * 4:
                return "manipulation"

        # Detect overload: too many observations in short window
        if len(observations) > 100:
            window = times[-1] - times[0]
            if window < 60:
                return "overload"

        return None
