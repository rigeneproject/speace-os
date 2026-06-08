"""LinguisticCurriculumEngine — T5: integrated linguistic postnatal curriculum.

Wraps LinguisticCurriculum with:
- Automatic stage advancement based on criteria
- Integration hooks for DialogueManager (exposure) and SymbolicGroundingEngine (grounding)
- Runtime metrics and reporting
"""

from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.postnatal_learning.linguistic_curriculum import (
    LinguisticCurriculum,
    LinguisticStage,
)


class LinguisticCurriculumEngine:
    """Orchestrates the linguistic curriculum with automatic stage advancement.

    The engine processes dialogue turns as linguistic exposure, tracks imitation
    success, and integrates with the symbolic grounding engine for semantic
    learning. It can auto-advance through stages:

    1. linguistic_babbling       -> 10 exposures
    2. imitation_sandbox       -> 5 successful imitations
    3. semantic_grounding      -> 3 grounded concepts
    4. syntactic_assembly      -> syntactic_complexity_score >= 0.6 + 2 patterns mastered
    5. pragmatic_inference     -> pragmatic_accuracy_score >= 0.6 + 2 contexts understood
    6. linguistic_abstraction  -> abstraction_depth_score >= 0.6 + 2 abstract concepts (final)
    """

    def __init__(
        self,
        curriculum: Optional[LinguisticCurriculum] = None,
        auto_advance: bool = True,
    ):
        self._curriculum = curriculum or LinguisticCurriculum()
        self._auto_advance = auto_advance

    @property
    def stage(self) -> LinguisticStage:
        return self._curriculum.current_stage()

    def process_dialogue_turn(
        self,
        user_tokens: List[str],
        speace_tokens: List[str],
        grounded_concepts: Optional[List[str]] = None,
        grounding_scores: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Process a dialogue turn as linguistic exposure and imitation.

        Returns updated metrics and curriculum entry.
        """
        entry = self._curriculum.expose_input(
            tokens=user_tokens,
            imitation_target=user_tokens,
            imitation_output=speace_tokens,
            grounded_concept=grounded_concepts[0] if grounded_concepts else None,
            grounding_score=(
                grounding_scores.get(grounded_concepts[0], 0.0)
                if grounding_scores and grounded_concepts
                else 0.0
            ),
        )

        if self._auto_advance:
            self._try_advance()

        return {
            "stage": self.stage.value,
            "entry": entry,
            "metrics": self._curriculum.get_learning_metrics(),
        }

    def record_grounding(
        self,
        concept: str,
        score: float,
        tokens: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Record a symbolic grounding event directly."""
        entry = self._curriculum.expose_input(
            tokens=tokens or [concept],
            grounded_concept=concept,
            grounding_score=score,
        )
        if self._auto_advance:
            self._try_advance()
        return {
            "stage": self.stage.value,
            "entry": entry,
            "metrics": self._curriculum.get_learning_metrics(),
        }

    def process_syntactic_turn(
        self,
        tokens: List[str],
        target_structure: Optional[str] = None,
        output_structure: Optional[str] = None,
        complexity_score: float = 0.0,
        mastered_pattern: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process a syntactic assembly turn."""
        entry = self._curriculum.expose_syntactic_assembly(
            tokens=tokens,
            target_structure=target_structure,
            output_structure=output_structure,
            complexity_score=complexity_score,
            mastered_pattern=mastered_pattern,
        )
        if self._auto_advance:
            self._try_advance()
        return {
            "stage": self.stage.value,
            "entry": entry,
            "metrics": self._curriculum.get_learning_metrics(),
        }

    def process_pragmatic_turn(
        self,
        tokens: List[str],
        context: Optional[str] = None,
        inference_correct: Optional[bool] = None,
        understood_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process a pragmatic inference turn."""
        entry = self._curriculum.expose_pragmatic_inference(
            tokens=tokens,
            context=context,
            inference_correct=inference_correct,
            understood_context=understood_context,
        )
        if self._auto_advance:
            self._try_advance()
        return {
            "stage": self.stage.value,
            "entry": entry,
            "metrics": self._curriculum.get_learning_metrics(),
        }

    def process_abstraction_turn(
        self,
        tokens: List[str],
        abstract_concept: Optional[str] = None,
        depth_score: float = 0.0,
        abstraction_success: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Process a linguistic abstraction turn."""
        entry = self._curriculum.expose_linguistic_abstraction(
            tokens=tokens,
            abstract_concept=abstract_concept,
            depth_score=depth_score,
            abstraction_success=abstraction_success,
        )
        if self._auto_advance:
            self._try_advance()
        return {
            "stage": self.stage.value,
            "entry": entry,
            "metrics": self._curriculum.get_learning_metrics(),
        }

    def _try_advance(self) -> None:
        metrics = self._curriculum.get_learning_metrics()
        current = self.stage

        if current == LinguisticStage.LINGUISTIC_BABBLING:
            if metrics["exposure_count"] >= 10:
                self._curriculum.advance_stage(criteria_met=True)
        elif current == LinguisticStage.IMITATION_SANDBOX:
            if metrics["imitation_successes"] >= 5:
                self._curriculum.advance_stage(criteria_met=True)
        elif current == LinguisticStage.SEMANTIC_GROUNDING:
            if metrics["grounded_concepts_count"] >= 3:
                self._curriculum.advance_stage(criteria_met=True)
        elif current == LinguisticStage.SYNTACTIC_ASSEMBLY:
            if (metrics["syntactic_complexity_score"] >= 0.6
                    and len(metrics["syntactic_patterns_mastered"]) >= 2):
                self._curriculum.advance_stage(criteria_met=True)
        elif current == LinguisticStage.PRAGMATIC_INFERENCE:
            if (metrics["pragmatic_accuracy_score"] >= 0.6
                    and len(metrics["pragmatic_contexts_understood"]) >= 2):
                self._curriculum.advance_stage(criteria_met=True)
        elif current == LinguisticStage.LINGUISTIC_ABSTRACTION:
            # Final stage — no further advancement
            pass

    def get_metrics(self) -> Dict[str, Any]:
        return self._curriculum.get_learning_metrics()

    def reset(self) -> None:
        """Start a fresh curriculum (clears state files and reloads)."""
        base_path = str(self._curriculum.base_path)
        # Remove persisted state files so the new instance starts clean
        for p in [self._curriculum.state_path, self._curriculum.exposure_log_path]:
            try:
                if p.exists():
                    p.unlink()
            except OSError:
                pass
        self._curriculum = LinguisticCurriculum(base_path=base_path)
