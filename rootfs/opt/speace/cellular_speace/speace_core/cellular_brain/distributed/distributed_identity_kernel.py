import json
import math
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class DistributedIdentityKernel:
    """Distributed identity kernel for SPEACE.

    Maintains a registry of peer nodes, synchronizes identity vectors across
    the network, builds a consensus identity via trust-weighted merging, and
    detects divergent nodes.
    """

    def __init__(
        self,
        node_id: str = "local",
        base_path: str = "data/distributed",
        identity_vector: Optional[List[float]] = None,
        divergence_tolerance: float = 0.25,
    ):
        self.node_id = node_id
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.peers_path = self.base_path / "identity_peers.jsonl"

        self.identity_vector: List[float] = identity_vector if identity_vector is not None else []
        self.consensus_identity: List[float] = list(self.identity_vector)
        self.divergence_tolerance = divergence_tolerance

        self._nodes: Dict[str, Dict[str, Any]] = {}
        self._node_identities: Dict[str, List[float]] = {}

        self._load()

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _load(self) -> None:
        if not self.peers_path.exists():
            return
        with open(self.peers_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                entry_type = record.get("type")
                if entry_type == "node_registry":
                    self._nodes = {
                        n["node_id"]: n for n in record.get("nodes", [])
                    }
                elif entry_type == "identity_snapshot":
                    self.identity_vector = record.get("identity_vector", self.identity_vector)
                    self.consensus_identity = record.get(
                        "consensus_identity", self.consensus_identity
                    )

    def _persist(self, entry_type: str, payload: Dict[str, Any]) -> None:
        record = {
            "type": entry_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        with open(self.peers_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------ #
    # Node registry
    # ------------------------------------------------------------------ #

    def register_node(self, node_id: str, address: str, initial_trust: float = 0.5) -> None:
        """Register a new peer node or update its address."""
        self._nodes[node_id] = {
            "node_id": node_id,
            "address": address,
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "trust_score": float(initial_trust),
        }
        self._persist(
            "node_registry",
            {"nodes": list(self._nodes.values())},
        )

    def heartbeat(self, node_id: str) -> None:
        """Update last_seen for a known node."""
        if node_id in self._nodes:
            self._nodes[node_id]["last_seen"] = datetime.now(timezone.utc).isoformat()
            # Slightly reinforce trust on heartbeat
            self._nodes[node_id]["trust_score"] = min(
                1.0, self._nodes[node_id]["trust_score"] + 0.01
            )

    def remove_stale_nodes(self, timeout_seconds: float = 300) -> List[str]:
        """Remove nodes that have not sent a heartbeat within *timeout_seconds*."""
        cutoff = datetime.now(timezone.utc).timestamp() - timeout_seconds
        stale = [
            nid
            for nid, node in self._nodes.items()
            if datetime.fromisoformat(node["last_seen"]).timestamp() < cutoff
        ]
        for nid in stale:
            del self._nodes[nid]
            self._node_identities.pop(nid, None)
        if stale:
            self._persist("node_registry", {"nodes": list(self._nodes.values())})
        return stale

    def get_node_list(self) -> List[Dict[str, Any]]:
        """Return all known nodes sorted by trust_score descending."""
        return sorted(
            [dict(n) for n in self._nodes.values()],
            key=lambda x: x["trust_score"],
            reverse=True,
        )

    # ------------------------------------------------------------------ #
    # Identity synchronization
    # ------------------------------------------------------------------ #

    def _fetch_identity(self, node_id: str, address: str) -> Dict[str, Any]:
        """Attempt to fetch identity from a remote node.

        Falls back to a simulated dict exchange if the address is unreachable.
        """
        url = f"http://{address}/identity"
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:
                data = json.loads(response.read().decode("utf-8"))
                return {
                    "node_id": node_id,
                    "identity_vector": data.get("identity_vector", []),
                    "trust_score": self._nodes.get(node_id, {}).get("trust_score", 0.5),
                }
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            # Simulated exchange: return the last known vector or a placeholder.
            return {
                "node_id": node_id,
                "identity_vector": self._node_identities.get(node_id, []),
                "trust_score": self._nodes.get(node_id, {}).get("trust_score", 0.5),
            }

    def synchronize_identity(self) -> Dict[str, Any]:
        """Exchange identity vectors with peer nodes and rebuild consensus."""
        vectors: List[Dict[str, Any]] = [
            {
                "node_id": self.node_id,
                "identity_vector": list(self.identity_vector),
                "trust_score": 1.0,
            }
        ]
        for nid, node in list(self._nodes.items()):
            fetched = self._fetch_identity(nid, node["address"])
            if fetched["identity_vector"]:
                self._node_identities[nid] = fetched["identity_vector"]
                vectors.append(fetched)

        self.consensus_identity = self.merge_identity_vectors(vectors)
        self._persist(
            "identity_snapshot",
            {
                "identity_vector": self.identity_vector,
                "consensus_identity": self.consensus_identity,
            },
        )
        return {
            "consensus_identity": self.consensus_identity,
            "peers_synced": len(vectors) - 1,
        }

    def merge_identity_vectors(self, vectors: List[Dict[str, Any]]) -> List[float]:
        """Merge identity vectors from multiple nodes using a trust-weighted average."""
        if not vectors:
            return []
        max_len = max(len(v["identity_vector"]) for v in vectors if v.get("identity_vector"))
        if max_len == 0:
            return []

        total_weight = 0.0
        padded_sums = [0.0] * max_len

        for v in vectors:
            vec = v.get("identity_vector", [])
            if not vec:
                continue
            weight = float(v.get("trust_score", 0.5))
            padded = vec + [0.0] * (max_len - len(vec))
            for i, val in enumerate(padded):
                padded_sums[i] += val * weight
            total_weight += weight

        if total_weight == 0:
            return [0.0] * max_len

        return [s / total_weight for s in padded_sums]

    def get_consensus_identity(self) -> List[float]:
        """Return the globally merged identity vector."""
        return list(self.consensus_identity)

    # ------------------------------------------------------------------ #
    # Divergence detection
    # ------------------------------------------------------------------ #

    @staticmethod
    def _euclidean_distance(a: List[float], b: List[float]) -> float:
        max_len = max(len(a), len(b))
        if max_len == 0:
            return 0.0
        pa = a + [0.0] * (max_len - len(a))
        pb = b + [0.0] * (max_len - len(b))
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(pa, pb)))

    def detect_divergence(self) -> List[Dict[str, Any]]:
        """Flag nodes whose identity differs significantly from the consensus."""
        flags: List[Dict[str, Any]] = []
        consensus = self.consensus_identity
        if not consensus:
            return flags

        for nid, vec in self._node_identities.items():
            dist = self._euclidean_distance(vec, consensus)
            if dist > self.divergence_tolerance:
                flags.append(
                    {
                        "node_id": nid,
                        "distance": dist,
                        "threshold": self.divergence_tolerance,
                        "flagged": True,
                    }
                )
        return flags
