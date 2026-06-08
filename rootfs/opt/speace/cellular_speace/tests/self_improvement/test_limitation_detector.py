import pytest

from speace_core.cellular_brain.self_improvement.limitation_detector import (
    LimitationDetector,
    LimitationDiagnosis,
    LimitationSignal,
)


class TestLimitationDetector:
    def test_detects_cognitive_regression(self):
        detector = LimitationDetector()
        metrics = {"cognitive_delta": -0.05}
        signals = detector.detect_from_metrics(metrics)
        assert len(signals) == 1
        assert signals[0].category == "cognitive_regression"
        assert signals[0].severity == 0.5

    def test_detects_phi_regression(self):
        detector = LimitationDetector()
        metrics = {"phi_delta": -0.04}
        signals = detector.detect_from_metrics(metrics)
        assert len(signals) == 1
        assert signals[0].category == "phi_regression"
        assert signals[0].severity == 0.4

    def test_detects_energy_regression(self):
        detector = LimitationDetector()
        metrics = {"energy_delta": -0.06}
        signals = detector.detect_from_metrics(metrics)
        assert len(signals) == 1
        assert signals[0].category == "energy_regression"
        assert signals[0].severity == 0.6

    def test_detects_routing_no_effect(self):
        detector = LimitationDetector()
        metrics = {
            "region_signal_routing_enabled": True,
            "regional_signal_flow_score": 0.0,
        }
        signals = detector.detect_from_metrics(metrics)
        assert len(signals) == 1
        assert signals[0].category == "routing_no_effect"

    def test_detects_plasticity_no_effect(self):
        detector = LimitationDetector()
        metrics = {
            "inter_region_plasticity_enabled": True,
            "inter_region_plasticity_events": 0,
        }
        signals = detector.detect_from_metrics(metrics)
        assert len(signals) == 1
        assert signals[0].category == "plasticity_no_effect"

    def test_detects_semantic_recall_weak(self):
        detector = LimitationDetector()
        metrics = {
            "semantic_memory_enabled": True,
            "semantic_recall_success_rate": 0.1,
        }
        signals = detector.detect_from_metrics(metrics)
        assert len(signals) == 1
        assert signals[0].category == "semantic_recall_weak"

    def test_detects_semantic_association_missing(self):
        detector = LimitationDetector()
        metrics = {
            "semantic_assembly_count": 5,
            "semantic_association_count": 0,
        }
        signals = detector.detect_from_metrics(metrics)
        assert len(signals) == 1
        assert signals[0].category == "semantic_association_missing"

    def test_aggregates_signals_into_diagnosis(self):
        detector = LimitationDetector()
        metrics = {
            "cognitive_delta": -0.05,
            "phi_delta": -0.04,
        }
        signals = detector.detect_from_metrics(metrics)
        assert len(signals) == 2
        diagnoses = detector.aggregate_signals(signals)
        assert len(diagnoses) == 2
        categories = {d.primary_category for d in diagnoses}
        assert "cognitive_regression" in categories
        assert "phi_regression" in categories

    def test_no_signals_when_all_healthy(self):
        detector = LimitationDetector()
        metrics = {
            "cognitive_delta": 0.01,
            "phi_delta": 0.01,
            "energy_delta": 0.01,
            "semantic_recall_success_rate": 0.5,
            "semantic_memory_enabled": True,
            "semantic_assembly_count": 0,
            "semantic_association_count": 0,
        }
        signals = detector.detect_from_metrics(metrics)
        assert len(signals) == 0

    def test_detect_from_audit_report_regression(self):
        detector = LimitationDetector()
        report = {"verdict": "POLICY_MAJOR_REGRESSION"}
        signals = detector.detect_from_audit_report(report)
        assert len(signals) == 1
        assert signals[0].category == "policy major regression"

    def test_detect_from_regression_guard_unsafe(self):
        detector = LimitationDetector()
        signals = detector.detect_from_regression_guard(
            "POLICY_UNSAFE", {"cognitive": True}
        )
        assert len(signals) == 1
        assert signals[0].category == "cognitive_regression"
        assert signals[0].severity == 0.95

    def test_detect_from_morphological_memory_immune_alerts(self):
        class FakeMemory:
            events = []

        class FakeEvent:
            def __init__(self, event_type):
                self.event_type = event_type

        memory = FakeMemory()
        memory.events = [FakeEvent("cellular_immune_alert") for _ in range(5)]
        detector = LimitationDetector()
        signals = detector.detect_from_morphological_memory(memory)
        assert len(signals) == 1
        assert signals[0].category == "cellular_damage"

    def test_diagnosis_urgency_sorted_descending(self):
        detector = LimitationDetector()
        metrics = {
            "cognitive_delta": -0.05,
            "phi_delta": -0.10,
        }
        signals = detector.detect_from_metrics(metrics)
        diagnoses = detector.aggregate_signals(signals)
        assert diagnoses[0].primary_category == "phi_regression"
