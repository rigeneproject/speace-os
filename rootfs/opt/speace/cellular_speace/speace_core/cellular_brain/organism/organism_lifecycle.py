from typing import Any, Dict, List, Optional, Tuple

from speace_core.cellular_brain.organism.organism_models import OrganismLifecycleState


class OrganismLifecycleManager:
    """T59 — Gestore del lifecycle dell'organismo computazionale."""

    VALID_TRANSITIONS: Dict[str, List[str]] = {
        OrganismLifecycleState.INITIALIZING.value: [
            OrganismLifecycleState.BASELINE.value,
            OrganismLifecycleState.ACTIVE.value,
            OrganismLifecycleState.AUDIT_ONLY.value,
        ],
        OrganismLifecycleState.BASELINE.value: [
            OrganismLifecycleState.ACTIVE.value,
            OrganismLifecycleState.CONSERVATION.value,
            OrganismLifecycleState.AUDIT_ONLY.value,
        ],
        OrganismLifecycleState.ACTIVE.value: [
            OrganismLifecycleState.BASELINE.value,
            OrganismLifecycleState.CONSERVATION.value,
            OrganismLifecycleState.RECOVERY.value,
            OrganismLifecycleState.DEGRADED.value,
            OrganismLifecycleState.CRITICAL.value,
            OrganismLifecycleState.AUDIT_ONLY.value,
        ],
        OrganismLifecycleState.CONSERVATION.value: [
            OrganismLifecycleState.BASELINE.value,
            OrganismLifecycleState.ACTIVE.value,
            OrganismLifecycleState.RECOVERY.value,
            OrganismLifecycleState.DEGRADED.value,
            OrganismLifecycleState.CRITICAL.value,
            OrganismLifecycleState.AUDIT_ONLY.value,
        ],
        OrganismLifecycleState.RECOVERY.value: [
            OrganismLifecycleState.BASELINE.value,
            OrganismLifecycleState.ACTIVE.value,
            OrganismLifecycleState.CONSERVATION.value,
            OrganismLifecycleState.DEGRADED.value,
            OrganismLifecycleState.AUDIT_ONLY.value,
        ],
        OrganismLifecycleState.DEGRADED.value: [
            OrganismLifecycleState.RECOVERY.value,
            OrganismLifecycleState.CRITICAL.value,
            OrganismLifecycleState.SUSPENDED.value,
            OrganismLifecycleState.AUDIT_ONLY.value,
        ],
        OrganismLifecycleState.CRITICAL.value: [
            OrganismLifecycleState.RECOVERY.value,
            OrganismLifecycleState.SUSPENDED.value,
            OrganismLifecycleState.AUDIT_ONLY.value,
        ],
        OrganismLifecycleState.SUSPENDED.value: [
            OrganismLifecycleState.INITIALIZING.value,
            OrganismLifecycleState.AUDIT_ONLY.value,
        ],
        OrganismLifecycleState.AUDIT_ONLY.value: [
            OrganismLifecycleState.INITIALIZING.value,
            OrganismLifecycleState.BASELINE.value,
        ],
    }

    def __init__(self, initial_state: str = OrganismLifecycleState.INITIALIZING.value):
        self._state = initial_state
        self._history: List[Tuple[str, str]] = []

    @property
    def current_state(self) -> str:
        return self._state

    def validate_transition(self, target: str) -> bool:
        return target in self.VALID_TRANSITIONS.get(self._state, [])

    def transition_to(self, target: str, reason: str = "") -> bool:
        if not self.validate_transition(target):
            return False
        self._history.append((self._state, target))
        self._state = target
        return True

    def classify_lifecycle_state(self, health_score: float, metabolic_mode: str, safety_risk: float) -> str:
        if safety_risk > 0.8:
            return OrganismLifecycleState.CRITICAL.value
        if health_score < 0.2:
            return OrganismLifecycleState.CRITICAL.value
        if health_score < 0.4:
            return OrganismLifecycleState.DEGRADED.value
        if metabolic_mode == "critical":
            return OrganismLifecycleState.CRITICAL.value
        if metabolic_mode in ("stress", "conservation"):
            return OrganismLifecycleState.CONSERVATION.value
        if safety_risk > 0.4:
            return OrganismLifecycleState.RECOVERY.value
        if health_score > 0.8:
            return OrganismLifecycleState.ACTIVE.value
        return OrganismLifecycleState.BASELINE.value

    def snapshot(self) -> Dict[str, Any]:
        return {
            "current_state": self._state,
            "transition_history": self._history,
            "possible_next_states": self.VALID_TRANSITIONS.get(self._state, []),
        }
