"""T-HDAS — Homeostatic Drive → Action Selector.

Couples :class:`GlobalHomeostaticDrive` to GOAP-style action selection.

How it works
------------
The :class:`ActionBias` model re-weights every action proposal with a
bias derived from the four canonical drives (exploration, stability,
survival, efficiency). The mapping is intentionally simple but
biologically motivated:

* **Survival high**  → prefer self-preservation actions
  (e.g. ``request_sleep``, ``reduce_load``).
* **Exploration high** → prefer novelty-seeking actions
  (e.g. ``explore``, ``sample_unknown``).
* **Stability high**  → prefer conservative actions
  (e.g. ``consolidate``, ``checkpoint``).
* **Efficiency low**  → prefer resource-conservation actions
  (e.g. ``hibernate``, ``garbage_collect``).

The class also exposes a :class:`BiasDecision` value object so callers
can audit *why* a particular action was preferred.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

_logger = logging.getLogger(__name__)


# Default affinity table: action_name -> {drive_name -> weight}
# Positive weight ⇒ the drive amplifies the action's priority.
# Negative weight ⇒ the drive suppresses it.
DEFAULT_AFFINITIES: Dict[str, Dict[str, float]] = {
    "explore": {"exploration": 1.0, "stability": -0.3, "efficiency": -0.2},
    "sample_unknown": {"exploration": 1.0, "stability": -0.2},
    "consolidate": {"stability": 1.0, "efficiency": 0.4},
    "checkpoint": {"stability": 0.8, "survival": 0.2, "efficiency": 0.3},
    "request_sleep": {"survival": 1.0, "stability": 0.4, "efficiency": 0.6},
    "request_resume": {"exploration": 0.5, "efficiency": -0.4},
    "reduce_load": {"survival": 0.7, "efficiency": 0.8},
    "hibernate": {"survival": 0.5, "efficiency": 1.0, "exploration": -0.6},
    "garbage_collect": {"efficiency": 0.7, "stability": 0.4},
    "recover": {"survival": 0.8, "efficiency": 0.3},
    "actuate": {"survival": -0.2, "efficiency": -0.4, "exploration": 0.3},
    "observe": {"stability": 0.2, "efficiency": 0.2, "exploration": 0.3},
}


@dataclass
class BiasDecision:
    """Decision record produced by :meth:`ActionBias.select`."""

    chosen: Optional[str]
    scores: Dict[str, float] = field(default_factory=dict)
    contributions: Dict[str, Dict[str, float]] = field(default_factory=dict)
    drives_snapshot: Dict[str, float] = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chosen": self.chosen,
            "scores": dict(self.scores),
            "contributions": {
                k: dict(v) for k, v in self.contributions.items()
            },
            "drives": dict(self.drives_snapshot),
            "reason": self.reason,
        }


class ActionBias:
    """Bias action selection according to homeostatic drives."""

    def __init__(
        self,
        affinity_table: Optional[Dict[str, Dict[str, float]]] = None,
        base_temperature: float = 1.0,
    ):
        self.affinity_table = dict(affinity_table or DEFAULT_AFFINITIES)
        self.base_temperature = float(base_temperature)
        self._last_decision: Optional[BiasDecision] = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def register_action(self, action_name: str, affinity: Optional[Dict[str, float]] = None) -> None:
        """Register (or overwrite) the affinity of a single action."""
        if affinity is None:
            self.affinity_table.setdefault(action_name, {})
        else:
            self.affinity_table[action_name] = dict(affinity)

    def _drive_snapshot(self, homeostatic_drive: Any) -> Dict[str, float]:
        snap: Dict[str, float] = {}
        for name in homeostatic_drive.list_drives():
            try:
                snap[name] = float(homeostatic_drive.get_drive_signal(name))
            except Exception:
                snap[name] = 0.0
        return snap

    def score_actions(
        self,
        candidate_actions: List[str],
        homeostatic_drive: Any,
    ) -> Dict[str, float]:
        """Return a score per action based on current drive signals."""
        drives = self._drive_snapshot(homeostatic_drive)
        scores: Dict[str, float] = {}
        for action in candidate_actions:
            affinity = self.affinity_table.get(action, {})
            score = 0.0
            for drive_name, weight in affinity.items():
                score += weight * drives.get(drive_name, 0.0)
            # Add a small exploration bonus for unregistered actions so
            # novel ones aren't permanently ignored.
            if not affinity:
                score += 0.05 * drives.get("exploration", 0.0)
            scores[action] = float(score)
        return scores

    def select(
        self,
        candidate_actions: List[str],
        homeostatic_drive: Any,
        base_scores: Optional[Dict[str, float]] = None,
    ) -> BiasDecision:
        """Choose an action, returning a transparent :class:`BiasDecision`.

        ``base_scores`` is an optional dict of a-priori utilities
        (e.g. from the active inference EFE) that the drive bias
        *adds to* rather than overwrites.
        """
        if not candidate_actions:
            return BiasDecision(chosen=None, reason="no_candidates")

        base_scores = base_scores or {}
        bias_scores = self.score_actions(candidate_actions, homeostatic_drive)
        contributions: Dict[str, Dict[str, float]] = {
            action: {"bias": bias_scores.get(action, 0.0)}
            for action in candidate_actions
        }

        combined: Dict[str, float] = {}
        for action in candidate_actions:
            base = float(base_scores.get(action, 0.0))
            bias = float(bias_scores.get(action, 0.0))
            # We *subtract* base because low EFE = preferred; we *add*
            # bias because high drive alignment = preferred.
            combined[action] = -base + bias
            contributions[action]["base"] = base

        # Softmax selection with the configured temperature.
        chosen = self._softmax_pick(combined)
        drives_snapshot = self._drive_snapshot(homeostatic_drive)
        decision = BiasDecision(
            chosen=chosen,
            scores=combined,
            contributions=contributions,
            drives_snapshot=drives_snapshot,
            reason=(
                "softmax over (-base + bias)"
                if chosen is not None
                else "no_evaluable_action"
            ),
        )
        self._last_decision = decision
        return decision

    def rank(
        self,
        candidate_actions: List[str],
        homeostatic_drive: Any,
        base_scores: Optional[Dict[str, float]] = None,
    ) -> List[str]:
        """Return the candidate actions sorted by descending score."""
        decision = self.select(candidate_actions, homeostatic_drive, base_scores)
        return sorted(decision.scores, key=decision.scores.get, reverse=True)

    # ------------------------------------------------------------------ #
    # Convenience for active-inference integration
    # ------------------------------------------------------------------ #

    def select_from_active_inference(
        self,
        homeostatic_drive: Any,
        active_inference: Any,
    ) -> BiasDecision:
        """Pick an action using active inference EFE as base scores."""
        actions = list(getattr(active_inference, "actions", {}).keys())
        base_scores: Dict[str, float] = {}
        for a in actions:
            try:
                base_scores[a] = float(active_inference.expected_free_energy(a))
            except Exception:
                base_scores[a] = 0.0
        return self.select(actions, homeostatic_drive, base_scores)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _softmax_pick(self, scores: Dict[str, float]) -> Optional[str]:
        if not scores:
            return None
        temp = max(1e-3, self.base_temperature)
        max_score = max(scores.values())
        exps = {a: math.exp((s - max_score) / temp) for a, s in scores.items()}
        total = sum(exps.values())
        if total <= 0:
            # Fallback: pick the highest-scoring deterministically.
            return max(scores, key=scores.get)
        # Deterministic argmax to keep tests reproducible.
        best_action = max(exps, key=exps.get)
        return best_action

    @property
    def last_decision(self) -> Optional[BiasDecision]:
        return self._last_decision
