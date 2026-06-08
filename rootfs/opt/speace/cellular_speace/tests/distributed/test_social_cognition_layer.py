"""Tests for T167 — Social Cognition Layer."""

import time

import pytest

from speace_core.cellular_brain.distributed.social_cognition_engine import MentalModel, SocialCognitionEngine
from speace_core.cellular_brain.distributed.social_coordinator import SocialCoordinator
from speace_core.cellular_brain.distributed.trust_reputation_model import TrustReputationModel


class TestMentalModel:
    def test_initial_reliability(self) -> None:
        m = MentalModel("node_a")
        assert m.predicted_reliability == 0.5

    def test_update_reliability(self) -> None:
        m = MentalModel("node_a")
        m.update_reliability(1.0)
        assert m.predicted_reliability > 0.5
        m.update_reliability(0.0)
        assert m.predicted_reliability < 0.8

    def test_record_interaction(self) -> None:
        m = MentalModel("node_a")
        m.record_interaction("sync", "success")
        assert len(m.interaction_history) == 1

    def test_snapshot(self) -> None:
        m = MentalModel("node_a")
        snap = m.snapshot()
        assert snap["node_id"] == "node_a"
        assert "predicted_reliability" in snap


class TestSocialCognitionEngine:
    def test_get_or_create_model(self) -> None:
        engine = SocialCognitionEngine()
        model = engine.get_or_create_model("node_b")
        assert isinstance(model, MentalModel)
        assert "node_b" in engine._models

    def test_record_interaction(self) -> None:
        engine = SocialCognitionEngine()
        engine.record_interaction("node_b", "sync", "observed")
        assert len(engine.list_models()) == 1

    def test_update_reliability(self) -> None:
        engine = SocialCognitionEngine()
        engine.update_reliability("node_b", 0.9)
        assert engine.get_or_create_model("node_b").predicted_reliability > 0.5

    def test_snapshot(self) -> None:
        engine = SocialCognitionEngine()
        engine.record_interaction("node_c", "sync", "observed")
        snap = engine.snapshot()
        assert snap["model_count"] == 1


class TestTrustReputationModel:
    def test_default_trust(self) -> None:
        tr = TrustReputationModel()
        assert tr.get_trust("node_x") == 0.5

    def test_positive_boosts(self) -> None:
        tr = TrustReputationModel()
        tr.record_positive("node_x")
        assert tr.get_trust("node_x") > 0.5

    def test_negative_reduces(self) -> None:
        tr = TrustReputationModel()
        tr.record_positive("node_x")
        tr.record_negative("node_x")
        assert tr.get_trust("node_x") < 0.5

    def test_decay_over_time(self) -> None:
        tr = TrustReputationModel()
        tr.record_positive("node_x")
        high = tr.get_trust("node_x")
        # Manually set last_positive to past
        tr._last_positive["node_x"] = time.time() - 86400 * 10
        low = tr.get_trust("node_x")
        assert low < high

    def test_can_cooperate_threshold(self) -> None:
        tr = TrustReputationModel()
        tr.record_positive("node_x")
        tr.record_positive("node_x")
        assert tr.can_cooperate("node_x")
        tr.record_negative("node_x")
        tr.record_negative("node_x")
        assert not tr.can_cooperate("node_x")

    def test_snapshot(self) -> None:
        tr = TrustReputationModel()
        tr.record_positive("node_y")
        snap = tr.snapshot()
        assert "trust_matrix" in snap


class TestSocialCoordinator:
    def test_propose_cooperation_when_trust_high(self) -> None:
        tr = TrustReputationModel()
        tr.record_positive("node_z")
        tr.record_positive("node_z")
        coord = SocialCoordinator(trust_model=tr)
        prop = coord.propose_cooperation("node_z", "task_share", {"task": "backup"})
        assert prop is not None
        assert prop["type"] == "cooperation"

    def test_propose_cooperation_when_trust_low(self) -> None:
        tr = TrustReputationModel()
        coord = SocialCoordinator(trust_model=tr)
        prop = coord.propose_cooperation("node_z", "task_share", {})
        assert prop is None

    def test_detect_conflict(self) -> None:
        coord = SocialCoordinator()
        conf = coord.detect_conflict("node_z", "world_model", "A", "B")
        assert conf is not None
        assert conf["status"] == "detected"
        assert len(coord.list_conflicts()) == 1

    def test_no_conflict_when_same(self) -> None:
        coord = SocialCoordinator()
        conf = coord.detect_conflict("node_z", "world_model", "A", "A")
        assert conf is None

    def test_snapshot(self) -> None:
        tr = TrustReputationModel()
        tr.record_positive("node_z")
        coord = SocialCoordinator(trust_model=tr)
        coord.propose_cooperation("node_z", "task_share", {})
        snap = coord.snapshot()
        assert "pending_proposals" in snap
        assert "trust_snapshot" in snap
