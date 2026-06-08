"""Tests for CoherenceProposalExecutor — T154-B."""

import pytest

from speace_core.cellular_brain.analysis.coherence_proposal_executor import (
    CoherenceProposalExecutor,
)


class TestCoherenceProposalExecutor:
    def test_blocked_type_not_allowed(self):
        executor = CoherenceProposalExecutor()
        result = executor.execute({"proposal_id": "p1", "proposal_type": "hack_governance"})
        assert result["outcome"] == "blocked"
        assert "not_allowed" in result["note"]

    def test_successful_execution(self):
        executor = CoherenceProposalExecutor()
        pre = {
            "metrics": {"redundancy_efficiency": 0.5},
            "aggregate_coherence": 0.5,
        }
        result = executor.execute(
            {"proposal_id": "p2", "proposal_type": "prune_redundant_skills"},
            pre_coherence=pre,
        )
        assert result["outcome"] == "success"
        assert result["post_coherence"] > result["pre_coherence"]

    def test_rollback_when_worsens(self):
        executor = CoherenceProposalExecutor()
        # Mock a scenario where coherence worsens: we set pre very high, but the effect will add delta
        # which in this case improves; to simulate worsening we need a metric where delta is negative
        # and we craft pre so post < pre * 0.95
        pre = {
            "metrics": {"regulation_density": 0.5},  # delta is -0.05 → 0.45, which is < 0.5 * 0.95 = 0.475
            "aggregate_coherence": 0.5,
        }
        result = executor.execute(
            {"proposal_id": "p3", "proposal_type": "lower_regulation_density"},
            pre_coherence=pre,
        )
        assert result["outcome"] == "rollback"
        assert "regressed" in result["note"]

    def test_proposal_with_blocked_categories(self):
        executor = CoherenceProposalExecutor()
        result = executor.execute(
            {
                "proposal_id": "p4",
                "proposal_type": "prune_redundant_skills",
                "blocked_categories": ["safety", "auth"],
            },
            pre_coherence=None,
        )
        # None pre_coherence → success without regression check
        assert result["outcome"] == "success"
