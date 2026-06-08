"""MetacognitiveMonitor — T127: observational metacognition engine.

Consumes plain organism state dicts (same shape as OrganismStateCollector)
and produces a structured MetaState without importing dashboard/monitoring.
"""

import math
import time
from collections import deque
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.metacognition.meta_state import (
    CognitiveErrorDetection,
    CognitiveObservation,
    EpistemicConfidence,
    MetaState,
    StrategyEvaluation,
)

try:
    from speace_core.cellular_brain.metacognition.confidence_engine import ConfidenceEngine
except Exception:  # pragma: no cover
    ConfidenceEngine = None  # type: ignore[misc,assignment]

try:
    from speace_core.cellular_brain.metacognition.reflective_narrative_generator import (
        ReflectiveNarrativeGenerator,
    )
except Exception:  # pragma: no cover
    ReflectiveNarrativeGenerator = None  # type: ignore[misc,assignment]

try:
    from speace_core.cellular_brain.metacognition.cognitive_strategy_evaluator import (
        CognitiveStrategyEvaluator,
    )
except Exception:  # pragma: no cover
    CognitiveStrategyEvaluator = None  # type: ignore[misc,assignment]


class MetacognitiveMonitor:
    """Observes organism state and emits metacognitive assessments."""

    def __init__(self, history_window: int = 60) -> None:
        self._history: deque[Dict[str, Any]] = deque(maxlen=history_window)
        self._meta_history: deque[MetaState] = deque(maxlen=history_window)
        self._confidence_engine = ConfidenceEngine() if ConfidenceEngine else None
        self._narrative_generator = ReflectiveNarrativeGenerator() if ReflectiveNarrativeGenerator else None
        self._strategy_evaluator = CognitiveStrategyEvaluator() if CognitiveStrategyEvaluator else None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def generate_meta_state(self, state: Dict[str, Any]) -> MetaState:
        """Full meta-cognitive snapshot from current state."""
        self._history.append(state)

        observation = self.observe(state)
        errors = self.detect_errors(state)
        confidence = self.attach_confidence(state)

        label = self._classify_meta_state(observation, errors)

        # T129: use ReflectiveNarrativeGenerator if available
        if self._narrative_generator is not None:
            narrative = self._narrative_generator.generate(
                MetaState(
                    meta_state_label=label,
                    cognitive_observation=observation,
                    error_detection=errors,
                    epistemic_confidence=confidence,
                    timestamp=time.time(),
                ),
                history=list(self._meta_history),
            )
        else:
            narrative = self.generate_reflective_narrative(observation, errors, confidence)

        meta = MetaState(
            meta_state_label=label,
            cognitive_observation=observation,
            error_detection=errors,
            epistemic_confidence=confidence,
            reflective_narrative=narrative,
            timestamp=time.time(),
        )
        self._meta_history.append(meta)
        return meta

    def observe(self, state: Dict[str, Any]) -> CognitiveObservation:
        """Extract cognitive self-observation metrics from state."""
        dynamics = state.get("dynamics", {})
        cognition = state.get("cognition", {})
        alert_engine = state.get("alert_engine", {})
        drives = state.get("drives", {})
        identity = state.get("identity", {})

        chaos = dynamics.get("chaos_score", 0.0)
        rigidity = dynamics.get("rigidity_score", 0.0)
        drift = dynamics.get("drift", 0.0)
        coherence = cognition.get("self_model", {}).get("coherence_phi", 0.0)

        # Workspace stability: high coherence, low chaos/rigidity
        workspace_stability = max(0.0, min(1.0, (coherence * 0.5) + ((1.0 - chaos) * 0.25) + ((1.0 - rigidity) * 0.25)))

        # T162 — Systemic Harmony integration
        sh = state.get("systemic_harmony", {})
        if sh:
            harmony_score = sh.get("latest_report", {}).get("aggregate_harmony", 0.5)
            workspace_stability = max(0.0, min(1.0, workspace_stability * 0.8 + harmony_score * 0.2))

        # Narrative coherence: from identity / narrative traces
        narrative_trace = cognition.get("narrative_trace", {})
        if isinstance(narrative_trace, dict):
            narrative_coherence = narrative_trace.get("coherence", identity.get("narrative_coherence", coherence))
        else:
            narrative_coherence = identity.get("narrative_coherence", coherence)
        narrative_coherence = max(0.0, min(1.0, float(narrative_coherence)))
        if sh:
            narrative_coherence = max(0.0, min(1.0, narrative_coherence * 0.7 + harmony_score * 0.3))

        # Regulation density: pending proposals vs health
        pending = alert_engine.get("regulation_proposals", {}).get("pending_count", 0)
        health = alert_engine.get("health_score", 0.5)
        regulation_density = max(0.0, min(1.0, (pending / 5.0) * (1.0 - health)))

        # Drive oscillations: entropy of drive urgencies inverted -> low entropy = high oscillation?
        # Actually high variance in drive urgencies over time = oscillation.
        drive_oscillations = self._compute_drive_oscillation(drives)

        # Dialogue patterns: infer from turn density if available; default to 0.5
        dialogue_patterns = state.get("experience", {}).get("dialogue_turn_rate", 0.5)
        dialogue_patterns = max(0.0, min(1.0, float(dialogue_patterns)))

        # Vector drift: already computed in dynamics
        vector_drift = max(0.0, min(1.0, float(drift)))

        # Memory quality: invert chaos as proxy
        memory_quality = max(0.0, min(1.0, 1.0 - chaos))

        # T143: incorporate cognitive-linguistic coherence if present
        clc = state.get("cognitive_linguistic_coherence", {})
        if clc:
            clc_score = clc.get("overall_coherence_score", 0.5)
            dialogue_patterns = max(0.0, min(1.0, clc_score))
            narrative_coherence = max(0.0, min(1.0, clc.get("narrative_coherence", narrative_coherence)))

        return CognitiveObservation(
            workspace_stability=workspace_stability,
            narrative_coherence=narrative_coherence,
            regulation_density=regulation_density,
            drive_oscillations=drive_oscillations,
            dialogue_patterns=dialogue_patterns,
            vector_drift=vector_drift,
            memory_quality=memory_quality,
        )

    def detect_errors(self, state: Dict[str, Any]) -> CognitiveErrorDetection:
        """Detect cognitive error patterns."""
        dynamics = state.get("dynamics", {})
        cognition = state.get("cognition", {})
        identity = state.get("identity", {})
        drives = state.get("drives", {})
        safety = state.get("safety", {})

        details: Dict[str, Any] = {}

        # Repetitive loop: action_tendency entropy near zero across history
        repetitive_loop = self._detect_repetitive_loop(drives)

        # Contradiction: conflicting alert types active simultaneously
        contradiction = self._detect_contradiction(state)

        # Overfocus: low stability but low drive entropy (narrow focus)
        chaos = dynamics.get("chaos_score", 0.0)
        drive_list = drives.get("drives", [])
        drive_urgencies = [d.get("urgency", 0.5) for d in drive_list if isinstance(d, dict)]
        drive_entropy = self._entropy(drive_urgencies) if drive_urgencies else 0.5
        overfocus = chaos < 0.3 and drive_entropy < 0.3

        # Similarity collapse: identity divergence or low modularity
        similarity_collapse = bool(identity.get("divergence_detected", False))

        # Memory saturation: safety pending patches > threshold
        pending_patches = safety.get("pending_patches", 0)
        memory_saturation = pending_patches > 5

        # Regulation oscillation: intervention count zig-zag in history
        regulation_oscillation = self._detect_regulation_oscillation()

        # T143: detect linguistic coherence errors
        clc = state.get("cognitive_linguistic_coherence", {})
        if clc:
            if clc.get("contradiction_rate", 0.0) > 0.5:
                details["linguistic_contradiction"] = True
            if clc.get("repetitive_loop_density", 0.0) > 0.5:
                details["linguistic_repetitive_loop"] = True
            if clc.get("overall_coherence_score", 1.0) < 0.3:
                details["linguistic_coherence_critical"] = True

        return CognitiveErrorDetection(
            repetitive_loop=repetitive_loop,
            contradiction=contradiction,
            overfocus=overfocus,
            similarity_collapse=similarity_collapse,
            memory_saturation=memory_saturation,
            regulation_oscillation=regulation_oscillation,
            details=details,
        )

    def evaluate_strategy(
        self,
        pre_snapshot: Dict[str, Any],
        post_snapshot: Dict[str, Any],
        regulation_id: str,
    ) -> StrategyEvaluation:
        """Compare pre/post regulation to determine efficacy."""
        pre_health = pre_snapshot.get("alert_engine", {}).get("health_score", 0.0)
        post_health = post_snapshot.get("alert_engine", {}).get("health_score", 0.0)
        delta = post_health - pre_health
        return StrategyEvaluation(
            regulation_id=regulation_id,
            pre_health=pre_health,
            post_health=post_health,
            delta=delta,
            improved=delta > 0.05,
        )

    def record_strategy_outcome(
        self,
        strategy_name: str,
        pre_health: float,
        post_health: float,
        regulation_id: str = "",
    ) -> Optional[StrategyEvaluation]:
        """T130: Record and evaluate a strategy outcome."""
        if self._strategy_evaluator is None:
            return None
        return self._strategy_evaluator.record_outcome(
            strategy_name=strategy_name,
            pre_health=pre_health,
            post_health=post_health,
            regulation_id=regulation_id,
        )

    def evaluate_all_strategies(self) -> Dict[str, Any]:
        """T130: Evaluate all recorded strategies."""
        if self._strategy_evaluator is None:
            return {}
        return self._strategy_evaluator.evaluate_all()

    def best_strategy(self) -> Optional[str]:
        """T130: Return the best-performing strategy name."""
        if self._strategy_evaluator is None:
            return None
        return self._strategy_evaluator.best_strategy()

    def attach_confidence(self, state: Dict[str, Any]) -> EpistemicConfidence:
        """Attach epistemic confidence to current state."""
        confidence = 0.5
        uncertainty = 0.5
        novelty = 0.0

        # If a circuit is present, delegate to ConfidenceEngine
        circuit = cognition.get("circuit", None) if (cognition := state.get("cognition")) else None
        if self._confidence_engine is not None and circuit is not None:
            try:
                cs = self._confidence_engine.evaluate(circuit=circuit)
                confidence = cs.confidence_score
                uncertainty = cs.uncertainty_score
            except Exception:
                pass
        else:
            # Fallback: compute novelty from state divergence vs history
            if len(self._history) >= 2:
                novelty = self._state_divergence(state, self._history[-2])
            confidence = max(0.0, min(1.0, 1.0 - novelty))
            uncertainty = 1.0 - confidence

        return EpistemicConfidence(
            confidence_score=round(confidence, 4),
            uncertainty_score=round(uncertainty, 4),
            novelty_score=round(novelty, 4),
        )

    def confidence_for_proposal(
        self, proposal: Dict[str, Any], state: Dict[str, Any]
    ) -> EpistemicConfidence:
        """T128: Compute epistemic confidence for a regulation proposal."""
        base = self.attach_confidence(state)
        # Adjust based on proposal risk and historical success
        risk = proposal.get("risk_score", 0.5)
        hist_conf = proposal.get("confidence", {}).get("confidence", 0.5)
        confidence = max(0.0, min(1.0, (base.confidence_score + hist_conf) / 2.0 - risk * 0.2))
        uncertainty = 1.0 - confidence
        novelty = base.novelty_score
        return EpistemicConfidence(
            confidence_score=round(confidence, 4),
            uncertainty_score=round(uncertainty, 4),
            novelty_score=round(novelty, 4),
        )

    def confidence_for_dialogue(
        self, dialogue_state: Dict[str, Any], state: Dict[str, Any]
    ) -> EpistemicConfidence:
        """T128: Compute epistemic confidence for a dialogue turn."""
        base = self.attach_confidence(state)
        # Dialogue confidence correlates with workspace stability and dialogue coherence
        turn_count = dialogue_state.get("turn_count", 0)
        coherence = state.get("cognition", {}).get("self_model", {}).get("coherence_phi", 0.5)
        if turn_count < 2:
            novelty = 0.8  # high novelty at start of conversation
            confidence = coherence * 0.6
        else:
            novelty = base.novelty_score * 0.5
            confidence = (base.confidence_score + coherence) / 2.0
        confidence = max(0.0, min(1.0, confidence))
        return EpistemicConfidence(
            confidence_score=round(confidence, 4),
            uncertainty_score=round(1.0 - confidence, 4),
            novelty_score=round(novelty, 4),
        )

    def generate_reflective_narrative(
        self,
        observation: CognitiveObservation,
        errors: CognitiveErrorDetection,
        confidence: EpistemicConfidence,
    ) -> str:
        """Lightweight reflective narrative (placeholder for T129)."""
        parts: List[str] = []

        if observation.workspace_stability < 0.4:
            parts.append("Workspace stability is low.")
        elif observation.workspace_stability > 0.8:
            parts.append("Workspace stability is high.")

        if errors.repetitive_loop:
            parts.append("Repetitive behavior patterns detected.")
        if errors.contradiction:
            parts.append("Contradictory cognitive signals present.")
        if errors.overfocus:
            parts.append("Narrow overfocus detected.")
        if errors.similarity_collapse:
            parts.append("Identity or representational collapse risk.")
        if errors.memory_saturation:
            parts.append("Memory saturation threshold exceeded.")
        if errors.regulation_oscillation:
            parts.append("Regulatory oscillation observed.")

        if confidence.confidence_score < 0.4:
            parts.append("Low epistemic confidence.")
        elif confidence.novelty_score > 0.6:
            parts.append("High novelty in current state.")

        if not parts:
            parts.append("Cognitive state appears stable.")

        return " ".join(parts)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _classify_meta_state(
        self, observation: CognitiveObservation, errors: CognitiveErrorDetection
    ) -> str:
        error_count = sum(
            [
                errors.repetitive_loop,
                errors.contradiction,
                errors.overfocus,
                errors.similarity_collapse,
                errors.memory_saturation,
                errors.regulation_oscillation,
            ]
        )
        if error_count >= 3 or observation.workspace_stability < 0.2:
            return "critical"
        if error_count >= 1 or observation.workspace_stability < 0.5:
            return "unstable"
        if observation.workspace_stability > 0.8 and error_count == 0:
            return "stable"
        return "stable"

    def _compute_drive_oscillation(self, drives: Dict[str, Any]) -> float:
        """Measure variance in drive urgencies over recent history."""
        if len(self._history) < 2:
            return 0.0
        urgencies_now = [d.get("urgency", 0.5) for d in drives.get("drives", []) if isinstance(d, dict)]
        urgencies_prev = [
            d.get("urgency", 0.5)
            for d in self._history[-2].get("drives", {}).get("drives", [])
            if isinstance(d, dict)
        ]
        if not urgencies_now or not urgencies_prev or len(urgencies_now) != len(urgencies_prev):
            return 0.0
        diffs = [abs(a - b) for a, b in zip(urgencies_now, urgencies_prev)]
        return max(0.0, min(1.0, sum(diffs) / len(diffs)))

    def _detect_repetitive_loop(self, drives: Dict[str, Any]) -> bool:
        """True if action_tendency has been identical across last N states."""
        if len(self._history) < 3:
            return False
        tendencies = [
            s.get("drives", {}).get("action_tendency", None)
            for s in list(self._history)[-3:]
        ]
        return len(set(str(t) for t in tendencies)) == 1 and tendencies[0] is not None

    def _detect_contradiction(self, state: Dict[str, Any]) -> bool:
        """True if both chaos and rigidity alerts are active."""
        alerts = state.get("alert_engine", {}).get("alerts", [])
        types = {a.get("alert_type", "") for a in alerts}
        has_chaos = any("chaos" in t for t in types)
        has_rigidity = any("rigidity" in t for t in types)
        return has_chaos and has_rigidity

    def _detect_regulation_oscillation(self) -> bool:
        """True if intervention count alternates up/down."""
        if len(self._history) < 3:
            return False
        counts = [
            s.get("dynamics", {}).get("stabilizer", {}).get("intervention_count", 0)
            for s in list(self._history)[-3:]
        ]
        if len(counts) < 3:
            return False
        deltas = [counts[i + 1] - counts[i] for i in range(len(counts) - 1)]
        # Alternating signs
        return (deltas[0] > 0 and deltas[1] < 0) or (deltas[0] < 0 and deltas[1] > 0)

    def _state_divergence(self, current: Dict[str, Any], previous: Dict[str, Any]) -> float:
        """Simple divergence metric between two state dicts."""
        keys = ["chaos_score", "rigidity_score", "drift", "coherence_phi"]
        cur_vals = []
        prev_vals = []
        for k in keys:
            cur_vals.append(current.get("dynamics", {}).get(k, current.get("cognition", {}).get("self_model", {}).get(k, 0.0)))
            prev_vals.append(previous.get("dynamics", {}).get(k, previous.get("cognition", {}).get("self_model", {}).get(k, 0.0)))
        diffs = [abs(a - b) for a, b in zip(cur_vals, prev_vals)]
        return max(0.0, min(1.0, sum(diffs) / len(diffs))) if diffs else 0.0

    @staticmethod
    def _entropy(values: List[float]) -> float:
        if not values:
            return 0.0
        shifted = [max(0.0, v) + 1e-12 for v in values]
        total = sum(shifted)
        if total == 0:
            return 0.0
        probs = [v / total for v in shifted]
        entropy = -sum(p * math.log(p + 1e-12) for p in probs)
        max_entropy = math.log(len(probs) + 1e-12)
        return entropy / max_entropy if max_entropy else 0.0
