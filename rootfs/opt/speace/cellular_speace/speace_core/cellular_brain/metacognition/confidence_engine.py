import math
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.analysis.community_detection_engine import (
    CommunityDetectionResult,
)
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regulation.homeostasis_engine import SystemMetrics


class ConfidenceState(BaseModel):
    confidence_score: float = 0.0
    uncertainty_score: float = 0.0
    output_entropy: float = 0.0
    activation_margin: float = 0.0
    decision_stability: float = 0.0
    error_risk: float = 0.0
    recommended_action: str = "maintain"
    adaptation_pressure: float = 0.0
    neurogenesis_recommended: bool = False
    plasticity_reduction_recommended: bool = False
    stabilization_recommended: bool = False


class ConfidenceTrace(BaseModel):
    trace_id: str
    tick_id: Optional[int] = None
    burst_id: Optional[int] = None
    confidence_state: ConfidenceState
    output_activations: List[float] = Field(default_factory=list)
    phi: float = 0.0
    mean_energy: float = 0.0
    community_count: Optional[int] = None
    modularity_proxy: Optional[float] = None
    timestamp: str = ""


class ConfidenceEngine:
    """Meta-learning engine: estimates confidence, uncertainty, and recommends actions."""

    def __init__(
        self,
        low_confidence_threshold: float = 0.35,
        high_confidence_threshold: float = 0.75,
        instability_threshold: float = 0.50,
        entropy_weight: float = 0.30,
        margin_weight: float = 0.30,
        phi_weight: float = 0.20,
        stability_weight: float = 0.20,
        history_window: int = 3,
    ):
        self.low_confidence_threshold = low_confidence_threshold
        self.high_confidence_threshold = high_confidence_threshold
        self.instability_threshold = instability_threshold
        self.entropy_weight = entropy_weight
        self.margin_weight = margin_weight
        self.phi_weight = phi_weight
        self.stability_weight = stability_weight
        self.history_window = history_window
        self._output_history: List[List[float]] = []

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def evaluate(
        self,
        circuit: NeuralCircuit,
        metrics: SystemMetrics | None = None,
        community_result: CommunityDetectionResult | None = None,
        memory: MorphologicalMemory | None = None,
    ) -> ConfidenceState:
        """Compute full confidence state for the current circuit condition."""
        output_activations = [n.activation for n in circuit.output_neurons]
        phi = metrics.coherence_phi if metrics else 0.0
        mean_energy = metrics.mean_energy if metrics else 0.0

        entropy = self.compute_output_entropy(output_activations)
        margin = self.compute_activation_margin(output_activations)
        stability = self.compute_decision_stability(output_activations)

        confidence = (
            self.entropy_weight * (1.0 - entropy)
            + self.margin_weight * margin
            + self.phi_weight * phi
            + self.stability_weight * stability
        )
        confidence = max(0.0, min(1.0, confidence))
        uncertainty = 1.0 - confidence

        error_risk = self.compute_error_risk(confidence, phi, mean_energy)
        adaptation_pressure = max(0.0, uncertainty + error_risk - confidence)

        action = self.recommend_action(
            confidence, phi, mean_energy, error_risk, community_result
        )

        state = ConfidenceState(
            confidence_score=confidence,
            uncertainty_score=uncertainty,
            output_entropy=entropy,
            activation_margin=margin,
            decision_stability=stability,
            error_risk=error_risk,
            recommended_action=action,
            adaptation_pressure=adaptation_pressure,
            neurogenesis_recommended=(
                confidence < self.low_confidence_threshold and mean_energy >= 0.3
            ),
            plasticity_reduction_recommended=(
                confidence >= self.high_confidence_threshold and error_risk > 0.5
            ),
            stabilization_recommended=(
                confidence < self.low_confidence_threshold and phi < 0.4
            ),
        )

        if memory is not None:
            memory.create_event(
                event_type=MorphologyEventType.CONFIDENCE_EVALUATED,
                source_id="confidence_engine",
                metadata={
                    "confidence_score": confidence,
                    "uncertainty_score": uncertainty,
                    "output_entropy": entropy,
                    "activation_margin": margin,
                    "decision_stability": stability,
                    "error_risk": error_risk,
                    "recommended_action": action,
                    "neurogenesis_recommended": state.neurogenesis_recommended,
                    "plasticity_reduction_recommended": state.plasticity_reduction_recommended,
                    "stabilization_recommended": state.stabilization_recommended,
                },
            )

        return state

    # ------------------------------------------------------------------ #
    # Component computations
    # ------------------------------------------------------------------ #

    def compute_output_entropy(self, output_activations: List[float]) -> float:
        """Normalized entropy of output distribution. High entropy = low confidence."""
        if not output_activations:
            return 0.0
        # Shift to non-negative and add epsilon
        shifted = [max(0.0, a) + 1e-12 for a in output_activations]
        total = sum(shifted)
        if total == 0:
            return 0.0
        probs = [v / total for v in shifted]
        entropy = -sum(p * math.log(p + 1e-12) for p in probs)
        max_entropy = math.log(len(probs) + 1e-12)
        if max_entropy == 0:
            return 0.0
        return entropy / max_entropy

    def compute_activation_margin(self, output_activations: List[float]) -> float:
        """Difference between top and second-top output activation, normalized."""
        if len(output_activations) < 2:
            return 0.0
        sorted_vals = sorted(output_activations, reverse=True)
        top = sorted_vals[0]
        second = sorted_vals[1]
        margin = top - second
        # Normalize by max possible margin (assuming activations roughly in [0,1])
        return max(0.0, min(1.0, margin))

    def compute_decision_stability(self, output_activations: List[float]) -> float:
        """Measure how similar current output is to recent history."""
        if not self._output_history:
            self._output_history.append(output_activations)
            return 1.0
        # Cosine similarity with most recent history entry
        prev = self._output_history[-1]
        if len(prev) != len(output_activations):
            self._output_history = [output_activations]
            return 1.0
        similarity = self._cosine_similarity(prev, output_activations)
        self._output_history.append(output_activations)
        if len(self._output_history) > self.history_window:
            self._output_history.pop(0)
        return max(0.0, min(1.0, similarity))

    def compute_error_risk(
        self, confidence: float, phi: float, mean_energy: float
    ) -> float:
        """Estimate risk of producing a wrong output."""
        # Low confidence + low coherence + low energy = high risk
        risk = (
            (1.0 - confidence) * 0.4
            + (1.0 - phi) * 0.3
            + abs(mean_energy - 0.5) * 0.3
        )
        return max(0.0, min(1.0, risk))

    def recommend_action(
        self,
        confidence: float,
        phi: float,
        mean_energy: float,
        error_risk: float,
        community_result: CommunityDetectionResult | None = None,
    ) -> str:
        """Produce an adaptive recommendation based on metacognitive state."""
        # High confidence + high coherence → maintain
        if confidence >= self.high_confidence_threshold and phi >= 0.5:
            if error_risk > 0.5:
                return "reduce_plasticity"
            return "maintain"

        # Low confidence + low coherence → stabilize
        if confidence < self.low_confidence_threshold and phi < 0.4:
            return "stabilize"

        # Oscillating / unstable → increase inhibition
        if confidence < self.instability_threshold and error_risk > 0.4:
            return "increase_inhibition"

        # Low confidence + isolated communities → community-guided growth
        if (
            community_result is not None
            and len(community_result.isolated_neurons) > 2
            and confidence < self.low_confidence_threshold
        ):
            return "community_guided_neurogenesis"

        # Low confidence + sufficient energy → neurogenesis
        if confidence < self.low_confidence_threshold and mean_energy >= 0.3:
            return "recommend_neurogenesis"

        return "increase_plasticity"

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
