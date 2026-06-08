import json
from datetime import datetime, timezone

import pytest

from speace_core.cellular_brain.distributed.distributed_identity_kernel import (
    DistributedIdentityKernel,
)


class TestDistributedIdentityKernel:
    def test_register_and_heartbeat(self, tmp_path):
        kernel = DistributedIdentityKernel(base_path=str(tmp_path / "dist"))
        kernel.register_node("node-a", "10.0.0.1:8080", initial_trust=0.6)
        nodes = kernel.get_node_list()
        assert len(nodes) == 1
        assert nodes[0]["node_id"] == "node-a"
        assert nodes[0]["trust_score"] == pytest.approx(0.6)

        kernel.heartbeat("node-a")
        nodes_after = kernel.get_node_list()
        assert nodes_after[0]["trust_score"] == pytest.approx(0.61)
        # last_seen should be updated
        last_seen = datetime.fromisoformat(nodes_after[0]["last_seen"])
        assert (datetime.now(timezone.utc) - last_seen).total_seconds() < 5

    def test_stale_removal(self, tmp_path):
        kernel = DistributedIdentityKernel(base_path=str(tmp_path / "dist"))
        kernel.register_node("node-a", "10.0.0.1:8080")
        # artificially age the node
        kernel._nodes["node-a"]["last_seen"] = (
            datetime.now(timezone.utc).replace(year=2000).isoformat()
        )
        stale = kernel.remove_stale_nodes(timeout_seconds=300)
        assert stale == ["node-a"]
        assert kernel.get_node_list() == []

    def test_identity_merge_weighted(self, tmp_path):
        kernel = DistributedIdentityKernel(base_path=str(tmp_path / "dist"))
        vectors = [
            {"node_id": "n1", "identity_vector": [1.0, 0.0], "trust_score": 0.5},
            {"node_id": "n2", "identity_vector": [0.0, 1.0], "trust_score": 1.5},
        ]
        merged = kernel.merge_identity_vectors(vectors)
        # weighted average: n1*0.5 + n2*1.5 = [0.5, 0] + [0, 1.5] => [0.5, 1.5] / 2.0
        assert merged[0] == pytest.approx(0.25)
        assert merged[1] == pytest.approx(0.75)

    def test_divergence_detection(self, tmp_path):
        kernel = DistributedIdentityKernel(
            base_path=str(tmp_path / "dist"),
            identity_vector=[0.0, 0.0],
            divergence_tolerance=0.5,
        )
        kernel.register_node("node-a", "10.0.0.1")
        kernel.register_node("node-b", "10.0.0.2")
        kernel._node_identities = {
            "node-a": [0.1, 0.1],
            "node-b": [3.0, 3.0],
        }
        # consensus must exist
        kernel.consensus_identity = [0.0, 0.0]
        flags = kernel.detect_divergence()
        assert len(flags) == 1
        assert flags[0]["node_id"] == "node-b"
        assert flags[0]["flagged"] is True

    def test_consensus_identity(self, tmp_path):
        kernel = DistributedIdentityKernel(
            base_path=str(tmp_path / "dist"),
            identity_vector=[1.0, 1.0],
        )
        kernel.register_node("peer-1", "10.0.0.1")
        kernel._node_identities["peer-1"] = [0.0, 2.0]
        result = kernel.synchronize_identity()
        consensus = result["consensus_identity"]
        # local vector [1,1] weight 1.0 + peer [0,2] weight 0.5 => [1,1] + [0,1] => [1,2] / 1.5
        assert consensus[0] == pytest.approx(1.0 / 1.5)
        assert consensus[1] == pytest.approx(2.0 / 1.5)
        assert kernel.get_consensus_identity() == consensus
