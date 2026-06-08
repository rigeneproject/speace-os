"""TrustReputationModel — per-node trust with temporal decay (T167).

Trust metric per node in [0,1], decaying over time if no positive interactions.
Reputation is stubbed for future gossip protocol.
"""

import time
from typing import Any, Dict, List, Optional


class TrustReputationModel:
    """Tracks trust and reputation for distributed peers."""

    TRUST_THRESHOLD: float = 0.6
    DECAY_RATE_PER_DAY: float = 0.05
    DEFAULT_TRUST: float = 0.5

    def __init__(self) -> None:
        self._trust: Dict[str, float] = {}
        self._last_positive: Dict[str, float] = {}
        self._history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    # Trust lifecycle
    # ------------------------------------------------------------------ #

    def record_positive(self, node_id: str) -> None:
        """Boost trust after a positive interaction."""
        current = self._trust.get(node_id, self.DEFAULT_TRUST)
        self._trust[node_id] = min(1.0, current + 0.1)
        self._last_positive[node_id] = time.time()
        self._history.append({
            "node_id": node_id,
            "event": "positive",
            "trust_after": self._trust[node_id],
            "timestamp": time.time(),
        })

    def record_negative(self, node_id: str) -> None:
        """Reduce trust after a negative interaction."""
        current = self._trust.get(node_id, self.DEFAULT_TRUST)
        self._trust[node_id] = max(0.0, current - 0.15)
        self._history.append({
            "node_id": node_id,
            "event": "negative",
            "trust_after": self._trust[node_id],
            "timestamp": time.time(),
        })

    def get_trust(self, node_id: str) -> float:
        raw = self._trust.get(node_id, self.DEFAULT_TRUST)
        last = self._last_positive.get(node_id)
        if last is None:
            return raw
        days_since = (time.time() - last) / 86400.0
        decay = self.DECAY_RATE_PER_DAY * days_since
        return max(0.0, raw - decay)

    def can_cooperate(self, node_id: str) -> bool:
        return self.get_trust(node_id) >= self.TRUST_THRESHOLD

    def get_trust_matrix(self) -> Dict[str, float]:
        return {nid: self.get_trust(nid) for nid in self._trust}

    def snapshot(self) -> Dict[str, Any]:
        return {
            "trust_threshold": self.TRUST_THRESHOLD,
            "trust_matrix": self.get_trust_matrix(),
            "history_count": len(self._history),
        }
