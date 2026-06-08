from speace_core.cellular_brain.immune.immune_response_engine import ImmuneResponseEngine, ThreatLevel
from speace_core.cellular_brain.immune.pattern_anomaly_detector import AnomalyEvent


def test_classify_critical_threat():
    engine = ImmuneResponseEngine()
    anomaly = AnomalyEvent(entity_type="neuron", entity_id="n1", anomaly_type="test", severity=0.9)
    assert engine.classify_threat(anomaly) == ThreatLevel.CRITICAL


def test_classify_low_threat():
    engine = ImmuneResponseEngine()
    anomaly = AnomalyEvent(entity_type="neuron", entity_id="n1", anomaly_type="test", severity=0.1)
    assert engine.classify_threat(anomaly) == ThreatLevel.LOW


def test_respond_to_anomalies():
    engine = ImmuneResponseEngine()
    anomalies = [
        AnomalyEvent(entity_type="neuron", entity_id="n1", anomaly_type="test", severity=0.9),
        AnomalyEvent(entity_type="synapse", entity_id="s1", anomaly_type="test", severity=0.3),
    ]
    actions = engine.respond_to_anomalies(anomalies)
    assert len(actions) >= 1
    assert any(a.action_type == "quarantine" for a in actions)
