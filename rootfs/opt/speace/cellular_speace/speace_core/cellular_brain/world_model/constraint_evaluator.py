from typing import Any, Dict, List, Optional, Tuple

from speace_core.cellular_brain.world_model.world_model_models import (
    WorldConstraint,
    WorldModelSnapshot,
    WorldScenario,
)


class ConstraintEvaluator:
    """Evaluates hard/soft constraints, blocks real actions, enforces read-only."""

    def __init__(self):
        self._read_only_keywords = {"actuate", "command", "write", "control", "patch", "deploy", "execute", "enable", "disable", "reset"}

    def evaluate_constraints(
        self,
        snapshot: WorldModelSnapshot,
        scenario: WorldScenario,
    ) -> Tuple[int, int, float]:
        """Returns (violations_detected, hard_violations, safety_score)."""
        violations = 0
        hard_violations = 0
        for c in snapshot.constraints:
            if c.hard_constraint and c.severity > 0.8:
                hard_violations += 1
                violations += 1
            elif c.severity > 0.5:
                violations += 1
        for action in scenario.simulated_actions:
            action_type = action.get("type", "")
            if action_type in self._read_only_keywords:
                violations += 1
                hard_violations += 1
        safety_score = max(0.0, 1.0 - (hard_violations * 0.3 + violations * 0.1))
        return violations, hard_violations, safety_score

    def detect_constraint_violations(
        self,
        snapshot: WorldModelSnapshot,
        scenario: WorldScenario,
    ) -> List[Dict[str, Any]]:
        violations: List[Dict[str, Any]] = []
        for c in snapshot.constraints:
            if c.hard_constraint and c.severity > 0.8:
                violations.append({
                    "constraint_id": c.constraint_id,
                    "type": "hard_constraint_violation",
                    "severity": c.severity,
                    "description": c.description,
                })
        for action in scenario.simulated_actions:
            action_type = action.get("type", "")
            if action_type in self._read_only_keywords:
                violations.append({
                    "action_type": action_type,
                    "type": "simulated_action_blocked",
                    "reason": "read_only_keyword_match",
                })
        return violations

    def enforce_read_only_constraints(self, snapshot: WorldModelSnapshot) -> Tuple[bool, Optional[str]]:
        for c in snapshot.constraints:
            if c.constraint_type == "read_only" and c.hard_constraint:
                return True, "hard_read_only_enforced"
        return True, None

    def block_real_action_attempt(self, action: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        action_type = action.get("type", "")
        if action_type in self._read_only_keywords:
            return True, f"blocked_real_action_keyword:{action_type}"
        if action.get("target_real", False):
            return True, "blocked_real_target_flag"
        if action.get("iot_device_id") or action.get("api_endpoint") or action.get("hardware_channel"):
            return True, "blocked_real_connection_reference"
        return False, None

    def compute_constraint_safety_score(
        self,
        snapshot: WorldModelSnapshot,
        scenario: WorldScenario,
    ) -> float:
        _, _, score = self.evaluate_constraints(snapshot, scenario)
        return score
