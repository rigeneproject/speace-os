import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field


class LinguisticStage(str, Enum):
    LINGUISTIC_BABBLING = "linguistic_babbling"
    IMITATION_SANDBOX = "imitation_sandbox"
    SEMANTIC_GROUNDING = "semantic_grounding"
    SYNTACTIC_ASSEMBLY = "syntactic_assembly"
    PRAGMATIC_INFERENCE = "pragmatic_inference"
    LINGUISTIC_ABSTRACTION = "linguistic_abstraction"


class LinguisticCurriculumState(BaseModel):
    stage: LinguisticStage = LinguisticStage.LINGUISTIC_BABBLING
    exposure_count: int = 0
    imitation_attempts: int = 0
    imitation_successes: int = 0
    grounded_concepts: Set[str] = Field(default_factory=set)
    concept_grounding_scores: Dict[str, float] = Field(default_factory=dict)

    syntactic_exposure_count: int = 0
    syntactic_complexity_score: float = 0.0
    syntactic_patterns_mastered: Set[str] = Field(default_factory=set)
    syntactic_assembly_attempts: int = 0
    syntactic_assembly_successes: int = 0

    pragmatic_inference_count: int = 0
    pragmatic_accuracy_score: float = 0.0
    pragmatic_contexts_understood: Set[str] = Field(default_factory=set)
    pragmatic_inference_attempts: int = 0
    pragmatic_inference_successes: int = 0

    abstraction_exposure_count: int = 0
    abstraction_depth_score: float = 0.0
    abstract_concepts_formed: Set[str] = Field(default_factory=set)
    abstraction_attempts: int = 0
    abstraction_successes: int = 0

    metadata: Dict[str, Any] = Field(default_factory=dict)


