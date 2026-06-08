"""CognitiveStrategyEvaluator — T130: evaluates efficacy of cognitive strategies.

Tracks regulation outcomes and cognitive trends to determine whether
strategies (e.g. "increase stability bias", "reduce exploration drive")
improve system health over time.
"""

import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.metacognition.meta_state import MetaState, StrategyEvaluation


class CognitiveStrategyEvaluator:
    """Evaluates whether cognitive strategies improve system state."""

    def __init__(self, outcome_window: int = 20) -> None:
        self._outcome_window = outcome_window
        # strategy_name -> list of (timestamp, pre_health, post_health, improved)
        self._outcomes: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def record_outcome(
        self,
        strategy_name: str,
        pre_health: float,
        post_health: float,
        regulation_id: str = "",
    ) -> StrategyEvaluation:
        """Record the result of applying a strategy."""
        delta = post_health - pre_health
        improved = delta > 0.05
        record = {
            "timestamp": time.time(),
            "pre_health": pre_health,
            "post_health": post_health,
            "delta": delta,
            "improved": improved,
            "regulation_id": regulation_id,
        }
        self._outcomes[strategy_name].append(record)
        # Trim old records
        if len(self._outcomes[strategy_name]) > self._outcome_window:
            self._outcomes[strategy_name].pop(0)
        return StrategyEvaluation(
            regulation_id=regulation_id,
            pre_health=pre_health,
            post_health=post_health,
            delta=delta,
            improved=improved,
        )

    def evaluate_strategy(self, strategy_name: str) -> Dict[str, Any]:
        """Aggregate evaluation for a named strategy."""
        records = self._outcomes.get(strategy_name, [])
        if not records:
            return {
                "strategy": strategy_name,
                "sample_count": 0,
                "success_rate": 0.0,
                "mean_delta": 0.0,
                "verdict": "unknown",
            }
        improved_count = sum(1 for r in records if r["improved"])
        success_rate = improved_count / len(records)
        mean_delta = sum(r["delta"] for r in records) / len(records)

        if success_rate >= 0.7 and mean_delta > 0.1:
            verdict = "effective"
        elif success_rate >= 0.4 and mean_delta > 0.0:
            verdict = "mixed"
        else:
            verdict = "ineffective"

        return {
            "strategy": strategy_name,
            "sample_count": len(records),
            "success_rate": round(success_rate, 4),
            "mean_delta": round(mean_delta, 4),
            "verdict": verdict,
        }

    def evaluate_all(self) -> Dict[str, Any]:
        """Evaluate all recorded strategies."""
        return {
            strategy: self.evaluate_strategy(strategy)
            for strategy in self._outcomes.keys()
        }

    def best_strategy(self) -> Optional[str]:
        """Return the name of the best-performing strategy."""
        if not self._outcomes:
            return None
        best = None
        best_score = -1.0
        for name, records in self._outcomes.items():
            if not records:
                continue
            improved_count = sum(1 for r in records if r["improved"])
            success_rate = improved_count / len(records)
            mean_delta = sum(r["delta"] for r in records) / len(records)
            score = success_rate * 0.6 + max(0.0, mean_delta) * 0.4
            if score > best_score:
                best_score = score
                best = name
        return best

    def trend_for_strategy(self, strategy_name: str) -> List[float]:
        """Return delta trend for a strategy."""
        return [r["delta"] for r in self._outcomes.get(strategy_name, [])]
