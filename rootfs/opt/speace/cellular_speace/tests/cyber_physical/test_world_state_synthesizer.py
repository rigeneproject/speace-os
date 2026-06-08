import pytest
from speace_core.cellular_brain.cyber_physical.world_state_synthesizer import (
    WorldStateSynthesizer,
)
from speace_core.cellular_brain.cyber_physical.cyber_physical_models import ExternalSignal


class TestWorldStateSynthesizer:
    def test_synthesize_world_state_basic(self):
        synth = WorldStateSynthesizer()
        signals = [
            ExternalSignal(
                signal_id="a",
                source_id="s",
                signal_type="environmental",
                value=0.5,
                confidence=0.8,
            ),
        ]
        state = synth.synthesize_world_state(signals)
        assert state.signal_count == 1
        assert state.environmental_pressure == 0.5

    def test_compute_environmental_pressure(self):
        signals = [
            ExternalSignal(
                signal_id="a", source_id="s", signal_type="environmental", value=0.4
            ),
            ExternalSignal(
                signal_id="b", source_id="s", signal_type="environmental", value=0.6
            ),
        ]
        pressure = WorldStateSynthesizer.compute_environmental_pressure(signals)
        assert pytest.approx(pressure, 0.01) == 0.5

    def test_compute_energy_pressure(self):
        signals = [
            ExternalSignal(
                signal_id="a", source_id="s", signal_type="energy", value=0.3
            ),
            ExternalSignal(
                signal_id="b", source_id="s", signal_type="energy", value=0.7
            ),
        ]
        pressure = WorldStateSynthesizer.compute_energy_pressure(signals)
        assert pytest.approx(pressure, 0.01) == 0.5

    def test_compute_safety_pressure(self):
        signals = [
            ExternalSignal(
                signal_id="a",
                source_id="s",
                signal_type="sensor",
                value=0.0,
                safety_relevance=0.8,
            ),
            ExternalSignal(
                signal_id="b",
                source_id="s",
                signal_type="sensor",
                value=0.0,
                safety_relevance=0.4,
            ),
        ]
        pressure = WorldStateSynthesizer.compute_safety_pressure(signals)
        # Only signals with safety_relevance > 0.5 count
        assert pytest.approx(pressure, 0.01) == 0.8

    def test_compute_infrastructure_pressure(self):
        signals = [
            ExternalSignal(
                signal_id="a",
                source_id="s",
                signal_type="infrastructure",
                value=0.2,
            ),
            ExternalSignal(
                signal_id="b",
                source_id="s",
                signal_type="infrastructure",
                value=0.8,
            ),
        ]
        pressure = WorldStateSynthesizer.compute_infrastructure_pressure(signals)
        assert pytest.approx(pressure, 0.01) == 0.5

    def test_compute_uncertainty(self):
        signals = [
            ExternalSignal(
                signal_id="a", source_id="s", signal_type="temp", confidence=0.8
            ),
            ExternalSignal(
                signal_id="b", source_id="s", signal_type="temp", confidence=0.6
            ),
        ]
        uncertainty = WorldStateSynthesizer.compute_uncertainty(signals)
        assert pytest.approx(uncertainty, 0.01) == 0.3

    def test_compute_uncertainty_empty(self):
        uncertainty = WorldStateSynthesizer.compute_uncertainty([])
        assert uncertainty == 0.0

    def test_compute_world_coherence_score_no_conflicts(self):
        signals = [
            ExternalSignal(
                signal_id="a", source_id="s", signal_type="environmental", value=0.5
            ),
            ExternalSignal(
                signal_id="b", source_id="s", signal_type="environmental", value=0.55
            ),
        ]
        score = WorldStateSynthesizer.compute_world_coherence_score(signals)
        assert score == 1.0

    def test_compute_world_coherence_score_with_conflicts(self):
        signals = [
            ExternalSignal(
                signal_id="a", source_id="s", signal_type="environmental", value=0.1
            ),
            ExternalSignal(
                signal_id="b", source_id="s", signal_type="environmental", value=0.9
            ),
        ]
        score = WorldStateSynthesizer.compute_world_coherence_score(signals)
        assert score < 1.0

    def test_detect_world_state_conflicts_environmental(self):
        signals = [
            ExternalSignal(
                signal_id="a", source_id="s", signal_type="environmental", value=0.1
            ),
            ExternalSignal(
                signal_id="b", source_id="s", signal_type="environmental", value=0.9
            ),
        ]
        conflicts = WorldStateSynthesizer.detect_world_state_conflicts(signals)
        assert "environmental_contradiction" in conflicts

    def test_detect_world_state_conflicts_safety_energy(self):
        signals = [
            ExternalSignal(
                signal_id="a",
                source_id="s",
                signal_type="sensor",
                value=0.0,
                safety_relevance=0.8,
            ),
            ExternalSignal(
                signal_id="b", source_id="s", signal_type="energy", value=0.9
            ),
        ]
        conflicts = WorldStateSynthesizer.detect_world_state_conflicts(signals)
        assert "safety_energy_conflict" in conflicts

    def test_detect_world_state_conflicts_none(self):
        signals = [
            ExternalSignal(
                signal_id="a", source_id="s", signal_type="environmental", value=0.5
            ),
        ]
        conflicts = WorldStateSynthesizer.detect_world_state_conflicts(signals)
        assert len(conflicts) == 0

    def test_compute_world_coherence_score_empty(self):
        score = WorldStateSynthesizer.compute_world_coherence_score([])
        assert score == 1.0

    def test_synthesize_world_state_with_metadata(self):
        synth = WorldStateSynthesizer()
        signals = [
            ExternalSignal(
                signal_id="a",
                source_id="s",
                signal_type="environmental",
                value=0.5,
            ),
            ExternalSignal(
                signal_id="b",
                source_id="s",
                signal_type="energy",
                value=0.3,
            ),
        ]
        state = synth.synthesize_world_state(signals)
        assert "environmental" in state.metadata["source_signal_types"]
        assert "energy" in state.metadata["source_signal_types"]

    def test_world_state_coherence_score_clamped(self):
        signals = [
            ExternalSignal(
                signal_id="a", source_id="s", signal_type="environmental", value=0.0
            ),
            ExternalSignal(
                signal_id="b", source_id="s", signal_type="environmental", value=1.0
            ),
            ExternalSignal(
                signal_id="c", source_id="s", signal_type="environmental", value=0.5
            ),
            ExternalSignal(
                signal_id="d", source_id="s", signal_type="environmental", value=0.2
            ),
            ExternalSignal(
                signal_id="e", source_id="s", signal_type="environmental", value=0.8
            ),
        ]
        score = WorldStateSynthesizer.compute_world_coherence_score(signals)
        assert score >= 0.0
