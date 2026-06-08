"""Tests for CoherenceProposalBuilder — T154-B."""

import pytest

from speace_core.cellular_brain.analysis.coherence_proposal_builder import (
    CoherenceProposalBuilder,
)


class TestCoherenceProposalBuilder:
    def test_build_from_report_generates_proposals(self):
        builder = CoherenceProposalBuilder()
        report = {
            "run_id": "test_001",
            "timestamp": 0,
            "metrics": {
                "redundancy_efficiency": 0.5,   # below 0.7
                "mutation_stability": 0.3,    # below 0.5
                "regulation_density": 0.95,   # above 0.9 (worse is higher here? Actually threshold means below)
                "modular_coherence": 0.4,       # below 0.5
            },
            "aggregate_coherence": 0.5,
        }
        proposals = builder.build_from_report(report)
        assert len(proposals) > 0
        ids = {p["proposal_id"] for p in proposals}
        assert len(ids) == len(proposals)  # unique ids

    def test_proposal_types_are_allowed(self):
        builder = CoherenceProposalBuilder()
        report = {
            "metrics": {"redundancy_efficiency": 0.5},
            "aggregate_coherence": 0.5,
        }
        proposals = builder.build_from_report(report)
        for p in proposals:
            assert p["proposal_type"] in builder.ALLOWED_TYPES

    def test_blocked_categories_present(self):
        builder = CoherenceProposalBuilder()
        report = {"metrics": {"redundancy_efficiency": 0.5}, "aggregate_coherence": 0.5}
        proposals = builder.build_from_report(report)
        for p in proposals:
            blocked = p.get("blocked_categories", [])
            assert "safety" in blocked
            assert "auth" in blocked
            assert "governance" in blocked
            assert "physical_action" in blocked

    def test_no_proposal_when_metric_above_threshold(self):
        builder = CoherenceProposalBuilder()
        report = {
            "metrics": {"redundancy_efficiency": 0.9},  # above 0.7
            "aggregate_coherence": 0.8,
        }
        proposals = builder.build_from_report(report)
        assert len(proposals) == 0

    def test_list_and_get(self):
        builder = CoherenceProposalBuilder()
        report = {"metrics": {"redundancy_efficiency": 0.5}, "aggregate_coherence": 0.5}
        proposals = builder.build_from_report(report)
        pid = proposals[0]["proposal_id"]
        assert builder.get_proposal(pid) is not None
        pending = builder.list_proposals(status="pending")
        assert len(pending) >= 1

    def test_update_status(self):
        builder = CoherenceProposalBuilder()
        report = {"metrics": {"redundancy_efficiency": 0.5}, "aggregate_coherence": 0.5}
        proposals = builder.build_from_report(report)
        pid = proposals[0]["proposal_id"]
        assert builder.update_status(pid, "approved", reviewer="tester")
        p = builder.get_proposal(pid)
        assert p["status"] == "approved"
        assert p["reviewer"] == "tester"
