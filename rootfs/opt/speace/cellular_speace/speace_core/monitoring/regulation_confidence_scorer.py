"""RegulationConfidenceScorer — epistemic memory of regulation outcomes (T104).

Tracks every approved regulation, its pre/post state, and outcome.
Provides a confidence score [0,1] for new proposals based on
historical similarity.
"""

import json
import pathlib
import time
from typing import Any, Dict, List, Optional


class RegulationConfidenceScorer:
    """Scores regulation proposals using historical outcomes."""

    def __init__(
        self,
        outcomes_path: str = "data/regulation/regulation_outcomes.jsonl",
        max_history: int = 5000,
    ) -> None:
        self.outcomes_path = pathlib.Path(outcomes_path)
        self.outcomes_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_history = max_history

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _read_outcomes(self, limit: int = 0) -> List[Dict[str, Any]]:
        if not self.outcomes_path.exists():
            return []
        outcomes: List[Dict[str, Any]] = []
        try:
            with self.outcomes_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        outcomes.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return []
        return outcomes[-limit:] if limit else outcomes

    def _persist(self, record: Dict[str, Any]) -> None:
        try:
            with self.outcomes_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _trim(self) -> None:
        outcomes = self._read_outcomes()
        if len(outcomes) > self.max_history:
            outcomes = outcomes[-self.max_history:]
            try:
                with self.outcomes_path.open("w", encoding="utf-8") as f:
                    for o in outcomes:
                        f.write(json.dumps(o, ensure_ascii=False) + "\n")
            except OSError:
                pass

    # ------------------------------------------------------------------ #
    # Confidence scoring
    # ------------------------------------------------------------------ #

    def score(
        self,
        proposed_action: str,
        alert_type: str,
        state: Dict[str, Any],
        lookback: int = 50,
    ) -> Dict[str, Any]:
        """Return confidence metrics for a proposed regulation."""
        outcomes = self._read_outcomes(limit=lookback)
        if not outcomes:
            return {
                "confidence": 0.5,
                "based_on_history": False,
                "previous_outcomes": [],
                "similar_count": 0,
                "success_rate": None,
            }

        # Filter by alert_type and action similarity
        similar = [
            o for o in outcomes
            if o.get("alert_type") == alert_type
            and _action_similarity(o.get("proposed_action", ""), proposed_action) > 0.5
        ]

        if not similar:
            return {
                "confidence": 0.5,
                "based_on_history": False,
                "previous_outcomes": [],
                "similar_count": 0,
                "success_rate": None,
            }

        # Weight by recency
        now = time.time()
        weights = []
        scores = []
        for o in similar:
            age = max(1.0, now - o.get("timestamp", now))
            w = 1.0 / (1.0 + age / 86400.0)  # decay over days
            outcome = o.get("outcome", "unknown")
            if outcome == "success":
                s = 1.0
            elif outcome == "rollback":
                s = 0.0
            elif outcome == "partial":
                s = 0.5
            else:
                s = 0.5
            weights.append(w)
            scores.append(s)

        total_w = sum(weights)
        if total_w == 0:
            confidence = 0.5
        else:
            confidence = sum(s * w for s, w in zip(scores, weights)) / total_w

        successes = sum(1 for o in similar if o.get("outcome") == "success")
        success_rate = successes / len(similar)

        return {
            "confidence": round(max(0.0, min(1.0, confidence)), 4),
            "based_on_history": True,
            "previous_outcomes": [
                {
                    "proposal_id": o.get("proposal_id"),
                    "outcome": o.get("outcome"),
                    "health_delta": o.get("health_delta"),
                    "timestamp": o.get("timestamp"),
                }
                for o in similar[-5:]
            ],
            "similar_count": len(similar),
            "success_rate": round(success_rate, 4),
        }

    # ------------------------------------------------------------------ #
    # Outcome recording
    # ------------------------------------------------------------------ #

    def record_outcome(
        self,
        proposal_id: str,
        alert_type: str,
        proposed_action: str,
        pre_health: float,
        post_health: float,
        outcome: str,  # success | rollback | partial | unknown
    ) -> None:
        record = {
            "proposal_id": proposal_id,
            "alert_type": alert_type,
            "proposed_action": proposed_action,
            "pre_health": pre_health,
            "post_health": post_health,
            "health_delta": round(post_health - pre_health, 6),
            "outcome": outcome,
            "timestamp": time.time(),
        }
        self._persist(record)
        self._trim()


def _action_similarity(a: str, b: str) -> float:
    """Simple word-overlap similarity for action strings."""
    aw = set(a.lower().split())
    bw = set(b.lower().split())
    if not aw or not bw:
        return 0.0
    inter = len(aw & bw)
    union = len(aw | bw)
    return inter / union if union else 0.0
