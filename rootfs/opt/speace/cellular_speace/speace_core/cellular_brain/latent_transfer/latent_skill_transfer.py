"""LatentSkillTransfer — encode learned skills as latent vectors and transfer
them across modules or nodes without textual serialization.
"""

import hashlib
import json
import time
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.latent_transfer.latent_packet import LatentPacket
from speace_core.cellular_brain.latent_transfer.recursive_link_adapter import RecursiveLinkAdapter


class LatentSkillTransfer:
    """Encodes skills into compact latent vectors for zero-shot-like transfer.

    A skill is represented as a vector derived from:
    - success-rate embedding
    - capability-region activation pattern
    - parameter-delta fingerprint
    """

    def __init__(self, vector_dim: int = 64, seed: Optional[int] = None) -> None:
        self.vector_dim = vector_dim
        if seed is not None:
            import random
            random.seed(seed)
        self._skill_registry: Dict[str, Dict[str, Any]] = {}
        self._transfer_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    # Encoding
    # ------------------------------------------------------------------ #

    def encode_skill(
        self,
        skill_name: str,
        success_rate: float,
        capability_vector: List[float],
        param_delta: Optional[List[float]] = None,
    ) -> LatentPacket:
        """Encode a skill into a latent vector."""
        # Normalize inputs
        sr = max(0.0, min(1.0, success_rate))
        cap = self._pad_or_truncate(capability_vector, self.vector_dim - 2)
        delta = param_delta or []
        delta_hash = self._hash_vector(delta)

        # Compose: [success_rate, delta_hash_scalar, capability...]
        delta_scalar = delta_hash % 1.0 if delta_hash > 0 else 0.0
        vector = [sr, delta_scalar] + cap
        vector = self._pad_or_truncate(vector, self.vector_dim)

        packet = LatentPacket(
            vector=vector,
            source="skill",
            target=skill_name,
            metadata={
                "success_rate": sr,
                "delta_hash": delta_hash,
                "encoded_at": time.time(),
            },
        )
        self._skill_registry[skill_name] = {
            "packet": packet,
            "capability_vector": capability_vector,
            "param_delta": param_delta,
        }
        return packet

    # ------------------------------------------------------------------ #
    # Decoding / application
    # ------------------------------------------------------------------ #

    def decode_skill(self, packet: LatentPacket) -> Dict[str, Any]:
        """Decode a latent skill packet into structured info."""
        vec = packet.vector
        if len(vec) < 2:
            return {"valid": False, "reason": "vector_too_short"}
        return {
            "valid": True,
            "skill_name": packet.target,
            "success_rate": vec[0],
            "delta_scalar": vec[1],
            "capability_pattern": vec[2:],
            "metadata": packet.metadata,
        }

    def apply_to_module(
        self,
        packet: LatentPacket,
        target_module: Any,
        adapter: Optional[RecursiveLinkAdapter] = None,
    ) -> bool:
        """Apply a transferred skill vector to a target module."""
        if adapter is not None:
            packet = adapter.transform(packet)
        decoded = self.decode_skill(packet)
        if not decoded["valid"]:
            return False

        # Heuristic: if target module has a .absorb_skill_vector method, call it
        absorber = getattr(target_module, "absorb_skill_vector", None)
        if callable(absorber):
            try:
                absorber(packet.vector)
                self._transfer_log.append({
                    "timestamp": time.time(),
                    "skill": decoded["skill_name"],
                    "success_rate": decoded["success_rate"],
                    "applied": True,
                })
                return True
            except Exception:
                pass

        self._transfer_log.append({
            "timestamp": time.time(),
            "skill": decoded["skill_name"],
            "applied": False,
            "reason": "no_absorber",
        })
        return False

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _pad_or_truncate(vec: List[float], target_len: int) -> List[float]:
        if len(vec) == target_len:
            return vec
        if len(vec) < target_len:
            mean = sum(vec) / len(vec) if vec else 0.0
            return vec + [mean] * (target_len - len(vec))
        return vec[:target_len]

    @staticmethod
    def _hash_vector(vec: List[float]) -> int:
        if not vec:
            return 0
        payload = json.dumps(vec, ensure_ascii=False)
        return int(hashlib.sha256(payload.encode()).hexdigest(), 16)

    # ------------------------------------------------------------------ #
    # Registry
    # ------------------------------------------------------------------ #

    def list_skills(self) -> List[str]:
        return list(self._skill_registry.keys())

    def get_skill_packet(self, skill_name: str) -> Optional[LatentPacket]:
        entry = self._skill_registry.get(skill_name)
        return entry["packet"] if entry else None

    def snapshot(self) -> Dict[str, Any]:
        return {
            "vector_dim": self.vector_dim,
            "skills": self.list_skills(),
            "transfer_count": len(self._transfer_log),
            "latest_transfer": self._transfer_log[-1] if self._transfer_log else None,
        }
