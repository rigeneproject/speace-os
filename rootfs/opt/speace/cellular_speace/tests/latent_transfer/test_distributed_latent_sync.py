"""Tests for T118 — Distributed Latent Sync."""

import json
from unittest.mock import MagicMock, patch

import pytest

from speace_core.cellular_brain.latent_transfer.cross_node_latent_bus import CrossNodeLatentBus
from speace_core.cellular_brain.latent_transfer.distributed_latent_sync import DistributedLatentSyncEngine
from speace_core.cellular_brain.latent_transfer.latent_packet import LatentPacket, VectorSource


# --------------------------------------------------------------------------- #
# Basic lifecycle
# --------------------------------------------------------------------------- #

def test_sync_no_peers():
    bus = CrossNodeLatentBus(node_id="node_a", default_vector_dim=8)
    engine = DistributedLatentSyncEngine(
        node_id="node_a",
        latent_bus=bus,
        sync_interval_ticks=3,
    )
    # Ticks 1 and 2 should skip (interval)
    assert engine.tick()["synced"] is False
    assert engine.tick()["synced"] is False
    # Tick 3 should attempt sync but find no peers
    report = engine.tick()
    assert report["synced"] is False
    assert report["reason"] == "no_peers"


def test_sync_register_peer():
    bus = CrossNodeLatentBus(node_id="node_a", default_vector_dim=8)
    engine = DistributedLatentSyncEngine(
        node_id="node_a",
        latent_bus=bus,
    )
    engine.register_peer("node_b", "127.0.0.1:9999", initial_trust=0.5)
    assert "node_b" in engine.snapshot()["peers"]
    assert bus.snapshot()["peers"] == ["node_b"]


# --------------------------------------------------------------------------- #
# Mocked network send / receive
# --------------------------------------------------------------------------- #

def test_sync_sends_outbound_packets():
    bus = CrossNodeLatentBus(node_id="node_a", default_vector_dim=4)
    bus.register_peer("node_b", initial_trust=0.5)
    bus.send(
        LatentPacket(vector=[0.1, 0.2, 0.3, 0.4], source=VectorSource.MEMORY),
        target_node="node_b",
    )

    engine = DistributedLatentSyncEngine(
        node_id="node_a",
        latent_bus=bus,
        sync_interval_ticks=1,
    )
    engine.register_peer("node_b", "127.0.0.1:9999")

    mock_response = MagicMock()
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.status = 200
    mock_response.read.return_value = b'{"ok": true}'

    with patch("urllib.request.urlopen", return_value=mock_response):
        report = engine.tick()

    assert report["synced"] is True
    assert report["sent"] == 1
    assert report["received"] == 0
    assert engine.snapshot()["packets_sent"] == 1


def test_sync_receives_inbound_packets():
    bus = CrossNodeLatentBus(node_id="node_a", default_vector_dim=4)
    bus.register_peer("node_b", initial_trust=0.5)

    engine = DistributedLatentSyncEngine(
        node_id="node_a",
        latent_bus=bus,
        sync_interval_ticks=1,
    )
    engine.register_peer("node_b", "127.0.0.1:9999")

    fake_inbound = {
        "packets": [
            {
                "vector": [0.5, 0.5, 0.5, 0.5],
                "source": "drive",
                "metadata": {"sender": "node_b"},
            }
        ]
    }
    mock_response = MagicMock()
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.status = 200
    mock_response.read.return_value = json.dumps(fake_inbound).encode()

    with patch("urllib.request.urlopen", return_value=mock_response):
        report = engine.tick()

    assert report["synced"] is True
    assert report["received"] == 1
    assert bus.snapshot()["inbound_queue"] == 1


def test_sync_receive_untrusted_peer_dropped():
    bus = CrossNodeLatentBus(node_id="node_a", default_vector_dim=4)
    bus.register_peer("node_b", initial_trust=0.0)  # zero trust

    engine = DistributedLatentSyncEngine(
        node_id="node_a",
        latent_bus=bus,
        sync_interval_ticks=1,
    )
    engine.register_peer("node_b", "127.0.0.1:9999")

    fake_inbound = {
        "packets": [
            {
                "vector": [0.5, 0.5, 0.5, 0.5],
                "source": "drive",
                "metadata": {"sender": "node_b"},
            }
        ]
    }
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps(fake_inbound).encode()

    with patch("urllib.request.urlopen", return_value=mock_response):
        report = engine.tick()

    # Bus.receive should drop packet because trust == 0
    assert report["received"] == 0
    assert bus.snapshot()["inbound_queue"] == 0


def test_sync_network_error_graceful():
    bus = CrossNodeLatentBus(node_id="node_a", default_vector_dim=4)
    bus.register_peer("node_b", initial_trust=0.5)

    engine = DistributedLatentSyncEngine(
        node_id="node_a",
        latent_bus=bus,
        sync_interval_ticks=1,
    )
    engine.register_peer("node_b", "127.0.0.1:9999")

    with patch("urllib.request.urlopen", side_effect=Exception("connection refused")):
        report = engine.tick()

    assert report["synced"] is True
    assert len(report["errors"]) > 0
    assert report["errors"][0]["peer"] == "node_b"


# --------------------------------------------------------------------------- #
# Snapshot
# --------------------------------------------------------------------------- #

def test_sync_snapshot():
    bus = CrossNodeLatentBus(node_id="node_a", default_vector_dim=4)
    engine = DistributedLatentSyncEngine(
        node_id="node_a",
        latent_bus=bus,
    )
    snap = engine.snapshot()
    assert snap["node_id"] == "node_a"
    assert snap["tick_count"] == 0
    assert snap["packets_sent"] == 0
    assert snap["packets_received"] == 0
    assert snap["peers"] == []
