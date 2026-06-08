"""RegulationProposalBuilder — transforms critical alerts into safe regulation
proposals (T104).  Each proposal includes a RegulationConfidenceScore
based on historical outcomes.

Read-only: proposals are queued for human approval; no automatic execution.
"""

import json
import pathlib
import time
import uuid
from typing import Any, Dict, List, Optional

from speace_core.monitoring.regulation_confidence_scorer import RegulationConfidenceScorer


class RegulationProposalBuilder:
    """Builds regulation proposals from alert engine outputs."""

    # Actions we are allowed to propose (tunable parameters only)
    _ACTION_CATALOG = {
        "chaos_warning": [
            "increase stability bias",
            "reduce exploration drive",
        ],
        "chaos_critical": [
            "increase stability bias",
            "reduce exploration drive",
            "pause autonomous actions",
        ],
        "rigidity_warning": [
            "increase exploration drive",
            "reduce stability bias",
        ],
        "rigidity_critical": [
            "increase exploration drive",
            "reduce stability bias",
            "inject noise threshold",
        ],
        "drift_warning": [
            "modulate drift correction",
        ],
        "drift_critical": [
            "modulate drift correction",
            "reset attractor baseline",
        ],
        "prediction_error_warning": [
            "increase prediction model learning rate",
        ],
        "prediction_error_critical": [
            "increase prediction model learning rate",
            "reduce action complexity",
        ],
        "coherence_phi_warning": [
            "increase integration coupling",
        ],
        "coherence_phi_critical": [
            "increase integration coupling",
            "global workspace reset",
        ],
        "safety_risk_warning": [
            "reduce action urgency",
        ],
        "safety_risk_critical": [
            "reduce action urgency",
            "pause autonomous actions",
        ],
        "identity_divergence_warning": [
            "trigger narrative merge",
        ],
        "drive_instability_warning": [
            "reduce dominant drive urgency",
        ],
        "drive_instability_critical": [
            "reduce dominant drive urgency",
            "pause autonomous actions",
        ],
    }

    def __init__(
        self,
        proposals_path: str = "data/regulation/regulation_proposals.jsonl",
        confidence_scorer: Optional[RegulationConfidenceScorer] = None,
    ) -> None:
        self.proposals_path = pathlib.Path(proposals_path)
        self.proposals_path.parent.mkdir(parents=True, exist_ok=True)
        self._scorer = confidence_scorer or RegulationConfidenceScorer()

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _persist(self, proposal: Dict[str, Any]) -> None:
        try:
            with self.proposals_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(proposal, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def list_proposals(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.proposals_path.exists():
            return []
        proposals: List[Dict[str, Any]] = []
        try:
            with self.proposals_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        p = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if status is None or p.get("status") == status:
                        proposals.append(p)
        except OSError:
            return []
        return proposals[-limit:]

    def get_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        for p in self.list_proposals(status=None, limit=0):
            if p.get("proposal_id") == proposal_id:
                return p
        return None

    def update_status(self, proposal_id: str, status: str, reviewer: Optional[str] = None) -> bool:
        if not self.proposals_path.exists():
            return False
        updated = False
        lines: List[str] = []
        try:
            with self.proposals_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        p = json.loads(line)
                    except json.JSONDecodeError:
                        lines.append(line)
                        continue
                    if p.get("proposal_id") == proposal_id:
                        p["status"] = status
                        p["updated_at"] = time.time()
                        if reviewer:
                            p["reviewer"] = reviewer
                        updated = True
                    lines.append(json.dumps(p, ensure_ascii=False))
        except OSError:
            return False
        try:
            with self.proposals_path.open("w", encoding="utf-8") as f:
                for ln in lines:
                    f.write(ln + "\n")
        except OSError:
            return False
        return updated

    # ------------------------------------------------------------------ #
    # Builder
    # ------------------------------------------------------------------ #

    def build_from_alerts(
        self,
        alerts: List[Dict[str, Any]],
        current_state: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Generate pending proposals from critical/warning alerts."""
        proposals: List[Dict[str, Any]] = []
        seen: set = set()

        for alert in alerts:
            sev = alert.get("severity", "")
            a_type = alert.get("alert_type", "")
            if sev not in ("critical", "warning"):
                continue

            # Normalize alert type (strip _warning / _critical suffix)
            base_type = a_type
            if base_type.endswith("_warning"):
                base_type = base_type[:-8]
            elif base_type.endswith("_critical"):
                base_type = base_type[:-9]

            actions = self._ACTION_CATALOG.get(a_type, self._ACTION_CATALOG.get(base_type, []))
            for action in actions:
                key = (a_type, action)
                if key in seen:
                    continue
                seen.add(key)

                proposal = self._create_proposal(
                    alert=alert,
                    action=action,
                    current_state=current_state,
                )
                self._persist(proposal)
                proposals.append(proposal)

        return proposals

    def create_manual_proposal(
        self,
        proposed_action: str,
        current_state: Dict[str, Any],
        alert_type: str = "manual",
        severity: str = "warning",
        message: str = "",
    ) -> Dict[str, Any]:
        """Create a proposal manually (e.g. from web runtime control)."""
        pid = f"RP-{uuid.uuid4().hex[:12]}"
        ts = time.time()
        confidence = self._scorer.score(
            proposed_action=proposed_action,
            alert_type=alert_type,
            state=current_state,
        )
        snapshot = {
            "coherence_phi": current_state.get("cognition", {}).get("self_model", {}).get("coherence_phi", 0.0),
            "chaos_score": current_state.get("dynamics", {}).get("chaos_score", 0.0),
            "rigidity_score": current_state.get("dynamics", {}).get("rigidity_score", 0.0),
            "drift": current_state.get("dynamics", {}).get("drift", 0.0),
            "prediction_error": current_state.get("embodiment", {}).get("prediction_error", 0.0),
            "health_score": current_state.get("alert_engine", {}).get("health_score", 0.0),
        }
        base_risk = 0.3 if severity == "warning" else 0.6
        risk = base_risk * (1.0 - confidence["confidence"] * 0.5)
        proposal = {
            "proposal_id": pid,
            "status": "pending",
            "created_at": ts,
            "updated_at": ts,
            "alert": {
                "alert_type": alert_type,
                "severity": severity,
                "message": message,
                "timestamp": ts,
            },
            "proposed_action": proposed_action,
            "reversibility": "tunable_parameter",
            "snapshot_pre": snapshot,
            "confidence": confidence,
            "risk_score": risk,
        }
        self._persist(proposal)
        return proposal

    def _create_proposal(
        self,
        alert: Dict[str, Any],
        action: str,
        current_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        pid = f"RP-{uuid.uuid4().hex[:12]}"
        ts = time.time()
        a_type = alert.get("alert_type", "unknown")

        # Epistemic confidence
        confidence = self._scorer.score(
            proposed_action=action,
            alert_type=a_type,
            state=current_state,
        )

        # Snapshot of pre-patch state (for rollback)
        snapshot = {
            "coherence_phi": current_state.get("cognition", {}).get("self_model", {}).get("coherence_phi", 0.0),
            "chaos_score": current_state.get("dynamics", {}).get("chaos_score", 0.0),
            "rigidity_score": current_state.get("dynamics", {}).get("rigidity_score", 0.0),
            "drift": current_state.get("dynamics", {}).get("drift", 0.0),
            "prediction_error": current_state.get("embodiment", {}).get("prediction_error", 0.0),
            "health_score": current_state.get("alert_engine", {}).get("health_score", 0.0),
        }

        # Risk: high confidence + critical = lower perceived risk; low confidence = higher risk
        severity = alert.get("severity", "warning")
        base_risk = 0.3 if severity == "warning" else 0.6
        risk = base_risk * (1.0 - confidence["confidence"] * 0.5)

        return {
            "proposal_id": pid,
            "status": "pending",
            "created_at": ts,
            "updated_at": ts,
            "alert": {
                "alert_type": a_type,
                "severity": severity,
                "message": alert.get("message", ""),
                "timestamp": alert.get("timestamp"),
            },
            "proposed_action": action,
            "reversibility": "tunable_parameter",  # we only touch config, not structure
            "snapshot_pre": snapshot,
            "risk_score": round(risk, 4),
            "confidence": confidence,
            "reviewer": None,
            "executed_at": None,
            "execution_outcome": None,
        }
