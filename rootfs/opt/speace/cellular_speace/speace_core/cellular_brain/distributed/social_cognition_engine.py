"""SocialCognitionEngine — theory of mind models for distributed nodes (T167).

Maintains lightweight mental models of other agents: predicted preferences,
reliability, and interaction history. Updates after each cross-node event.
"""

import time
from typing import Any, Dict, List, Optional


class MentalModel:
    """Theory-of-mind snapshot for a single peer."""

    def __init__(self, node_id: str) -> None:
        self.node_id = node_id
        self.predicted_preferences: Dict[str, float] = {}
        self.predicted_reliability: float = 0.5
        self.interaction_history: List[Dict[str, Any]] = []
        self.last_updated: float = time.time()

    def record_interaction(
        self,
        event_type: str,
        outcome: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.interaction_history.append({
            "event_type": event_type,
            "outcome": outcome,
            "metadata": metadata or {},
            "timestamp": time.time(),
        })
        if len(self.interaction_history) > 100:
            self.interaction_history.pop(0)
        self.last_updated = time.time()

    def update_reliability(self, accuracy: float) -> None:
        """accuracy in [0,1]; 1.0 means prediction matched outcome."""
        self.predicted_reliability = 0.7 * self.predicted_reliability + 0.3 * accuracy
        self.predicted_reliability = max(0.0, min(1.0, self.predicted_reliability))

    def snapshot(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "predicted_preferences": dict(self.predicted_preferences),
            "predicted_reliability": round(self.predicted_reliability, 3),
            "interaction_count": len(self.interaction_history),
            "last_updated": self.last_updated,
        }


class SocialCognitionEngine:
    """Manages theory-of-mind models for all known peers."""

    def __init__(self) -> None:
        self._models: Dict[str, MentalModel] = {}

    def get_or_create_model(self, node_id: str) -> MentalModel:
        if node_id not in self._models:
            self._models[node_id] = MentalModel(node_id)
        return self._models[node_id]

    def record_interaction(
        self,
        node_id: str,
        event_type: str,
        outcome: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        model = self.get_or_create_model(node_id)
        model.record_interaction(event_type, outcome, metadata)

    def update_reliability(self, node_id: str, accuracy: float) -> None:
        model = self.get_or_create_model(node_id)
        model.update_reliability(accuracy)

    def list_models(self) -> List[Dict[str, Any]]:
        return [m.snapshot() for m in self._models.values()]

    def snapshot(self) -> Dict[str, Any]:
        return {
            "model_count": len(self._models),
            "models": self.list_models(),
        }
