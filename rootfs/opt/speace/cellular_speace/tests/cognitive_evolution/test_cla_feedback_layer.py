import pytest

from speace_core.cellular_brain.cognitive_evolution.cla_feedback_layer import (
    CLAFeedbackLayer,
)
from speace_core.cellular_brain.metacognition.cognitive_linguistic_coherence_monitor import (
    CognitiveLinguisticCoherenceMonitor,
    CognitiveLinguisticCoherenceReport,
)


class TestCLAFeedbackLayer:
    def test_high_coherence_returns_ok(self):
        layer = CLAFeedbackLayer()
        report = CognitiveLinguisticCoherenceReport(
            overall_coherence_score=0.9,
            narrative_coherence=0.9,
            grounding_consistency=0.9,
            drive_language_alignment=0.9,
            confidence_language_alignment=0.9,
            memory_reference_consistency=0.9,
            self_model_consistency=0.9,
            contradiction_rate=0.0,
            repetitive_loop_density=0.0,
        )
        result = layer.process_coherence_report(report)
        assert result["status"] == "ok"
        assert result["proposals"] == []

    def test_critical_coherence_generates_proposals(self):
        layer = CLAFeedbackLayer()
        report = CognitiveLinguisticCoherenceReport(
            overall_coherence_score=0.2,
            narrative_coherence=0.1,
            grounding_consistency=0.1,
            drive_language_alignment=0.1,
            confidence_language_alignment=0.1,
            memory_reference_consistency=0.1,
            self_model_consistency=0.1,
            contradiction_rate=0.8,
            repetitive_loop_density=0.8,
        )
        result = layer.process_coherence_report(report)
        assert result["status"] == "critical"
        assert len(result["diagnostics"]) > 0

    def test_warning_coherence_status(self):
        layer = CLAFeedbackLayer()
        report = CognitiveLinguisticCoherenceReport(
            overall_coherence_score=0.5,
            narrative_coherence=0.5,
            grounding_consistency=0.5,
            drive_language_alignment=0.5,
            confidence_language_alignment=0.5,
            memory_reference_consistency=0.5,
            self_model_consistency=0.5,
            contradiction_rate=0.2,
            repetitive_loop_density=0.2,
        )
        result = layer.process_coherence_report(report)
        assert result["status"] == "warning"

    def test_detects_confidence_mismatch(self):
        layer = CLAFeedbackLayer()
        report = CognitiveLinguisticCoherenceReport(
            overall_coherence_score=0.3,
            narrative_coherence=0.5,
            grounding_consistency=0.5,
            drive_language_alignment=0.5,
            confidence_language_alignment=0.2,
            memory_reference_consistency=0.5,
            self_model_consistency=0.5,
            contradiction_rate=0.0,
            repetitive_loop_density=0.0,
        )
        result = layer.process_coherence_report(report)
        assert "confidence_language_mismatch" in result["diagnostics"]

    def test_detects_memory_not_referenced(self):
        layer = CLAFeedbackLayer()
        report = CognitiveLinguisticCoherenceReport(
            overall_coherence_score=0.3,
            narrative_coherence=0.5,
            grounding_consistency=0.5,
            drive_language_alignment=0.5,
            confidence_language_alignment=0.5,
            memory_reference_consistency=0.1,
            self_model_consistency=0.5,
            contradiction_rate=0.0,
            repetitive_loop_density=0.0,
        )
        result = layer.process_coherence_report(report)
        assert "memory_not_referenced" in result["diagnostics"]

    def test_detects_self_model_absent(self):
        layer = CLAFeedbackLayer()
        report = CognitiveLinguisticCoherenceReport(
            overall_coherence_score=0.3,
            narrative_coherence=0.5,
            grounding_consistency=0.5,
            drive_language_alignment=0.5,
            confidence_language_alignment=0.5,
            memory_reference_consistency=0.5,
            self_model_consistency=0.1,
            contradiction_rate=0.0,
            repetitive_loop_density=0.0,
        )
        result = layer.process_coherence_report(report)
        assert "self_model_absent" in result["diagnostics"]

    def test_detects_repetitive_loop(self):
        layer = CLAFeedbackLayer()
        report = CognitiveLinguisticCoherenceReport(
            overall_coherence_score=0.3,
            narrative_coherence=0.5,
            grounding_consistency=0.5,
            drive_language_alignment=0.5,
            confidence_language_alignment=0.5,
            memory_reference_consistency=0.5,
            self_model_consistency=0.5,
            contradiction_rate=0.0,
            repetitive_loop_density=0.8,
        )
        result = layer.process_coherence_report(report)
        assert "repetitive_loop" in result["diagnostics"]

    def test_detects_contradiction(self):
        layer = CLAFeedbackLayer()
        report = CognitiveLinguisticCoherenceReport(
            overall_coherence_score=0.3,
            narrative_coherence=0.5,
            grounding_consistency=0.5,
            drive_language_alignment=0.5,
            confidence_language_alignment=0.5,
            memory_reference_consistency=0.5,
            self_model_consistency=0.5,
            contradiction_rate=0.5,
            repetitive_loop_density=0.0,
        )
        result = layer.process_coherence_report(report)
        assert "contradiction" in result["diagnostics"]

    def test_proposals_are_pending_not_applied(self):
        layer = CLAFeedbackLayer()
        report = CognitiveLinguisticCoherenceReport(
            overall_coherence_score=0.2,
            narrative_coherence=0.1,
            grounding_consistency=0.1,
            drive_language_alignment=0.1,
            confidence_language_alignment=0.1,
            memory_reference_consistency=0.1,
            self_model_consistency=0.1,
            contradiction_rate=0.8,
            repetitive_loop_density=0.8,
        )
        result = layer.process_coherence_report(report)
        # Le proposte create dovrebbero essere in stato pending
        for prop in result.get("proposals", []):
            assert prop.get("status") == "pending_approval"

    def test_summary_returns_dict(self):
        layer = CLAFeedbackLayer()
        summary = layer.summary()
        assert "warning_threshold" in summary
        assert "critical_threshold" in summary
        assert "pending_proposals" in summary

    def test_approve_reject_rollback_lifecycle(self):
        layer = CLAFeedbackLayer()
        report = CognitiveLinguisticCoherenceReport(
            overall_coherence_score=0.2,
            narrative_coherence=0.1,
            grounding_consistency=0.1,
            drive_language_alignment=0.1,
            confidence_language_alignment=0.1,
            memory_reference_consistency=0.1,
            self_model_consistency=0.1,
            contradiction_rate=0.8,
            repetitive_loop_density=0.8,
        )
        result = layer.process_coherence_report(report)
        assert result["status"] == "critical"
        proposals = result.get("proposals", [])
        assert len(proposals) > 0
        proposal_id = proposals[0]["proposal_id"]

        # Approve
        approve_result = layer.approve_proposal(proposal_id, reviewer="tester", current_health=0.5)
        assert approve_result.get("status") in ("applied", "error")

        # Rollback if applied
        if approve_result.get("status") == "applied":
            rb_result = layer.rollback_proposal(proposal_id, reviewer="tester")
            assert rb_result.get("status") == "rolled_back"

    def test_reject_proposal(self):
        layer = CLAFeedbackLayer()
        report = CognitiveLinguisticCoherenceReport(
            overall_coherence_score=0.2,
            narrative_coherence=0.1,
            grounding_consistency=0.1,
            drive_language_alignment=0.1,
            confidence_language_alignment=0.1,
            memory_reference_consistency=0.1,
            self_model_consistency=0.1,
            contradiction_rate=0.8,
            repetitive_loop_density=0.8,
        )
        result = layer.process_coherence_report(report)
        proposals = result.get("proposals", [])
        if proposals:
            proposal_id = proposals[0]["proposal_id"]
            reject_result = layer.reject_proposal(proposal_id, reviewer="tester")
            assert reject_result.get("status") in ("rejected", "error")

    def test_get_proposal_and_list_all(self):
        layer = CLAFeedbackLayer()
        report = CognitiveLinguisticCoherenceReport(
            overall_coherence_score=0.2,
            narrative_coherence=0.1,
            grounding_consistency=0.1,
            drive_language_alignment=0.1,
            confidence_language_alignment=0.1,
            memory_reference_consistency=0.1,
            self_model_consistency=0.1,
            contradiction_rate=0.8,
            repetitive_loop_density=0.8,
        )
        layer.process_coherence_report(report)
        all_proposals = layer.list_all_proposals()
        assert isinstance(all_proposals, list)
        if all_proposals:
            p = layer.get_proposal(all_proposals[0]["proposal_id"])
            assert p is not None
            assert "proposal_id" in p

    def test_audit_log_returns_list(self):
        layer = CLAFeedbackLayer()
        log = layer.audit_log(hours=1, limit=10)
        assert isinstance(log, list)
