"""CausalWorldModel — T153.

Accumulates causal observations from CausalLearningAuditor into a structured
predictive model:

    action → observed effect → confidence → context → future prediction

Persisted as JSONL. Provides query by action similarity.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class CausalWorldModel:
    """Lightweight causal world model built from audited embodied actions."""

    def __init__(self, data_root: str = "data/embodiment/causal_world_model") -> None:
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._observations_path = self._data_root / "observations.jsonl"
        self._observations: List[Dict[str, Any]] = []
        self._load()

    # ------------------------------------------------------------------ #
    # Recording
    # ------------------------------------------------------------------ #

    def record_observation(
        self,
        action_name: str,
        action_params: Dict[str, Any],
        effect: str,
        confidence: float,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Store a new causal observation."""
        entry = {
            "timestamp": time.time(),
            "action_name": action_name,
            "action_params": action_params,
            "effect": effect,
            "confidence": round(max(0.0, min(1.0, confidence)), 4),
            "context": context or {},
        }
        self._observations.append(entry)
        self._persist(entry)
        return entry

    def ingest_report(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Ingest a full CausalLearningAuditor report."""
        entries: List[Dict[str, Any]] = []
        action = report.get("action", {})
        hypotheses = report.get("hypotheses", [])
        for h in hypotheses:
            entry = self.record_observation(
                action_name=action.get("name", "unknown"),
                action_params=action.get("params", {}),
                effect=h.get("effect", "unknown"),
                confidence=h.get("confidence", 0.0),
                context={
                    "cause": h.get("cause"),
                    "pre_state_summary": report.get("pre_state_summary"),
                    "post_state_summary": report.get("post_state_summary"),
                },
            )
            entries.append(entry)
        return entries

    # ------------------------------------------------------------------ #
    # Prediction
    # ------------------------------------------------------------------ #

    def predict(self, action_name: str, action_params: Optional[Dict[str, Any]] = None, top_k: int = 3) -> List[Dict[str, Any]]:
        """Return the most likely effects for a given action based on history."""
        action_params = action_params or {}
        scored: List[tuple] = []
        for obs in self._observations:
            sim = self._action_similarity(action_name, action_params, obs)
            if sim > 0.0:
                scored.append((sim, obs))

        scored.sort(key=lambda x: x[0], reverse=True)
        seen_effects: set[str] = set()
        results: List[Dict[str, Any]] = []
        for sim, obs in scored:
            effect = obs["effect"]
            if effect in seen_effects:
                continue
            seen_effects.add(effect)
            results.append({
                "effect": effect,
                "confidence": obs["confidence"],
                "similarity": round(sim, 4),
                "observation_count": self._count_observations(action_name, effect),
            })
            if len(results) >= top_k:
                break
        return results

    def predict_confidence(self, action_name: str, effect: str) -> float:
        """Aggregate confidence for a specific action→effect pair."""
        total_confidence = 0.0
        count = 0
        for obs in self._observations:
            if obs["action_name"] == action_name and obs["effect"] == effect:
                total_confidence += obs["confidence"]
                count += 1
        return round(total_confidence / max(count, 1), 4)

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def recent_observations(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._observations[-limit:]

    def by_action(self, action_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        return [o for o in self._observations if o["action_name"] == action_name][-limit:]

    def summary(self) -> Dict[str, Any]:
        total = len(self._observations)
        actions: Dict[str, int] = {}
        effects: Dict[str, int] = {}
        for obs in self._observations:
            a = obs["action_name"]
            e = obs["effect"]
            actions[a] = actions.get(a, 0) + 1
            effects[e] = effects.get(e, 0) + 1
        return {
            "total_observations": total,
            "unique_actions": len(actions),
            "unique_effects": len(effects),
            "action_distribution": actions,
            "effect_distribution": effects,
            "average_confidence": round(
                sum(o["confidence"] for o in self._observations) / max(total, 1), 4
            ),
        }

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _persist(self, entry: Dict[str, Any]) -> None:
        try:
            with self._observations_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _load(self) -> None:
        if not self._observations_path.exists():
            return
        lines = self._observations_path.read_text(encoding="utf-8").strip().split("\n")
        for line in lines:
            try:
                self._observations.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _action_similarity(
        name: str,
        params: Dict[str, Any],
        obs: Dict[str, Any],
    ) -> float:
        if obs["action_name"] != name:
            return 0.0
        # Simple param overlap Jaccard
        obs_params = obs.get("action_params", {})
        keys = set(params.keys()) | set(obs_params.keys())
        if not keys:
            return 1.0
        overlap = sum(1 for k in keys if params.get(k) == obs_params.get(k))
        return overlap / len(keys)

    def _count_observations(self, action_name: str, effect: str) -> int:
        return sum(
            1
            for o in self._observations
            if o["action_name"] == action_name and o["effect"] == effect
        )
