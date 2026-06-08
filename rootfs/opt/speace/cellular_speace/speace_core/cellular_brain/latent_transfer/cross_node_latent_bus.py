"""CrossNodeLatentBus — distributed latent vector exchange between SPEACE nodes.

Lightweight, no LLM decoding/encoding. Vectors are serialized as compact
float arrays and routed via node_id.
"""

import json
import time
from collections import deque
from typing import Deque, Dict, List, Optional

from speace_core.cellular_brain.latent_transfer.latent_packet import LatentPacket
from speace_core.cellular_brain.latent_transfer.recursive_link_adapter import RecursiveLinkAdapter


class CrossNodeLatentBus:
    """Bus for latent-packet exchange across SPEACE nodes."""

    def __init__(
        self,
        node_id: str,
        max_buffer: int = 1000,
        default_vector_dim: int = 64,
    ) -> None:
        self.node_id = node_id
        self.max_buffer = max_buffer
        self.default_vector_dim = default_vector_dim
        self._inbound: Deque[LatentPacket] = deque()
        self._outbound: Deque[LatentPacket] = deque()
        self._adapters: Dict[str, RecursiveLinkAdapter] = {}
        self._trust_scores: Dict[str, float] = {}

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #

    def register_peer(
        self,
        peer_node_id: str,
        adapter: Optional[RecursiveLinkAdapter] = None,
        initial_trust: float = 0.1,
    ) -> None:
        if adapter is None:
            adapter = RecursiveLinkAdapter(
                in_dim=self.default_vector_dim,
                out_dim=self.default_vector_dim,
                outer_link=True,
            )
        self._adapters[peer_node_id] = adapter
        self._trust_scores[peer_node_id] = initial_trust

    # ------------------------------------------------------------------ #
    # Send / receive
    # ------------------------------------------------------------------ #

    def send(self, packet: LatentPacket, target_node: str) -> bool:
        """Queue a packet for transmission to target_node."""
        if target_node not in self._adapters:
            return False
        adapter = self._adapters[target_node]
        transformed = adapter.transform(packet)
        transformed.metadata["sender"] = self.node_id
        transformed.metadata["recipient"] = target_node
        transformed.metadata["trust"] = self._trust_scores.get(target_node, 0.0)
        self._outbound.append(transformed)
        if len(self._outbound) > self.max_buffer:
            self._outbound.popleft()
        return True

    def receive(self, raw_packet: dict) -> Optional[LatentPacket]:
        """Ingest a raw packet dict from network. Returns None if rejected."""
        try:
            packet = LatentPacket(
                vector=raw_packet["vector"],
                source=raw_packet.get("source", "unknown"),
                target=raw_packet.get("target"),
                timestamp=raw_packet.get("timestamp", time.time()),
                metadata=raw_packet.get("metadata", {}),
            )
        except (KeyError, TypeError):
            return None
        sender = packet.metadata.get("sender")
        if sender is not None and self._trust_scores.get(sender, 0.0) <= 0.0:
            return None
        self._inbound.append(packet)
        if len(self._inbound) > self.max_buffer:
            self._inbound.popleft()
        return packet

    # ------------------------------------------------------------------ #
    # Draining
    # ------------------------------------------------------------------ #

    def drain_outbound(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Pop outbound packets for network transmission."""
        batch: List[Dict[str, Any]] = []
        while self._outbound and len(batch) < limit:
            p = self._outbound.popleft()
            batch.append({
                "vector": p.vector,
                "source": p.source,
                "target": p.target,
                "timestamp": p.timestamp,
                "metadata": p.metadata,
            })
        return batch

    def drain_inbound(self, limit: int = 100) -> List[LatentPacket]:
        """Pop inbound packets for local consumption."""
        batch: List[LatentPacket] = []
        while self._inbound and len(batch) < limit:
            batch.append(self._inbound.popleft())
        return batch

    # ------------------------------------------------------------------ #
    # Trust management
    # ------------------------------------------------------------------ #

    def update_trust(self, peer_node_id: str, delta: float) -> None:
        current = self._trust_scores.get(peer_node_id, 0.0)
        self._trust_scores[peer_node_id] = max(0.0, min(1.0, current + delta))

    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #

    def snapshot(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "inbound_queue": len(self._inbound),
            "outbound_queue": len(self._outbound),
            "peers": list(self._adapters.keys()),
            "trust_scores": self._trust_scores.copy(),
        }
