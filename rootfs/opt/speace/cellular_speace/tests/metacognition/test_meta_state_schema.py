"""Tests for T127 meta-state Pydantic schema."""

import json

import pytest
from pydantic import ValidationError

from speace_core.cellular_brain.metacognition.meta_state import (
    CognitiveErrorDetection,
    CognitiveObservation,
    EpistemicConfidence,
    MetaState,
    StrategyEvaluation,
)


def test_cognitive_observation_defaults():
    obs = CognitiveObservation()
    assert obs.workspace_stability == 0.0
    assert obs.narrative_coherence == 0.0


def test_cognitive_error_detection_defaults():
    errs = CognitiveErrorDetection()
    assert errs.repetitive_loop is False
    assert errs.details == {}


def test_meta_state_roundtrip():
    ms = MetaState(
        meta_state_label="stable",
        cognitive_observation=CognitiveObservation(workspace_stability=0.9),
        error_detection=CognitiveErrorDetection(overfocus=True),
        epistemic_confidence=EpistemicConfidence(confidence_score=0.8),
        reflective_narrative="Workspace stable.",
        timestamp=1234567890.0,
    )
    dumped = ms.model_dump(mode="json")
    loaded = MetaState(**dumped)
    assert loaded.meta_state_label == "stable"
    assert loaded.cognitive_observation.workspace_stability == 0.9
    assert loaded.error_detection.overfocus is True


def test_meta_state_json_serializable():
    ms = MetaState(
        meta_state_label="unstable",
        cognitive_observation=CognitiveObservation(workspace_stability=0.2),
    )
    dumped = ms.model_dump(mode="json")
    json_str = json.dumps(dumped)
    assert "unstable" in json_str
    assert "workspace_stability" in json_str
