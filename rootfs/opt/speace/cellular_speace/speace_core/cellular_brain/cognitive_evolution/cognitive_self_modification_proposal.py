"""CognitiveSelfModificationProposal — T133: controlled cognitive self-modification.

Integrates T132 patch proposals with HumanApprovalGate.
Rules:
- No auto-modification without human approval
- All changes are reversible (rollback snapshot captured)
- Only parameter-level and template-level changes allowed
- Core code, governance, safety gates, actuators are immutable
"""

import copy
import time
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.cognitive_evolution.cognitive_patch_proposal import (
    CognitivePatchProposalBuilder,
)
from speace_core.cellular_brain.cognitive_evolution.cognitive_skill_registry import (
    CognitiveSkillRegistry,
)
from speace_core.cellular_brain.cognitive_evolution.longitudinal_evolution_tracker import (
    LongitudinalEvolutionTracker,
)


class CognitiveSelfModificationProposal:
    """T133: manages the lifecycle of cognitive self-modification proposals.

    Pipeline:
    errore cognitivo rilevato
      ↓
    genera variante skill (T132)
      ↓
    test in sandbox
      ↓
    valuta fitness
      ↓
    crea proposta
      ↓
    HumanApprovalGate
      ↓
    applica solo se approvata
      ↓
    rollback se peggiora
    """

    # Immutable domains — never allow self-modification here
    _IMMUTABLE_DOMAINS: set = {
        "core_code",
        "governance",
        "safety_gate",
        "actuator",
        "web_gateway_auth",
        "self_replication",
        "shell_access",
        "internet_access",
    }

    def __init__(
        self,
        registry: Optional[CognitiveSkillRegistry] = None,
        proposal_builder: Optional[CognitivePatchProposalBuilder] = None,
        tracker: Optional[LongitudinalEvolutionTracker] = None,
    ) -> None:
        self._registry = registry or CognitiveSkillRegistry()
        self._proposals = proposal_builder or CognitivePatchProposalBuilder()
        self._tracker = tracker or LongitudinalEvolutionTracker()

    # ------------------------------------------------------------------ #
    # Proposal lifecycle
    # ------------------------------------------------------------------ #

    def submit_proposal(
        self,
        proposal_id: str,
        requested_by: str = "",
    ) -> Dict[str, Any]:
        """Submit a pending proposal for human review."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            return {"error": "proposal_not_found"}
        if proposal.status != "pending":
            return {"error": "not_pending", "status": proposal.status}

        # Validate proposal does not touch immutable domains
        if self._touches_immutable_domain(proposal):
            self._proposals.reject(proposal_id, reviewer="system_guard")
            return {"error": "immutable_domain_touched", "proposal_id": proposal_id}

        return {
            "proposal_id": proposal_id,
            "status": "pending",
            "description": proposal.description,
            "fitness": proposal.fitness,
        }

    def approve_and_apply(
        self,
        proposal_id: str,
        reviewer: str,
        current_health: float = 0.0,
    ) -> Dict[str, Any]:
        """Approve a proposal and apply it to the skill registry.

        Captures rollback snapshot before application.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            return {"error": "proposal_not_found"}
        if proposal.status != "pending":
            return {"error": "not_pending", "status": proposal.status}

        # Approve
        ok = self._proposals.approve(proposal_id, reviewer)
        if not ok:
            return {"error": "approval_failed"}

        # Capture rollback snapshot (current skill state)
        parent = self._registry.get(proposal.skill_id)
        rollback_snapshot: Dict[str, Any] = {}
        if parent is not None:
            rollback_snapshot = {
                "skill_id": parent.skill_id,
                "params": copy.deepcopy(parent.params),
                "template": parent.template,
                "fitness_score": parent.fitness_score,
            }

        # Apply variant
        apply_result = self._apply_variant(proposal)

        # Mark applied with rollback snapshot
        self._proposals.mark_applied(proposal_id, rollback_snapshot)

        if self._tracker is not None:
            self._tracker.record_event(
                proposal.skill_id,
                "proposal_applied",
                {"proposal_id": proposal_id, "reviewer": reviewer, "fitness": proposal.fitness},
            )

        return {
            "proposal_id": proposal_id,
            "status": "applied",
            "reviewer": reviewer,
            "apply_result": apply_result,
            "rollback_available": bool(rollback_snapshot),
        }

    def reject(
        self,
        proposal_id: str,
        reviewer: str,
    ) -> Dict[str, Any]:
        """Reject a pending proposal."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            return {"error": "proposal_not_found"}
        if proposal.status != "pending":
            return {"error": "not_pending", "status": proposal.status}

        ok = self._proposals.reject(proposal_id, reviewer)
        if not ok:
            return {"error": "rejection_failed"}

        if self._tracker is not None:
            self._tracker.record_event(
                proposal.skill_id,
                "proposal_rejected",
                {"proposal_id": proposal_id, "reviewer": reviewer},
            )

        return {
            "proposal_id": proposal_id,
            "status": "rejected",
            "reviewer": reviewer,
        }

    def rollback(self, proposal_id: str, reviewer: str) -> Dict[str, Any]:
        """Rollback an applied proposal to its pre-modification state."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            return {"error": "proposal_not_found"}
        if proposal.status not in ("applied", "approved"):
            return {"error": "cannot_rollback", "status": proposal.status}

        rollback_snapshot = proposal.rollback_snapshot
        if not rollback_snapshot:
            return {"error": "no_rollback_snapshot"}

        parent = self._registry.get(rollback_snapshot.get("skill_id", ""))
        if parent is None:
            return {"error": "parent_skill_not_found"}

        # Restore params and template
        parent.params = rollback_snapshot["params"]
        parent.template = rollback_snapshot["template"]
        parent.fitness_score = rollback_snapshot.get("fitness_score", 0.0)
        self._registry.register(parent)

        self._proposals.mark_rolled_back(proposal_id)

        if self._tracker is not None:
            self._tracker.record_event(
                proposal.skill_id,
                "proposal_rolled_back",
                {"proposal_id": proposal_id, "reviewer": reviewer},
            )

        return {
            "proposal_id": proposal_id,
            "status": "rolled_back",
            "reviewer": reviewer,
            "restored_skill_id": parent.skill_id,
        }

    def evaluate_post_apply(
        self,
        proposal_id: str,
        post_health: float,
    ) -> Dict[str, Any]:
        """Evaluate if an applied proposal improved the system.

        If health regressed > 10%, auto-rollback.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None or proposal.status != "applied":
            return {"error": "not_applied"}

        pre_health = proposal.pre_snapshot.get("alert_engine", {}).get("health_score", 0.5)
        delta = post_health - pre_health

        if delta < -0.1:
            # Auto-rollback
            rb = self.rollback(proposal_id, reviewer="system_auto_rollback")
            if self._tracker is not None:
                self._tracker.record_event(
                    proposal.skill_id,
                    "fitness_evaluated",
                    {
                        "proposal_id": proposal_id,
                        "pre_health": pre_health,
                        "post_health": post_health,
                        "delta": delta,
                        "action": "auto_rollback",
                    },
                )
            return {
                "proposal_id": proposal_id,
                "pre_health": pre_health,
                "post_health": post_health,
                "delta": delta,
                "action": "auto_rollback",
                "rollback_result": rb,
            }

        if self._tracker is not None:
            self._tracker.record_event(
                proposal.skill_id,
                "fitness_evaluated",
                {
                    "proposal_id": proposal_id,
                    "pre_health": pre_health,
                    "post_health": post_health,
                    "delta": delta,
                    "action": "keep",
                },
            )

        return {
            "proposal_id": proposal_id,
            "pre_health": pre_health,
            "post_health": post_health,
            "delta": delta,
            "action": "keep",
        }

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def list_pending(self) -> List[Dict[str, Any]]:
        return [p.model_dump(mode="json") for p in self._proposals.list_proposals(status="pending")]

    def list_applied(self) -> List[Dict[str, Any]]:
        return [p.model_dump(mode="json") for p in self._proposals.list_proposals(status="applied")]

    def summary(self) -> Dict[str, Any]:
        all_proposals = self._proposals.list_proposals()
        counts: Dict[str, int] = {}
        for p in all_proposals:
            counts[p.status] = counts.get(p.status, 0) + 1
        return {
            "total_proposals": len(all_proposals),
            "by_status": counts,
            "immutable_domains": sorted(self._IMMUTABLE_DOMAINS),
        }

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _touches_immutable_domain(self, proposal: Any) -> bool:
        """Check if a proposal attempts to modify an immutable domain."""
        # For now, skill_type is the only domain indicator
        skill_type = getattr(proposal, "skill_type", "")
        return skill_type in self._IMMUTABLE_DOMAINS

    def _apply_variant(self, proposal: Any) -> Dict[str, Any]:
        """Apply an approved variant to the skill registry."""
        skill = self._registry.get(proposal.skill_id)
        if skill is None:
            return {"error": "skill_not_found"}

        skill.params = copy.deepcopy(proposal.variant_params)
        skill.template = proposal.variant_template
        skill.fitness_score = proposal.fitness.get("fitness", 0.0)
        self._registry.register(skill)

        return {
            "skill_id": skill.skill_id,
            "new_fitness": skill.fitness_score,
            "params_updated": list(proposal.variant_params.keys()),
        }
