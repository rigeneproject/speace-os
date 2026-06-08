"""LatentPacket — compact vector payload for inter-module communication."""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


class VectorSource:
    """Semantic origin of a latent vector."""

    MEMORY = "memory"
    WORKSPACE = "workspace"
    DRIVE = "drive"
    HEALTH = "health"
    NARRATIVE = "narrative"
    EXPERIENCE = "experience"
    SKILL = "skill"


@dataclass
class LatentPacket:
    """A lightweight latent vector payload."""

    vector: List[float]
    source: str = VectorSource.MEMORY
    target: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, float] = field(default_factory=dict)

    def dimension(self) -> int:
        return len(self.vector)

    def magnitude(self) -> float:
        if not self.vector:
            return 0.0
        return sum(v * v for v in self.vector) ** 0.5

    def normalized(self) -> "LatentPacket":
        mag = self.magnitude()
        if mag == 0:
            return LatentPacket(
                vector=self.vector[:],
                source=self.source,
                target=self.target,
                timestamp=self.timestamp,
                metadata=self.metadata.copy(),
            )
        norm = [v / mag for v in self.vector]
        return LatentPacket(
            vector=norm,
            source=self.source,
            target=self.target,
            timestamp=self.timestamp,
            metadata=self.metadata.copy(),
        )
