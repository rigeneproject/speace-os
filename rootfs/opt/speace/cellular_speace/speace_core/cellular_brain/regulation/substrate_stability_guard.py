"""T-CDS-SAFE — Substrate Stability Guard.

Watches the :class:`ContinuousSubstrateCoordinator` state and the host
circuit for runaway dynamics:

* Divergence: activations, weights or energy drift to extreme values.
* Hyper-synchrony: Kuramoto order parameter pegged near 1.0 for too
  long (rigidity / loss of representational flexibility).
* Hypo-synchrony: order parameter near 0 sustained (chaos).
* Criticality loss: branching ratio far from 1.0.
* Energy collapse: too many neurons below the fatigue threshold.
* Free-energy explosion: predictive coding free energy grows
  monotonically.

When a violation is detected, the guard produces a *modulation
recommendation* (small, bounded adjustments to circuit and substrate
parameters) and an optional *halt request*. It never overwrites the
substrate's own modules — it only emits JSON-serialisable suggestions
that the orchestrator / runtime apply or reject.

The guard complements — but does not replace —
:class:`speace_core.cellular_brain.regulation.emergent_dynamics_stabilizer.EmergentDynamicsStabilizer`,
which works at the cognitive-symbolic level. This guard is intentionally
narrow: its responsibility is the *physical* substrate.
"""
from __future__ import annotations

import json
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque, Dict, List, Optional

_logger = logging.getLogger(__name__)


class GuardVerdict(str, Enum):
    """Severity of a guard intervention."""

    OK = "ok"
    ADJUST = "adjust"
    DAMPEN = "dampen"
    EMERGENCY = "emergency"


@dataclass
class GuardReport:
    """Result of a single guard evaluation."""

    tick: int
    verdict: GuardVerdict
    reason: str = ""
    recommendations: Dict[str, float] = field(default_factory=dict)
    measurements: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "verdict": self.verdict.value,
            "reason": self.reason,
            "recommendations": dict(self.recommendations),
            "measurements": dict(self.measurements),
        }


