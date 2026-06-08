"""Tests for T129 — Reflective Narrative Generator."""

from speace_core.cellular_brain.metacognition.meta_state import (
    CognitiveErrorDetection,
    CognitiveObservation,
    EpistemicConfidence,
    MetaState,
)
from speace_core.cellular_brain.metacognition.reflective_narrative_generator import (
    ReflectiveNarrativeGenerator,
)


def test_generate_critical_narrative():
    gen = ReflectiveNarrativeGenerator()
    meta = MetaState(
        meta_state_label="critical",
        cognitive_observation=CognitiveObservation(workspace_stability=0.1, memory_quality=0.2),
        error_detection=CognitiveErrorDetection(repetitive_loop=True, contradiction=True),
        epistemic_confidence=EpistemicConfidence(confidence_score=0.2),
    )
    text = gen.generate(meta)
    assert "CRITICAL" in text
    assert "repetitive" in text.lower() or "contradict" in text.lower()


def test_generate_stable_narrative():
    gen = ReflectiveNarrativeGenerator()
    meta = MetaState(
        meta_state_label="stable",
        cognitive_observation=CognitiveObservation(workspace_stability=0.9, memory_quality=0.9),
        error_detection=CognitiveErrorDetection(),
        epistemic_confidence=EpistemicConfidence(confidence_score=0.9),
    )
    text = gen.generate(meta)
    assert "stable" in text.lower()


def test_generate_with_history_improvement():
    gen = ReflectiveNarrativeGenerator()
    prev = MetaState(
        meta_state_label="unstable",
        cognitive_observation=CognitiveObservation(workspace_stability=0.3, narrative_coherence=0.8, memory_quality=0.8),
    )
    curr = MetaState(
        meta_state_label="stable",
        cognitive_observation=CognitiveObservation(workspace_stability=0.8, narrative_coherence=0.8, memory_quality=0.8),
    )
    text = gen.generate(curr, history=[prev, prev])
    assert "improved" in text.lower()


def test_generate_summary():
    gen = ReflectiveNarrativeGenerator()
    meta = MetaState(
        meta_state_label="unstable",
        cognitive_observation=CognitiveObservation(workspace_stability=0.4),
        error_detection=CognitiveErrorDetection(overfocus=True),
        epistemic_confidence=EpistemicConfidence(confidence_score=0.5),
    )
    summary = gen.generate_summary(meta)
    assert summary["label"] == "unstable"
    assert summary["error_count"] == 1
    assert "narrative" in summary
