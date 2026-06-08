"""HeartbeatService — background task for multi-node liveness (T106).

Sends periodic heartbeats to registered peers and updates local
last_seen / trust_score.
"""

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional

from speace_core.cellular_brain.distributed.distributed_identity_kernel import (
    DistributedIdentityKernel,
)
from speace_core.cellular_brain.distributed.node_client import NodeClient


class HeartbeatService:
    """Schedules heartbeat checks across registered nodes."""

    def __init__(
        self,
        kernel: DistributedIdentityKernel,
        client: Optional[NodeClient] = None,
        interval_seconds: float = 30.0,
        stale_timeout_seconds: float = 300.0,
    ) -> None:
        self.kernel = kernel
        self.client = client or NodeClient()
        self.interval = interval_seconds
        self.stale_timeout = stale_timeout_seconds
        self._task: Optional[asyncio.Task[Any]] = None
        self._running = False

    async def _loop(self) -> None:
        while self._running:
            try:
                nodes = self.kernel.get_node_list()
                for node in nodes:
                    nid = node.get("node_id")
                    addr = node.get("address", "")
                    if not addr:
                        continue
                    # Extract host:port from address
                    host, port = self._parse_address(addr)
                    state = await self.client.fetch_state(host, port)
                    if state and not state.get("node_unreachable"):
                        self.kernel.heartbeat(nid)
                    else:
                        # Penalize trust on failure
                        self._penalize_trust(nid)
                # Remove stale nodes
                self.kernel.remove_stale_nodes(timeout_seconds=self.stale_timeout)
            except Exception:
                pass
            await asyncio.sleep(self.interval)

    def _parse_address(self, addr: str) -> tuple:
        if ":" in addr:
            host, port_str = addr.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                port = 8787
            return host, port
        return addr, 8787

    def _penalize_trust(self, node_id: str) -> None:
        nodes = self.kernel.get_node_list()
        for n in nodes:
            if n.get("node_id") == node_id:
                n["trust_score"] = max(0.0, n.get("trust_score", 0.5) - 0.05)
                break

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
