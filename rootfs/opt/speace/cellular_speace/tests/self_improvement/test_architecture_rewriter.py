import pytest

from speace_core.cellular_brain.self_improvement.limitation_detector import (
    LimitationDiagnosis,
    LimitationSignal,
)
from speace_core.cellular_brain.self_improvement.architecture_rewriter import (
    ArchitectureRewriter,
    ArchitectureRewriteProposal,
)


class TestArchitectureRewriter:
    def test_generates_t44_proposal_for_semantic_association_missing(self):
        rewriter = ArchitectureRewriter()
        diagnosis = LimitationDiagnosis(
            id="diag-test",
            signals=[
                LimitationSignal(
                    id="sig-1",
                    source="metrics",
                    category="semantic_association_missing",
                    severity=0.6,
                    confidence=0.85,
                    description="Assemblies exist but no associations",
                    detected_at="2024-01-01T00:00:00Z",
                )
            ],
            primary_category="semantic_association_missing",
            root_cause_hypothesis="Missing associative learning",
            affected_modules=["semantic_memory"],
            recommended_action_type="module_addition",
        )
        proposal = rewriter.generate_proposal(diagnosis)
        assert "T44" in proposal.title
        assert proposal.proposal_type == "module_addition"
        assert "semantic_memory" in proposal.target_modules
        assert proposal.status == "draft"

    def test_generates_routing_redesign_for_routing_no_effect(self):
        rewriter = ArchitectureRewriter()
        diagnosis = LimitationDiagnosis(
            id="diag-test",
            signals=[],
            primary_category="routing_no_effect",
            root_cause_hypothesis="Routing produces no signal flow",
            affected_modules=["region_signal_router"],
            recommended_action_type="routing_redesign",
        )
        proposal = rewriter.generate_proposal(diagnosis)
        assert "Routing" in proposal.title
        assert proposal.proposal_type == "routing_redesign"

    def test_generates_stability_proposal_for_phi_regression(self):
        rewriter = ArchitectureRewriter()
        diagnosis = LimitationDiagnosis(
            id="diag-test",
            signals=[],
            primary_category="phi_regression",
            root_cause_hypothesis="Phi regressing",
            affected_modules=["region_stability_controller"],
            recommended_action_type="stability_control",
        )
        proposal = rewriter.generate_proposal(diagnosis)
        assert "Stability" in proposal.title or "stability" in proposal.title.lower()
        assert proposal.proposal_type == "module_refactor"

    def test_estimates_risk_bounds(self):
        rewriter = ArchitectureRewriter()
        proposal = ArchitectureRewriteProposal(
            id="prop-test",
            diagnosis_id="diag-test",
            title="Test Proposal",
            proposal_type="module_addition",
            rationale="Test rationale",
            expected_risks={"safety": 0.10, "regression": 0.15},
            created_at="2024-01-01T00:00:00Z",
        )
        risks = rewriter.estimate_risk(proposal)
        assert risks["safety"] >= 0.15
        assert risks["regression"] >= 0.20
        assert all(v <= 1.0 for v in risks.values())

    def test_estimates_benefit_bounds(self):
        rewriter = ArchitectureRewriter()
        proposal = ArchitectureRewriteProposal(
            id="prop-test",
            diagnosis_id="diag-test",
            title="Test Proposal",
            proposal_type="parameter_tuning",
            rationale="Test rationale",
            expected_benefits={"recall_rate": 0.5, "phi": 1.2},
            created_at="2024-01-01T00:00:00Z",
        )
        benefits = rewriter.estimate_benefit(proposal)
        assert benefits["recall_rate"] == 0.5
        assert benefits["phi"] == 1.0

    def test_validates_conservative_safety_constraints(self):
        rewriter = ArchitectureRewriter()
        proposal = ArchitectureRewriteProposal(
            id="prop-test",
            diagnosis_id="diag-test",
            title="Test Proposal",
            proposal_type="parameter_tuning",
            rationale="Test rationale",
            safety_constraints=["No core mutation", "Run tests first"],
            rollback_plan=["Revert parameters"],
            created_at="2024-01-01T00:00:00Z",
        )
        assert rewriter.validate_safety_constraints(proposal) is True

    def test_rejects_unsafe_high_risk_proposal(self):
        rewriter = ArchitectureRewriter()
        proposal = ArchitectureRewriteProposal(
            id="prop-test",
            diagnosis_id="diag-test",
            title="Test Proposal",
            proposal_type="genome_mutation",
            rationale="Test rationale",
            expected_risks={"safety": 0.30, "regression": 0.40},
            created_at="2024-01-01T00:00:00Z",
        )
        risks = rewriter.estimate_risk(proposal)
        assert risks["safety"] == 0.30
        assert risks["regression"] == 0.40

    def test_fallback_generic_proposal(self):
        rewriter = ArchitectureRewriter()
        diagnosis = LimitationDiagnosis(
            id="diag-test",
            signals=[],
            primary_category="unknown_category",
            root_cause_hypothesis="Something is wrong",
            affected_modules=["module_a"],
            recommended_action_type="no_action",
        )
        proposal = rewriter.generate_proposal(diagnosis)
        assert proposal.proposal_type == "parameter_tuning"
        assert proposal.status == "draft"
