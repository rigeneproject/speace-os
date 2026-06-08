"""InfantCuriosityLayer — T158.

Purely observational curiosity layer.
Does NOT act autonomously.
Computes an "informative value" score for each experience based on:
- novelty (how different from past experiences)
- coherence (alignment with existing narrative)
- causal clarity (strength of causal links)
- multisensory consistency (sensor agreement)
- prediction error reduction (surprise vs expectation)

Higher score = more "interesting" to the infant mind.
"""

from __future__ import annotations

import json
import logging
import math
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional


class InfantCuriosityLayer:
    """Observational curiosity layer for SPEACE.

    Usage:
        layer = InfantCuriosityLayer(narrative_engine=..., causal_world_model=...)
        score = layer.evaluate_experience(event_dict)
        # score is a float 0-1; higher = more informative
    """

    def __init__(
        self,
        narrative_engine: Optional[Any] = None,
        causal_world_model: Optional[Any] = None,
        exploration_bonus_model: Optional[Any] = None,
        data_root: str = "data/experience/curiosity",
        history_window: int = 100,
    ) -> None:
        self._narrative = narrative_engine
        self._causal_world = causal_world_model
        self._exploration_bonus = exploration_bonus_model
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._scores_path = self._data_root / "curiosity_scores.jsonl"

        self._history: deque[Dict[str, Any]] = deque(maxlen=history_window)
        self._recent_narrative_hashes: set = set()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def evaluate_experience(self, event: Dict[str, Any]) -> float:
        """Compute curiosity/informative value for a single experience event.

        Returns a score in [0, 1]. Higher = more interesting.
        """
        scores: Dict[str, float] = {
            "novelty": self._novelty_score(event),
            "coherence": self._coherence_score(event),
            "causal_clarity": self._causal_clarity_score(event),
            "multisensory_consistency": self._multisensory_consistency_score(event),
            "prediction_error_reduction": self._prediction_error_reduction_score(event),
        }

        # Endogenous exploration bonus (intrinsic curiosity)
        endogenous_bonus = 0.0
        if self._exploration_bonus is not None:
            try:
                bonus_result = self._exploration_bonus.compute_bonus(event)
                endogenous_bonus = bonus_result.total_bonus
            except Exception:
                pass
        scores["endogenous_bonus"] = endogenous_bonus

        # Weighted average (equal weights by default, endogenous bonus added)
        weights = {"novelty": 0.25, "coherence": 0.20, "causal_clarity": 0.20,
                   "multisensory_consistency": 0.15, "prediction_error_reduction": 0.20,
                   "endogenous_bonus": 0.15}
        total = sum(weights[k] * scores.get(k, 0.0) for k in weights)
        result = round(max(0.0, min(1.0, total)), 4)

        record = {
            "timestamp": time.time(),
            "event_type": event.get("event_type", "unknown"),
            "scores": scores,
            "total": result,
        }
        self._history.append(record)
        self._persist(record)
        return result

    def get_top_interesting(self, n: int = 5) -> List[Dict[str, Any]]:
        """Return the most interesting recent experiences."""
        return sorted(self._history, key=lambda x: x["total"], reverse=True)[:n]

    def get_average_curiosity(self, window: int = 50) -> float:
        """Average curiosity score over recent experiences."""
        recent = list(self._history)[-window:]
        if not recent:
            return 0.0
        return round(sum(r["total"] for r in recent) / len(recent), 4)

    def suggest_next_observation(self) -> Optional[str]:
        """Suggest what to observe next based on curiosity patterns.

        Returns a human-readable suggestion string, NOT an action.
        """
        top = self.get_top_interesting(n=10)
        if not top:
            return None

        # Count event types among top interesting experiences
        type_counts: Dict[str, int] = {}
        for rec in top:
            et = rec.get("event_type", "unknown")
            type_counts[et] = type_counts.get(et, 0) + 1

        if not type_counts:
            return None

        preferred = max(type_counts, key=type_counts.get)
        suggestions: Dict[str, str] = {
            "multisensory_snapshot": "Potrebbe essere utile osservare ulteriori snapshot multisensoriali per rafforzare il grounding.",
            "infant_learning_event": "Continuare con sessioni di apprendimento guidato infantile sembra produttivo.",
            "causal_audit": "Esplorare ulteriori azioni causali per costruire il world model.",
            "speaker_beep": "Sperimentare con stimoli sonori potrebbe rivelare pattern interessanti.",
        }
        return suggestions.get(preferred, f"Esperienze di tipo '{preferred}' sembrano particolarmente informative.")

    # ------------------------------------------------------------------ #
    # Scoring heuristics
    # ------------------------------------------------------------------ #

    def _novelty_score(self, event: Dict[str, Any]) -> float:
        """Higher if event is dissimilar from recent history."""
        desc = event.get("description", "")
        # Simple hash-based novelty: if exact description seen before → low novelty
        h = hash(desc.lower().strip())
        if h in self._recent_narrative_hashes:
            return 0.2
        self._recent_narrative_hashes.add(h)
        # Also check historical descriptions
        recent = list(self._history)[-20:]
        for rec in recent:
            # compare to stored events — we don't have full event here, skip
            pass
        return 0.8

    def _coherence_score(self, event: Dict[str, Any]) -> float:
        """Higher if event aligns with existing narrative."""
        if self._narrative is None:
            return 0.5
        etype = event.get("event_type", "")
        similar = 0
        try:
            similar_events = self._narrative.by_type(etype, limit=10)
            similar = len(similar_events)
        except Exception:
            logging.getLogger(__name__).warning("Curiosity layer event failed for coherence", exc_info=True)
        # Some similar events = coherent, but too many = redundant
        if similar == 0:
            return 0.3  # novel but isolated
        if similar <= 5:
            return 0.8  # nicely integrated
        return 0.5  # becoming redundant

    def _causal_clarity_score(self, event: Dict[str, Any]) -> float:
        """Higher if event has strong causal links."""
        if self._causal_world is None:
            return 0.5
        action = event.get("action_name") or event.get("event_type", "")
        if not action:
            return 0.5
        try:
            predictions = self._causal_world.predict(action, {}, top_k=3)
            if predictions:
                avg_conf = sum(p.get("confidence", 0) for p in predictions) / len(predictions)
                return round(avg_conf, 4)
        except Exception:
            logging.getLogger(__name__).warning("Curiosity layer event failed for causal clarity", exc_info=True)
        return 0.3

    def _multisensory_consistency_score(self, event: Dict[str, Any]) -> float:
        """Higher if multiple sensors agree."""
        meta = event.get("metadata", {})
        if not isinstance(meta, dict):
            return 0.5
        sensors = [k for k in ("camera", "microphone", "screen") if k in meta]
        if len(sensors) >= 2:
            return 0.9
        if len(sensors) == 1:
            return 0.6
        return 0.4

    def _prediction_error_reduction_score(self, event: Dict[str, Any]) -> float:
        """Higher if event reduces uncertainty / surprise."""
        # If the event matches a predicted outcome, it's "understood"
        if self._causal_world is None:
            return 0.5
        action = event.get("action_name") or event.get("event_type", "")
        effect = event.get("effect") or event.get("description", "")
        if not action or not effect:
            return 0.5
        try:
            predictions = self._causal_world.predict(action, {}, top_k=5)
            for p in predictions:
                if effect.lower() in p.get("effect", "").lower():
                    return round(p.get("confidence", 0.5), 4)
        except Exception:
            logging.getLogger(__name__).warning("Curiosity layer event failed for prediction error reduction", exc_info=True)
        return 0.3

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _persist(self, record: Dict[str, Any]) -> None:
        try:
            with self._scores_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass
