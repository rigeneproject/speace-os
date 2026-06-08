"""Smoke tests for the MM-APR multi-agent reasoning council."""

import pytest

from speace_core.cellular_brain.cognition.mmapr_council import (
    AdversarialCritic,
    CouncilVerdict,
    EpistemicAuditor,
    InterpreterAgent,
    MMAPRCouncil,
    StructuralVerifier,
    _compute_candidate_id,
    _grid_eq,
    _perturb_grid,
    _pixel_match_score,
)
from speace_core.cellular_brain.cognition.program_models import (
    GridTransformation,
    TransformationProgram,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
def _identity():
    """A program that just copies the input (no-op)."""
    def fn(grid, params):
        return [row[:] for row in grid]
    return fn


def _flip_h():
    """A program that flips horizontally."""
    def fn(grid, params):
        return [row[::-1] for row in grid]
    return fn


@pytest.fixture
def simple_pair():
    return {
        "input": [[1, 0], [0, 1]],
        "output": [[1, 0], [0, 1]],
    }


@pytest.fixture
def horizontal_flip_pair():
    return {
        "input": [[1, 2, 3], [4, 5, 6]],
        "output": [[3, 2, 1], [6, 5, 4]],
    }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
class TestHelpers:
    def test_grid_eq_true(self):
        assert _grid_eq([[1, 2], [3, 4]], [[1, 2], [3, 4]]) is True

    def test_grid_eq_false_shape(self):
        assert _grid_eq([[1, 2]], [[1, 2], [3, 4]]) is False

    def test_grid_eq_false_value(self):
        assert _grid_eq([[1, 2], [3, 4]], [[1, 2], [3, 5]]) is False

    def test_grid_eq_none(self):
        assert _grid_eq(None, [[1]]) is False

    def test_pixel_match_score_perfect(self):
        s = _pixel_match_score([[1, 2], [3, 4]], [[1, 2], [3, 4]])
        assert s == 1.0

    def test_pixel_match_score_half(self):
        s = _pixel_match_score([[1, 0], [3, 0]], [[1, 2], [3, 4]])
        assert s == 0.5

    def test_perturb_grid_deterministic(self):
        g = [[1, 2, 3], [4, 5, 6]]
        p1 = _perturb_grid(g, seed=1)
        p2 = _perturb_grid(g, seed=1)
        assert p1 == p2
        # And it differs from the original
        assert p1 != g

    def test_compute_candidate_id_stable(self):
        prog = TransformationProgram(steps=[
            GridTransformation(name="flip_horizontal"),
        ])
        id1 = _compute_candidate_id(prog)
        id2 = _compute_candidate_id(prog)
        assert id1 == id2
        assert id1.startswith("cand-")


# --------------------------------------------------------------------------- #
# Interpreter
# --------------------------------------------------------------------------- #
class TestInterpreter:
    def test_apply_identity(self, simple_pair):
        # Use a real registered primitive for identity (just use flip_horizontal twice)
        prog = TransformationProgram(steps=[
            GridTransformation(name="flip_horizontal"),
            GridTransformation(name="flip_horizontal"),
        ])
        interp = InterpreterAgent()
        result = interp.apply(prog, [simple_pair])
        assert result["outputs"][0] == simple_pair["output"]
        assert result["execution_success_rate"] == 1.0

    def test_apply_returns_none_on_unknown(self):
        prog = TransformationProgram(steps=[
            GridTransformation(name="nonexistent_primitive_xyz"),
        ])
        interp = InterpreterAgent()
        result = interp.apply(prog, [{"input": [[1]], "output": [[1]]}])
        assert result["outputs"][0] is None
        assert result["execution_success_rate"] == 0.0

    def test_apply_empty_pairs(self):
        prog = TransformationProgram(steps=[])
        interp = InterpreterAgent()
        result = interp.apply(prog, [])
        assert result["outputs"] == []


# --------------------------------------------------------------------------- #
# Structural Verifier
# --------------------------------------------------------------------------- #
class TestVerifier:
    def test_full_match(self, simple_pair):
        prog = TransformationProgram(steps=[
            GridTransformation(name="flip_horizontal"),
            GridTransformation(name="flip_horizontal"),
        ])
        interp = InterpreterAgent()
        io = interp.apply(prog, [simple_pair, simple_pair, simple_pair])
        v = StructuralVerifier()
        vote = v.verify(io, [simple_pair, simple_pair, simple_pair])
        assert vote.accept is True
        assert vote.confidence == 1.0
        assert "3/3" in vote.rationale

    def test_no_match(self):
        prog = TransformationProgram(steps=[
            GridTransformation(name="flip_horizontal"),
        ])
        # Input is symmetric horizontally so flip_h is identity; but the
        # expected output is different. Use a non-symmetric pair.
        train = [{"input": [[1, 2]], "output": [[9, 9]]}]
        interp = InterpreterAgent()
        io = interp.apply(prog, train)
        v = StructuralVerifier()
        vote = v.verify(io, train)
        assert vote.accept is False
        assert vote.confidence < 1.0

    def test_empty_pairs(self):
        v = StructuralVerifier()
        vote = v.verify({"outputs": []}, [])
        assert vote.accept is False
        assert vote.confidence == 0.0


# --------------------------------------------------------------------------- #
# Adversarial Critic
# --------------------------------------------------------------------------- #
class TestAdversarialCritic:
    def test_robust_program(self, simple_pair):
        # Two flips = identity → robust under perturbations
        prog = TransformationProgram(steps=[
            GridTransformation(name="flip_horizontal"),
            GridTransformation(name="flip_horizontal"),
        ])
        c = AdversarialCritic(n_perturbations=3)
        vote = c.challenge(prog, [simple_pair, simple_pair])
        assert vote.confidence > 0.0

    def test_failing_program(self):
        # A program that crashes on unknown primitives
        prog = TransformationProgram(steps=[
            GridTransformation(name="nonexistent_xyz"),
        ])
        c = AdversarialCritic()
        vote = c.challenge(prog, [{"input": [[1]], "output": [[1]]}])
        assert vote.accept is False
        assert vote.confidence == 0.0

    def test_empty_pairs(self):
        c = AdversarialCritic()
        vote = c.challenge(TransformationProgram(steps=[]), [])
        assert vote.accept is False


# --------------------------------------------------------------------------- #
# Epistemic Auditor
# --------------------------------------------------------------------------- #
class TestAuditor:
    def test_high_evidence(self):
        # 5 pairs, short program, diverse inputs
        prog = TransformationProgram(steps=[GridTransformation(name="flip_horizontal")])
        pairs = [
            {"input": [[1, 2, 3], [4, 5, 6]], "output": [[3, 2, 1], [6, 5, 4]]},
            {"input": [[7, 8], [9, 1]], "output": [[8, 7], [1, 9]]},
            {"input": [[2, 2], [2, 2]], "output": [[2, 2], [2, 2]]},
            {"input": [[3, 1, 4], [1, 5, 9]], "output": [[4, 1, 3], [9, 5, 1]]},
            {"input": [[6, 2, 8], [0, 0, 1]], "output": [[8, 2, 6], [1, 0, 0]]},
        ]
        a = EpistemicAuditor()
        vote = a.audit(prog, pairs)
        assert vote.confidence > 0.5

    def test_low_evidence(self):
        prog = TransformationProgram(steps=[GridTransformation(name="flip_horizontal")])
        a = EpistemicAuditor()
        vote = a.audit(prog, [{"input": [[1]], "output": [[1]]}])
        assert vote.confidence < 0.5

    def test_empty_pairs(self):
        a = EpistemicAuditor()
        vote = a.audit(TransformationProgram(steps=[]), [])
        assert vote.confidence == 0.0


# --------------------------------------------------------------------------- #
# Council
# --------------------------------------------------------------------------- #
class TestCouncil:
    def test_full_deliberation(self, simple_pair):
        prog = TransformationProgram(steps=[
            GridTransformation(name="flip_horizontal"),
            GridTransformation(name="flip_horizontal"),
        ])
        council = MMAPRCouncil()
        verdict = council.deliberate(prog, [simple_pair, simple_pair])
        assert isinstance(verdict, CouncilVerdict)
        assert len(verdict.votes) == 3  # verifier, critic, auditor
        assert 0.0 <= verdict.emergent_confidence <= 1.0
        assert verdict.deliberation_id.startswith("delib-")

    def test_vote_ordering_deterministic(self, simple_pair):
        prog = TransformationProgram(steps=[
            GridTransformation(name="flip_horizontal"),
        ])
        c = MMAPRCouncil()
        v1 = c.deliberate(prog, [simple_pair])
        v2 = c.deliberate(prog, [simple_pair])
        # Same agent order
        assert [vote.agent for vote in v1.votes] == [vote.agent for vote in v2.votes]

    def test_to_dict_roundtrip(self, simple_pair):
        prog = TransformationProgram(steps=[GridTransformation(name="flip_horizontal")])
        c = MMAPRCouncil()
        verdict = c.deliberate(prog, [simple_pair])
        d = verdict.to_dict()
        assert d["accept"] in (True, False)
        assert "votes" in d
        assert len(d["votes"]) == 3
        for v in d["votes"]:
            assert "agent" in v
            assert "confidence" in v
            assert "accept" in v

    def test_score_uncertain_below_threshold(self):
        c = MMAPRCouncil()
        r = c.score_uncertain(
            TransformationProgram(steps=[]),
            [],
            pixel_score=0.01,  # T169 — wide band: < 0.05 → deterministic reject
        )
        assert r["ran_council"] is False
        assert r["accept"] is False

    def test_score_uncertain_above_threshold(self):
        c = MMAPRCouncil()
        r = c.score_uncertain(
            TransformationProgram(steps=[]),
            [{"input": [[1]], "output": [[1]]}],
            pixel_score=0.995,  # T169 — wide band: >= 0.99 → deterministic accept
        )
        assert r["ran_council"] is False
        assert r["accept"] is True

    def test_score_uncertain_in_band_runs_council(self, simple_pair):
        prog = TransformationProgram(steps=[
            GridTransformation(name="flip_horizontal"),
            GridTransformation(name="flip_horizontal"),
        ])
        c = MMAPRCouncil()
        # T169 — wide band: 0.05-0.99 → council runs
        r = c.score_uncertain(prog, [simple_pair, simple_pair], pixel_score=0.6)
        assert r["ran_council"] is True
        assert "verdict" in r
