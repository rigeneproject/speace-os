"""VectorAlignment — align heterogeneous vector spaces for cross-module transfer."""

import math
from typing import Dict, List, Optional

from speace_core.cellular_brain.latent_transfer.latent_packet import LatentPacket


class VectorAlignment:
    """Manages alignment of vector spaces with different dimensions.

    Uses learned projection matrices (PCA-style or linear regression)
    to map vectors from source space to target space.
    """

    def __init__(self, source_dim: int, target_dim: int, seed: Optional[int] = None) -> None:
        self.source_dim = source_dim
        self.target_dim = target_dim
        if seed is not None:
            import random
            random.seed(seed)
        # Simple linear projection matrix (target_dim x source_dim)
        limit = math.sqrt(6.0 / (source_dim + target_dim))
        import random
        self.projection: List[List[float]] = [
            [random.uniform(-limit, limit) for _ in range(source_dim)]
            for _ in range(target_dim)
        ]
        self.bias: List[float] = [0.0] * target_dim

    def align(self, packet: LatentPacket) -> LatentPacket:
        """Project packet into target dimension space."""
        x = packet.vector
        if len(x) != self.source_dim:
            # Auto-resize via interpolation or padding
            x = self._resize(x, self.source_dim)
        y = [
            sum(self.projection[i][j] * x[j] for j in range(self.source_dim)) + self.bias[i]
            for i in range(self.target_dim)
        ]
        return LatentPacket(
            vector=y,
            source=packet.source,
            target=packet.target,
            metadata={**packet.metadata, "aligned": 1.0},
        )

    def update_projection(self, source_samples: List[List[float]], target_samples: List[List[float]], lr: float = 0.01) -> None:
        """Online update using least-squares gradient step."""
        if len(source_samples) != len(target_samples) or not source_samples:
            return
        for s, t in zip(source_samples, target_samples):
            if len(s) != self.source_dim or len(t) != self.target_dim:
                continue
            pred = [
                sum(self.projection[i][j] * s[j] for j in range(self.source_dim)) + self.bias[i]
                for i in range(self.target_dim)
            ]
            errors = [t[i] - pred[i] for i in range(self.target_dim)]
            for i in range(self.target_dim):
                for j in range(self.source_dim):
                    self.projection[i][j] += lr * errors[i] * s[j]
                self.bias[i] += lr * errors[i]

    @staticmethod
    def _resize(vec: List[float], target_len: int) -> List[float]:
        if len(vec) == target_len:
            return vec
        if len(vec) < target_len:
            # Pad with mean value
            mean = sum(vec) / len(vec) if vec else 0.0
            return vec + [mean] * (target_len - len(vec))
        # Truncate
        return vec[:target_len]

    def to_dict(self) -> dict:
        return {
            "source_dim": self.source_dim,
            "target_dim": self.target_dim,
            "projection": self.projection,
            "bias": self.bias,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VectorAlignment":
        inst = cls(d["source_dim"], d["target_dim"])
        inst.projection = d["projection"]
        inst.bias = d["bias"]
        return inst
