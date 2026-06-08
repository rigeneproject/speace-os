"""EcosystemActuator — T131-E: controlled ecosystem interaction with human approval gates.

Safety rules:
- NO autonomous execution
- All actions require human approval (reviewer+)
- Actions are logged and auditable
- Execution is stubbed by default — real actuation requires explicit enablement
- RBAC enforced at API layer
"""

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EcosystemActionProposal(BaseModel):
    proposal_id: str
    source_id: str
    action_type: str  # e.g. "mqtt_publish", "http_post", "ros_command"
    payload: Dict[str, Any] = Field(default_factory=dict)
    requested_by: str = ""  # user/api key fingerprint
    status: str = "pending"  # pending | approved | rejected | executed | failed
    created_at: float = 0.0
    approved_by: str = ""
    approved_at: float = 0.0
    rejected_by: str = ""
    rejected_at: float = 0.0
    executed_at: float = 0.0
    result: Dict[str, Any] = Field(default_factory=dict)
    audit_log: List[str] = Field(default_factory=list)


class EcosystemActuator:
    """Manages proposed ecosystem actions with human approval gates.

    T131-E implements the bridge from observation to controlled interaction.
    By default, execution is stubbed (no-op) for safety.
    """

    def __init__(
        self,
        data_root: str = "data/ecosystem",
        allow_execution: bool = False,
    ) -> None:
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._proposals_path = self._data_root / "action_proposals.jsonl"
        self._allow_execution = allow_execution
        self._proposals: Dict[str, EcosystemActionProposal] = {}
        self._load_proposals()

    # ------------------------------------------------------------------ #
    # Proposal lifecycle
    # ------------------------------------------------------------------ #

    def propose(
        self,
        source_id: str,
        action_type: str,
        payload: Dict[str, Any],
        requested_by: str = "",
    ) -> EcosystemActionProposal:
        """Create a new action proposal."""
        proposal = EcosystemActionProposal(
            proposal_id=str(uuid.uuid4())[:8],
            source_id=source_id,
            action_type=action_type,
            payload=payload,
            requested_by=requested_by,
            status="pending",
            created_at=time.time(),
        )
        self._proposals[proposal.proposal_id] = proposal
        self._persist()
        return proposal

    def approve(self, proposal_id: str, approver: str = "") -> Optional[EcosystemActionProposal]:
        """Approve a pending proposal."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None or proposal.status != "pending":
            return None
        proposal.status = "approved"
        proposal.approved_by = approver
        proposal.approved_at = time.time()
        proposal.audit_log.append(f"approved by {approver} at {proposal.approved_at}")
        self._persist()
        return proposal

    def reject(self, proposal_id: str, reviewer: str = "") -> Optional[EcosystemActionProposal]:
        """Reject a pending proposal."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None or proposal.status != "pending":
            return None
        proposal.status = "rejected"
        proposal.rejected_by = reviewer
        proposal.rejected_at = time.time()
        proposal.audit_log.append(f"rejected by {reviewer} at {proposal.rejected_at}")
        self._persist()
        return proposal

    def execute(self, proposal_id: str) -> Optional[EcosystemActionProposal]:
        """Execute an approved proposal.

        By default (allow_execution=False), this is a no-op that records
        what would have happened. Set allow_execution=True only in
        controlled environments with full audit trails.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None or proposal.status != "approved":
            return None

        proposal.executed_at = time.time()
        proposal.audit_log.append(f"execution attempted at {proposal.executed_at}")

        if not self._allow_execution:
            proposal.status = "executed"
            proposal.result = {
                "_mode": "stub",
                "_note": "Execution is stubbed for safety. No external action was taken.",
                "action_type": proposal.action_type,
                "target_source": proposal.source_id,
                "payload_preview": str(proposal.payload)[:200],
            }
            self._persist()
            return proposal

        # Real execution path (only when explicitly enabled)
        try:
            # T131-E: controlled actuation placeholder
            # In a real deployment, this would delegate to the appropriate adapter
            proposal.result = {"_mode": "executed", "_detail": "real_execution_placeholder"}
            proposal.status = "executed"
        except Exception as exc:
            proposal.status = "failed"
            proposal.result = {"_error": str(exc)}

        proposal.audit_log.append(f"execution completed with status {proposal.status}")
        self._persist()
        return proposal

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get(self, proposal_id: str) -> Optional[EcosystemActionProposal]:
        return self._proposals.get(proposal_id)

    def list_proposals(
        self,
        status_filter: Optional[str] = None,
        source_filter: Optional[str] = None,
    ) -> List[EcosystemActionProposal]:
        results = list(self._proposals.values())
        if status_filter:
            results = [p for p in results if p.status == status_filter]
        if source_filter:
            results = [p for p in results if p.source_id == source_filter]
        # Sort by created_at descending
        results.sort(key=lambda p: p.created_at, reverse=True)
        return results

    def summary(self) -> Dict[str, Any]:
        counts: Dict[str, int] = {}
        for p in self._proposals.values():
            counts[p.status] = counts.get(p.status, 0) + 1
        return {
            "total": len(self._proposals),
            "by_status": counts,
            "execution_enabled": self._allow_execution,
        }

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

    def _load_proposals(self) -> None:
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
                        proposal = EcosystemActionProposal(**data)
                        self._proposals[proposal.proposal_id] = proposal
                    except (json.JSONDecodeError, TypeError):
                        continue
        except OSError:
            pass
