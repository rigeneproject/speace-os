import pytest
import tempfile

from speace_core.cellular_brain.self_improvement.outcome_tracker import ProposalOutcome
from speace_core.cellular_brain.self_improvement.proposal_learning_engine import (
    ProposalLearningEngine,
    ProposalLearningRecord,
)


class FakeMorphologicalMemory:
    def __init__(self):
        self.events = []

    def log_event(self, event):
        self.events.append(event)


class TestProposalLearningEngine:
    def test_learning_record_created_from_outcome(self):
        with tempfile.TemporaryDirectory() as td:
            mem = FakeMorphologicalMemory()
            engine = ProposalLearningEngine(base_path=td, memory=mem)
            outcome = ProposalOutcome(
                id="out-001",
                proposal_id="prop-001",
                originating_limitation_type="semantic_association_missing",
                implemented_task_id="T44",
                audit_verdict="ASSOCIATIVE_MEMORY_VALIDATED",
                net_gain=0.29,
                success=True,
                timestamp="2026-05-17T00:00:00",
            )
            record = engine.update_from_outcome(outcome)
            assert record.limitation_type == "semantic_association_missing"
            assert record.proposed_task_id == "T44"
            assert record.attempts == 1
            assert record.successes == 1

    def test_successful_outcome_increases_confidence(self):
        with tempfile.TemporaryDirectory() as td:
            mem = FakeMorphologicalMemory()
            engine = ProposalLearningEngine(base_path=td, memory=mem)
            outcome = ProposalOutcome(
                id="out-001",
                proposal_id="prop-001",
                originating_limitation_type="semantic_association_missing",
                implemented_task_id="T44",
                audit_verdict="ASSOCIATIVE_MEMORY_VALIDATED",
                net_gain=0.29,
                success=True,
                timestamp="2026-05-17T00:00:00",
            )
            record = engine.update_from_outcome(outcome)
            assert record.confidence > 0.0

    def test_regression_outcome_decreases_confidence(self):
        with tempfile.TemporaryDirectory() as td:
            mem = FakeMorphologicalMemory()
            engine = ProposalLearningEngine(base_path=td, memory=mem)
            outcome = ProposalOutcome(
                id="out-001",
                proposal_id="prop-001",
                originating_limitation_type="semantic_association_missing",
                implemented_task_id="T44",
                audit_verdict="ENERGY_REGRESSION",
                net_gain=-0.1,
                success=False,
                regression_detected=True,
                timestamp="2026-05-17T00:00:00",
            )
            record = engine.update_from_outcome(outcome)
            assert record.confidence < 0.5

    def test_confidence_clamped_between_zero_and_one(self):
        with tempfile.TemporaryDirectory() as td:
            mem = FakeMorphologicalMemory()
            engine = ProposalLearningEngine(base_path=td, memory=mem)
            for i in range(5):
                outcome = ProposalOutcome(
                    id=f"out-{i}",
                    proposal_id="prop-001",
                    originating_limitation_type="semantic_association_missing",
                    implemented_task_id="T44",
                    audit_verdict="ASSOCIATIVE_MEMORY_VALIDATED",
                    net_gain=0.9,
                    success=True,
                    timestamp="2026-05-17T00:00:00",
                )
                record = engine.update_from_outcome(outcome)
            assert 0.0 <= record.confidence <= 1.0

    def test_mean_net_gain_updates_incrementally(self):
        with tempfile.TemporaryDirectory() as td:
            mem = FakeMorphologicalMemory()
            engine = ProposalLearningEngine(base_path=td, memory=mem)
            record = engine.update_from_outcome(
                ProposalOutcome(
                    id="out-1",
                    proposal_id="prop-001",
                    originating_limitation_type="l1",
                    implemented_task_id="T44",
                    audit_verdict="VALIDATED",
                    net_gain=0.2,
                    success=True,
                    timestamp="t1",
                )
            )
            assert record.mean_net_gain == pytest.approx(0.2)
            record = engine.update_from_outcome(
                ProposalOutcome(
                    id="out-2",
                    proposal_id="prop-001",
                    originating_limitation_type="l1",
                    implemented_task_id="T44",
                    audit_verdict="VALIDATED",
                    net_gain=0.4,
                    success=True,
                    timestamp="t2",
                )
            )
            assert record.mean_net_gain == pytest.approx(0.3)

    def test_rank_candidate_proposals_prefers_high_confidence_mapping(self):
        with tempfile.TemporaryDirectory() as td:
            mem = FakeMorphologicalMemory()
            engine = ProposalLearningEngine(base_path=td, memory=mem)
            engine.update_from_outcome(
                ProposalOutcome(
                    id="out-1",
                    proposal_id="prop-a",
                    originating_limitation_type="l1",
                    implemented_task_id="T44",
                    audit_verdict="VALIDATED",
                    net_gain=0.8,
                    success=True,
                    timestamp="t1",
                )
            )
            engine.update_from_outcome(
                ProposalOutcome(
                    id="out-2",
                    proposal_id="prop-b",
                    originating_limitation_type="l1",
                    implemented_task_id="T45",
                    audit_verdict="VALIDATED",
                    net_gain=0.1,
                    success=True,
                    timestamp="t2",
                )
            )
            candidates = [
                {"task_id": "T45", "proposal_id": "prop-b"},
                {"task_id": "T44", "proposal_id": "prop-a"},
            ]
            ranked = engine.rank_candidate_proposals("l1", candidates)
            assert ranked[0]["task_id"] == "T44"

    def test_rank_candidate_proposals_penalizes_regression_mapping(self):
        with tempfile.TemporaryDirectory() as td:
            mem = FakeMorphologicalMemory()
            engine = ProposalLearningEngine(base_path=td, memory=mem)
            engine.update_from_outcome(
                ProposalOutcome(
                    id="out-1",
                    proposal_id="prop-a",
                    originating_limitation_type="l1",
                    implemented_task_id="T44",
                    audit_verdict="VALIDATED",
                    net_gain=0.5,
                    success=True,
                    timestamp="t1",
                )
            )
            engine.update_from_outcome(
                ProposalOutcome(
                    id="out-2",
                    proposal_id="prop-b",
                    originating_limitation_type="l1",
                    implemented_task_id="T45",
                    audit_verdict="REGRESSION",
                    net_gain=-0.2,
                    success=False,
                    regression_detected=True,
                    timestamp="t2",
                )
            )
            candidates = [
                {"task_id": "T45", "proposal_id": "prop-b"},
                {"task_id": "T44", "proposal_id": "prop-a"},
            ]
            ranked = engine.rank_candidate_proposals("l1", candidates)
            assert ranked[0]["task_id"] == "T44"

    def test_load_learning_records_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            engine = ProposalLearningEngine(base_path=td)
            engine.update_from_outcome(
                ProposalOutcome(
                    id="out-1",
                    proposal_id="prop-001",
                    originating_limitation_type="l1",
                    implemented_task_id="T44",
                    audit_verdict="VALIDATED",
                    net_gain=0.5,
                    success=True,
                    timestamp="t1",
                )
            )
            engine2 = ProposalLearningEngine(base_path=td)
            record = engine2.get_learning_record("l1", "T44")
            assert record is not None
            assert record.attempts == 1

    def test_t44b_outcome_yields_high_confidence_for_semantic_association_missing(self):
        with tempfile.TemporaryDirectory() as td:
            mem = FakeMorphologicalMemory()
            engine = ProposalLearningEngine(base_path=td, memory=mem)
            outcome = ProposalOutcome(
                id="out-t44b",
                proposal_id="prop-t45",
                originating_limitation_type="semantic_association_missing",
                implemented_task_id="T44",
                audit_verdict="ASSOCIATIVE_MEMORY_VALIDATED",
                net_gain=0.2903,
                success=True,
                timestamp="2026-05-17T00:00:00",
            )
            record = engine.update_from_outcome(outcome)
            assert record.confidence > 0.50

    def test_get_learning_record_returns_none_for_unknown(self):
        with tempfile.TemporaryDirectory() as td:
            engine = ProposalLearningEngine(base_path=td)
            assert engine.get_learning_record("unknown", "T99") is None
