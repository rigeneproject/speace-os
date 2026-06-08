"""StateTransitionPolicy — deterministic transition guard logic for T163.

Computes state-transition suggestions based on homeostatic variables,
energy, cognitive load, prediction error, circadian phase, and curiosity.
Enforces minimum dwell time to prevent oscillation.
"""

from typing import Any, Dict, Optional, Tuple


class StateTransitionPolicy:
    """Encodes guard conditions for organismic state transitions."""

    # Minimum ticks before a state can transition again
    DEFAULT_MIN_DWELL_TICKS: int = 3

    # Thresholds (tunable)
    ENERGY_LOW: float = 0.2
    ENERGY_CRITICAL: float = 0.1
    PREDICTION_ERROR_HIGH: float = 0.7
    COGNITIVE_LOAD_HIGH: float = 0.85
    CURIOSITY_HIGH: float = 0.6
    STABILITY_OK: float = 0.5
    HEALTH_RECOVERED: float = 0.7
    RECOVERY_TICKS_MIN: int = 5

    def __init__(self, min_dwell_ticks: int = DEFAULT_MIN_DWELL_TICKS) -> None:
        self.min_dwell_ticks = min_dwell_ticks

    def suggest_transition(
        self,
        current_state: str,
        ticks_in_state: int,
        homeostasis_metrics: Any,
        energy: float,
        cognitive_load: float,
        prediction_error: float,
        circadian_phase: str,
        health_score: float,
        curiosity_score: float,
    ) -> Optional[str]:
        """Return a suggested next state, or None if no transition should occur."""

        # Enforce minimum dwell time
        if ticks_in_state < self.min_dwell_ticks:
            return None

        # Compute derived booleans
        energy_low = energy < self.ENERGY_LOW
        energy_crit = energy < self.ENERGY_CRITICAL
        pred_err_high = prediction_error > self.PREDICTION_ERROR_HIGH
        load_high = cognitive_load > self.COGNITIVE_LOAD_HIGH
        curiosity_high = curiosity_score > self.CURIOSITY_HIGH
        stability_ok = energy > self.STABILITY_OK  # simplified proxy
        health_recovered = health_score > self.HEALTH_RECOVERED

        # Guard logic per current state
        if current_state == "awake":
            if pred_err_high or load_high:
                return "overloaded"
            if energy_low and circadian_phase in ("night", "sleep"):
                return "resting"
            if curiosity_high and stability_ok:
                return "exploring"
            if prediction_error < 0.3 and health_score > 0.6:
                return "focused"

        elif current_state == "focused":
            if pred_err_high or load_high:
                return "overloaded"
            if energy_low:
                return "resting"
            if curiosity_high and stability_ok:
                return "exploring"
            if prediction_error < 0.2 and health_score > 0.8:
                return "consolidating"

        elif current_state == "exploring":
            if pred_err_high or load_high:
                return "overloaded"
            if energy_low or circadian_phase in ("night", "sleep"):
                return "resting"
            if prediction_error < 0.3 and not curiosity_high:
                return "focused"

        elif current_state == "resting":
            if pred_err_high or load_high:
                return "overloaded"
            if energy > 0.5 and circadian_phase in ("day", "awake"):
                return "awake"
            if health_recovered and energy > 0.4:
                return "recovering"

        elif current_state == "consolidating":
            if pred_err_high or load_high:
                return "overloaded"
            if energy_low:
                return "resting"
            if ticks_in_state >= self.RECOVERY_TICKS_MIN and health_score > 0.6:
                return "awake"

        elif current_state == "overloaded":
            # Must stay in overloaded until conditions improve
            if not pred_err_high and not load_high and energy > 0.3:
                return "recovering"
            if energy_crit:
                return "resting"

        elif current_state == "recovering":
            if pred_err_high or load_high:
                return "overloaded"
            if energy_low:
                return "resting"
            if health_recovered and energy > 0.5:
                return "awake"
            if ticks_in_state >= self.RECOVERY_TICKS_MIN and prediction_error < 0.4:
                return "focused"

        return None

    def policy_snapshot(self) -> Dict[str, Any]:
        return {
            "min_dwell_ticks": self.min_dwell_ticks,
            "thresholds": {
                "energy_low": self.ENERGY_LOW,
                "energy_critical": self.ENERGY_CRITICAL,
                "prediction_error_high": self.PREDICTION_ERROR_HIGH,
                "cognitive_load_high": self.COGNITIVE_LOAD_HIGH,
                "curiosity_high": self.CURIOSITY_HIGH,
                "stability_ok": self.STABILITY_OK,
                "health_recovered": self.HEALTH_RECOVERED,
                "recovery_ticks_min": self.RECOVERY_TICKS_MIN,
            },
        }
