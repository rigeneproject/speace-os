"""SocialCoordinator — cooperation, conflict detection, and mediation proposals (T167).

All proposals are logged and surfaced to the dashboard. No binding commitment
is executed without human approval gate.
"""

import time
import uuid
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.distributed.trust_reputation_model import TrustReputationModel


class SocialCoordinator:
    """Generates cooperation proposals and detects conflicts between nodes."""

    def __init__(self, trust_model: Optional[TrustReputationModel] = None) -> None:
        self._trust = trust_model or TrustReputationModel()
        self._pending_proposals: List[Dict[str, Any]] = []
        self._conflict_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    # Cooperation
    # ------------------------------------------------------------------ #

    def propose_cooperation(
        self,
        node_id: str,
        cooperation_type: str,
        payload: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Generate a cooperation proposal if trust threshold is met."""
        if not self._trust.can_cooperate(node_id):
            return None
        proposal = {
            "proposal_id": f"soc_{uuid.uuid4().hex[:8]}",
            "type": "cooperation",
            "cooperation_type": cooperation_type,
            "target_node": node_id,
            "payload": payload,
            "status": "pending",
            "created_at": time.time(),
        }
        self._pending_proposals.append(proposal)
        return proposal

    # ------------------------------------------------------------------ #
    # Conflict detection
    # ------------------------------------------------------------------ #

    def detect_conflict(
        self,
        node_id: str,
        topic: str,
        local_position: Any,
        remote_position: Any,
    ) -> Optional[Dict[str, Any]]:
        """Detect divergence and generate a mediation proposal."""
        if local_position == remote_position:
            return None
        conflict = {
            "conflict_id": f"conf_{uuid.uuid4().hex[:8]}",
            "node_id": node_id,
            "topic": topic,
            "local_position": local_position,
            "remote_position": remote_position,
            "status": "detected",
            "timestamp": time.time(),
            "mediation_proposed": True,
        }
        self._conflict_log.append(conflict)
        return conflict

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def list_pending_proposals(self) -> List[Dict[str, Any]]:
        return [p for p in self._pending_proposals if p["status"] == "pending"]

    def list_conflicts(self, hours: float = 24.0) -> List[Dict[str, Any]]:
        cutoff = time.time() - (hours * 3600)
        return [c for c in self._conflict_log if c["timestamp"] >= cutoff]

    def snapshot(self) -> Dict[str, Any]:
        return {
            "pending_proposals": self.list_pending_proposals(),
            "recent_conflicts": self.list_conflicts(),
            "trust_snapshot": self._trust.snapshot(),
        }
