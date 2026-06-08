import json
import tempfile
from pathlib import Path

import pytest

from speace_core.cellular_brain.self_improvement.architecture_rewriter import (
    ArchitectureRewriteProposal,
    SelfImprovementCycleResult,
)
from speace_core.cellular_brain.self_improvement.proposal_store import ProposalStore


class TestProposalStore:
    def test_save_and_load_proposal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProposalStore(base_path=tmpdir)
            proposal = ArchitectureRewriteProposal(
                id="prop-001",
                diagnosis_id="diag-001",
                title="Test Proposal",
                proposal_type="module_addition",
                target_modules=["semantic_memory"],
                rationale="Test rationale",
                expected_benefits={"recall": 0.5},
                expected_risks={"safety": 0.1},
                implementation_plan=["Step 1"],
                rollback_plan=["Revert"],
                safety_constraints=["No core mutation"],
                status="draft",
                created_at="2024-01-01T00:00:00Z",
            )
            store.save_proposal(proposal)
            loaded = store.load_proposal("prop-001")
            assert loaded.id == "prop-001"
            assert loaded.title == "Test Proposal"

    def test_list_proposals_by_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProposalStore(base_path=tmpdir)
            for status in ["draft", "draft", "accepted"]:
                proposal = ArchitectureRewriteProposal(
                    id=f"prop-{status}",
                    diagnosis_id="diag-001",
                    title=f"Proposal {status}",
                    proposal_type="parameter_tuning",
                    rationale="Test rationale",
                    status=status,
                    created_at="2024-01-01T00:00:00Z",
                )
                store.save_proposal(proposal)
            drafts = store.list_proposals(status="draft")
            assert len(drafts) == 2
            accepted = store.list_proposals(status="accepted")
            assert len(accepted) == 1
            all_proposals = store.list_proposals()
            assert len(all_proposals) == 3

    def test_save_and_load_cycle_result(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProposalStore(base_path=tmpdir)
            result = SelfImprovementCycleResult(
                cycle_id="cycle-001",
                final_verdict="SAFE_PROPOSAL_GENERATED",
            )
            store.save_cycle_result(result)
            cycles = store.list_cycle_results()
            assert len(cycles) == 1
            assert cycles[0].cycle_id == "cycle-001"
            assert cycles[0].final_verdict == "SAFE_PROPOSAL_GENERATED"

    def test_missing_store_files_return_empty_lists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProposalStore(base_path=tmpdir)
            assert store.list_proposals() == []
            assert store.list_cycle_results() == []

    def test_jsonl_persistence_is_append_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProposalStore(base_path=tmpdir)
            for i in range(3):
                proposal = ArchitectureRewriteProposal(
                    id=f"prop-{i}",
                    diagnosis_id="diag-001",
                    title=f"Proposal {i}",
                    proposal_type="parameter_tuning",
                    rationale="Test rationale",
                    status="draft",
                    created_at="2024-01-01T00:00:00Z",
                )
                store.save_proposal(proposal)
            proposals_path = Path(tmpdir) / "proposals.jsonl"
            with open(proposals_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            assert len(lines) == 3
