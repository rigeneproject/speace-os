from typing import Any, Dict, Optional

from speace_core.cellular_brain.cyber_physical.cyber_physical_models import (
    ActuationRequest,
    AssimilationDecision,
)


class ActuationGuard:
    """T60 — Guardia che blocca sempre ogni richiesta attuativa in T60."""

    def evaluate_actuation_request(self, request: ActuationRequest) -> ActuationRequest:
        request.blocked = True
        request.reason = "T60_actuation_always_blocked_in_read_only_mode"
        return request

    def block_actuation(self, request: ActuationRequest) -> AssimilationDecision:
        return AssimilationDecision(
            decision_id=f"block_actuation_{request.request_id}",
            action="block_actuation",
            reason="T60_read_only_mode_blocks_all_actuation",
            accepted=False,
            quarantined=False,
            safety_relevant=request.risk_score > 0.5,
        )

    def simulate_actuation_dry_run(self, request: ActuationRequest) -> Dict[str, Any]:
        return {
            "request_id": request.request_id,
            "target_system": request.target_system,
            "action": request.action,
            "would_execute": False,
            "blocked": True,
            "reason": "dry_run_simulation_only",
            "simulated_payload": request.payload,
        }

    @staticmethod
    def requires_human_approval(request: ActuationRequest) -> bool:
        return True
