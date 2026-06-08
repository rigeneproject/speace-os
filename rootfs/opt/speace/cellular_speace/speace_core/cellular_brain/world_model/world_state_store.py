import random
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.world_model.world_model_models import (
    WorldEntity,
    WorldEntityType,
    WorldModelSnapshot,
    WorldZone,
)


class WorldStateStore:
    """Archives simulated world snapshots. Imports WorldStateSnapshot from T60/T60B as read-only input."""

    def __init__(self, seed: int = 42):
        self._snapshots: Dict[str, WorldModelSnapshot] = {}
        self._history: List[str] = []
        self._seed = seed
        self._rng = random.Random(seed)

    def create_snapshot(
        self,
        entities: Optional[List[WorldEntity]] = None,
        zones: Optional[List[WorldZone]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorldModelSnapshot:
        snapshot_id = f"wms_{len(self._history)}_{self._rng.randint(0, 999999)}"
        snapshot = WorldModelSnapshot(
            snapshot_id=snapshot_id,
            timestamp=datetime.now(UTC).isoformat(),
            entities=entities or [],
            zones=zones or [],
            metadata=metadata or {},
        )
        snapshot.global_uncertainty_score = self.compute_global_uncertainty(snapshot)
        snapshot.global_coherence_score = self.compute_global_coherence(snapshot)
        snapshot.global_risk_score = self.compute_global_risk(snapshot)
        self._snapshots[snapshot_id] = snapshot
        self._history.append(snapshot_id)
        return snapshot

    def import_cyber_physical_snapshot(self, cp_snapshot: dict) -> WorldModelSnapshot:
        """Convert a T60 WorldStateSnapshot dict into a WorldModelSnapshot. Purely read-only."""
        entities: List[WorldEntity] = []
        zones: List[WorldZone] = []
        streams = cp_snapshot.get("streams", {})
        for stream_name, signals in streams.items():
            entity_type = WorldEntityType.SENSOR_SOURCE
            if "env" in stream_name.lower():
                entity_type = WorldEntityType.ENVIRONMENT
            elif "energy" in stream_name.lower():
                entity_type = WorldEntityType.ENERGY_SYSTEM
            elif "infra" in stream_name.lower():
                entity_type = WorldEntityType.INFRASTRUCTURE
            entity_id = f"cp_{stream_name}"
            state = {"signals": signals} if isinstance(signals, list) else {"signals": [signals]}
            entities.append(
                WorldEntity(
                    entity_id=entity_id,
                    entity_type=entity_type,
                    name=stream_name,
                    state=state,
                    confidence=0.9,
                    uncertainty=0.1,
                    safety_relevance=0.3,
                )
            )
        return self.create_snapshot(entities=entities, zones=zones, metadata={"source": "cyber_physical", "original_id": cp_snapshot.get("snapshot_id", "")})

    def get_snapshot(self, snapshot_id: str) -> Optional[WorldModelSnapshot]:
        return self._snapshots.get(snapshot_id)

    def list_snapshots(self) -> List[str]:
        return list(self._history)

    def compute_global_uncertainty(self, snapshot: WorldModelSnapshot) -> float:
        if not snapshot.entities:
            return 0.0
        entity_uncertainty = sum(e.uncertainty for e in snapshot.entities) / len(snapshot.entities)
        zone_uncertainty = sum(z.uncertainty_score for z in snapshot.zones) / len(snapshot.zones) if snapshot.zones else 0.0
        return min(1.0, (entity_uncertainty + zone_uncertainty) / 2.0)

    def compute_global_coherence(self, snapshot: WorldModelSnapshot) -> float:
        if not snapshot.entities:
            return 1.0
        avg_confidence = sum(e.confidence for e in snapshot.entities) / len(snapshot.entities)
        return max(0.0, min(1.0, avg_confidence))

    def compute_global_risk(self, snapshot: WorldModelSnapshot) -> float:
        if not snapshot.entities:
            return 0.0
        max_safety = max((e.safety_relevance for e in snapshot.entities), default=0.0)
        zone_risk = max((z.safety_pressure for z in snapshot.zones), default=0.0)
        return min(1.0, max(max_safety, zone_risk))
