"""CognitiveSkillLibrary — T135: initial library of evolvable cognitive skills.

Pre-configured skills for:
- reasoning (ragionamento)
- metacognition
- Italian language
- narrative synthesis
- vocal dialogue
- confidence scoring

All skills are approved by default as baseline templates.
They can be cloned, mutated, and evolved via T132/T133.
"""

import time
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.cognitive_evolution.cognitive_skill_registry import (
    CognitiveSkill,
    CognitiveSkillRegistry,
)


class CognitiveSkillLibrary:
    """T135: managed library of baseline cognitive skills."""

    def __init__(self, registry: CognitiveSkillRegistry) -> None:
        self._registry = registry

    def install_all(self) -> List[str]:
        """Register all baseline skills. Returns list of installed skill IDs."""
        installed: List[str] = []
        for skill in self._baseline_skills():
            if self._registry.get(skill.skill_id) is None:
                self._registry.register(skill)
                installed.append(skill.skill_id)
        return installed

    def _baseline_skills(self) -> List[CognitiveSkill]:
        ts = time.time()
        return [
            # ------------------------------------------------------------------ #
            # Reasoning
            # ------------------------------------------------------------------ #
            CognitiveSkill(
                skill_id="SK-REASON-001",
                skill_type="thought",
                name="basic_reasoning",
                params={
                    "reasoning_depth": 3,
                    "reasoning_breadth": 3,
                    "success_bias": 0.8,
                    "stability_boost": 0.1,
                    "coherence_boost": 0.1,
                    "confidence_boost": 0.05,
                },
                template=(
                    "Analyze the current state across {reasoning_depth} levels "
                    "with {reasoning_breadth} branches per level. "
                    "Prioritize stability and coherence."
                ),
                approved=True,
                origin="human",
                created_at=ts,
            ),
            # ------------------------------------------------------------------ #
            # Metacognition
            # ------------------------------------------------------------------ #
            CognitiveSkill(
                skill_id="SK-META-001",
                skill_type="metacognitive",
                name="basic_metacognition",
                params={
                    "meta_effectiveness": 0.7,
                    "self_observation_rate": 0.5,
                    "error_sensitivity": 0.6,
                    "strategy_evaluation_window": 10,
                    "success_bias": 0.8,
                    "stability_boost": 0.15,
                    "coherence_boost": 0.1,
                    "confidence_boost": 0.1,
                },
                template=(
                    "Observe workspace stability and narrative coherence. "
                    "Detect repetitive loops, contradictions, and overfocus. "
                    "Evaluate recent strategies over {strategy_evaluation_window} cycles."
                ),
                approved=True,
                origin="human",
                created_at=ts,
            ),
            # ------------------------------------------------------------------ #
            # Italian Language
            # ------------------------------------------------------------------ #
            CognitiveSkill(
                skill_id="SK-LANG-IT-001",
                skill_type="language",
                name="italian_language",
                params={
                    "language_fluency": 0.85,
                    "context_depth": 3,
                    "formality_level": 0.5,
                    "success_bias": 0.85,
                    "stability_boost": 0.0,
                    "coherence_boost": 0.15,
                    "confidence_boost": 0.05,
                },
                template=(
                    "Generate Italian responses with {language_fluency} fluency. "
                    "Maintain context depth of {context_depth} turns. "
                    "Adapt formality to interlocutor."
                ),
                approved=True,
                origin="human",
                created_at=ts,
            ),
            # ------------------------------------------------------------------ #
            # Narrative Synthesis
            # ------------------------------------------------------------------ #
            CognitiveSkill(
                skill_id="SK-NARR-001",
                skill_type="language",
                name="narrative_synthesis",
                params={
                    "narrative_compression_ratio": 0.3,
                    "temporal_span_hours": 24.0,
                    "importance_threshold": 5,
                    "success_bias": 0.8,
                    "stability_boost": 0.05,
                    "coherence_boost": 0.2,
                    "confidence_boost": 0.05,
                },
                template=(
                    "Synthesize events from the last {temporal_span_hours} hours. "
                    "Compress by {narrative_compression_ratio} while preserving events "
                    "with importance >= {importance_threshold}. "
                    "Maintain causal and temporal coherence."
                ),
                approved=True,
                origin="human",
                created_at=ts,
            ),
            # ------------------------------------------------------------------ #
            # Vocal Dialogue
            # ------------------------------------------------------------------ #
            CognitiveSkill(
                skill_id="SK-DIALOGUE-001",
                skill_type="language",
                name="vocal_dialogue",
                params={
                    "turn_memory": 10,
                    "prosody_adaptation": 0.5,
                    "pause_threshold_ms": 300.0,
                    "success_bias": 0.9,
                    "stability_boost": 0.0,
                    "coherence_boost": 0.1,
                    "confidence_boost": 0.05,
                },
                template=(
                    "Engage in vocal dialogue remembering {turn_memory} prior turns. "
                    "Adapt prosody with factor {prosody_adaptation}. "
                    "Respect pause threshold of {pause_threshold_ms}ms."
                ),
                approved=True,
                origin="human",
                created_at=ts,
            ),
            # ------------------------------------------------------------------ #
            # Confidence Scoring
            # ------------------------------------------------------------------ #
            CognitiveSkill(
                skill_id="SK-CONF-001",
                skill_type="metacognitive",
                name="confidence_scoring",
                params={
                    "novelty_weight": 0.3,
                    "history_window": 10,
                    "divergence_threshold": 0.4,
                    "success_bias": 0.8,
                    "stability_boost": 0.1,
                    "coherence_boost": 0.05,
                    "confidence_boost": 0.15,
                },
                template=(
                    "Score epistemic confidence from circuit evaluation or state divergence. "
                    "Weight novelty at {novelty_weight}. "
                    "Compare against {history_window} recent states. "
                    "Flag if divergence exceeds {divergence_threshold}."
                ),
                approved=True,
                origin="human",
                created_at=ts,
            ),
        ]

    def get_skill(self, skill_id: str) -> Optional[CognitiveSkill]:
        return self._registry.get(skill_id)

    def list_by_type(self, skill_type: str) -> List[CognitiveSkill]:
        return self._registry.list_skills(skill_type=skill_type, approved_only=True)

    def summary(self) -> Dict[str, Any]:
        return {
            "total_skills": len(self._registry.list_skills(approved_only=True)),
            "by_type": {
                "thought": len(self._registry.list_skills(skill_type="thought", approved_only=True)),
                "metacognitive": len(self._registry.list_skills(skill_type="metacognitive", approved_only=True)),
                "language": len(self._registry.list_skills(skill_type="language", approved_only=True)),
            },
        }
