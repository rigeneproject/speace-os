"""DistributedOrganismController — Phase 4: distributed mature organism foundation.

Provides observational coordination of multiple physical nodes as a single
organism.  All distributed physical actions are blocked by default; the
controller only plans, observes, and logs.  Execution requires multi-node
consensus + human_review approval.

This module is intentionally conservative: it builds the architectural
scaffolding for a distributed body without ever performing autonomous
distributed physical actuation.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.embodiment.body_registry import BodyRegistry
from speace_core.cellular_brain.memory.morphology_events import (
    MorphologyEvent,
    MorphologyEventType,
)


try:
    from speace_core.cellular_brain.action_governance.action_governance_models import (
        ExternalActionProposal,
        ExternalActionType,
    )
    from speace_core.cellular_brain.action_governance.action_policy_engine import (
        ActionPolicyEngine,
    )
    from speace_core.cellular_brain.action_governance.action_risk_classifier import (
        ActionRiskClassifier,
    )
    from speace_core.cellular_brain.action_governance.reversibility_analyzer import (
        ReversibilityAnalyzer,
    )

    _GOVERNANCE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _GOVERNANCE_AVAILABLE = False


class DistributedOrganismController:
    """Observational controller for a distributed physical organism.

    Maintains a :class:`BodyRegistry` of nodes, collects their sensorimotor
    state, and plans (but does not autonomously execute) coordinated actions.
    """

    # Physical actions that are NEVER executed autonomously
    DISTRIBUTED_PHYSICAL_ACTIONS = {
        "coordinated_move",
        "coordinated_speak",
        "coordinated_light",
        "coordinated_notify",
    }

    def __init__(
        self,
        data_root: str = "data/embodiment/distributed_organism",
        body_registry: Optional[BodyRegistry] = None,
        consensus_threshold: float = 0.66,
    ) -> None:
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._audit_path = self._data_root / "distributed_organism_audit.jsonl"
        self._proposals_path = self._data_root / "distributed_proposals.jsonl"

        self._registry = body_registry or BodyRegistry()
        self._consensus_threshold = consensus_threshold

        self._proposals: Dict[str, Dict[str, Any]] = {}
        self._history: List[Dict[str, Any]] = []

        if _GOVERNANCE_AVAILABLE:
            self._risk_classifier = ActionRiskClassifier()
            self._reversibility_analyzer = ReversibilityAnalyzer()
            self._policy_engine = ActionPolicyEngine()
        else:
            self._risk_classifier = None
            self._reversibility_analyzer = None
            self._policy_engine = None

    # ------------------------------------------------------------------ #
    # Node management
    # ------------------------------------------------------------------ #

    def register_node(
        self,
        node_id: str,
        node_type: str,
        capabilities: Dict[str, List[str]],
        health_score: float = 1.0,
    ) -> None:
        """Register a new node in the distributed organism."""
        self._registry.register_body(
            body_id=node_id,
            body_type=node_type,
            connection_string="distributed://" + node_id,
            capabilities=capabilities,
        )
        self._registry.update_health(node_id, health_score)
        self._log(
            MorphologyEventType.ACTION_EXECUTED,
            f"register_{node_id}",
            {"event": "node_registered", "node_id": node_id, "node_type": node_type},
        )

    def unregister_node(self, node_id: str) -> bool:
        """Remove a node from the distributed organism."""
        result = self._registry.unregister_body(node_id)
        if result:
            self._log(
                MorphologyEventType.ACTION_EXECUTED,
                f"unregister_{node_id}",
                {"event": "node_unregistered", "node_id": node_id},
            )
        return result

    def list_nodes(self) -> List[Dict[str, Any]]:
        """Return all registered nodes."""
        return self._registry.list_all()

    # ------------------------------------------------------------------ #
    # Observational coordination
    # ------------------------------------------------------------------ #

    def observe_distributed_state(self) -> Dict[str, Any]:
        """Collect current sensorimotor state from all registered nodes.

        In a fully-deployed system this would query each node over the
        network.  Here we aggregate the local registry and return a snapshot.
        """
        nodes = self.list_nodes()
        total_health = sum(n.get("health_score", 0.0) for n in nodes)
        avg_health = total_health / len(nodes) if nodes else 0.0

        sensor_counts: Dict[str, int] = {}
        actuator_counts: Dict[str, int] = {}
        for node in nodes:
            caps = node.get("capabilities", {})
            for sensor in caps.get("sensors", []):
                sensor_counts[sensor] = sensor_counts.get(sensor, 0) + 1
            for actuator in caps.get("actuators", []):
                actuator_counts[actuator] = actuator_counts.get(actuator, 0) + 1

        state = {
            "timestamp": time.time(),
            "node_count": len(nodes),
            "average_health": round(avg_health, 4),
            "nodes": [
                {
                    "node_id": n["body_id"],
                    "node_type": n["body_type"],
                    "health_score": n.get("health_score", 0.0),
                    "last_active": n.get("last_active"),
                }
                for n in nodes
            ],
            "sensor_inventory": sensor_counts,
            "actuator_inventory": actuator_counts,
        }
        self._log(
            MorphologyEventType.ACTION_EXECUTED,
            f"obs_{uuid.uuid4().hex[:8]}",
            {"event": "distributed_state_observed", "node_count": len(nodes)},
        )
        return state

    # ------------------------------------------------------------------ #
    # Distributed action planning (blocked by default)
    # ------------------------------------------------------------------ #

    def propose_distributed_action(
        self,
        action_plan: Dict[str, Any],
    ) -> str:
        """Propose a coordinated action across multiple nodes.

        The action is logged and returned as a proposal, but it is **blocked**
        from autonomous execution.  Human review is always required.
        """
        proposal_id = f"dist_{uuid.uuid4().hex[:8]}"
        action_type = action_plan.get("action_type", "unknown")

        # Build governance proposal
        if _GOVERNANCE_AVAILABLE and self._policy_engine is not None:
            ext = ExternalActionProposal(
                proposal_id=proposal_id,
                action_type=ExternalActionType.RESOURCE_SHIFT_SIMULATED,
                title=f"Distributed action: {action_type}",
                description="Coordinated multi-node physical action",
                simulated_only=False,
                requested_real_execution=True,
                estimated_risk=0.8,
                estimated_urgency=0.3,
                estimated_benefit=0.3,
                uncertainty_score=0.3,
                metadata={"action_plan": action_plan},
            )
            risk = self._risk_classifier.classify_action_risk(ext)
            rev = self._reversibility_analyzer.assess_reversibility(ext)
            decision = self._policy_engine.evaluate_action_proposal(ext, risk, rev)

            proposal: Dict[str, Any] = {
                "proposal_id": proposal_id,
                "action_type": action_type,
                "action_plan": action_plan,
                "status": "blocked",
                "governance_decision": decision.model_dump(),
                "consensus": None,
                "timestamp": time.time(),
            }
            self._proposals[proposal_id] = proposal
            self._persist_proposal(proposal)
            self._log(
                MorphologyEventType.ACTION_BLOCKED,
                proposal_id,
                {
                    "reason": "distributed_physical_action_blocked_by_default",
                    "action_type": action_type,
                },
            )
            self._history.append({
                "proposal_id": proposal_id,
                "action_type": action_type,
                "outcome": "blocked",
                "error": "distributed_physical_action_blocked_by_default",
            })
            return proposal_id

        # Fallback when governance is unavailable
        proposal = {
            "proposal_id": proposal_id,
            "action_type": action_type,
            "action_plan": action_plan,
            "status": "blocked",
            "governance_decision": None,
            "consensus": None,
            "timestamp": time.time(),
        }
        self._proposals[proposal_id] = proposal
        self._persist_proposal(proposal)
        self._log(
            MorphologyEventType.ACTION_BLOCKED,
            proposal_id,
            {
                "reason": "distributed_physical_action_blocked_by_default",
                "action_type": action_type,
            },
        )
        self._history.append({
            "proposal_id": proposal_id,
            "action_type": action_type,
            "outcome": "blocked",
            "error": "distributed_physical_action_blocked_by_default",
        })
        return proposal_id

    def evaluate_consensus(self, proposal_id: str) -> Dict[str, Any]:
        """Simulate consensus evaluation for a distributed action.

        Returns a quorum summary.  In a real deployment this would poll
        registered nodes; here we simulate a conservative quorum.
        """
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            return {"error": "proposal_not_found"}

        nodes = self.list_nodes()
        total = max(1, len(nodes))
        # Simulated: require at least consensus_threshold fraction of nodes
        required = max(1, int(self._consensus_threshold * total))
        # For safety, simulated votes always fall short of quorum
        simulated_approve = max(0, required - 1)
        quorum_reached = simulated_approve >= required

        consensus = {
            "proposal_id": proposal_id,
            "total_nodes": total,
            "required_votes": required,
            "approve_votes": simulated_approve,
            "quorum_reached": quorum_reached,
            "status": "approved" if quorum_reached else "quorum_failed",
        }
        proposal["consensus"] = consensus
        return consensus

    # ------------------------------------------------------------------ #
    # Summary / queries
    # ------------------------------------------------------------------ #

    def summary(self) -> Dict[str, Any]:
        """Human-readable summary of the distributed organism."""
        nodes = self.list_nodes()
        total_health = sum(n.get("health_score", 0.0) for n in nodes)
        avg_health = total_health / len(nodes) if nodes else 0.0

        proposals = list(self._proposals.values())
        blocked = sum(1 for p in proposals if p.get("status") == "blocked")

        return {
            "node_count": len(nodes),
            "average_health": round(avg_health, 4),
            "total_proposals": len(proposals),
            "blocked_proposals": blocked,
            "autonomous_execution_enabled": False,
            "consensus_threshold": self._consensus_threshold,
            "nodes": [
                {
                    "node_id": n["body_id"],
                    "type": n["body_type"],
                    "health": n.get("health_score", 0.0),
                }
                for n in nodes
            ],
        }

    def get_action_history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _log(
        self,
        event_type: MorphologyEventType,
        action_id: str,
        metadata: Dict[str, Any],
    ) -> None:
        record = {
            "timestamp": time.time(),
            "event_type": str(event_type),
            "action_id": action_id,
            "metadata": metadata,
        }
        try:
            with self._audit_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _persist_proposal(self, proposal: Dict[str, Any]) -> None:
        try:
            with self._proposals_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(proposal, ensure_ascii=False) + "\n")
        except OSError:
            pass
