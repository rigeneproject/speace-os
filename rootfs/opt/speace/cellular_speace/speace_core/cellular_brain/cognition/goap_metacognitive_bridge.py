"""GOAPMetacognitiveBridge — connects GOAP planning to metacognitive evaluation (T166).

Queries EpistemicConfidenceEngine and CognitiveStrategyEvaluator to decide if
GOAP is the right strategy, and to estimate confidence in a generated plan.
"""

from typing import Any, Dict, Optional

from speace_core.cellular_brain.cognition.goap_planner import GOAPPlanner
from speace_core.cellular_brain.metacognition.confidence_engine import ConfidenceEngine
from speace_core.cellular_brain.metacognition.cognitive_strategy_evaluator import CognitiveStrategyEvaluator


class GOAPMetacognitiveBridge:
    """Evaluates GOAP plans via metacognitive layers."""

    CONFIDENCE_THRESHOLD: float = 0.3

    def __init__(
        self,
        confidence_engine: Optional[Any] = None,
        strategy_evaluator: Optional[Any] = None,
    ) -> None:
        self._confidence_engine = confidence_engine
        self._strategy_evaluator = strategy_evaluator

    def evaluate_plan(
        self,
        plan: Optional[Dict[str, Any]],
        current_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Return evaluation dict with confidence, strategy fitness, and fallback signal."""
        if plan is None:
            return {
                "proceed": False,
                "confidence": 0.0,
                "strategy_fit": 0.0,
                "fallback_to_reflex": True,
                "reason": "no_plan_found",
            }

        # Confidence estimation
        confidence = 0.5
        if self._confidence_engine is not None and hasattr(self._confidence_engine, "evaluate"):
            try:
                confidence = self._confidence_engine.evaluate(plan, current_state)
            except Exception:
                pass

        # Strategy fitness
        strategy_fit = 0.5
        if self._strategy_evaluator is not None and hasattr(self._strategy_evaluator, "fitness"):
            try:
                strategy_fit = self._strategy_evaluator.fitness("goap", current_state)
            except Exception:
                pass

        proceed = confidence >= self.CONFIDENCE_THRESHOLD and strategy_fit >= self.CONFIDENCE_THRESHOLD

        return {
            "proceed": proceed,
            "confidence": round(confidence, 3),
            "strategy_fit": round(strategy_fit, 3),
            "fallback_to_reflex": not proceed,
            "reason": "confidence_too_low" if confidence < self.CONFIDENCE_THRESHOLD else (
                "strategy_mismatch" if strategy_fit < self.CONFIDENCE_THRESHOLD else "ok"
            ),
        }

    def snapshot(self) -> Dict[str, Any]:
        return {
            "confidence_threshold": self.CONFIDENCE_THRESHOLD,
            "has_confidence_engine": self._confidence_engine is not None,
            "has_strategy_evaluator": self._strategy_evaluator is not None,
        }
