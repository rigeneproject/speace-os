import pytest
import tempfile

from speace_core.cellular_brain.postnatal_learning.linguistic_curriculum_engine import (
    LinguisticCurriculumEngine,
)
from speace_core.cellular_brain.postnatal_learning.linguistic_curriculum import (
    LinguisticCurriculum,
    LinguisticStage,
)


class TestLinguisticCurriculumEngine:
    def test_initial_stage_is_babbling(self):
        with tempfile.TemporaryDirectory() as td:
            curriculum = LinguisticCurriculum(base_path=td)
            engine = LinguisticCurriculumEngine(curriculum=curriculum, auto_advance=False)
            assert engine.stage == LinguisticStage.LINGUISTIC_BABBLING

    def test_process_dialogue_turn_tracks_exposure(self):
        with tempfile.TemporaryDirectory() as td:
            curriculum = LinguisticCurriculum(base_path=td)
            engine = LinguisticCurriculumEngine(curriculum=curriculum, auto_advance=False)
            result = engine.process_dialogue_turn(
                user_tokens=["ciao"],
                speace_tokens=["ciao"],
            )
            assert result["stage"] == "linguistic_babbling"
            assert result["metrics"]["exposure_count"] == 1

    def test_process_dialogue_turn_tracks_imitation_success(self):
        with tempfile.TemporaryDirectory() as td:
            curriculum = LinguisticCurriculum(base_path=td)
            engine = LinguisticCurriculumEngine(curriculum=curriculum, auto_advance=False)
            engine.process_dialogue_turn(
                user_tokens=["ciao"],
                speace_tokens=["ciao"],
            )
            metrics = engine.get_metrics()
            assert metrics["imitation_attempts"] == 1
            assert metrics["imitation_successes"] == 1

    def test_auto_advance_from_babbling(self):
        with tempfile.TemporaryDirectory() as td:
            curriculum = LinguisticCurriculum(base_path=td)
            engine = LinguisticCurriculumEngine(curriculum=curriculum, auto_advance=True)
            for _ in range(10):
                engine.process_dialogue_turn(
                    user_tokens=["hello"],
                    speace_tokens=["hello"],
                )
            assert engine.stage == LinguisticStage.IMITATION_SANDBOX

    def test_auto_advance_from_imitation(self):
        with tempfile.TemporaryDirectory() as td:
            curriculum = LinguisticCurriculum(base_path=td, initial_stage=LinguisticStage.IMITATION_SANDBOX)
            engine = LinguisticCurriculumEngine(curriculum=curriculum, auto_advance=True)
            for _ in range(5):
                engine.process_dialogue_turn(
                    user_tokens=["hello"],
                    speace_tokens=["hello"],
                )
            assert engine.stage == LinguisticStage.SEMANTIC_GROUNDING

    def test_record_grounding_advances_to_semantic(self):
        with tempfile.TemporaryDirectory() as td:
            curriculum = LinguisticCurriculum(base_path=td, initial_stage=LinguisticStage.IMITATION_SANDBOX)
            engine = LinguisticCurriculumEngine(curriculum=curriculum, auto_advance=True)
            for _ in range(5):
                engine.process_dialogue_turn(
                    user_tokens=["hello"],
                    speace_tokens=["hello"],
                )
            assert engine.stage == LinguisticStage.SEMANTIC_GROUNDING
            engine.record_grounding("cat", 0.8)
            engine.record_grounding("dog", 0.8)
            engine.record_grounding("bird", 0.8)
            metrics = engine.get_metrics()
            assert metrics["grounded_concepts_count"] == 3
            assert set(metrics["grounded_concepts"]) == {"bird", "cat", "dog"}

    def test_reset_creates_new_curriculum_instance(self):
        with tempfile.TemporaryDirectory() as td:
            curriculum = LinguisticCurriculum(base_path=td)
            engine = LinguisticCurriculumEngine(curriculum=curriculum, auto_advance=False)
            engine.process_dialogue_turn(user_tokens=["a"], speace_tokens=["a"])
            old_metrics = engine.get_metrics()
            engine.reset()
            new_metrics = engine.get_metrics()
            assert new_metrics["exposure_count"] == 0
            assert old_metrics["exposure_count"] == 1

    # ------------------------------------------------------------------ #
    # Auto-advance through advanced stages
    # ------------------------------------------------------------------ #

    def test_auto_advance_from_semantic_to_syntactic(self):
        with tempfile.TemporaryDirectory() as td:
            curriculum = LinguisticCurriculum(
                base_path=td,
                initial_stage=LinguisticStage.SEMANTIC_GROUNDING,
            )
            engine = LinguisticCurriculumEngine(curriculum=curriculum, auto_advance=True)
            # Reach 3 grounded concepts
            for concept in ("cat", "dog", "bird"):
                engine.record_grounding(concept, 0.8)
            assert engine.stage == LinguisticStage.SYNTACTIC_ASSEMBLY

    def test_auto_advance_from_syntactic_to_pragmatic(self):
        with tempfile.TemporaryDirectory() as td:
            curriculum = LinguisticCurriculum(
                base_path=td,
                initial_stage=LinguisticStage.SYNTACTIC_ASSEMBLY,
            )
            engine = LinguisticCurriculumEngine(curriculum=curriculum, auto_advance=True)
            engine.process_syntactic_turn(
                ["if"], complexity_score=0.3, mastered_pattern="conditional",
            )
            engine.process_syntactic_turn(
                ["that"], complexity_score=0.3, mastered_pattern="relative_clause",
            )
            assert engine.stage == LinguisticStage.PRAGMATIC_INFERENCE

    def test_auto_advance_from_pragmatic_to_abstraction(self):
        with tempfile.TemporaryDirectory() as td:
            curriculum = LinguisticCurriculum(
                base_path=td,
                initial_stage=LinguisticStage.PRAGMATIC_INFERENCE,
            )
            engine = LinguisticCurriculumEngine(curriculum=curriculum, auto_advance=True)
            engine.process_pragmatic_turn(
                ["sure"], inference_correct=True, understood_context="irony",
            )
            engine.process_pragmatic_turn(
                ["i", "see"], inference_correct=True, understood_context="implication",
            )
            assert engine.stage == LinguisticStage.LINGUISTIC_ABSTRACTION

    def test_auto_advance_stops_at_abstraction(self):
        with tempfile.TemporaryDirectory() as td:
            curriculum = LinguisticCurriculum(
                base_path=td,
                initial_stage=LinguisticStage.LINGUISTIC_ABSTRACTION,
            )
            engine = LinguisticCurriculumEngine(curriculum=curriculum, auto_advance=True)
            engine.process_abstraction_turn(
                ["causality"], depth_score=0.5, abstract_concept="causality",
            )
            engine.process_abstraction_turn(
                ["infinity"], depth_score=0.5, abstract_concept="infinity",
            )
            # Should remain at abstraction (final stage)
            assert engine.stage == LinguisticStage.LINGUISTIC_ABSTRACTION

    def test_process_syntactic_turn_returns_metrics(self):
        with tempfile.TemporaryDirectory() as td:
            engine = LinguisticCurriculumEngine(
                curriculum=LinguisticCurriculum(base_path=td),
            )
            result = engine.process_syntactic_turn(
                ["if", "then"], complexity_score=0.2,
            )
            assert "stage" in result
            assert "entry" in result
            assert "metrics" in result

    def test_process_pragmatic_turn_returns_metrics(self):
        with tempfile.TemporaryDirectory() as td:
            engine = LinguisticCurriculumEngine(
                curriculum=LinguisticCurriculum(base_path=td),
            )
            result = engine.process_pragmatic_turn(
                ["oh", "really"], inference_correct=True,
            )
            assert "stage" in result
            assert "entry" in result
            assert "metrics" in result

    def test_process_abstraction_turn_returns_metrics(self):
        with tempfile.TemporaryDirectory() as td:
            engine = LinguisticCurriculumEngine(
                curriculum=LinguisticCurriculum(base_path=td),
            )
            result = engine.process_abstraction_turn(
                ["time", "is", "relative"], depth_score=0.4,
            )
            assert "stage" in result
            assert "entry" in result
            assert "metrics" in result
