import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.memory.morphology_events import MorphologyEvent, MorphologyEventType


class ProposalOutcome(BaseModel):
    id: str
    proposal_id: str
    originating_limitation_type: str
    implemented_task_id: str
    audit_verdict: str
    net_gain: float = 0.0
    cognitive_delta: float = 0.0
    phi_delta: float = 0.0
    energy_delta: float = 0.0
    risk_delta: float = 0.0
    success: bool = False
    partial_success: bool = False
    regression_detected: bool = False
    timestamp: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OutcomeTracker:
    """T46 — Record and manage outcomes of architecture proposals."""

    def __init__(
        self,
        base_path: str = "data/self_improvement",
        memory=None,
    ):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.outcomes_path = self.base_path / "outcomes.jsonl"
        self.memory = memory

    # ------------------------------------------------------------------ #
    # Outcome recording
    # ------------------------------------------------------------------ #

    def record_outcome(
        self,
        proposal_id: str,
        limitation_type: str,
        task_id: str,
        audit_verdict: str,
        metrics: Dict[str, Any],
    ) -> ProposalOutcome:
        now = datetime.now(timezone.utc).isoformat()
        net_gain = float(metrics.get("net_gain", 0.0))
        cognitive_delta = float(metrics.get("cognitive_delta", 0.0))
        phi_delta = float(metrics.get("phi_delta", 0.0))
        energy_delta = float(metrics.get("energy_delta", 0.0))
        risk_delta = float(metrics.get("risk_delta", 0.0))

        success = self._is_success(audit_verdict, net_gain)
        partial_success = self._is_partial_success(audit_verdict, net_gain, success)
        regression_detected = self._is_regression(audit_verdict, net_gain)

        outcome = ProposalOutcome(
            id=f"outcome-{uuid.uuid4().hex[:8]}",
            proposal_id=proposal_id,
            originating_limitation_type=limitation_type,
            implemented_task_id=task_id,
            audit_verdict=audit_verdict,
            net_gain=net_gain,
            cognitive_delta=cognitive_delta,
            phi_delta=phi_delta,
            energy_delta=energy_delta,
            risk_delta=risk_delta,
            success=success,
            partial_success=partial_success,
            regression_detected=regression_detected,
            timestamp=now,
            metadata=metrics.get("metadata", {}),
        )

        self._persist_outcome(outcome)
        self._log_event(
            MorphologyEventType.SELF_IMPROVEMENT_OUTCOME_RECORDED,
            {
                "outcome_id": outcome.id,
                "proposal_id": outcome.proposal_id,
                "limitation_type": limitation_type,
                "task_id": task_id,
                "audit_verdict": audit_verdict,
                "net_gain": net_gain,
                "success": success,
                "regression_detected": regression_detected,
            },
        )

        if success:
            self._log_event(
                MorphologyEventType.SELF_IMPROVEMENT_PROPOSAL_VALIDATED,
                {
                    "outcome_id": outcome.id,
                    "proposal_id": proposal_id,
                    "limitation_type": limitation_type,
                },
            )
        elif regression_detected:
            self._log_event(
                MorphologyEventType.SELF_IMPROVEMENT_PROPOSAL_FAILED,
                {
                    "outcome_id": outcome.id,
                    "proposal_id": proposal_id,
                    "limitation_type": limitation_type,
                },
            )

        return outcome

    # ------------------------------------------------------------------ #
    # Classification helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_success(audit_verdict: str, net_gain: float) -> bool:
        if "VALIDATED" in audit_verdict.upper():
            return True
        return net_gain > 0.05

    @staticmethod
    def _is_partial_success(audit_verdict: str, net_gain: float, already_success: bool) -> bool:
        if already_success:
            return False
        if net_gain > 0.0:
            return True
        upper = audit_verdict.upper()
        if any(k in upper for k in ("WEAK", "PARTIAL", "RECOVERY", "PASSIVE")):
            return True
        return False

    @staticmethod
    def _is_regression(audit_verdict: str, net_gain: float) -> bool:
        if "REGRESSION" in audit_verdict.upper():
            return True
        return net_gain < -0.02

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _persist_outcome(self, outcome: ProposalOutcome) -> None:
        record = outcome.model_dump()
        record["_stored_at"] = datetime.now(timezone.utc).isoformat()
        with open(self.outcomes_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def load_outcomes(self) -> List[ProposalOutcome]:
        results: List[ProposalOutcome] = []
        if not self.outcomes_path.exists():
            return results
        with open(self.outcomes_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                record.pop("_stored_at", None)
                results.append(ProposalOutcome(**record))
        return results

    def get_outcomes_for_limitation(self, limitation_type: str) -> List[ProposalOutcome]:
        return [o for o in self.load_outcomes() if o.originating_limitation_type == limitation_type]

    # ------------------------------------------------------------------ #
    # Reporting
    # ------------------------------------------------------------------ #

    def generate_outcome_report(self, outcome: ProposalOutcome) -> str:
        lines = [
            "# T46 — Proposal Outcome Report",
            "",
            f"**Outcome ID:** {outcome.id}",
            f"**Proposal ID:** {outcome.proposal_id}",
            f"**Limitation Type:** {outcome.originating_limitation_type}",
            f"**Implemented Task:** {outcome.implemented_task_id}",
            f"**Audit Verdict:** {outcome.audit_verdict}",
            f"**Net Gain:** {outcome.net_gain:+.4f}",
            f"**Success:** {outcome.success}",
            f"**Partial Success:** {outcome.partial_success}",
            f"**Regression Detected:** {outcome.regression_detected}",
            f"**Timestamp:** {outcome.timestamp}",
            "",
            "## Metrics",
            f"- Cognitive Δ: {outcome.cognitive_delta:+.4f}",
            f"- Φ Δ: {outcome.phi_delta:+.4f}",
            f"- Energy Δ: {outcome.energy_delta:+.4f}",
            f"- Risk Δ: {outcome.risk_delta:+.4f}",
            "",
            "---",
            "*Generated by T46 OutcomeTracker*",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _log_event(
        self,
        event_type: MorphologyEventType,
        metadata: Dict[str, Any],
    ) -> None:
        if self.memory is None or not hasattr(self.memory, "log_event"):
            return
        try:
            event = MorphologyEvent(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=event_type,
                timestamp=datetime.now(timezone.utc).timestamp(),
                metadata=metadata,
            )
            self.memory.log_event(event)
        except Exception:
            pass
