"""MultiNodeAggregator — aggregates states from distributed SPEACE nodes (T106).

Includes Node Personality Drift metrics:
  - drive divergence
  - self-model divergence
  - narrative divergence
  - decisional divergence

Exposes:
  consensus_health_score, max_divergence, node_count, personality_drift
"""

import math
from typing import Any, Dict, List, Optional


class MultiNodeAggregator:
    """Aggregates remote node states and computes cross-node drift."""

    def __init__(self) -> None:
        self._states: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------ #
    # State ingestion
    # ------------------------------------------------------------------ #

    def ingest(self, node_id: str, state: Dict[str, Any]) -> None:
        self._states[node_id] = state

    def remove_node(self, node_id: str) -> None:
        self._states.pop(node_id, None)

    # ------------------------------------------------------------------ #
    # Aggregation
    # ------------------------------------------------------------------ #

    def aggregate(self) -> Dict[str, Any]:
        if not self._states:
            return {
                "node_count": 0,
                "consensus_health_score": None,
                "max_divergence": None,
                "personality_drift": {},
            }

        health_scores = [
            s.get("alert_engine", {}).get("health_score", 0.0)
            for s in self._states.values()
            if s.get("alert_engine", {}).get("health_score") is not None
        ]
        consensus_health = sum(health_scores) / len(health_scores) if health_scores else 0.0

        # Max divergence from consensus identity hash
        hashes = [
            s.get("identity", {}).get("consensus_identity_hash", "")
            for s in self._states.values()
        ]
        max_div = self._max_hash_divergence(hashes)

        # Personality drift
        drift = self._compute_personality_drift()

        return {
            "node_count": len(self._states),
            "consensus_health_score": round(consensus_health, 4),
            "max_divergence": max_div,
            "personality_drift": drift,
            "nodes": list(self._states.keys()),
        }

    # ------------------------------------------------------------------ #
    # Node Personality Drift
    # ------------------------------------------------------------------ #

    def _compute_personality_drift(self) -> Dict[str, Any]:
        if len(self._states) < 2:
            return {
                "drive_divergence": 0.0,
                "self_model_divergence": 0.0,
                "narrative_divergence": 0.0,
                "decisional_divergence": 0.0,
                "overall_drift": 0.0,
            }

        # Drive divergence
        drive_div = self._drive_divergence()

        # Self-model divergence
        self_div = self._self_model_divergence()

        # Narrative divergence
        nar_div = self._narrative_divergence()

        # Decisional divergence
        dec_div = self._decisional_divergence()

        overall = max(drive_div, self_div, nar_div, dec_div)

        return {
            "drive_divergence": round(drive_div, 4),
            "self_model_divergence": round(self_div, 4),
            "narrative_divergence": round(nar_div, 4),
            "decisional_divergence": round(dec_div, 4),
            "overall_drift": round(overall, 4),
        }

    def _drive_divergence(self) -> float:
        nodes = list(self._states.values())
        drives_list = []
        for s in nodes:
            dr = s.get("drives", {}).get("drives", [])
            # Build urgency map by name
            urgencies = {d.get("name", "unknown"): d.get("urgency", 0.0) for d in dr}
            drives_list.append(urgencies)
        return self._dict_list_divergence(drives_list)

    def _self_model_divergence(self) -> float:
        nodes = list(self._states.values())
        phi_vals = [
            s.get("cognition", {}).get("self_model", {}).get("coherence_phi", 0.0)
            for s in nodes
        ]
        return self._scalar_divergence(phi_vals)

    def _narrative_divergence(self) -> float:
        nodes = list(self._states.values())
        # Simple metric: count of shared narrative titles / total narratives
        narratives = []
        for s in nodes:
            n = s.get("cognition", {}).get("narrative_trace", [])
            titles = {it.get("title", it.get("event", "")) for it in n if isinstance(it, dict)}
            narratives.append(titles)
        if not any(narratives):
            return 0.0
        # Jaccard distance between all pairs
        dists = []
        for i in range(len(narratives)):
            for j in range(i + 1, len(narratives)):
                a, b = narratives[i], narratives[j]
                inter = len(a & b)
                union = len(a | b)
                if union == 0:
                    continue
                dists.append(1.0 - inter / union)
        return sum(dists) / len(dists) if dists else 0.0

    def _decisional_divergence(self) -> float:
        nodes = list(self._states.values())
        tendencies = [
            s.get("drives", {}).get("action_tendency", "idle")
            for s in nodes
        ]
        # Entropy-like metric: fraction of unique tendencies
        if not tendencies:
            return 0.0
        unique = len(set(tendencies))
        return unique / len(tendencies)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _scalar_divergence(values: List[float]) -> float:
        if len(values) < 2:
            return 0.0
        avg = sum(values) / len(values)
        variance = sum((v - avg) ** 2 for v in values) / len(values)
        return math.sqrt(variance)

    @staticmethod
    def _dict_list_divergence(dicts: List[Dict[str, float]]) -> float:
        if len(dicts) < 2:
            return 0.0
        all_keys = set().union(*dicts)
        diffs = []
        for i in range(len(dicts)):
            for j in range(i + 1, len(dicts)):
                for k in all_keys:
                    diffs.append(abs(dicts[i].get(k, 0.0) - dicts[j].get(k, 0.0)))
        return sum(diffs) / len(diffs) if diffs else 0.0

    @staticmethod
    def _max_hash_divergence(hashes: List[str]) -> float:
        if len(hashes) < 2:
            return 0.0
        # Simple: fraction of nodes with differing hash
        first = hashes[0]
        diffs = sum(1 for h in hashes if h != first)
        return diffs / len(hashes)
