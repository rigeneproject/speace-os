"""Metacognition package — T127/T128/T129/T130."""

from speace_core.cellular_brain.metacognition.meta_state import (
    CognitiveErrorDetection,
    CognitiveObservation,
    EpistemicConfidence,
    MetaState,
    StrategyEvaluation,
)
from speace_core.cellular_brain.metacognition.metacognitive_monitor import (
    MetacognitiveMonitor,
)
from speace_core.cellular_brain.metacognition.reflective_narrative_generator import (
    ReflectiveNarrativeGenerator,
)
from speace_core.cellular_brain.metacognition.cognitive_strategy_evaluator import (
    CognitiveStrategyEvaluator,
)
from speace_core.cellular_brain.metacognition.cognitive_linguistic_coherence_monitor import (
    CognitiveLinguisticCoherenceMonitor,
    CognitiveLinguisticCoherenceReport,
)

__all__ = [
    "CognitiveErrorDetection",
    "CognitiveObservation",
    "EpistemicConfidence",
    "MetaState",
    "StrategyEvaluation",
    "MetacognitiveMonitor",
    "ReflectiveNarrativeGenerator",
    "CognitiveStrategyEvaluator",
    "CognitiveLinguisticCoherenceMonitor",
    "CognitiveLinguisticCoherenceReport",
]
