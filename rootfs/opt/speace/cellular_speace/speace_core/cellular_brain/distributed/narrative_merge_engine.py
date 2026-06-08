from typing import Any, Dict, List, Optional


class NarrativeMergeEngine:
    """Merges narrative traces from multiple SPEACE nodes."""

    def __init__(self, node_trust: Optional[Dict[str, float]] = None):
        self._events: List[Dict[str, Any]] = []
        self._node_trust: Dict[str, float] = dict(node_trust) if node_trust else {}

    # ------------------------------------------------------------------ #
    # Node trust helpers
    # ------------------------------------------------------------------ #

    def update_trust(self, node_id: str, trust_score: float) -> None:
        self._node_trust[node_id] = float(trust_score)

    def get_trust(self, node_id: str) -> float:
        return self._node_trust.get(node_id, 0.5)

    # ------------------------------------------------------------------ #
    # Narrative ingestion
    # ------------------------------------------------------------------ #

    def add_narrative(self, node_id: str, narrative_event: Dict[str, Any]) -> None:
        """Add a narrative event from a specific node."""
        self._events.append(
            {
                "node_id": node_id,
                **narrative_event,
            }
        )

    def get_merged_narrative(self) -> List[Dict[str, Any]]:
        """Return all events sorted chronologically by *timestamp* (or *tick*)."""
        def _sort_key(event: Dict[str, Any]) -> Any:
            ts = event.get("timestamp")
            if ts is not None:
                return ts
            return event.get("tick", 0)

        return sorted(self._events, key=_sort_key)

    # ------------------------------------------------------------------ #
    # Conflict detection
    # ------------------------------------------------------------------ #

    def detect_conflicts(self) -> List[Dict[str, Any]]:
        """Find contradictory events across nodes.

        Two events are considered conflicting when they share the same
        *event_key* (event_type + tick) but differ in their *checksum*
        (a simple hash of the serialised payload without node_id).
        """
        from collections import defaultdict

        buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for event in self._events:
            key = self._conflict_key(event)
            buckets[key].append(event)

        conflicts: List[Dict[str, Any]] = []
        for key, group in buckets.items():
            if len(group) < 2:
                continue
            checksums = {self._checksum(ev) for ev in group}
            if len(checksums) > 1:
                conflicts.append(
                    {
                        "event_key": key,
                        "events": group,
                        "reason": "divergent_payload",
                    }
                )
        return conflicts

    @staticmethod
    def _conflict_key(event: Dict[str, Any]) -> str:
        event_type = event.get("event_type", event.get("event", "unknown"))
        tick = event.get("tick", 0)
        return f"{event_type}::{tick}"

    @staticmethod
    def _checksum(event: Dict[str, Any]) -> str:
        import json

        payload = {k: v for k, v in event.items() if k != "node_id"}
        return json.dumps(payload, sort_keys=True, ensure_ascii=False)

    # ------------------------------------------------------------------ #
    # Conflict resolution
    # ------------------------------------------------------------------ #

    def resolve_conflict(
        self, event1: Dict[str, Any], event2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Simple resolution: keep the higher-trust-node version and flag for review."""
        trust1 = self.get_trust(event1.get("node_id", ""))
        trust2 = self.get_trust(event2.get("node_id", ""))
        if trust1 >= trust2:
            winner = event1
            loser = event2
        else:
            winner = event2
            loser = event1

        return {
            "winner": winner,
            "loser": loser,
            "reason": "higher_trust",
            "winner_trust": max(trust1, trust2),
            "loser_trust": min(trust1, trust2),
            "flag_for_review": True,
        }
