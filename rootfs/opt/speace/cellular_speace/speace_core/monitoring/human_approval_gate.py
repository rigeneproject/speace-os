"""HumanApprovalGate — stateful gate for regulation proposals (T104).

API surface:
  GET  /api/regulation/proposals  → list pending
  POST /api/regulation/approve/{proposal_id}  → approve + execute
  POST /api/regulation/reject/{proposal_id}   → reject

Audit trail written to data/regulation/approval_log.jsonl.
"""

import json
import pathlib
import time
from typing import Any, Dict, List, Optional

from speace_core.monitoring.regulation_proposal_builder import RegulationProposalBuilder
from speace_core.monitoring.safe_regulation_executor import SafeRegulationExecutor


class HumanApprovalGate:
    """Manages proposal lifecycle: pending → approved/rejected."""

    def __init__(
        self,
        builder: Optional[RegulationProposalBuilder] = None,
        executor: Optional[SafeRegulationExecutor] = None,
        log_path: str = "data/regulation/approval_log.jsonl",
    ) -> None:
        self.builder = builder or RegulationProposalBuilder()
        self.executor = executor or SafeRegulationExecutor()
        self.log_path = pathlib.Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Audit
    # ------------------------------------------------------------------ #

    def _audit(self, event: str, proposal_id: str, reviewer: str, detail: Optional[str] = None) -> None:
        record: Dict[str, Any] = {
            "event": event,
            "proposal_id": proposal_id,
            "reviewer": reviewer,
            "timestamp": time.time(),
        }
        if detail:
            record["detail"] = detail
        try:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass

    # ------------------------------------------------------------------ #
    # Actions
    # ------------------------------------------------------------------ #

    def list_pending(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.builder.list_proposals(status="pending", limit=limit)

    def list_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self.builder.list_proposals(status=None, limit=limit)

    def approve(self, proposal_id: str, reviewer: str, current_health: float = 0.0) -> Dict[str, Any]:
        proposal = self.builder.get_proposal(proposal_id)
        if not proposal:
            return {"error": "proposal_not_found", "proposal_id": proposal_id}
        if proposal.get("status") != "pending":
            return {"error": "not_pending", "status": proposal.get("status")}

        self.builder.update_status(proposal_id, "approved", reviewer=reviewer)
        self._audit("approved", proposal_id, reviewer)

        # Execute under safe regulation
        exec_result = self.executor.execute(proposal, current_health=current_health)

        # Mark executed
        self.builder.update_status(proposal_id, "executed", reviewer=reviewer)
        self._audit("executed", proposal_id, reviewer, detail=exec_result.get("outcome"))

        return {
            "proposal_id": proposal_id,
            "status": "executed",
            "reviewer": reviewer,
            "execution": exec_result,
        }

    def reject(self, proposal_id: str, reviewer: str) -> Dict[str, Any]:
        proposal = self.builder.get_proposal(proposal_id)
        if not proposal:
            return {"error": "proposal_not_found", "proposal_id": proposal_id}
        if proposal.get("status") != "pending":
            return {"error": "not_pending", "status": proposal.get("status")}

        self.builder.update_status(proposal_id, "rejected", reviewer=reviewer)
        self._audit("rejected", proposal_id, reviewer)
        return {"proposal_id": proposal_id, "status": "rejected", "reviewer": reviewer}
