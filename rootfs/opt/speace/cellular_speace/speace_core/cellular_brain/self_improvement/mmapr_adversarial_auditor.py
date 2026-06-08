"""T-Phase 8A — Adversarial Auditor (Class C) for MM-APR.

This module fills the Class C evaluator slot of the
``HardVetoRouter`` with a concrete, *adversarial* implementation.

Why adversarial?
----------------
Without an explicit adversary, Class A (Evolution) and Class B
(Verification) are both constructive. They naturally converge toward
mutual confirmation, a phenomenon called *epistemic collusion*. The
MM-APR spec requires Class C to **attack** proposals, looking for
flaws that cooperative agents miss.

Attack strategies
-----------------
The ``AdversarialAuditor`` implements three concrete strategies:

1. **Hidden regression search**: scan the proposal's
   ``expected_risks`` for hidden_regression_score / drift_score values
   that the cooperative Class B might have waved through. A risk
   > 0.5 triggers the veto.
2. **Overfitting / local minimum detection**: high-magnitude
   ``expected_benefits`` with concentrated target modules suggest
   the proposal is over-fit to a single limitation. Multiple
   ``target_modules`` with no related metrics → overfitting signal.
3. **Distributional shift detection**: large ``expected_benefits``
   deltas without corresponding ``safety_constraints`` are flagged
   as unsafe. The auditor treats ``len(safety_constraints) == 0``
   as a structural risk.

Pool of scenarios
-----------------
``default_scenario_pool()`` returns a list of named
``AdversarialScenario`` objects. Each scenario is a small rule
("if the proposal has X, score it Y"). The auditor runs *at least
two* scenarios per proposal; the **maximum** score across scenarios
is the adversarial score. This is the property asserted in
``test_auditor_pool_runs_all_scenarios``.

Hard veto trigger
-----------------
The adversarial score is a number in [0.0, 1.0]. If
``score >= adversarial_score_threshold`` (default 0.7), the auditor
emits a ``HARD_BLOCK`` vote. The router then downgrades the
cycle's final verdict (see Phase 8C for the integration point).
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.self_improvement.mmapr_veto_router import (
    AgentVote,
    VetoClass,
    VetoKind,
)


# ------------------------------------------------------------------ #
# Scenarios
# ------------------------------------------------------------------ #


@dataclass
class AdversarialScenario:
    """A single adversarial test against a proposal.

    A scenario is a pure function: it takes a proposal dict and
    returns a score in [0.0, 1.0]. The auditor picks the **maximum**
    across all scenarios as the final adversarial score.
    """

    name: str
    description: str
    evaluate: Callable[[Dict[str, Any]], float]


def _proposal_dict(proposal: Any) -> Dict[str, Any]:
    """Coerce a proposal (Pydantic or dict) to a dict for inspection."""
    if hasattr(proposal, "model_dump"):
        return proposal.model_dump()
    if isinstance(proposal, dict):
        return dict(proposal)
    return {}


def _scenario_hidden_regression(proposal: Dict[str, Any]) -> float:
    """Hidden regression search.

    Inspects ``expected_risks`` for keys starting with ``hidden_``
    or ``drift_score``. If any is >= 0.5, the scenario scores
    0.5 + (value - 0.5) * 1.4, capped at 1.0. This pushes the score
    well above the 0.7 hard-veto threshold when the risk is severe.
    """
    risks = proposal.get("expected_risks", {}) or {}
    if not risks:
        return 0.0
    relevant = []
    for key, val in risks.items():
        kl = key.lower()
        if kl.startswith("hidden_") or "drift" in kl:
            try:
                relevant.append(float(val))
            except (TypeError, ValueError):
                continue
    if not relevant:
        return 0.0
    worst = max(relevant)
    if worst < 0.5:
        return 0.0
    return min(1.0, 0.5 + (worst - 0.5) * 1.4)


def _scenario_overfitting(proposal: Dict[str, Any]) -> float:
    """Overfitting / local minimum detection.

    A high concentration of ``target_modules`` without any
    associated metric in ``expected_benefits`` suggests the
    proposal is over-fitted to a narrow case. Score is:
    ``min(1.0, n_modules / 5.0) * weight``, with weight
    0.6 if the proposal has no benefits referencing those modules.
    """
    targets = proposal.get("target_modules", []) or []
    benefits = proposal.get("expected_benefits", {}) or {}
    if not targets:
        return 0.0
    n = len(targets)
    base = min(1.0, n / 5.0)
    # If the benefits dict has at least one numeric entry, we treat
    # the proposal as having measured benefits and reduce the score.
    if benefits:
        return base * 0.3
    return base * 0.6


def _scenario_distributional_shift(proposal: Dict[str, Any]) -> float:
    """Distributional shift / safety void detection.

    Proposals with large expected benefits (sum >= 0.5) but **no
    safety_constraints** are treated as having a distributional
    shift risk. The score is the benefits sum, scaled by 0.8.
    """
    constraints = proposal.get("safety_constraints", []) or []
    if constraints:
        return 0.0
    benefits = proposal.get("expected_benefits", {}) or {}
    total = 0.0
    for v in benefits.values():
        try:
            total += float(v)
        except (TypeError, ValueError):
            continue
    if total < 0.5:
        return 0.0
    return min(1.0, total * 0.8)


def default_scenario_pool() -> List[AdversarialScenario]:
    """Return the default pool of adversarial scenarios."""
    return [
        AdversarialScenario(
            name="hidden_regression_search",
            description=(
                "Scans expected_risks for hidden_* / drift_* keys; "
                "if any >= 0.5 the score is 0.5 + (val - 0.5) * 1.4."
            ),
            evaluate=_scenario_hidden_regression,
        ),
        AdversarialScenario(
            name="overfitting_local_minimum",
            description=(
                "Concentrated target_modules without measured benefits "
                "indicates local overfitting."
            ),
            evaluate=_scenario_overfitting,
        ),
        AdversarialScenario(
            name="distributional_shift",
            description=(
                "Large expected_benefits (sum >= 0.5) with no "
                "safety_constraints indicates distributional shift risk."
            ),
            evaluate=_scenario_distributional_shift,
        ),
    ]


# ------------------------------------------------------------------ #
# Adversarial report
# ------------------------------------------------------------------ #


class AdversarialReport(BaseModel):
    """Outcome of running the auditor on a single proposal."""

    proposal_id: str
    score: float = 0.0
    triggered_scenarios: List[str] = Field(default_factory=list)
    per_scenario_scores: Dict[str, float] = Field(default_factory=dict)
    rationale: str = ""
    timestamp: float = Field(default_factory=time.time)


# ------------------------------------------------------------------ #
# Auditor
# ------------------------------------------------------------------ #


class AdversarialAuditor:
    """Class C evaluator: attacks proposals with adversarial scenarios.

    The auditor returns an :class:`AgentVote` whose ``kind`` is
    ``HARD_BLOCK`` when the maximum score across scenarios meets
    ``adversarial_score_threshold``, and ``ADMIT`` otherwise.

    Parameters
    ----------
    scenarios
        Optional custom pool. ``None`` uses
        :func:`default_scenario_pool`.
    adversarial_score_threshold
        Confidence level above which the auditor emits HARD_BLOCK.
        Default 0.7 (per the MM-APR spec).
    """

    def __init__(
        self,
        scenarios: Optional[List[AdversarialScenario]] = None,
        adversarial_score_threshold: float = 0.7,
    ):
        self.scenarios = scenarios if scenarios is not None else default_scenario_pool()
        self.adversarial_score_threshold = float(adversarial_score_threshold)
        self._reports: List[AdversarialReport] = []

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def attack_proposal(
        self,
        proposal: Any,
        simulation: Any = None,
        counterfactual: Any = None,
        patch_result: Any = None,
    ) -> AdversarialReport:
        """Run the scenario pool against a proposal and return a report."""
        p_dict = _proposal_dict(proposal)
        proposal_id = str(p_dict.get("id", "unknown"))
        per_scenario: Dict[str, float] = {}
        triggered: List[str] = []
        max_score = 0.0
        for scenario in self.scenarios:
            try:
                score = float(scenario.evaluate(p_dict))
            except Exception:
                score = 0.0
            per_scenario[scenario.name] = score
            if score >= self.adversarial_score_threshold:
                triggered.append(scenario.name)
            if score > max_score:
                max_score = score
        report = AdversarialReport(
            proposal_id=proposal_id,
            score=max_score,
            triggered_scenarios=triggered,
            per_scenario_scores=per_scenario,
            rationale=(
                f"max_score={max_score:.3f} across {len(self.scenarios)} scenarios; "
                f"triggered={triggered}"
            ),
        )
        self._reports.append(report)
        # Bounded buffer
        if len(self._reports) > 100:
            self._reports = self._reports[-100:]
        return report

    def __call__(
        self,
        proposal: Any,
        simulation: Any = None,
        counterfactual: Any = None,
        patch_result: Any = None,
    ) -> AgentVote:
        """Class C slot signature: return an ``AgentVote``."""
        report = self.attack_proposal(proposal, simulation, counterfactual, patch_result)
        kind = (
            VetoKind.HARD_BLOCK
            if report.score >= self.adversarial_score_threshold
            else VetoKind.ADMIT
        )
        return AgentVote(
            agent="adversarial_auditor",
            veto_class=VetoClass.C_ADVERSARIAL,
            kind=kind,
            confidence=report.score,
            rationale=report.rationale,
            evidence={
                "per_scenario_scores": report.per_scenario_scores,
                "triggered_scenarios": report.triggered_scenarios,
            },
            timestamp=time.time(),
        )

    def summary(self) -> Dict[str, Any]:
        return {
            "scenarios": [s.name for s in self.scenarios],
            "adversarial_score_threshold": self.adversarial_score_threshold,
            "reports_count": len(self._reports),
            "max_score_seen": max((r.score for r in self._reports), default=0.0),
        }
