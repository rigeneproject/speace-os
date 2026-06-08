"""FitnessEvaluator — measures the impact of proposals vs baseline.

The evaluator scores a candidate proposal on:
  - baseline coherence retention
  - predicted accuracy uplift
  - risk of regression
  - governance cost

All inputs are read-only; no code mutation.
"""

from __future__ import annotations

import json
import logging
import statistics
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)


class FitnessEvaluator:
    """Computes a composite fitness score in ``[0, 1]``."""

    def __init__(self, data_root: str | Path = "data") -> None:
        self.data_root = Path(data_root)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def measure(
        self,
        proposal: Dict[str, Any],
        baseline_metrics: Optional[Dict[str, Any]] = None,
        candidate_metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return a fitness dict for a single proposal."""
        baseline = baseline_metrics or self._latest_benchmark()
        candidate = candidate_metrics or baseline
        coherence = self._score_coherence(baseline, candidate)
        accuracy = self._score_accuracy(baseline, candidate)
        stability = self._score_stability(proposal)
        cost = self._score_cost(proposal)
        composite = 0.4 * coherence + 0.3 * accuracy + 0.2 * stability + 0.1 * (1.0 - cost)
        return {
            "fitness": round(max(0.0, min(1.0, composite)), 4),
            "coherence": round(coherence, 4),
            "accuracy": round(accuracy, 4),
            "stability": round(stability, 4),
            "cost": round(cost, 4),
        }

    def rank(self, proposals: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort proposals by ``fitness`` descending, returning a list of
        ``(proposal, fitness)`` dicts.
        """
        scored: List[Dict[str, Any]] = []
        for p in proposals:
            score = self.measure(p)
            scored.append({"proposal": p, **score})
        scored.sort(key=lambda d: d["fitness"], reverse=True)
        return scored

    # ------------------------------------------------------------------ #
    # Scoring helpers
    # ------------------------------------------------------------------ #
    def _score_coherence(self, base: Dict[str, Any], cand: Dict[str, Any]) -> float:
        b = float(base.get("coherence_phi", 0.0))
        c = float(cand.get("coherence_phi", b))
        # Reward retention, penalise drops > 20%.
        if b <= 0:
            return 0.5
        ratio = c / b
        return max(0.0, min(1.0, ratio * 0.8 + 0.2))

    def _score_accuracy(self, base: Dict[str, Any], cand: Dict[str, Any]) -> float:
        b = float(base.get("accuracy", 0.0))
        c = float(cand.get("accuracy", b))
        if c >= b:
            return min(1.0, 0.5 + (c - b) * 2.0)
        return max(0.0, 0.5 * (c / b)) if b > 0 else 0.0

    def _score_stability(self, proposal: Dict[str, Any]) -> float:
        cat = str(proposal.get("category", ""))
        if cat == "investigation":
            return 0.6  # informational, low risk
        if cat == "refactor":
            return 0.7
        return 0.5

    def _score_cost(self, proposal: Dict[str, Any]) -> float:
        files = proposal.get("files_hint", "")
        n = len([x for x in str(files).split(",") if x.strip()])
        # Normalise to [0, 1] where 0 = cheap, 1 = expensive.
        return max(0.0, min(1.0, n / 10.0))

    def _latest_benchmark(self) -> Dict[str, Any]:
        path = self.data_root / "evolution_daemon" / "benchmarks" / "latest.json"
        if not path.exists():
            return {"coherence_phi": 0.0, "accuracy": 0.0}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            comps = data.get("components", {}) or {}
            return {
                "coherence_phi": float(comps.get("adaptation_after_error", 0.0)),
                "accuracy": float(comps.get("arc_agi_subset", 0.0)),
            }
        except (json.JSONDecodeError, OSError):
            return {"coherence_phi": 0.0, "accuracy": 0.0}

    # ------------------------------------------------------------------ #
    # Aggregation utility
    # ------------------------------------------------------------------ #
    @staticmethod
    def aggregate(fitnesses: List[Dict[str, Any]]) -> Dict[str, float]:
        """Aggregate a list of fitness dicts into population stats."""
        if not fitnesses:
            return {"mean": 0.0, "stdev": 0.0, "max": 0.0, "min": 0.0, "count": 0}
        values = [f.get("fitness", 0.0) for f in fitnesses]
        return {
            "mean": round(statistics.fmean(values), 4),
            "stdev": round(statistics.pstdev(values), 4) if len(values) > 1 else 0.0,
            "max": round(max(values), 4),
            "min": round(min(values), 4),
            "count": len(values),
        }
