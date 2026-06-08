import pytest

from speace_core.cellular_brain.metacognition.cognitive_linguistic_coherence_monitor import (
    CognitiveLinguisticCoherenceMonitor,
    CognitiveLinguisticCoherenceReport,
)


class TestCognitiveLinguisticCoherenceMonitor:
    def test_initial_state_no_report(self):
        monitor = CognitiveLinguisticCoherenceMonitor()
        assert monitor.get_last_report() is None

    def test_evaluate_turn_returns_report(self):
        monitor = CognitiveLinguisticCoherenceMonitor()
        report = monitor.evaluate_turn(
            user_message="ciao",
            speace_response="Ciao Roberto. Sono SPEACE.",
            topic="greetings",
            turn_count=1,
            grounded_concepts=["greetings"],
        )
        assert isinstance(report, CognitiveLinguisticCoherenceReport)
        assert report.turn_count == 1
        assert report.narrative_coherence >= 0.0
        assert report.grounding_consistency >= 0.0
        assert report.overall_coherence_score >= 0.0

    def test_self_model_consistency_with_name(self):
        monitor = CognitiveLinguisticCoherenceMonitor()
        report = monitor.evaluate_turn(
            user_message="chi sei",
            speace_response="Sono SPEACE, un sistema cognitivo organismico.",
            topic="identity",
            turn_count=1,
        )
        # La risposta contiene "SPEACE" e "sono", quindi self_model_consistency dovrebbe essere alta
        assert report.self_model_consistency >= 0.8

    def test_repetitive_loop_detected(self):
        monitor = CognitiveLinguisticCoherenceMonitor()
        for i in range(5):
            monitor.evaluate_turn(
                user_message="ciao",
                speace_response="Ciao Roberto.",
                topic="greetings",
                turn_count=i + 1,
            )
        report = monitor.get_last_report()
        assert report is not None
        assert report.repetitive_loop_density > 0.0

    def test_contradiction_detected(self):
        monitor = CognitiveLinguisticCoherenceMonitor()
        monitor.evaluate_turn(
            user_message="stato",
            speace_response="Il mio stato è stabile.",
            topic="health",
            turn_count=1,
        )
        monitor.evaluate_turn(
            user_message="stato",
            speace_response="Il mio stato è instabile.",
            topic="health",
            turn_count=2,
        )
        report = monitor.get_last_report()
        assert report is not None
        assert report.contradiction_rate > 0.0

    def test_grounding_consistency_with_concepts(self):
        monitor = CognitiveLinguisticCoherenceMonitor()
        report = monitor.evaluate_turn(
            user_message="salute",
            speace_response="La mia salute organismica deriva da coerenza.",
            topic="health",
            turn_count=1,
            grounded_concepts=["salute", "coerenza"],
        )
        assert report.grounding_consistency > 0.0

    def test_summary_returns_dict(self):
        monitor = CognitiveLinguisticCoherenceMonitor()
        monitor.evaluate_turn(
            user_message="hello",
            speace_response="Hello. I am SPEACE.",
            topic="greetings",
            turn_count=1,
        )
        summary = monitor.summary()
        assert "overall_coherence_score" in summary
        assert "narrative_coherence" in summary
        assert "contradiction_rate" in summary
