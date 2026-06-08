"""Tests for T116 — Latent Vector Transfer Layer."""

import pytest

from speace_core.cellular_brain.latent_transfer.latent_packet import LatentPacket, VectorSource
from speace_core.cellular_brain.latent_transfer.recursive_link_adapter import RecursiveLinkAdapter
from speace_core.cellular_brain.latent_transfer.vector_alignment import VectorAlignment
from speace_core.cellular_brain.latent_transfer.cross_node_latent_bus import CrossNodeLatentBus
from speace_core.cellular_brain.latent_transfer.latent_skill_transfer import LatentSkillTransfer


# --------------------------------------------------------------------------- #
# LatentPacket
# --------------------------------------------------------------------------- #

def test_latent_packet_basics():
    p = LatentPacket(vector=[0.1, 0.2, 0.3], source=VectorSource.MEMORY)
    assert p.dimension() == 3
    assert p.magnitude() > 0
    norm = p.normalized()
    assert pytest.approx(norm.magnitude(), 0.01) == 1.0


# --------------------------------------------------------------------------- #
# RecursiveLinkAdapter
# --------------------------------------------------------------------------- #

def test_recursive_link_inner_same_dim():
    adapter = RecursiveLinkAdapter(in_dim=8, out_dim=8, outer_link=False, seed=42)
    p = LatentPacket(vector=[0.1] * 8, source=VectorSource.WORKSPACE)
    out = adapter.transform(p)
    assert len(out.vector) == 8
    assert out.metadata.get("transformed") == 1.0


def test_recursive_link_outer_cross_dim():
    adapter = RecursiveLinkAdapter(in_dim=8, out_dim=16, outer_link=True, seed=42)
    p = LatentPacket(vector=[0.1] * 8, source=VectorSource.MEMORY)
    out = adapter.transform(p)
    assert len(out.vector) == 16


def test_recursive_link_hebbian_update():
    adapter = RecursiveLinkAdapter(in_dim=4, out_dim=4, seed=42)
    pre = [0.1, 0.2, 0.3, 0.4]
    post = [0.2, 0.3, 0.4, 0.5]
    adapter.hebbian_update(pre, post, lr=0.01)
    # Just verify it does not crash and modifies weights
    assert any(any(v != 0 for v in row) for row in adapter.W1)


def test_recursive_link_serialize():
    adapter = RecursiveLinkAdapter(in_dim=4, out_dim=4, seed=42)
    d = adapter.to_dict()
    adapter2 = RecursiveLinkAdapter.from_dict(d)
    assert adapter2.in_dim == adapter.in_dim
    assert adapter2.out_dim == adapter.out_dim


# --------------------------------------------------------------------------- #
# VectorAlignment
# --------------------------------------------------------------------------- #

def test_vector_alignment_pad():
    align = VectorAlignment(source_dim=4, target_dim=8, seed=42)
    p = LatentPacket(vector=[1.0, 2.0, 3.0, 4.0])
    out = align.align(p)
    assert len(out.vector) == 8


def test_vector_alignment_truncate():
    align = VectorAlignment(source_dim=8, target_dim=4, seed=42)
    p = LatentPacket(vector=[1.0] * 8)
    out = align.align(p)
    assert len(out.vector) == 4


def test_vector_alignment_update():
    align = VectorAlignment(source_dim=4, target_dim=4, seed=42)
    sources = [[0.1, 0.2, 0.3, 0.4], [0.2, 0.3, 0.4, 0.5]]
    targets = [[0.2, 0.3, 0.4, 0.5], [0.3, 0.4, 0.5, 0.6]]
    align.update_projection(sources, targets, lr=0.1)
    # Non-crash assertion
    assert len(align.projection) == 4


# --------------------------------------------------------------------------- #
# CrossNodeLatentBus
# --------------------------------------------------------------------------- #

def test_bus_register_and_send():
    bus = CrossNodeLatentBus(node_id="node_a", default_vector_dim=8)
    bus.register_peer("node_b")
    p = LatentPacket(vector=[0.1] * 8, source=VectorSource.SKILL)
    ok = bus.send(p, target_node="node_b")
    assert ok is True
    assert len(bus._outbound) == 1


def test_bus_reject_unknown_peer():
    bus = CrossNodeLatentBus(node_id="node_a")
    p = LatentPacket(vector=[0.1] * 8)
    ok = bus.send(p, target_node="node_unknown")
    assert ok is False


def test_bus_receive_and_trust():
    bus = CrossNodeLatentBus(node_id="node_a")
    bus.register_peer("node_b", initial_trust=0.5)
    raw = {
        "vector": [0.1, 0.2],
        "source": "memory",
        "metadata": {"sender": "node_b"},
    }
    pkt = bus.receive(raw)
    assert pkt is not None
    assert len(bus._inbound) == 1


