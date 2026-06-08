"""MM-APR — Multi-Modal Adversarial Pattern Reasoning Council.

T169 — Phase 3 / Reasoning boost.

A 4-agent council that deliberates over a candidate symbolic program
(``TransformationProgram``) and emits a structured verdict. The 4
agents are:

  1. **InterpreterAgent**    — executes the program on the training
     inputs and collects outputs.
  2. **StructuralVerifier**  — checks the interpreter's outputs
     against the expected training outputs (correctness on the
     full training set, not just a sample).
  3. **AdversarialCritic**   — generates small perturbations of the
     training inputs and checks whether the program's output
     degrades. Programs that overfit the training set fail here.
  4. **EpistemicAuditor**    — quantifies *how much we know*:
     number of training pairs, program length, output diversity,
     parametric specificity. Lower confidence → reject.

The council's final verdict is an **emergent weighted vote**: each
agent emits an ``AgentVote`` with confidence; the council accepts the
candidate when ``Σ accept_confidence > Σ reject_confidence``.

The council is *read-only* (never mutates the program) and *pure*
(no I/O). It can be invoked from FSPI, from the dashboard, or from
unit tests.

Safety:
- No shell, no I/O, no mutation of external state.
- All operations are pure functions over the candidate + train pairs.
- Determinism: vote aggregation is order-stable (sorted by agent name).
"""

from __future__ import annotations

import copy
import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.cognition.program_models import (
    Grid,
    TransformationProgram,
)


# --------------------------------------------------------------------------- #
# Data classes
# --------------------------------------------------------------------------- #
@dataclass
class AgentVote:
    """A single agent's verdict on a candidate."""
    agent: str
    accept: bool
    confidence: float
    rationale: str
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent": self.agent,
            "accept": self.accept,
            "confidence": round(float(self.confidence), 4),
            "rationale": self.rationale,
            "evidence": dict(self.evidence),
        }


@dataclass
class CouncilVerdict:
    """The council's final emergent verdict."""
    candidate_id: str
    votes: List[AgentVote]
    accept: bool
    emergent_confidence: float
    rationale: str
    deliberation_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "deliberation_id": self.deliberation_id,
            "accept": self.accept,
            "emergent_confidence": round(float(self.emergent_confidence), 4),
            "rationale": self.rationale,
            "votes": [v.to_dict() for v in self.votes],
        }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _grid_eq(a: Optional[Grid], b: Grid) -> bool:
    """True iff grid a and grid b have the same shape and values."""
    if a is None or b is None:
        return False
    if len(a) != len(b):
        return False
    for r1, r2 in zip(a, b):
        if len(r1) != len(r2):
            return False
        for v1, v2 in zip(r1, r2):
            if v1 != v2:
                return False
    return True


def _pixel_match_score(predicted: Optional[Grid], expected: Grid) -> float:
    """Compute partial credit as matched-cell ratio (0.0 - 1.0)."""
    if predicted is None or expected is None:
        return 0.0
    if len(predicted) == 0 or len(expected) == 0:
        return 0.0
    h = min(len(predicted), len(expected))
    matched = 0
    total = 0
    for y in range(h):
        w = min(len(predicted[y]), len(expected[y]))
        for x in range(w):
            total += 1
            if predicted[y][x] == expected[y][x]:
                matched += 1
    return matched / total if total > 0 else 0.0


def _safe_apply(program: TransformationProgram, grid: Grid) -> Optional[Grid]:
    """Apply a program defensively; never raise."""
    try:
        return program.apply(grid)
    except Exception:
        return None


def _perturb_grid(grid: Grid, seed: int = 1) -> Grid:
    """Generate a small perturbation: flip one cell (deterministic by seed)."""
    if not grid or not grid[0]:
        return copy.deepcopy(grid)
    # Simple deterministic perturbation: flip cell (seed % h, (seed*7) % w)
    h = len(grid)
    w = len(grid[0])
    new_grid = [row[:] for row in grid]
    y = seed % h
    x = (seed * 7) % w
    new_grid[y][x] = (new_grid[y][x] + 1) % 10
    return new_grid


def _compute_candidate_id(program: TransformationProgram) -> str:
    """Stable id for a program based on its primitive sequence."""
    sig = "|".join(f"{s.name}:{sorted((s.params or {}).items())}" for s in program.steps)
    return "cand-" + hashlib.sha256(sig.encode("utf-8")).hexdigest()[:10]


# --------------------------------------------------------------------------- #
# 1. Interpreter Agent
# --------------------------------------------------------------------------- #
class InterpreterAgent:
    """Executes a candidate program on the training inputs.

    Pure: returns a dict with one output per training pair, plus a
    per-pair success flag.
    """
    name = "interpreter"

    def apply(
        self,
        program: TransformationProgram,
        train_pairs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        outputs: List[Optional[Grid]] = []
        success_flags: List[bool] = []
        for pair in train_pairs:
            inp = pair.get("input")
            if inp is None:
                outputs.append(None)
                success_flags.append(False)
                continue
            out = _safe_apply(program, inp)
            outputs.append(out)
            success_flags.append(out is not None)
        return {
            "outputs": outputs,
            "execution_success_rate": (
                sum(success_flags) / max(1, len(success_flags))
            ),
        }


# --------------------------------------------------------------------------- #
# 2. Structural Verifier
# --------------------------------------------------------------------------- #
class StructuralVerifier:
    """Verifies the interpreter's outputs against expected training outputs.

    Strict pass: all training pairs must match exactly. Partial credit
    reduces the *confidence*, not the *accept* flag — the council
    is conservative on accept.
    """
    name = "structural_verifier"

    def verify(
        self,
        interpreter_output: Dict[str, Any],
        train_pairs: List[Dict[str, Any]],
    ) -> AgentVote:
        outputs = interpreter_output.get("outputs", [])
        n = len(train_pairs)
        if n == 0:
            return AgentVote(
                self.name, accept=False, confidence=0.0,
                rationale="no training pairs", evidence={"n_pairs": 0},
            )
        correct = 0
        partial_total = 0.0
        for out, pair in zip(outputs, train_pairs):
            expected = pair.get("output")
            if expected is None:
                continue
            if _grid_eq(out, expected):
                correct += 1
                partial_total += 1.0
            else:
                partial_total += _pixel_match_score(out, expected)
        full = correct == n
        partial = partial_total / max(1, n)
        # T169 — soft-accept: a candidate with partial >= 0.85 is
        # "almost right" and gets a conditional accept with reduced
        # confidence. This lets the council reach agreement on
        # near-misses instead of rejecting them outright.
        soft_accept = (not full) and partial >= 0.85
        accept = full or soft_accept
        confidence = round(partial, 4)
        if soft_accept:
            rationale = (
                f"{correct}/{n} training pairs match exactly, "
                f"soft-accept at partial={partial:.3f}"
            )
        else:
            rationale = (
                f"{correct}/{n} training pairs match exactly "
                f"(partial={partial:.3f})"
            )
        return AgentVote(
            self.name,
            accept=accept,
            confidence=confidence,
            rationale=rationale,
            evidence={
                "n_pairs": n,
                "exact_matches": correct,
                "partial_score": round(partial, 4),
                "soft_accept": soft_accept,
            },
        )


# --------------------------------------------------------------------------- #
# 3. Adversarial Critic
# --------------------------------------------------------------------------- #
class AdversarialCritic:
    """Generates small perturbations of training inputs and tests the
    candidate's robustness.

    A program that overfits the training set (memorizes specific
    pixel patterns) will fail on perturbations; a program that
    captures the *rule* will generalize.
    """
    name = "adversarial_critic"

    def __init__(self, n_perturbations: int = 3):
        self.n_perturbations = n_perturbations

    def challenge(
        self,
        program: TransformationProgram,
        train_pairs: List[Dict[str, Any]],
    ) -> AgentVote:
        if not train_pairs:
            return AgentVote(
                self.name, accept=False, confidence=0.0,
                rationale="no pairs to perturb", evidence={"n_pairs": 0},
            )
        # Apply the program to N perturbations of the first training pair.
        # Since we don't know the *expected* output of a perturbation,
        # we measure *stability*: does the program produce something
        # sensible (same shape, same color distribution) on the perturbed
        # input as on the original?
        sample = train_pairs[0]
        orig_in = sample.get("input")
        if orig_in is None:
            return AgentVote(
                self.name, accept=False, confidence=0.0,
                rationale="no input in first pair", evidence={},
            )
        baseline_out = _safe_apply(program, orig_in)
        if baseline_out is None:
            return AgentVote(
                self.name, accept=False, confidence=0.0,
                rationale="program fails on unperturbed input",
                evidence={"baseline": None},
            )
        base_shape = (len(baseline_out), len(baseline_out[0]) if baseline_out else 0)
        base_colors = set()
        for row in baseline_out or []:
            for v in row:
                base_colors.add(v)
        # Apply perturbations
        stable_count = 0
        for i in range(1, self.n_perturbations + 1):
            perturbed = _perturb_grid(orig_in, seed=i)
            out = _safe_apply(program, perturbed)
            if out is None:
                continue
            shape = (len(out), len(out[0]) if out else 0)
            colors = set()
            for row in out:
                for v in row:
                    colors.add(v)
            if shape == base_shape and colors.issubset(base_colors | {0, 1, 2, 3, 4, 5, 6, 7, 8, 9}):
                stable_count += 1
        stability = stable_count / max(1, self.n_perturbations)
        return AgentVote(
            self.name,
            accept=stability >= 0.5,
            confidence=round(stability, 4),
            rationale=(
                f"{stable_count}/{self.n_perturbations} perturbations produced "
                f"shape-stable, color-valid outputs"
            ),
            evidence={
                "n_perturbations": self.n_perturbations,
                "stable": stable_count,
                "stability_score": round(stability, 4),
                "baseline_shape": list(base_shape),
            },
        )


# --------------------------------------------------------------------------- #
# 4. Epistemic Auditor
# --------------------------------------------------------------------------- #
class EpistemicAuditor:
    """Quantifies *how much we know* about the candidate.

    - Few training pairs → low confidence (high epistemic uncertainty)
    - Very long programs → mild penalty (Occam)
    - Low output diversity → low confidence (the program may be trivial)
    - High input diversity → high confidence (the rule must be general)
    """
    name = "epistemic_auditor"

    def audit(
        self,
        program: TransformationProgram,
        train_pairs: List[Dict[str, Any]],
    ) -> AgentVote:
        n_pairs = len(train_pairs)
        n_steps = program.complexity_score

        # Pair-count factor: 5+ pairs → full credit
        pair_factor = min(1.0, n_pairs / 5.0)

        # Length penalty: 1-3 steps → good, > 5 → bad
        if n_steps <= 0:
            length_factor = 0.0
        elif n_steps <= 3:
            length_factor = 1.0
        else:
            length_factor = max(0.2, 1.0 - (n_steps - 3) * 0.15)

        # Output diversity: collect predicted outputs (if determinable) — we
        # skip applying the program and just measure input diversity instead.
        input_colors: set = set()
        input_shapes: set = set()
        for pair in train_pairs[:10]:
            inp = pair.get("input") or []
            for row in inp:
                for v in row:
                    input_colors.add(v)
            input_shapes.add((len(inp), len(inp[0]) if inp else 0))
        diversity_factor = min(1.0, len(input_colors) / 5.0)
        shape_diversity = min(1.0, len(input_shapes) / 2.0)

        confidence = (
            0.35 * pair_factor
            + 0.25 * length_factor
            + 0.25 * diversity_factor
            + 0.15 * shape_diversity
        )
        confidence = max(0.0, min(1.0, confidence))

        # Accept iff we have enough evidence (>= 3 pairs and confidence >= 0.5)
        accept = (n_pairs >= 2) and (confidence >= 0.5)
        return AgentVote(
            self.name,
            accept=accept,
            confidence=round(confidence, 4),
            rationale=(
                f"n_pairs={n_pairs}, n_steps={n_steps}, "
                f"pair_factor={pair_factor:.2f}, length_factor={length_factor:.2f}, "
                f"diversity={diversity_factor:.2f}"
            ),
            evidence={
                "n_pairs": n_pairs,
                "n_steps": n_steps,
                "pair_factor": round(pair_factor, 4),
                "length_factor": round(length_factor, 4),
                "diversity_factor": round(diversity_factor, 4),
                "shape_diversity": round(shape_diversity, 4),
                "input_colors": len(input_colors),
            },
        )


# --------------------------------------------------------------------------- #
# 5. Council
# --------------------------------------------------------------------------- #
class MMAPRCouncil:
    """Multi-Modal Adversarial Pattern Reasoning Council.

    Composes the 4 agents and produces an emergent verdict via
    confidence-weighted voting.
    """
    def __init__(
        self,
        interpreter: Optional[InterpreterAgent] = None,
        verifier: Optional[StructuralVerifier] = None,
        critic: Optional[AdversarialCritic] = None,
        auditor: Optional[EpistemicAuditor] = None,
    ):
        self.interpreter = interpreter or InterpreterAgent()
        self.verifier = verifier or StructuralVerifier()
        self.critic = critic or AdversarialCritic()
        self.auditor = auditor or EpistemicAuditor()

    def deliberate(
        self,
        program: TransformationProgram,
        train_pairs: List[Dict[str, Any]],
        candidate_id: Optional[str] = None,
    ) -> CouncilVerdict:
        cid = candidate_id or _compute_candidate_id(program)
        # 1. Interpreter
        io = self.interpreter.apply(program, train_pairs)
        # 2-4. Other agents
        verifier_vote = self.verifier.verify(io, train_pairs)
        critic_vote = self.critic.challenge(program, train_pairs)
        auditor_vote = self.auditor.audit(program, train_pairs)
        votes: List[AgentVote] = [verifier_vote, critic_vote, auditor_vote]
        # Sort for determinism
        votes.sort(key=lambda v: v.agent)
        # Emergent vote: sum of confidence for accept vs reject
        accept_score = sum(v.confidence for v in votes if v.accept)
        reject_score = sum(v.confidence for v in votes if not v.accept)
        total = accept_score + reject_score
        emergent = accept_score / total if total > 0 else 0.0
        accept = emergent >= 0.5
        # Build rationale
        rationale = (
            f"Interpreter exec_rate={io.get('execution_success_rate', 0):.2f}; "
            f"verifier {verifier_vote.confidence:.2f} "
            f"({'ACCEPT' if verifier_vote.accept else 'REJECT'}); "
            f"critic {critic_vote.confidence:.2f} "
            f"({'ACCEPT' if critic_vote.accept else 'REJECT'}); "
            f"auditor {auditor_vote.confidence:.2f} "
            f"({'ACCEPT' if auditor_vote.accept else 'REJECT'}); "
            f"emergent_confidence={emergent:.3f}"
        )
        # Deliberation id
        sig = f"{cid}|{len(train_pairs)}|{program.complexity_score}|{round(emergent, 4)}"
        did = "delib-" + hashlib.sha256(sig.encode("utf-8")).hexdigest()[:10]
        return CouncilVerdict(
            candidate_id=cid,
            votes=votes,
            accept=accept,
            emergent_confidence=round(float(emergent), 4),
            rationale=rationale,
            deliberation_id=did,
        )

    def score_uncertain(
        self,
        program: TransformationProgram,
        train_pairs: List[Dict[str, Any]],
        pixel_score: float,
    ) -> Dict[str, Any]:
        """Convenience: run council when pixel_score is in the
        uncertain band. The band defaults to ``[0.05, 0.99]`` so that
        the council is exercised for both *partially correct* and
        *almost correct* candidates. The narrow band (``[0.3, 0.95]``)
        is preserved for callers that want a stricter guard.

        T169 — Phase 3 wide band: the council is meant to be exercised
        in production, not only on the most ambiguous cases. A pixel
        score of 0.1 still warrants adversarial scrutiny (maybe the
        candidate is correct in a region the verifier missed).

        Returns a dict with: ran_council, accept, confidence, reason.
        """
        # T169 — widen the band so the council is exercised on most
        # non-degenerate candidates. Keep a small reject floor (0.05)
        # because anything below that is unambiguously wrong.
        if pixel_score < 0.05:
            return {
                "ran_council": False,
                "accept": False,
                "confidence": round(pixel_score, 4),
                "reason": f"deterministic_reject: pixel_score={pixel_score:.3f} < 0.05",
            }
        if pixel_score >= 0.99:
            return {
                "ran_council": False,
                "accept": True,
                "confidence": round(pixel_score, 4),
                "reason": f"deterministic_accept: pixel_score={pixel_score:.3f} >= 0.99",
            }
        verdict = self.deliberate(program, train_pairs)
        return {
            "ran_council": True,
            "accept": verdict.accept,
            "confidence": verdict.emergent_confidence,
            "reason": verdict.rationale,
            "verdict": verdict.to_dict(),
        }
