"""T-CFC — Criticality Feedback to Circuit.

Consumes :class:`CriticalityMonitor` recommendations and translates them
into concrete, *bounded* modulations of the host circuit:

* When the branching ratio ``sigma`` is below ~1.0 the system is
  *subcritical*: too few avalanches propagate, information transfer is
  limited. The feedback boosts per-neuron excitability.
* When ``sigma`` is above ~1.0 the system is *supercritical*:
  avalanches cascade, the network risks runaway. The feedback raises
  thresholds and accelerates decay.

The goal is to self-organise near criticality (sigma ≈ 1.0), which
empirically maximises dynamic range, information transmission and
storage capacity.

This module never overwrites the host circuit unconditionally: it
returns a :class:`CriticalityFeedback` value object that callers apply
or refuse.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

_logger = logging.getLogger(__name__)


@dataclass
class CriticalityFeedback:
    """A bounded modulation request derived from the branching ratio."""

    branching_ratio: float
    target: float
    excitability_delta: float
    threshold_delta: float
    plasticity_scale: float
    decay_scale: float
    reason: str

    def to_dict(self) -> Dict[str, float]:
        return {
            "branching_ratio": self.branching_ratio,
            "target": self.target,
            "excitability_delta": self.excitability_delta,
            "threshold_delta": self.threshold_delta,
            "plasticity_scale": self.plasticity_scale,
            "decay_scale": self.decay_scale,
            "reason": self.reason,
        }


class CriticalityFeedbackController:
    """Translate criticality monitoring into circuit-level feedback."""

    def __init__(
        self,
        target_branching_ratio: float = 1.0,
        max_excitability_delta: float = 0.3,
        max_threshold_delta: float = 0.15,
        max_plasticity_scale: float = 2.0,
        plasticity_floor: float = 0.25,
        decay_floor: float = 0.5,
        decay_ceiling: float = 2.0,
    ):
        self.target = float(target_branching_ratio)
        self.max_excitability_delta = float(max_excitability_delta)
        self.max_threshold_delta = float(max_threshold_delta)
        self.max_plasticity_scale = float(max_plasticity_scale)
        self.plasticity_floor = float(plasticity_floor)
        self.decay_floor = float(decay_floor)
        self.decay_ceiling = float(decay_ceiling)
        self._last_feedback: Optional[CriticalityFeedback] = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def step(self, criticality_monitor: Any) -> CriticalityFeedback:
        """Return the feedback to apply given the current monitor state."""
        try:
            rec = criticality_monitor.recommend_modulation()
        except Exception as exc:  # pragma: no cover - defensive
            _logger.debug("Criticality monitor unavailable: %s", exc)
            return self._identity_feedback()

        br = float(rec.get("current_branching_ratio", 0.0))
        raw_delta = float(rec.get("excitability_delta", 0.0))
        reason = str(rec.get("reason", "unknown"))

        excitability_delta = _clip(raw_delta, -self.max_excitability_delta, self.max_excitability_delta)
        # The threshold delta is *opposite* to excitability: when we
        # need more activity, we lower thresholds; when we need less, we
        # raise them.
        threshold_delta = -excitability_delta * 0.5
        threshold_delta = _clip(
            threshold_delta, -self.max_threshold_delta, self.max_threshold_delta
        )

        # Plasticity: subcritical regimes benefit from more exploration
        # (boost LTP); supercritical regimes benefit from consolidation
        # (slight reduction).
        if br < 1.0:
            plasticity_scale = 1.0 + 0.5 * (1.0 - br)
        elif br > 1.0:
            plasticity_scale = max(
                self.plasticity_floor, 1.0 - 0.25 * (br - 1.0)
            )
        else:
            plasticity_scale = 1.0
        plasticity_scale = min(self.max_plasticity_scale, plasticity_scale)

        # Decay: when supercritical, accelerate decay to bleed off energy.
        if br > 1.0:
            decay_scale = min(self.decay_ceiling, 1.0 + 0.5 * (br - 1.0))
        else:
            decay_scale = max(self.decay_floor, 1.0 - 0.25 * (1.0 - br))

        feedback = CriticalityFeedback(
            branching_ratio=br,
            target=self.target,
            excitability_delta=excitability_delta,
            threshold_delta=threshold_delta,
            plasticity_scale=plasticity_scale,
            decay_scale=decay_scale,
            reason=reason,
        )
        self._last_feedback = feedback
        return feedback

    def apply_to_circuit(
        self,
        circuit: Any,
        feedback: CriticalityFeedback,
    ) -> int:
        """Apply *feedback* to every neuron in *circuit* in place.

        Returns the number of neurons modified. The modifications are:
        ``activation`` shifted by ``excitability_delta`` (clipped to
        [-1, 1]); ``threshold`` shifted by ``threshold_delta`` (clipped
        to [0.05, 1.0]); ``plasticity_rate`` scaled by
        ``plasticity_scale``; ``decay`` scaled by ``decay_scale``.
        """
        neurons = (
            list(getattr(circuit, "input_neurons", []) or [])
            + list(getattr(circuit, "hidden_neurons", []) or [])
            + list(getattr(circuit, "output_neurons", []) or [])
        )
        modified = 0
        for n in neurons:
            try:
                if hasattr(n, "activation"):
                    n.activation = max(
                        -1.0,
                        min(1.0, float(n.activation) + feedback.excitability_delta),
                    )
                if hasattr(n, "threshold"):
                    n.threshold = max(
                        0.05,
                        min(1.0, float(n.threshold) + feedback.threshold_delta),
                    )
                if hasattr(n, "plasticity_rate"):
                    n.plasticity_rate = max(
                        0.0, float(n.plasticity_rate) * feedback.plasticity_scale
                    )
                if hasattr(n, "decay"):
                    n.decay = max(
                        0.0, float(n.decay) * feedback.decay_scale
                    )
                modified += 1
            except Exception:
                continue
        return modified

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #

    @property
    def last_feedback(self) -> Optional[CriticalityFeedback]:
        return self._last_feedback

    def _identity_feedback(self) -> CriticalityFeedback:
        fb = CriticalityFeedback(
            branching_ratio=0.0,
            target=self.target,
            excitability_delta=0.0,
            threshold_delta=0.0,
            plasticity_scale=1.0,
            decay_scale=1.0,
            reason="criticality_disabled",
        )
        self._last_feedback = fb
        return fb


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))
