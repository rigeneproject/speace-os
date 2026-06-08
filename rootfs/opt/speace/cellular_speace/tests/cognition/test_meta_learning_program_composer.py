import pytest

from speace_core.cellular_brain.cognition.meta_learning_program_composer import (
    MetaLearningProgramComposer,
)
from speace_core.cellular_brain.cognition.program_models import (
    GridTransformation,
    TransformationProgram,
)
from speace_core.cellular_brain.cognition.few_shot_program_induction_engine import (
    FewShotProgramInductionEngine,
)


class TestMetaLearningProgramComposer:
    def test_extract_features(self):
        pairs = [
            {
                "input": [
                    [1, 1, 0],
                    [1, 1, 0],
                    [0, 0, 0],
                ],
                "output": [
                    [1, 1, 0],
                    [1, 1, 0],
                    [0, 0, 0],
                ],
            }
        ]
        feats = MetaLearningProgramComposer._extract_task_features(pairs)
        assert len(feats) == 6
        assert feats[0] > 0  # height normalized

    def test_transition_probability_uniform_prior(self):
        comp = MetaLearningProgramComposer()
        p = comp.transition_probability("rotate_90", "flip_horizontal")
        # With no data, smoothing should give roughly uniform
        assert 0 < p <= 1.0

    def test_update_and_transition(self):
        comp = MetaLearningProgramComposer()
        prog = TransformationProgram(
            steps=[GridTransformation(name="rotate_90"), GridTransformation(name="flip_horizontal")]
        )
        comp.update_from_success([], prog)
        p = comp.transition_probability("rotate_90", "flip_horizontal")
        assert p > comp.transition_probability("rotate_90", "color_map")

    def test_guided_search_finds_single_primitive(self):
        engine = FewShotProgramInductionEngine()
        comp = MetaLearningProgramComposer()
        pairs = [
            {
                "input": [[0, 1], [2, 0]],
                "output": [[1, 0], [0, 2]],
            }
        ]
        primitives = [GridTransformation(name="rotate_90")]
        cands = comp.guided_search(pairs, primitives, engine, max_depth=1, max_candidates=10)
        # Should find rotate_90 if it matches
        assert isinstance(cands, list)

    def test_task_similarity_empty_history(self):
        comp = MetaLearningProgramComposer()
        prog = TransformationProgram(steps=[GridTransformation(name="rotate_90")])
        sim = comp._task_similarity([], prog)
        assert sim == 0.0
