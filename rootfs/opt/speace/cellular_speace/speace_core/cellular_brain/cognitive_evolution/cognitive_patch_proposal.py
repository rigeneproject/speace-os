"""CognitivePatchProposal — T133: formal proposal for cognitive self-modification.

Wraps a skill variant and its fitness evaluation into a proposal that must
pass through HumanApprovalGate before being applied.

Rollback snapshot is captured before application.
"""

import copy
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CognitivePatchProposal(BaseModel):
    proposal_id: str
    skill_id: str
    skill_type: str
    description: str = ""
    fitness: Dict[str, Any] = Field(default_factory=dict)
    pre_snapshot: Dict[str, Any] = Field(default_factory=dict)
    variant_params: Dict[str, Any] = Field(default_factory=dict)
    variant_template: str = ""
    status: str = "pending"  # pending | approved | rejected | applied | rolled_back
    requested_by: str = ""
    reviewer: str = ""
    reviewed_at: float = 0.0
    applied_at: float = 0.0
    rollback_snapshot: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = 0.0


class CognitivePatchProposalBuilder:
    """Builds, persists, and manages cognitive patch proposals."""

    def __init__(self, data_root: str = "data/cognitive_evolution") -> None:
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._proposals_path = self._data_root / "patch_proposals.jsonl"
        self._proposals: Dict[str, CognitivePatchProposal] = {}
        self._load()

    def create(
        self,
        skill_id: str,
        skill_type: str,
        fitness: Dict[str, Any],
        pre_snapshot: Dict[str, Any],
        variant_params: Dict[str, Any],
        variant_template: str,
        requested_by: str = "",
        description: str = "",
    ) -> CognitivePatchProposal:
        """Create a new patch proposal from a sandbox-evaluated variant."""
        proposal = CognitivePatchProposal(
            proposal_id=f"CP-{uuid.uuid4().hex[:12]}",
            skill_id=skill_id,
            skill_type=skill_type,
            description=description,
            fitness=fitness,
            pre_snapshot=copy.deepcopy(pre_snapshot),
            variant_params=copy.deepcopy(variant_params),
            variant_template=variant_template,
            requested_by=requested_by,
            created_at=time.time(),
        )
        self._proposals[proposal.proposal_id] = proposal
        self._persist()
        return proposal

    def get(self, proposal_id: str) -> Optional[CognitivePatchProposal]:
        return self._proposals.get(proposal_id)

    def list_proposals(
        self,
        status: Optional[str] = None,
        skill_type: Optional[str] = None,
    ) -> List[CognitivePatchProposal]:
        results = list(self._proposals.values())
        if status:
            results = [p for p in results if p.status == status]
        if skill_type:
            results = [p for p in results if p.skill_type == skill_type]
        return sorted(results, key=lambda p: p.created_at, reverse=True)

    def approve(self, proposal_id: str, reviewer: str) -> bool:
        proposal = self._proposals.get(proposal_id)
        if proposal is None or proposal.status != "pending":
            return False
        proposal.status = "approved"
        proposal.reviewer = reviewer
        proposal.reviewed_at = time.time()
        self._persist()
        return True

    def reject(self, proposal_id: str, reviewer: str) -> bool:
        proposal = self._proposals.get(proposal_id)
        if proposal is None or proposal.status != "pending":
            return False
        proposal.status = "rejected"
        proposal.reviewer = reviewer
        proposal.reviewed_at = time.time()
        self._persist()
        return True

    def mark_applied(self, proposal_id: str, rollback_snapshot: Dict[str, Any]) -> bool:
        proposal = self._proposals.get(proposal_id)
        if proposal is None or proposal.status != "approved":
            return False
        proposal.status = "applied"
        proposal.applied_at = time.time()
        proposal.rollback_snapshot = copy.deepcopy(rollback_snapshot)
        self._persist()
        return True

    def mark_rolled_back(self, proposal_id: str) -> bool:
        proposal = self._proposals.get(proposal_id)
        if proposal is None or proposal.status not in ("applied", "approved"):
            return False
        proposal.status = "rolled_back"
        self._persist()
        return True

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _persist(self) -> None:
        try:
            lines = [json.dumps(p.model_dump(mode="json")) + "\n" for p in self._proposals.values()]
            with self._proposals_path.open("w", encoding="utf-8") as f:
                f.writelines(lines)
        except OSError:
            pass

    def _load(self) -> None:
        if not self._proposals_path.exists():
            return
        try:
            with self._proposals_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        proposal = CognitivePatchProposal(**data)
                        self._proposals[proposal.proposal_id] = proposal
                    except (json.JSONDecodeError, TypeError):
                        continue
        except OSError:
            pass
