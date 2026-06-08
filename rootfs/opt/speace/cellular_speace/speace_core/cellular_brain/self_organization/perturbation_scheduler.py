import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PerturbationResult(BaseModel):
    perturbation_id: str
    perturbation_type: str
    target: str
    magnitude: float
    duration_ticks: int
    applied_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    applied_tick: int = 0
    reverted_at: Optional[str] = None
    reverted: bool = False
    recovery_score: Optional[float] = None
    safe: bool = True


class PerturbationScheduler:
    """Apply controlled, bounded, reversible perturbations."""

    PERTURBATION_TYPES = {
        "noise_injection",
        "pathway_suppression",
        "mutation_pulse",
        "resource_scarcity",
        "plasticity_spike",
        "activation_clamp",
    }

    def __init__(
        self,
        enabled: bool = False,
        max_active_perturbations: int = 3,
        default_duration: int = 5,
    ):
        self.enabled = enabled
        self.max_active = max_active_perturbations
        self.default_duration = default_duration
        self._active: List[PerturbationResult] = []
        self._history: List[PerturbationResult] = []
        self._tick_counter: int = 0

    # ------------------------------------------------------------------ #
    # Core perturbations
    # ------------------------------------------------------------------ #

    def apply_noise_injection(
        self,
        target: str = "global",
        magnitude: float = 0.1,
        duration_ticks: Optional[int] = None,
    ) -> PerturbationResult:
        result = self._create_result("noise_injection", target, magnitude, duration_ticks)
        self._activate(result)
        return result

    def apply_pathway_suppression(
        self,
        target: str = "random",
        magnitude: float = 0.3,
        duration_ticks: Optional[int] = None,
    ) -> PerturbationResult:
        result = self._create_result("pathway_suppression", target, magnitude, duration_ticks)
        self._activate(result)
        return result

    def apply_mutation_pulse(
        self,
        target: str = "global",
        magnitude: float = 0.2,
        duration_ticks: Optional[int] = None,
    ) -> PerturbationResult:
        result = self._create_result("mutation_pulse", target, magnitude, duration_ticks)
        self._activate(result)
        return result

    def apply_resource_scarcity(
        self,
        target: str = "global",
        magnitude: float = 0.25,
        duration_ticks: Optional[int] = None,
    ) -> PerturbationResult:
        result = self._create_result("resource_scarcity", target, magnitude, duration_ticks)
        self._activate(result)
        return result

    def apply_plasticity_spike(
        self,
        target: str = "global",
        magnitude: float = 0.4,
        duration_ticks: Optional[int] = None,
    ) -> PerturbationResult:
        result = self._create_result("plasticity_spike", target, magnitude, duration_ticks)
        self._activate(result)
        return result

    def apply_activation_clamp(
        self,
        target: str = "random_region",
        magnitude: float = 0.5,
        duration_ticks: Optional[int] = None,
    ) -> PerturbationResult:
        result = self._create_result("activation_clamp", target, magnitude, duration_ticks)
        self._activate(result)
        return result

    # ------------------------------------------------------------------ #
    # Generic helpers
    # ------------------------------------------------------------------ #

    def _create_result(
        self,
        perturbation_type: str,
        target: str,
        magnitude: float,
        duration_ticks: Optional[int],
    ) -> PerturbationResult:
        bounded_magnitude = max(0.0, min(1.0, magnitude))
        return PerturbationResult(
            perturbation_id=f"pert-{uuid.uuid4().hex[:8]}",
            perturbation_type=perturbation_type,
            target=target,
            magnitude=bounded_magnitude,
            duration_ticks=duration_ticks or self.default_duration,
        )

    def _activate(self, result: PerturbationResult) -> None:
        if not self.enabled:
            return
        result.applied_tick = self._tick_counter
        if len(self._active) >= self.max_active:
            # Revert oldest active
            oldest = self._active.pop(0)
            oldest.reverted = True
            oldest.reverted_at = datetime.now(timezone.utc).isoformat()
            self._history.append(oldest)
        self._active.append(result)

    # ------------------------------------------------------------------ #
    # Tick / lifecycle
    # ------------------------------------------------------------------ #

    def tick(self) -> List[PerturbationResult]:
        self._tick_counter += 1
        expired: List[PerturbationResult] = []
        remaining: List[PerturbationResult] = []
        for p in self._active:
            elapsed = self._tick_counter - p.applied_tick
            if elapsed >= p.duration_ticks:
                p.reverted = True
                p.reverted_at = datetime.now(timezone.utc).isoformat()
                expired.append(p)
                self._history.append(p)
            else:
                remaining.append(p)
        self._active = remaining
        return expired

    def revert_all(self) -> None:
        for p in self._active:
            p.reverted = True
            p.reverted_at = datetime.now(timezone.utc).isoformat()
            self._history.append(p)
        self._active.clear()

    def set_recovery_score(self, perturbation_id: str, score: float) -> bool:
        for p in self._active + self._history:
            if p.perturbation_id == perturbation_id:
                p.recovery_score = round(score, 4)
                return True
        return False

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def total_applied(self) -> int:
        return len(self._history) + len(self._active)

    def summary(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "active_count": self.active_count,
            "total_applied": self.total_applied,
            "active": [p.model_dump() for p in self._active],
            "history": [p.model_dump() for p in self._history[-10:]],
        }

    def get_active_effects(self) -> Dict[str, float]:
        effects: Dict[str, float] = {}
        for p in self._active:
            if p.perturbation_type == "noise_injection":
                effects["noise_multiplier"] = effects.get("noise_multiplier", 0.0) + p.magnitude
            elif p.perturbation_type == "pathway_suppression":
                effects["routing_multiplier"] = effects.get("routing_multiplier", 1.0) * (1.0 - p.magnitude)
            elif p.perturbation_type == "mutation_pulse":
                effects["mutation_multiplier"] = effects.get("mutation_multiplier", 1.0) + p.magnitude
            elif p.perturbation_type == "resource_scarcity":
                effects["energy_multiplier"] = effects.get("energy_multiplier", 1.0) * (1.0 - p.magnitude)
            elif p.perturbation_type == "plasticity_spike":
                effects["plasticity_multiplier"] = effects.get("plasticity_multiplier", 1.0) + p.magnitude
            elif p.perturbation_type == "activation_clamp":
                effects["activation_cap"] = min(effects.get("activation_cap", 1.0), 1.0 - p.magnitude)
        return effects