class LinguisticCurriculum:
    """Postnatal linguistic curriculum engine.

    Stages:
      1. linguistic_babbling       — unstructured exposure, pattern absorption
      2. imitation_sandbox         — safe repetition and echoing
      3. semantic_grounding        — linking symbols to meaning
      4. syntactic_assembly        — complex sentence structure, grammar rules
      5. pragmatic_inference       — context-dependent meaning, implicature
      6. linguistic_abstraction    — metaphors, abstract concepts, recursion
    """

    def __init__(
        self,
        base_path: str = "data/linguistic_curriculum",
        initial_stage: Optional[LinguisticStage] = None,
    ):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.state_path = self.base_path / "state.json"
        self.exposure_log_path = self.base_path / "exposure_log.jsonl"

        self._stage_order = [
            LinguisticStage.LINGUISTIC_BABBLING,
            LinguisticStage.IMITATION_SANDBOX,
            LinguisticStage.SEMANTIC_GROUNDING,
            LinguisticStage.SYNTACTIC_ASSEMBLY,
            LinguisticStage.PRAGMATIC_INFERENCE,
            LinguisticStage.LINGUISTIC_ABSTRACTION,
        ]

        self._state = self._load_state(initial_stage)

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _load_state(self, initial_stage: Optional[LinguisticStage]) -> LinguisticCurriculumState:
        if self.state_path.exists():
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            # Rehydrate sets from lists
            for set_field in ("grounded_concepts", "syntactic_patterns_mastered",
                              "pragmatic_contexts_understood", "abstract_concepts_formed"):
                data[set_field] = set(data.get(set_field, []))
            return LinguisticCurriculumState(**data)
        return LinguisticCurriculumState(stage=initial_stage or LinguisticStage.LINGUISTIC_BABBLING)

    def _save_state(self) -> None:
        dump = self._state.model_dump()
        for set_field in ("grounded_concepts", "syntactic_patterns_mastered",
                          "pragmatic_contexts_understood", "abstract_concepts_formed"):
            dump[set_field] = sorted(dump[set_field])
        self.state_path.write_text(json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8")

    def _log_exposure(self, entry: Dict[str, Any]) -> None:
        with open(self.exposure_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------ #
    # Stage management
    # ------------------------------------------------------------------ #

    def current_stage(self) -> LinguisticStage:
        return self._state.stage

    def advance_stage(self, criteria_met: bool = False) -> LinguisticStage:
        """Advance to the next stage if criteria are met."""
        if not criteria_met:
            return self._state.stage
        idx = self._stage_order.index(self._state.stage)
        if idx < len(self._stage_order) - 1:
            self._state.stage = self._stage_order[idx + 1]
            self._save_state()
        return self._state.stage

    # ------------------------------------------------------------------ #
    # Learning interface
    # ------------------------------------------------------------------ #

    def expose_input(
        self,
        tokens: List[str],
        imitation_target: Optional[List[str]] = None,
        imitation_output: Optional[List[str]] = None,
        grounded_concept: Optional[str] = None,
        grounding_score: float = 0.0,
    ) -> Dict[str, Any]:
        """Expose the curriculum to linguistic input."""
        self._state.exposure_count += 1
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": self._state.stage.value,
            "tokens": tokens,
            "exposure_count": self._state.exposure_count,
        }

        if imitation_target is not None and imitation_output is not None:
            self._state.imitation_attempts += 1
            accuracy = self._compute_imitation_accuracy(imitation_target, imitation_output)
            if accuracy >= 0.8:
                self._state.imitation_successes += 1
            entry["imitation_accuracy"] = accuracy

        if grounded_concept is not None:
            current = self._state.concept_grounding_scores.get(grounded_concept, 0.0)
            updated = min(1.0, current + grounding_score)
            self._state.concept_grounding_scores[grounded_concept] = updated
            if updated >= 0.7:
                self._state.grounded_concepts.add(grounded_concept)
            entry["grounded_concept"] = grounded_concept
            entry["grounding_score"] = updated

        self._log_exposure(entry)
        self._save_state()
        return entry

    def expose_syntactic_assembly(
        self,
        tokens: List[str],
        target_structure: Optional[str] = None,
        output_structure: Optional[str] = None,
        complexity_score: float = 0.0,
        mastered_pattern: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Expose the curriculum to syntactic assembly input (stage 4)."""
        self._state.syntactic_exposure_count += 1
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": self._state.stage.value,
            "tokens": tokens,
            "syntactic_exposure_count": self._state.syntactic_exposure_count,
        }

        if target_structure is not None and output_structure is not None:
            self._state.syntactic_assembly_attempts += 1
            structure_match = target_structure == output_structure
            if structure_match:
                self._state.syntactic_assembly_successes += 1
            entry["structure_match"] = structure_match

        if complexity_score > 0:
            self._state.syntactic_complexity_score = min(
                1.0, self._state.syntactic_complexity_score + complexity_score
            )
            entry["complexity_score"] = self._state.syntactic_complexity_score

        if mastered_pattern is not None:
            self._state.syntactic_patterns_mastered.add(mastered_pattern)
            entry["mastered_pattern"] = mastered_pattern

        self._log_exposure(entry)
        self._save_state()
        return entry

    def expose_pragmatic_inference(
        self,
        tokens: List[str],
        context: Optional[str] = None,
        inference_correct: Optional[bool] = None,
        understood_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Expose the curriculum to pragmatic inference input (stage 5)."""
        self._state.pragmatic_inference_count += 1
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": self._state.stage.value,
            "tokens": tokens,
            "pragmatic_inference_count": self._state.pragmatic_inference_count,
        }

        if inference_correct is not None:
            self._state.pragmatic_inference_attempts += 1
            if inference_correct:
                self._state.pragmatic_inference_successes += 1
            current_accuracy = (
                self._state.pragmatic_inference_successes
                / max(1, self._state.pragmatic_inference_attempts)
            )
            self._state.pragmatic_accuracy_score = current_accuracy
            entry["inference_correct"] = inference_correct
            entry["pragmatic_accuracy"] = current_accuracy

        if understood_context is not None:
            self._state.pragmatic_contexts_understood.add(understood_context)
            entry["understood_context"] = understood_context

        self._log_exposure(entry)
        self._save_state()
        return entry

    def expose_linguistic_abstraction(
        self,
        tokens: List[str],
        abstract_concept: Optional[str] = None,
        depth_score: float = 0.0,
        abstraction_success: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Expose the curriculum to linguistic abstraction input (stage 6)."""
        self._state.abstraction_exposure_count += 1
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": self._state.stage.value,
            "tokens": tokens,
            "abstraction_exposure_count": self._state.abstraction_exposure_count,
        }

        if abstraction_success is not None:
            self._state.abstraction_attempts += 1
            if abstraction_success:
                self._state.abstraction_successes += 1
            entry["abstraction_success"] = abstraction_success

        if depth_score > 0:
            self._state.abstraction_depth_score = min(
                1.0, self._state.abstraction_depth_score + depth_score
            )
            entry["depth_score"] = self._state.abstraction_depth_score

        if abstract_concept is not None:
            self._state.abstract_concepts_formed.add(abstract_concept)
            entry["abstract_concept"] = abstract_concept

        self._log_exposure(entry)
        self._save_state()
        return entry

    def get_learning_metrics(self) -> Dict[str, Any]:
        return {
            "stage": self._state.stage.value,
            "exposure_count": self._state.exposure_count,
            "imitation_attempts": self._state.imitation_attempts,
            "imitation_successes": self._state.imitation_successes,
            "imitation_accuracy": (
                self._state.imitation_successes / max(1, self._state.imitation_attempts)
            ),
            "grounded_concepts_count": len(self._state.grounded_concepts),
            "grounded_concepts": sorted(self._state.grounded_concepts),
            "concept_grounding_scores": dict(self._state.concept_grounding_scores),
            "syntactic_exposure_count": self._state.syntactic_exposure_count,
            "syntactic_complexity_score": self._state.syntactic_complexity_score,
            "syntactic_patterns_mastered": sorted(self._state.syntactic_patterns_mastered),
            "syntactic_assembly_attempts": self._state.syntactic_assembly_attempts,
            "syntactic_assembly_successes": self._state.syntactic_assembly_successes,
            "syntactic_assembly_accuracy": (
                self._state.syntactic_assembly_successes / max(1, self._state.syntactic_assembly_attempts)
            ),
            "pragmatic_inference_count": self._state.pragmatic_inference_count,
            "pragmatic_accuracy_score": self._state.pragmatic_accuracy_score,
            "pragmatic_contexts_understood": sorted(self._state.pragmatic_contexts_understood),
            "pragmatic_inference_attempts": self._state.pragmatic_inference_attempts,
            "pragmatic_inference_successes": self._state.pragmatic_inference_successes,
            "abstraction_exposure_count": self._state.abstraction_exposure_count,
            "abstraction_depth_score": self._state.abstraction_depth_score,
            "abstract_concepts_formed": sorted(self._state.abstract_concepts_formed),
            "abstraction_attempts": self._state.abstraction_attempts,
            "abstraction_successes": self._state.abstraction_successes,
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_imitation_accuracy(target: List[str], output: List[str]) -> float:
        if not target:
            return 0.0
        matches = sum(1 for t, o in zip(target, output) if t == o)
        max_len = max(len(target), len(output))
        return matches / max_len if max_len > 0 else 0.0
