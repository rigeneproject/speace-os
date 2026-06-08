"""EcosystemBoundaryLayer — T131 governance: observed → trusted → assimilated.

Security rules:
- observed: source is only passively monitored (read-only)
- trusted: source has proven stable and validated, but remains external
- assimilated: source is considered part of the SPEACE organism (requires audit)

Transitions are gated by:
- trust score thresholds
- stability audit duration
- semantic validation
- identity drift checks
- human approval for assimilation
"""

import time
from typing import Any, Dict, List, Optional

from speace_core.ecosystem.ecosystem_state import EcosystemSource


class EcosystemBoundaryLayer:
    """Manages boundary state transitions for ecosystem sources."""

    # Thresholds for automatic transitions (observed → trusted)
    TRUSTED_MIN_TRUST = 0.7
    TRUSTED_MIN_OBSERVATIONS = 10
    TRUSTED_MIN_STABLE_HOURS = 24.0

    # Assimilation requires explicit human approval and audits
    ASSIMILATION_REQUIRES_APPROVAL = True

    def __init__(self, data_root: str = "data/ecosystem") -> None:
        self._data_root = data_root
        self._assimilation_approvals: Dict[str, str] = {}  # source_id -> approver
        self._audit_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    # Transition logic
    # ------------------------------------------------------------------ #

    def evaluate_transition(
        self,
        source: EcosystemSource,
        observation_count: int = 0,
        first_seen: float = 0.0,
        audit_results: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Return recommended boundary_status for a source."""
        current = source.boundary_status

        if current == "assimilated":
            # Assimilated sources stay assimilated unless revoked
            if source.trust_score < 0.3:
                return "observed"  # emergency demotion
            return "assimilated"

        if current == "trusted":
            # Trusted → assimilated only with explicit approval + audits
            if source.trust_score < 0.4:
                return "observed"
            if self._can_assimilate(source, audit_results):
                return "assimilated"
            return "trusted"

        # current == "observed"
        if source.trust_score >= self.TRUSTED_MIN_TRUST:
            if observation_count >= self.TRUSTED_MIN_OBSERVATIONS:
                if (time.time() - first_seen) >= (self.TRUSTED_MIN_STABLE_HOURS * 3600):
                    return "trusted"
        return "observed"

    def _can_assimilate(
        self,
        source: EcosystemSource,
        audit_results: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if self.ASSIMILATION_REQUIRES_APPROVAL:
            if source.source_id not in self._assimilation_approvals:
                return False
        if audit_results is None:
            return False
        required_audits = ("stability", "semantic", "trust", "identity_drift", "reversibility")
        for audit in required_audits:
            if not audit_results.get(audit, {}).get("passed", False):
                return False
        return True

    def approve_assimilation(self, source_id: str, approver: str) -> None:
        """Human approval required before a source can be assimilated."""
        self._assimilation_approvals[source_id] = approver
        self._log_audit("assimilation_approved", source_id, {"approver": approver})

    def revoke_assimilation(self, source_id: str, reviewer: str) -> None:
        """Revoke assimilation and demote to observed."""
        self._assimilation_approvals.pop(source_id, None)
        self._log_audit("assimilation_revoked", source_id, {"reviewer": reviewer})

    # ------------------------------------------------------------------ #
    # Audit helpers
    # ------------------------------------------------------------------ #

    def _log_audit(self, event: str, source_id: str, details: Dict[str, Any]) -> None:
        self._audit_log.append({
            "timestamp": time.time(),
            "event": event,
            "source_id": source_id,
            **details,
        })

    def audit_trail(self, source_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if source_id is None:
            return list(self._audit_log)
        return [e for e in self._audit_log if e.get("source_id") == source_id]

    def summary(self) -> Dict[str, Any]:
        counts: Dict[str, int] = {}
        for entry in self._audit_log:
            status = entry.get("event", "unknown")
            counts[status] = counts.get(status, 0) + 1
        return {
            "assimilation_approvals": len(self._assimilation_approvals),
            "audit_events": len(self._audit_log),
            "event_counts": counts,
        }
