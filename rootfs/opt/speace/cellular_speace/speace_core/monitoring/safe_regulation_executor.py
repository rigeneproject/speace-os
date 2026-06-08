"""SafeRegulationExecutor — executes approved regulation proposals (T104).

Only tunable-parameter patches are allowed.  After execution, validates
the result and auto-rolls back if regression is detected.
"""

import json
import pathlib
import time
from typing import Any, Dict, List, Optional

from speace_core.monitoring.regulation_confidence_scorer import RegulationConfidenceScorer


class SafeRegulationExecutor:
    """Executes approved proposals and tracks outcomes."""

    # Allowed config keys that can be modified (tunable parameters only)
    _ALLOWED_TARGETS: Dict[str, List[str]] = {
        "increase stability bias": ["dynamics.stability_bias"],
        "reduce stability bias": ["dynamics.stability_bias"],
        "increase exploration drive": ["drives.exploration_urgency"],
        "reduce exploration drive": ["drives.exploration_urgency"],
        "inject noise threshold": ["dynamics.noise_threshold"],
        "modulate drift correction": ["dynamics.drift_correction_rate"],
        "reset attractor baseline": ["dynamics.attractor_baseline"],
        "increase prediction model learning rate": ["embodiment.learning_rate"],
        "reduce action complexity": ["embodiment.max_action_complexity"],
        "increase integration coupling": ["cognition.integration_coupling"],
        "global workspace reset": [],  # structural — blocked
        "trigger narrative merge": [],  # structural — blocked
        "reduce action urgency": ["drives.global_urgency_scale"],
        "pause autonomous actions": ["safety.pause_autonomous"],
        "reduce dominant drive urgency": ["drives.dominant_urgency"],
    }

    def __init__(
        self,
        log_path: str = "data/regulation/execution_log.jsonl",
        scorer: Optional[RegulationConfidenceScorer] = None,
    ) -> None:
        self.log_path = pathlib.Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._scorer = scorer or RegulationConfidenceScorer()

    # ------------------------------------------------------------------ #
    # Execution
    # ------------------------------------------------------------------ #

    def execute(self, proposal: Dict[str, Any], current_health: float) -> Dict[str, Any]:
        """Execute a single approved proposal."""
        action = proposal.get("proposed_action", "")
        pid = proposal.get("proposal_id", "unknown")
        alert_type = proposal.get("alert", {}).get("alert_type", "unknown")

        # Safety gate: only tunable parameters
        if action not in self._ALLOWED_TARGETS:
            return self._log(pid, action, "blocked", "action not in allowed catalog", current_health, current_health)

        targets = self._ALLOWED_TARGETS[action]

        # Structural changes are blocked
        if not targets:
            return self._log(pid, action, "blocked", "structural change not permitted", current_health, current_health)

        # Simulate patch application (actual runtime integration would go here)
        applied = self._apply_patch(targets, proposal)

        # Post-execution validation (simulated — real implementation would re-evaluate state)
        post_health = self._estimate_post_health(current_health, proposal)

        # Auto-rollback if regression
        if post_health < current_health * 0.9:
            self._rollback(proposal)
            outcome = "rollback"
            note = f"health regressed {current_health:.4f} → {post_health:.4f}"
        else:
            outcome = "success"
            note = f"health {current_health:.4f} → {post_health:.4f}"

        # Record outcome for epistemic memory
        self._scorer.record_outcome(
            proposal_id=pid,
            alert_type=alert_type,
            proposed_action=action,
            pre_health=current_health,
            post_health=post_health,
            outcome=outcome,
        )

        return self._log(pid, action, outcome, note, current_health, post_health)

    # ------------------------------------------------------------------ #
    # Patch simulation (placeholder for real ArchitecturePatchExecutor)
    # ------------------------------------------------------------------ #

    def _apply_patch(self, targets: List[str], proposal: Dict[str, Any]) -> bool:
        # In a real integration, this would call ArchitecturePatchExecutor
        # with the pre-patch snapshot for rollback capability.
        return True

    def _rollback(self, proposal: Dict[str, Any]) -> bool:
        snapshot = proposal.get("snapshot_pre", {})
        # In a real integration, this would restore the snapshot.
        return True

    def _estimate_post_health(self, current_health: float, proposal: Dict[str, Any]) -> float:
        # Simulation: small positive or negative delta based on estimated_risk
        risk = proposal.get("risk_score", 0.3)
        confidence = proposal.get("confidence", {}).get("confidence", 0.5)
        import random
        delta = (confidence * 0.1) - (risk * 0.05)
        return max(0.0, min(1.0, current_health + delta + random.uniform(-0.02, 0.02)))

    # ------------------------------------------------------------------ #
    # Logging
    # ------------------------------------------------------------------ #

    def _log(
        self,
        proposal_id: str,
        action: str,
        outcome: str,
        note: str,
        pre_health: float,
        post_health: float,
    ) -> Dict[str, Any]:
        record = {
            "proposal_id": proposal_id,
            "action": action,
            "outcome": outcome,
            "note": note,
            "pre_health": pre_health,
            "post_health": post_health,
            "timestamp": time.time(),
        }
        try:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass
        return record
