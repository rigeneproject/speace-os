import pytest
from speace_core.cellular_brain.action_governance.action_governance_models import (
    ExternalActionProposal,
    ExternalActionType,
)
from speace_core.cellular_brain.action_governance.reversibility_analyzer import (
    ReversibilityAnalyzer,
)


def test_assess_reversibility_observe():
    analyzer = ReversibilityAnalyzer()
    p = ExternalActionProposal(proposal_id="p1", action_type=ExternalActionType.OBSERVE_ONLY)
    rev = analyzer.assess_reversibility(p)
    assert rev.reversible is True
    assert rev.reversibility_score == 1.0
    assert rev.rollback_complexity_score == 0.0


def test_assess_reversibility_actuate_external():
    analyzer = ReversibilityAnalyzer()
    p = ExternalActionProposal(proposal_id="p1", action_type=ExternalActionType.ACTUATE_EXTERNAL)
    rev = analyzer.assess_reversibility(p)
    assert rev.reversible is False
    assert rev.reversibility_score == 0.0
    assert rev.rollback_complexity_score == 1.0
    assert rev.irreversible_effect_detected is True


def test_detect_irreversible_effects_actuate():
    analyzer = ReversibilityAnalyzer()
    p = ExternalActionProposal(proposal_id="p1", action_type=ExternalActionType.ACTUATE_EXTERNAL)
    assert analyzer.detect_irreversible_effects(p) is True


def test_detect_irreversible_effects_isolate_high_risk():
    analyzer = ReversibilityAnalyzer()
    p = ExternalActionProposal(proposal_id="p1", action_type=ExternalActionType.ISOLATE_SIMULATED, estimated_risk=0.7)
    assert analyzer.detect_irreversible_effects(p) is True


def test_estimate_rollback_complexity():
    analyzer = ReversibilityAnalyzer()
    assert analyzer.estimate_rollback_complexity(
        ExternalActionProposal(proposal_id="p1", action_type=ExternalActionType.OBSERVE_ONLY)
    ) == 0.0
    assert analyzer.estimate_rollback_complexity(
        ExternalActionProposal(proposal_id="p1", action_type=ExternalActionType.ACTUATE_EXTERNAL)
    ) == 1.0
    assert analyzer.estimate_rollback_complexity(
        ExternalActionProposal(proposal_id="p1", action_type=ExternalActionType.ISOLATE_SIMULATED)
    ) == 0.6


def test_compute_reversibility_score_resource_shift():
    analyzer = ReversibilityAnalyzer()
    p = ExternalActionProposal(proposal_id="p1", action_type=ExternalActionType.RESOURCE_SHIFT_SIMULATED)
    assert analyzer.compute_reversibility_score(p) == 0.7
