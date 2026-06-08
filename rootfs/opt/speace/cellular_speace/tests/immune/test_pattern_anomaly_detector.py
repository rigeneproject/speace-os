from speace_core.cellular_brain.immune.pattern_anomaly_detector import PatternAnomalyDetector
from speace_core.cellular_brain.cells.digital_neuron import DigitalNeuron
from speace_core.cellular_brain.cells.digital_synapse import DigitalSynapse


def test_detect_neuron_extreme_activation():
    detector = PatternAnomalyDetector()
    neurons = [DigitalNeuron(cell_id="n1", role="hidden", activation=5.0)]
    events = detector.detect_neuron_anomalies(neurons)
    assert len(events) == 1
    assert events[0].anomaly_type == "extreme_activation"
    assert events[0].severity > 0.5


def test_detect_synapse_extreme_weight():
    detector = PatternAnomalyDetector()
    synapses = [DigitalSynapse(cell_id="s1", role="synapse", source="a", target="b", weight=3.0)]
    events = detector.detect_synapse_anomalies(synapses)
    assert len(events) == 1
    assert events[0].anomaly_type == "extreme_weight"


def test_detect_no_anomalies():
    detector = PatternAnomalyDetector()
    neurons = [DigitalNeuron(cell_id="n1", role="input", activation=0.5)]
    synapses = [DigitalSynapse(cell_id="s1", role="synapse", source="a", target="b", weight=0.5)]
    report = detector.detect_all(neurons, synapses)
    assert len(report.anomalies) == 0


def test_assembly_collapse_detection():
    detector = PatternAnomalyDetector()

    class FakeAssembly:
        def __init__(self, signature):
            self.id = "asm"
            self.signature = signature

    assemblies = [FakeAssembly([1.0, 0.0]), FakeAssembly([0.99, 0.01])]
    events = detector.detect_assembly_anomalies(assemblies)
    assert len(events) >= 1
    assert events[0].anomaly_type == "functional_collapse"