class SubstrateStabilityGuard:
    """Bounded watchdog for the continuous substrate."""

    def __init__(
        self,
        kuramoto_hyper_threshold: float = 0.92,
        kuramoto_hypo_threshold: float = 0.05,
        kuramoto_window: int = 20,
        branching_low: float = 0.5,
        branching_high: float = 1.5,
        free_energy_growth_window: int = 30,
        free_energy_growth_ratio: float = 3.0,
        fatigue_fraction_emergency: float = 0.7,
        activation_max: float = 100.0,
        energy_min_emergency: float = 0.05,
        cooldown_ticks: int = 10,
    ):
        self.kuramoto_hyper_threshold = kuramoto_hyper_threshold
        self.kuramoto_hypo_threshold = kuramoto_hypo_threshold
        self.kuramoto_window = kuramoto_window
        self.branching_low = branching_low
        self.branching_high = branching_high
        self.free_energy_growth_window = free_energy_growth_window
        self.free_energy_growth_ratio = free_energy_growth_ratio
        self.fatigue_fraction_emergency = fatigue_fraction_emergency
        self.activation_max = activation_max
        self.energy_min_emergency = energy_min_emergency
        self.cooldown_ticks = cooldown_ticks

        self._kuramoto_history: Deque[float] = deque(maxlen=kuramoto_window)
        self._free_energy_history: Deque[float] = deque(
            maxlen=free_energy_growth_window
        )
        self._tick: int = 0
        self._cooldown_until: int = 0
        self._last_report: Optional[GuardReport] = None
        self._report_log: List[GuardReport] = []
        self._emergency_count: int = 0

    # ------------------------------------------------------------------ #
    # Main entry point
    # ------------------------------------------------------------------ #

    def evaluate(
        self,
        substrate_state: Any,
        circuit_neurons: Optional[List[Any]] = None,
    ) -> GuardReport:
        """Evaluate the substrate state and emit a report.

        ``substrate_state`` is expected to expose ``to_dict()`` (a
        :class:`SubstrateState` does). ``circuit_neurons`` is used to
        check for activation explosions.
        """
        measurements: Dict[str, float] = {}
        recommendations: Dict[str, float] = {}
        verdict = GuardVerdict.OK
        reason = "all signals within bounds"

        snap = (
            substrate_state.to_dict()
            if hasattr(substrate_state, "to_dict")
            else dict(substrate_state or {})
        )

        kuramoto = float(snap.get("kuramoto_order_parameter", 0.0))
        branching = float(snap.get("branching_ratio", 0.0))
        mean_energy = float(snap.get("mean_energy_field", 1.0))
        free_energy = float(snap.get("total_free_energy", 0.0))
        fatigue_count = int(snap.get("fatigue_count", 0))
        neuron_count = int(snap.get("neuron_count", 0) or 0)

        measurements.update(
            {
                "kuramoto_order_parameter": kuramoto,
                "branching_ratio": branching,
                "mean_energy_field": mean_energy,
                "total_free_energy": free_energy,
                "fatigue_count": float(fatigue_count),
            }
        )

        self._kuramoto_history.append(kuramoto)
        self._free_energy_history.append(free_energy)

        # Cooldown after an emergency: skip harsh recommendations.
        if self._cooldown_until > self._tick:
            self._tick += 1
            self._last_report = GuardReport(self._tick, GuardVerdict.OK, "cooldown")
            return self._last_report

        # 1) Hyper-synchrony (rigidity).
        if (
            len(self._kuramoto_history) >= self.kuramoto_window
            and all(
                k >= self.kuramoto_hyper_threshold
                for k in self._kuramoto_history
            )
        ):
            verdict = GuardVerdict.ADJUST
            reason = "hyper-synchrony: Kuramoto order parameter pegged high"
            recommendations["noise_injection"] = 0.05
            recommendations["coupling_strength_reduction"] = 0.10

        # 2) Hypo-synchrony (chaos).
        elif (
            len(self._kuramoto_history) >= self.kuramoto_window
            and all(
                k <= self.kuramoto_hypo_threshold
                for k in self._kuramoto_history
            )
        ):
            verdict = GuardVerdict.ADJUST
            reason = "hypo-synchrony: oscillators desynchronised"
            recommendations["coupling_strength_boost"] = 0.15

        # 3) Criticality loss.
        if branching > 0.0 and (
            branching < self.branching_low or branching > self.branching_high
        ):
            measurements["criticality_drift"] = abs(branching - 1.0)
            # Excitability recommendation comes from the monitor itself;
            # we just amplify the sign of the delta.
            if branching < self.branching_low:
                recommendations["excitability_delta"] = 0.3
            else:
                recommendations["excitability_delta"] = -0.3
            if verdict == GuardVerdict.OK:
                verdict = GuardVerdict.ADJUST
                reason = "criticality drift"

        # 4) Free-energy growth (unbounded surprise).
        if len(self._free_energy_history) >= self.free_energy_growth_window:
            recent = list(self._free_energy_history)[
                -self.free_energy_growth_window :
            ]
            head, tail = recent[0], recent[-1]
            if head > 1e-6 and tail / head >= self.free_energy_growth_ratio:
                verdict = GuardVerdict.DAMPEN
                reason = "free-energy explosion: prediction error unbounded"
                recommendations["prediction_learning_rate_reduction"] = 0.5

        # 5) Activation explosion (host circuit).
        if circuit_neurons:
            try:
                max_act = max(
                    abs(float(getattr(n, "activation", 0.0)))
                    for n in circuit_neurons
                )
            except Exception:
                max_act = 0.0
            measurements["max_activation"] = max_act
            if max_act > self.activation_max:
                verdict = GuardVerdict.EMERGENCY
                reason = "activation explosion in host circuit"
                recommendations["decay_boost"] = 2.0
                recommendations["threshold_boost"] = 0.1
                self._cooldown_until = self._tick + self.cooldown_ticks
                self._emergency_count += 1

        # 6) Energy collapse: too many neurons exhausted.
        if neuron_count > 0:
            fatigue_fraction = fatigue_count / neuron_count
            measurements["fatigue_fraction"] = fatigue_fraction
            if fatigue_fraction >= self.fatigue_fraction_emergency:
                verdict = max(verdict, GuardVerdict.DAMPEN, key=_severity)
                reason = (
                    f"energy collapse: {fatigue_fraction:.2%} neurons "
                    "below fatigue threshold"
                )
                recommendations["global_supply_boost"] = 1.5

            if mean_energy < self.energy_min_emergency:
                verdict = max(verdict, GuardVerdict.EMERGENCY, key=_severity)
                reason = "metabolic emergency: mean energy below safety floor"
                recommendations["halt_request"] = 1.0
                self._cooldown_until = self._tick + self.cooldown_ticks
                self._emergency_count += 1

        self._tick += 1
        report = GuardReport(
            tick=self._tick,
            verdict=verdict,
            reason=reason,
            recommendations=recommendations,
            measurements=measurements,
        )
        self._last_report = report
        self._report_log.append(report)
        if len(self._report_log) > 1024:
            self._report_log = self._report_log[-512:]
        if verdict in (GuardVerdict.EMERGENCY, GuardVerdict.DAMPEN):
            _logger.warning(
                "Substrate guard %s: %s (recs=%s)",
                verdict.value,
                reason,
                recommendations,
            )
        return report

    # ------------------------------------------------------------------ #
    # Convenience API
    # ------------------------------------------------------------------ #

    def should_halt(self) -> bool:
        return bool(
            self._last_report
            and self._last_report.recommendations.get("halt_request", 0.0) >= 1.0
        )

    @property
    def last_report(self) -> Optional[GuardReport]:
        return self._last_report

    @property
    def emergency_count(self) -> int:
        return self._emergency_count

    def save_log(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(
                [r.to_dict() for r in self._report_log],
                fh,
                indent=2,
            )

    def reset(self) -> None:
        self._kuramoto_history.clear()
        self._free_energy_history.clear()
        self._tick = 0
        self._cooldown_until = 0
        self._last_report = None
        self._report_log.clear()
        self._emergency_count = 0


def _severity(v: GuardVerdict) -> int:
    return {
        GuardVerdict.OK: 0,
        GuardVerdict.ADJUST: 1,
        GuardVerdict.DAMPEN: 2,
        GuardVerdict.EMERGENCY: 3,
    }[v]
