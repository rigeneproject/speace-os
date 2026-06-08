"""DistributedLatentSyncEngine — T118: cross-node latent vector exchange.

Extends T117 observe-only local integration with peer-to-peer latent
packet synchronization.  Relies on peer address registry for routing.
Inbound packets are queued for observation only; no automatic
behaviour modification.
"""

import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.latent_transfer.cross_node_latent_bus import CrossNodeLatentBus


class DistributedLatentSyncEngine:
    """Periodically synchronizes latent packets with registered peer nodes."""

    def __init__(
        self,
        node_id: str,
        latent_bus: CrossNodeLatentBus,
        sync_interval_ticks: int = 10,
        peer_fetch_timeout: float = 2.0,
    ) -> None:
        self.node_id = node_id
        self.latent_bus = latent_bus
        self.sync_interval_ticks = sync_interval_ticks
        self.peer_fetch_timeout = peer_fetch_timeout

        self._tick_count = 0
        self._packets_sent = 0
        self._packets_received = 0
        self._last_sync_at: float = 0.0
        self._peer_addresses: Dict[str, str] = {}

    # ------------------------------------------------------------------ #
    # Main tick hook
    # ------------------------------------------------------------------ #

    def tick(self) -> Dict[str, Any]:
        """Called every runtime tick. Syncs only on interval boundaries."""
        self._tick_count += 1
        if self._tick_count % self.sync_interval_ticks != 0:
            return {"synced": False, "reason": "interval"}
        return self._sync()

    # ------------------------------------------------------------------ #
    # Sync logic
    # ------------------------------------------------------------------ #

    def _sync(self) -> Dict[str, Any]:
        peers = list(self._peer_addresses.keys())
        if not peers:
            return {"synced": False, "reason": "no_peers"}

        sent_total = 0
        received_total = 0
        errors: List[Dict[str, str]] = []

        for peer_id in peers:
            # 1. Drain outbound and send
            outbound = self.latent_bus.drain_outbound(limit=50)
            if outbound:
                try:
                    self._send_packets(peer_id, outbound)
                    sent_total += len(outbound)
                except Exception as e:
                    errors.append({"peer": peer_id, "phase": "send", "error": str(e)})

            # 2. Receive inbound from peer
            try:
                inbound = self._receive_packets(peer_id)
                for raw in inbound:
                    pkt = self.latent_bus.receive(raw)
                    if pkt is not None:
                        received_total += 1
            except Exception as e:
                errors.append({"peer": peer_id, "phase": "receive", "error": str(e)})

        self._packets_sent += sent_total
        self._packets_received += received_total
        self._last_sync_at = time.time()

        return {
            "synced": True,
            "peers": len(peers),
            "sent": sent_total,
            "received": received_total,
            "errors": errors,
        }

    # ------------------------------------------------------------------ #
    # Network I/O (blocking — caller should run in executor if async)
    # ------------------------------------------------------------------ #

    def _send_packets(self, peer_id: str, packets: List[Dict[str, Any]]) -> None:
        address = self._peer_address(peer_id)
        if not address:
            raise ValueError(f"No address for peer {peer_id}")
        url = f"http://{address}/latent"
        payload = json.dumps({
            "sender": self.node_id,
            "packets": packets,
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.peer_fetch_timeout) as resp:
            if resp.status != 200:
                raise urllib.error.HTTPError(url, resp.status, "", None, None)

    def _receive_packets(self, peer_id: str) -> List[Dict[str, Any]]:
        address = self._peer_address(peer_id)
        if not address:
            return []
        url = f"http://{address}/latent?receiver={self.node_id}"
        try:
            with urllib.request.urlopen(url, timeout=self.peer_fetch_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("packets", [])
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return []

    def _peer_address(self, peer_id: str) -> Optional[str]:
        return self._peer_addresses.get(peer_id)

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #

    def register_peer(self, peer_id: str, address: str, initial_trust: float = 0.1) -> None:
        """Register a remote peer node address and latent bus adapter."""
        self._peer_addresses[peer_id] = address
        self.latent_bus.register_peer(peer_id, initial_trust=initial_trust)

    # ------------------------------------------------------------------ #
    # Stats
    # ------------------------------------------------------------------ #

    def snapshot(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "tick_count": self._tick_count,
            "last_sync_at": self._last_sync_at,
            "packets_sent": self._packets_sent,
            "packets_received": self._packets_received,
            "peers": list(self._peer_addresses.keys()),
        }
