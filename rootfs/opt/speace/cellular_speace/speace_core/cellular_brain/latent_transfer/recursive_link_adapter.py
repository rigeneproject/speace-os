"""RecursiveLinkAdapter — lightweight residual projection for latent transfer.

Inspired by RecursiveMAS (Yang et al., 2026), but adapted for SPEACE's
internal vectors (memory, workspace, drives, etc.) rather than LLM hidden
states.
"""

import math
import random
from typing import List, Optional

from speace_core.cellular_brain.latent_transfer.latent_packet import LatentPacket


def _gelu(x: float) -> float:
    """Gaussian Error Linear Unit approximation."""
    return 0.5 * x * (1.0 + math.tanh(math.sqrt(2.0 / math.pi) * (x + 0.044715 * x * x * x)))


class RecursiveLinkAdapter:
    """Two-layer residual projection for latent-state transmission.

    Supports both inner-link (same module) and outer-link (cross-module)
    modes. In outer-link mode an additional linear layer aligns source
    and target embedding spaces.
    """

    def __init__(
        self,
        in_dim: int,
        out_dim: int,
        hidden_dim: Optional[int] = None,
        outer_link: bool = False,
        seed: Optional[int] = None,
    ) -> None:
        self.in_dim = in_dim
        self.out_dim = out_dim
        self.hidden_dim = hidden_dim or min(in_dim, out_dim)
        self.outer_link = outer_link

        if seed is not None:
            random.seed(seed)

        # Xavier-like init for stability
        def _init_matrix(rows: int, cols: int) -> List[List[float]]:
            limit = math.sqrt(6.0 / (rows + cols))
            return [[random.uniform(-limit, limit) for _ in range(cols)] for _ in range(rows)]

        # W1: in_dim -> hidden_dim
        self.W1 = _init_matrix(self.hidden_dim, self.in_dim)
        # W2: hidden_dim -> out_dim
        self.W2 = _init_matrix(self.out_dim, self.hidden_dim)
        # Optional outer alignment: in_dim -> out_dim
        self.W3: Optional[List[List[float]]] = None
        if self.outer_link:
            self.W3 = _init_matrix(self.out_dim, self.in_dim)

        # Residual bias (learnable via Hebbian or frozen)
        self.residual_scale = 1.0

    # ------------------------------------------------------------------ #
    # Forward
    # ------------------------------------------------------------------ #

    def transform(self, packet: LatentPacket) -> LatentPacket:
        """Project packet.vector through RecursiveLink."""
        x = packet.vector
        if len(x) != self.in_dim:
            raise ValueError(
                f"Input dimension mismatch: expected {self.in_dim}, got {len(x)}"
            )

        # Branch: W2 * GELU(W1 * x)
        h = [_dot(self.W1[i], x) for i in range(self.hidden_dim)]
        h = [_gelu(v) for v in h]
        y = [_dot(self.W2[i], h) for i in range(self.out_dim)]

        # Residual + optional outer alignment
        if self.outer_link and self.W3 is not None:
            align = [_dot(self.W3[i], x) for i in range(self.out_dim)]
            y = [yi + ai for yi, ai in zip(y, align)]
        elif self.in_dim == self.out_dim:
            y = [yi + self.residual_scale * xi for yi, xi in zip(y, x)]
        else:
            # Zero-pad or truncate for residual when dims differ
            pad_len = self.out_dim - self.in_dim
            if pad_len >= 0:
                y = [yi + self.residual_scale * xi for yi, xi in zip(y, x + [0.0] * pad_len)]
            else:
                y = [yi + self.residual_scale * xi for yi, xi in zip(y, x[: self.out_dim])]

        return LatentPacket(
            vector=y,
            source=packet.source,
            target=packet.target,
            metadata={**packet.metadata, "transformed": 1.0},
        )

    # ------------------------------------------------------------------ #
    # Learning (Hebbian-style lightweight update)
    # ------------------------------------------------------------------ #

    def hebbian_update(self, pre: List[float], post: List[float], lr: float = 0.001) -> None:
        """Tiny Hebbian adjustment to W1 and W2."""
        if len(pre) != self.in_dim or len(post) != self.out_dim:
            return
        # Simplified: strengthen W1 and W2 based on correlation
        for i in range(self.hidden_dim):
            for j in range(self.in_dim):
                self.W1[i][j] += lr * pre[j] * _dot(self.W2[:, i] if False else [self.W2[k][i] for k in range(self.out_dim)], post)
        # Clip for stability
        for row in self.W1:
            for j in range(len(row)):
                row[j] = max(-2.0, min(2.0, row[j]))
        for row in self.W2:
            for j in range(len(row)):
                row[j] = max(-2.0, min(2.0, row[j]))

    # ------------------------------------------------------------------ #
    # Serialization
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict:
        return {
            "in_dim": self.in_dim,
            "out_dim": self.out_dim,
            "hidden_dim": self.hidden_dim,
            "outer_link": self.outer_link,
            "W1": self.W1,
            "W2": self.W2,
            "W3": self.W3,
            "residual_scale": self.residual_scale,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RecursiveLinkAdapter":
        inst = cls(
            in_dim=d["in_dim"],
            out_dim=d["out_dim"],
            hidden_dim=d.get("hidden_dim"),
            outer_link=d.get("outer_link", False),
        )
        inst.W1 = d["W1"]
        inst.W2 = d["W2"]
        inst.W3 = d.get("W3")
        inst.residual_scale = d.get("residual_scale", 1.0)
        return inst


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #


def _dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
