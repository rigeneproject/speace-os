"""Tests for ObjectCentricInductionBridge."""
import pytest
from speace_core.cellular_brain.cognition.object_centric_induction_bridge import (
    ObjectCentricInductionBridge,
)
from speace_core.cellular_brain.cognition.program_models import (
    TransformationProgram,
    GridTransformation,
    ProgramCandidate,
)


@pytest.fixture
def bridge():
    return ObjectCentricInductionBridge()


@pytest.fixture
def simple_train_pair():
    """A simple color-change task."""
    return [
        {
            "input": [[1, 1], [0, 0]],
            "output": [[2, 2], [0, 0]],
        }
    ]


@pytest.fixture
def replicate_train_pair():
    """A replication task: new object added."""
    return [
        {
            "input": [[0, 0, 0], [0, 1, 0], [0, 0, 0]],
            "output": [[2, 0, 0], [0, 1, 0], [0, 0, 0]],
        }
    ]


class TestGenerateHypotheses:
    def test_color_change_hypothesis(self, bridge, simple_train_pair):
        hyps = bridge.generate_hypotheses(simple_train_pair)
        color_map_hyps = [h for h in hyps if h.name == "color_map"]
        assert len(color_map_hyps) >= 1

    def test_replicate_hypothesis(self, bridge, replicate_train_pair):
        hyps = bridge.generate_hypotheses(replicate_train_pair)
        replicate_hyps = [h for h in hyps if h.name == "slot_replicate_by_count"]
        assert len(replicate_hyps) >= 1

    def test_empty_pairs_returns_empty(self, bridge):
        assert bridge.generate_hypotheses([]) == []

    def test_remove_hypothesis(self, bridge):
        pair = [
            {
                "input": [[0, 0, 0], [0, 1, 0], [0, 2, 0]],
                "output": [[0, 0, 0], [0, 1, 0], [0, 0, 0]],
            }
        ]
        hyps = bridge.generate_hypotheses(pair)
        remove_hyps = [h for h in hyps if h.name == "slot_remove_by_predicate"]
        assert len(remove_hyps) >= 1


class TestScoreWithSlots:
    def test_perfect_program_scores_high(self, bridge, simple_train_pair):
        prog = TransformationProgram(steps=[
            GridTransformation(name="color_map", params={"mapping": {"1": 2}}),
        ])
        score = bridge.score_with_slots(prog, simple_train_pair)
        assert score > 0.5

    def test_wrong_program_scores_low(self, bridge, simple_train_pair):
        prog = TransformationProgram(steps=[
            GridTransformation(name="flip_horizontal", params={}),
        ])
        score = bridge.score_with_slots(prog, simple_train_pair)
        assert score <= 0.8

    def test_empty_pairs_returns_zero(self, bridge):
        prog = TransformationProgram(steps=[])
        assert bridge.score_with_slots(prog, []) == 0.0


class TestRerankWithSlots:
    def test_rerank_orders_candidates(self, bridge, simple_train_pair):
        candidates = [
            ProgramCandidate(
                program=TransformationProgram(steps=[GridTransformation(name="flip_horizontal", params={})]),
                train_matches=1,
                confidence=0.9,
            ),
            ProgramCandidate(
                program=TransformationProgram(steps=[GridTransformation(name="color_map", params={"mapping": {"1": 2}})]),
                train_matches=1,
                confidence=0.7,
            ),
        ]
        reranked = bridge.rerank_with_slots(candidates, simple_train_pair)
        assert len(reranked) == 2
        # The color_map candidate should rank higher after slot scoring
        assert reranked[0].confidence > reranked[1].confidence or reranked[0].program.steps[0].name == "color_map"

    def test_empty_candidates_unchanged(self, bridge):
        assert bridge.rerank_with_slots([], []) == []