def test_bus_receive_untrusted():
    bus = CrossNodeLatentBus(node_id="node_a")
    bus.register_peer("node_b", initial_trust=0.0)
    raw = {
        "vector": [0.1, 0.2],
        "source": "memory",
        "metadata": {"sender": "node_b"},
    }
    pkt = bus.receive(raw)
    assert pkt is None


def test_bus_drain():
    bus = CrossNodeLatentBus(node_id="node_a", default_vector_dim=4)
    bus.register_peer("node_b")
    bus.send(LatentPacket(vector=[0.1] * 4), "node_b")
    out = bus.drain_outbound()
    assert len(out) == 1
    assert len(bus._outbound) == 0


# --------------------------------------------------------------------------- #
# LatentSkillTransfer
# --------------------------------------------------------------------------- #

def test_skill_encode_decode():
    xfer = LatentSkillTransfer(vector_dim=16, seed=42)
    p = xfer.encode_skill(
        skill_name="foo",
        success_rate=0.8,
        capability_vector=[0.1, 0.2, 0.3],
        param_delta=[0.01, -0.02],
    )
    assert p.source == "skill"
    assert len(p.vector) == 16
    decoded = xfer.decode_skill(p)
    assert decoded["valid"] is True
    assert decoded["success_rate"] == pytest.approx(0.8, 0.01)


def test_skill_transfer_log():
    xfer = LatentSkillTransfer(vector_dim=8, seed=42)
    p = xfer.encode_skill(skill_name="bar", success_rate=0.5, capability_vector=[0.1])
    # Fake module without absorber
    class FakeMod:
        pass
    ok = xfer.apply_to_module(p, FakeMod())
    assert ok is False
    assert xfer.snapshot()["transfer_count"] == 1


def test_skill_transfer_with_absorber():
    xfer = LatentSkillTransfer(vector_dim=8, seed=42)
    p = xfer.encode_skill(skill_name="baz", success_rate=0.9, capability_vector=[0.1])
    class FakeMod:
        absorbed = []
        def absorb_skill_vector(self, vec):
            self.absorbed.append(vec)
    mod = FakeMod()
    ok = xfer.apply_to_module(p, mod)
    assert ok is True
    assert len(mod.absorbed) == 1


# --------------------------------------------------------------------------- #
# T117 — RuntimeLatentIntegrator
# --------------------------------------------------------------------------- #

class FakeOrchestratorT117:
    def __init__(self):
        self.current_tick = 0
        self.metrics_log = []
        self._global_workspace = None
        self._memory = None
        self._homeostatic_drive = None
        self._self_model = None
        self._dialogue_manager = None
        self._skill_transfer_layer = None


def test_integrator_tick_with_empty_orchestrator():
    from speace_core.cellular_brain.latent_transfer.runtime_latent_integrator import RuntimeLatentIntegrator
    orch = FakeOrchestratorT117()
    integrator = RuntimeLatentIntegrator(orchestrator=orch, vector_dim=16)
    report = integrator.tick()
    assert report["tick"] == 1
    assert report["packets_generated"] == 0  # no modules present
    assert integrator.latest_metrics()["packet_count"] == 0


def test_integrator_history_and_drift():
    from speace_core.cellular_brain.latent_transfer.runtime_latent_integrator import RuntimeLatentIntegrator
    from speace_core.cellular_brain.latent_transfer.latent_packet import LatentPacket, VectorSource
    orch = FakeOrchestratorT117()
    integrator = RuntimeLatentIntegrator(orchestrator=orch, vector_dim=4)
    # Manually inject history
    integrator._history[VectorSource.MEMORY].append(LatentPacket(vector=[1.0, 0.0, 0.0, 0.0], source=VectorSource.MEMORY))
    integrator._history[VectorSource.MEMORY].append(LatentPacket(vector=[0.9, 0.1, 0.0, 0.0], source=VectorSource.MEMORY))
    metrics = integrator._compute_metrics(integrator._history[VectorSource.MEMORY])
    assert metrics["packet_count"] == 2
    assert metrics["mean_drift"] > 0
    assert metrics["mean_cosine_similarity"] > 0.9


def test_integrator_snapshot():
    from speace_core.cellular_brain.latent_transfer.runtime_latent_integrator import RuntimeLatentIntegrator
    orch = FakeOrchestratorT117()
    integrator = RuntimeLatentIntegrator(orchestrator=orch, vector_dim=8)
    snap = integrator.snapshot()
    assert snap["tick"] == 0
    assert snap["vector_dim"] == 8
    assert "local_bus" in snap
