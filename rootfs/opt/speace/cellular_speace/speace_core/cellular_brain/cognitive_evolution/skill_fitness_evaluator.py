"""SkillFitnessEvaluator — T132: evaluates fitness of cognitive skill variants.

Metrics:
- task_success_rate
- latency_efficiency
- cognitive_stability_delta
- narrative_coherence_delta
- confidence_score_delta
"""

import time
from typing import Any, Dict, List, Optional


class SkillFitnessEvaluator:
    """Evaluates how well a skill variant performs in sandbox trials."""

    def __init__(self, trials_per_variant: int = 5) -> None:
        self._trials = trials_per_variant

    def evaluate(
        self,
        skill_variant: Dict[str, Any],
        trial_results: List[Dict[str, Any]],
        baseline: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Compute fitness score from sandbox trial results."""
        if not trial_results:
            return {"fitness": 0.0, "passed": False, "reason": "no_trials"}

        success_rate = sum(1 for t in trial_results if t.get("success", False)) / len(trial_results)
        avg_latency = sum(t.get("latency_ms", 0.0) for t in trial_results) / len(trial_results)
        stability_deltas = [t.get("stability_delta", 0.0) for t in trial_results]
        coherence_deltas = [t.get("coherence_delta", 0.0) for t in trial_results]
        confidence_deltas = [t.get("confidence_delta", 0.0) for t in trial_results]

        avg_stability = sum(stability_deltas) / len(stability_deltas) if stability_deltas else 0.0
        avg_coherence = sum(coherence_deltas) / len(coherence_deltas) if coherence_deltas else 0.0
        avg_confidence = sum(confidence_deltas) / len(confidence_deltas) if confidence_deltas else 0.0

        # Fitness: weighted composite
        fitness = (
            success_rate * 0.4
            + max(0.0, 1.0 - (avg_latency / 1000.0)) * 0.1
            + max(0.0, avg_stability) * 0.2
            + max(0.0, avg_coherence) * 0.15
            + max(0.0, avg_confidence) * 0.15
        )

        # Must beat baseline if provided
        baseline_fitness = baseline.get("fitness", 0.0) if baseline else 0.0
        passed = success_rate >= 0.6 and (baseline is None or fitness > baseline_fitness)

        return {
            "fitness": round(fitness, 4),
            "passed": passed,
            "success_rate": round(success_rate, 4),
            "avg_latency_ms": round(avg_latency, 2),
            "avg_stability_delta": round(avg_stability, 4),
            "avg_coherence_delta": round(avg_coherence, 4),
            "avg_confidence_delta": round(avg_confidence, 4),
            "baseline_fitness": round(baseline_fitness, 4),
            "timestamp": time.time(),
        }
