"""ReflectiveNarrativeGenerator — T129: generates human-readable cognitive state reports.

Consumes MetaState and produces structured reflective narratives.
"""

import time
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.metacognition.meta_state import (
    CognitiveErrorDetection,
    CognitiveObservation,
    EpistemicConfidence,
    MetaState,
)


class ReflectiveNarrativeGenerator:
    """Generates reflective narratives from metacognitive state."""

    def generate(self, meta_state: MetaState, history: Optional[List[MetaState]] = None) -> str:
        """Produce a reflective narrative string."""
        parts: List[str] = []
        obs = meta_state.cognitive_observation
        errs = meta_state.error_detection
        conf = meta_state.epistemic_confidence

        # Opening: meta-state label
        label = meta_state.meta_state_label
        if label == "critical":
            parts.append("CRITICAL: The cognitive system is in a critical state.")
        elif label == "unstable":
            parts.append("WARNING: The cognitive system is unstable.")
        else:
            parts.append("The cognitive system is stable.")

        # Observation details
        if obs.workspace_stability < 0.3:
            parts.append("Workspace stability is critically low.")
        elif obs.workspace_stability < 0.6:
            parts.append("Workspace stability is below optimal.")
        elif obs.workspace_stability > 0.8:
            parts.append("Workspace stability is strong.")

        if obs.narrative_coherence < 0.5:
            parts.append("Narrative coherence is fragmented.")
        elif obs.narrative_coherence > 0.8:
            parts.append("Narrative coherence is well maintained.")

        if obs.regulation_density > 0.5:
            parts.append("Regulatory pressure is high.")
        elif obs.regulation_density > 0.2:
            parts.append("Moderate regulatory activity detected.")

        if obs.drive_oscillations > 0.5:
            parts.append("Drive oscillations are significant.")

        if obs.vector_drift > 0.5:
            parts.append("Vector drift indicates representational shift.")

        if obs.memory_quality < 0.4:
            parts.append("Memory quality is degraded.")
        elif obs.memory_quality > 0.8:
            parts.append("Memory quality is excellent.")

        # Error detection
        error_list: List[str] = []
        if errs.repetitive_loop:
            error_list.append("repetitive loops")
        if errs.contradiction:
            error_list.append("contradictions")
        if errs.overfocus:
            error_list.append("overfocus")
        if errs.similarity_collapse:
            error_list.append("similarity collapse")
        if errs.memory_saturation:
            error_list.append("memory saturation")
        if errs.regulation_oscillation:
            error_list.append("regulation oscillation")

        if error_list:
            parts.append(f"Detected issues: {', '.join(error_list)}.")

        # Confidence
        if conf.confidence_score < 0.3:
            parts.append("Epistemic confidence is very low.")
        elif conf.confidence_score < 0.6:
            parts.append("Epistemic confidence is moderate.")
        else:
            parts.append("Epistemic confidence is high.")

        if conf.novelty_score > 0.6:
            parts.append("High novelty suggests an unfamiliar state.")

        # Historical context
        if history and len(history) >= 2:
            prev = history[-2].cognitive_observation.workspace_stability
            curr = obs.workspace_stability
            delta = curr - prev
            if delta > 0.1:
                parts.append("Workspace stability has improved compared to the previous observation.")
            elif delta < -0.1:
                parts.append("Workspace stability has declined compared to the previous observation.")

        if not parts:
            parts.append("No significant cognitive events to report.")

        return " ".join(parts)

    def generate_summary(self, meta_state: MetaState) -> Dict[str, Any]:
        """Produce a structured summary object."""
        return {
            "narrative": self.generate(meta_state),
            "label": meta_state.meta_state_label,
            "confidence": meta_state.epistemic_confidence.confidence_score,
            "error_count": sum(
                [
                    meta_state.error_detection.repetitive_loop,
                    meta_state.error_detection.contradiction,
                    meta_state.error_detection.overfocus,
                    meta_state.error_detection.similarity_collapse,
                    meta_state.error_detection.memory_saturation,
                    meta_state.error_detection.regulation_oscillation,
                ]
            ),
            "timestamp": time.time(),
        }
