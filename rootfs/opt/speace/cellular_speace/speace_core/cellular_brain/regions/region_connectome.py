from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class InterRegionConnection(BaseModel):
    source_region_id: str
    target_region_id: str
    connection_type: str = "feedforward"
    strength: float = 0.5
    plasticity_enabled: bool = True
    inhibitory: bool = False


class RegionConnectome(BaseModel):
    regions: Dict[str, dict] = Field(default_factory=dict)
    connections: List[InterRegionConnection] = Field(default_factory=list)

    def add_connection(
        self,
        source_region_id: str,
        target_region_id: str,
        connection_type: str = "feedforward",
        strength: float = 0.5,
        plasticity_enabled: bool = True,
        inhibitory: bool = False,
    ) -> InterRegionConnection:
        conn = InterRegionConnection(
            source_region_id=source_region_id,
            target_region_id=target_region_id,
            connection_type=connection_type,
            strength=strength,
            plasticity_enabled=plasticity_enabled,
            inhibitory=inhibitory,
        )
        self.connections.append(conn)
        return conn

    def get_connections_from(
        self, source_region_id: str
    ) -> List[InterRegionConnection]:
        return [c for c in self.connections if c.source_region_id == source_region_id]

    def get_connections_to(
        self, target_region_id: str
    ) -> List[InterRegionConnection]:
        return [c for c in self.connections if c.target_region_id == target_region_id]

    def remove_connections_involving(self, region_id: str) -> None:
        self.connections = [
            c
            for c in self.connections
            if c.source_region_id != region_id and c.target_region_id != region_id
        ]

    def compute_connectome_density(self) -> float:
        n = len(self.regions)
        if n < 2:
            return 0.0
        max_possible = n * (n - 1)
        return len(self.connections) / max_possible
