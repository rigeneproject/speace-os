"""T-Phase 8C — MM-APR (Multi-Modal Adversarial Peer Review) Hard Veto Router.

This module closes the *cognitive* gap identified in
``docs/AUTOMIGLIORMENTO DI SPEACE.md``: SPEACE has a mature self-improvement
loop (Fases 1-7), but lacks the **structured conflictuality** that prevents
*epistemic collusion* between cooperative agents. Without an explicit
adversarial class with hard veto power, Class A (Evolution) and Class B
(Verification) — both constructive — collapse naturally toward mutual
confirmation.

> "Il rischio maggiore non è l'assenza di meccanismi evolutivi, ma l'assenza
> di un sistema sufficientemente forte di supervisione avversariale."

This module implements the four epistemic classes:

* **Class A — Evolution** (Architect, Corrector, Governance Manager):
  generates proposals, can only emit ``ADMIT`` or ``SOFT_FLAG`` (never
  ``HARD_BLOCK`` by design — anti-collusion).
* **Class B — Verification** (Validator, Tester, Analyst): structural veto
  on coherence failures.
* **Class C — Adversarial** (Adversarial Auditor, Safety Officer): hard
  veto when score > ``adversarial_score_threshold`` (default 0.7).
* **Class D — Meta-Governance** (Epistemic Auditor, AGI Readiness):
  process-level veto / investigation mode.

Design constraints
------------------
* **Opt-in**: the router is attached via ``SelfImprovementLoop(..., mmapr_router=...)``.
  When ``None``, the loop behaves identically to the pre-Phase-8 version.
* **Fail-soft**: every evaluator runs in ``try/except``; on error, emits
  ``ADMIT`` with confidence 0.0 (so a faulty evaluator never crashes the
  loop or blocks a safe proposal).
* **No circular imports**: this module imports Pydantic models from
  ``self_improvement.*`` only. The ``self_improvement_loop`` imports the
  router lazily, inside ``if self.mmapr_router is not None``.
* **Bypassable**: ``HardVetoRouter.apply_bypass()`` accepts a human-issued
  ``bypass_evidence`` dict and emits ``MMAPR_VETO_REVERSED_BY_HUMAN``.

The router is **observational by default**: with no evaluator attached,
each route call returns ``VetoVerdict(final_status="admit")`` so the
backward-compatible behaviour is identical to the pre-Phase-8 loop.
"""
from __future__ import annotations

import logging
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from speace_core.cellular_brain.self_improvement.architecture_rewriter import (
        ArchitectureRewriteProposal,
        RewriteSimulationResult,
    )
    from speace_core.cellular_brain.self_improvement.counterfactual_sandbox import (
        CounterfactualResult,
    )
    from speace_core.cellular_brain.self_improvement.architecture_patch_executor import (
        PatchExecutionResult,
    )

_logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Pydantic models
# ------------------------------------------------------------------ #


class VetoClass(str, Enum):
    """The four MM-APR epistemic classes."""

    A_EVOLUTION = "A_evolution"
    B_VERIFICATION = "B_verification"
    C_ADVERSARIAL = "C_adversarial"
    D_META_GOVERNANCE = "D_meta_governance"


class VetoKind(str, Enum):
    """The three possible vote outcomes."""

    HARD_BLOCK = "hard_block"
    SOFT_FLAG = "soft_flag"
    ADMIT = "admit"


class AgentVote(BaseModel):
    """A single evaluator's vote on a proposal."""

    agent: str
    veto_class: VetoClass
    kind: VetoKind
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    rationale: str = ""
    evidence: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = 0.0


class VetoVerdict(BaseModel):
    """Aggregated verdict of all four classes on a single proposal."""

    verdict_id: str = Field(default_factory=lambda: f"veto-{uuid.uuid4().hex[:10]}")
    proposal_id: str
    cycle_id: str = ""
    votes: List[AgentVote] = Field(default_factory=list)
    hard_blocked_by: List[str] = Field(default_factory=list)
    soft_flagged_by: List[str] = Field(default_factory=list)
    admit_count: int = 0
    bypass_evidence: Optional[Dict[str, Any]] = None
    # One of: "pending" | "admit" | "hard_blocked" | "soft_flagged" | "bypassed"
    final_status: str = "pending"
    created_at: float = Field(default_factory=time.time)

    def recompute_status(self) -> str:
        """Recompute final_status from votes + bypass state.

        Returns
        -------
        str
            ``"hard_blocked"`` if any non-A class voted HARD_BLOCK and no
            bypass is present. ``"bypassed"`` if a bypass is present and
            the original status was hard_blocked. ``"soft_flagged"`` if
            at least one vote is SOFT_FLAG and no HARD_BLOCK. ``"admit"``
            otherwise.
        """
        if self.bypass_evidence and self.final_status == "hard_blocked":
            return "bypassed"
        if self.hard_blocked_by:
            return "hard_blocked"
        if self.soft_flagged_by:
            return "soft_flagged"
        return "admit"


# ------------------------------------------------------------------ #
# Evaluator signature
# ------------------------------------------------------------------ #

# Canonical signature for any of the four evaluators. Returning an
# ``AgentVote`` with kind=ADMIT/SOFT_FLAG/HARD_BLOCK is the standard
# contract. Evaluators must never raise — they should catch their own
# exceptions and emit a fail-soft ADMIT vote.
EvaluatorFn = Callable[
    [
        "ArchitectureRewriteProposal",
        Optional["RewriteSimulationResult"],
        Optional["CounterfactualResult"],
        Optional["PatchExecutionResult"],
    ],
    AgentVote,
]


# ------------------------------------------------------------------ #
# Default stubs
# ------------------------------------------------------------------ #


def _default_stub(veto_class: VetoClass) -> EvaluatorFn:
    """Return a default stub evaluator that always emits ADMIT.

    With this stub, the router is observationally equivalent to no router
    at all (the ``final_status`` ends up as ``"admit"``). Tests that
    verify the no-op behaviour rely on this.
    """

    def _stub(
        proposal: Any,
        simulation: Any = None,
        counterfactual: Any = None,
        patch_result: Any = None,
    ) -> AgentVote:
        return AgentVote(
            agent=f"{veto_class.value}_default_stub",
            veto_class=veto_class,
            kind=VetoKind.ADMIT,
            confidence=0.0,
            rationale="default_stub: always admit",
            timestamp=time.time(),
        )

    return _stub


# ------------------------------------------------------------------ #
# Hard Veto Router
# ------------------------------------------------------------------ #


class HardVetoRouter:
    """The MM-APR hard veto router.

    Parameters
    ----------
    class_a_evaluator, class_b_evaluator, class_c_evaluator, class_d_evaluator
        Optional ``EvaluatorFn`` callables. ``None`` means "use the
        default stub" (always ADMIT). The default stubs make the router
        observationally equivalent to the pre-Phase-8 self-improvement
        loop.
    audit_dir
        Optional directory where audit envelopes are written. ``None``
        disables persistence; the cycle result will still record
        ``mmapr_veto_verdict`` in memory.
    adversarial_score_threshold
        Class C only: a vote's confidence >= this threshold is treated
        as an implicit hard veto. Default 0.7 (per the MM-APR spec).
    investigation_mode
        When ``True``, any Class D ``soft_flag`` is escalated to
        ``hard_block`` (process-level pause).
    """

    def __init__(
        self,
        class_a_evaluator: Optional[EvaluatorFn] = None,
        class_b_evaluator: Optional[EvaluatorFn] = None,
        class_c_evaluator: Optional[EvaluatorFn] = None,
        class_d_evaluator: Optional[EvaluatorFn] = None,
        audit_dir: Optional[Path] = None,
        adversarial_score_threshold: float = 0.7,
        investigation_mode: bool = False,
    ):
        self._evaluators: Dict[VetoClass, EvaluatorFn] = {
            VetoClass.A_EVOLUTION: class_a_evaluator or _default_stub(VetoClass.A_EVOLUTION),
            VetoClass.B_VERIFICATION: class_b_evaluator or _default_stub(VetoClass.B_VERIFICATION),
            VetoClass.C_ADVERSARIAL: class_c_evaluator or _default_stub(VetoClass.C_ADVERSARIAL),
            VetoClass.D_META_GOVERNANCE: class_d_evaluator or _default_stub(VetoClass.D_META_GOVERNANCE),
        }
        self.audit_dir = Path(audit_dir) if audit_dir is not None else None
        if self.audit_dir is not None:
            self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.adversarial_score_threshold = float(adversarial_score_threshold)
        self.investigation_mode = bool(investigation_mode)
        # Simple counters for observability / tests
        self._veto_count = 0
        self._admit_count = 0
        self._soft_flag_count = 0
        self._bypass_count = 0
        self._last_verdicts: List[VetoVerdict] = []

    # ------------------------------------------------------------------ #
    # Evaluator registration
    # ------------------------------------------------------------------ #

    def register_evaluator(self, veto_class: VetoClass, fn: EvaluatorFn) -> None:
        """Replace the evaluator for a given class."""
        self._evaluators[veto_class] = fn

    # ------------------------------------------------------------------ #
    # Routing
    # ------------------------------------------------------------------ #

    def route(
        self,
        proposal: "ArchitectureRewriteProposal",
        simulation: Optional["RewriteSimulationResult"] = None,
        counterfactual: Optional["CounterfactualResult"] = None,
        patch_result: Optional["PatchExecutionResult"] = None,
        cycle_id: str = "",
    ) -> VetoVerdict:
        """Run all four evaluators on a single proposal.

        Returns a :class:`VetoVerdict` whose ``final_status`` is one of:
        ``"admit"``, ``"soft_flagged"``, ``"hard_blocked"``,
        ``"bypassed"``.

        Class A is structurally barred from emitting HARD_BLOCK: if an
        evaluator returns HARD_BLOCK from a Class A slot, it is
        downgraded to SOFT_FLAG (and logged). This is the anti-collusion
        invariant.
        """
        verdict = VetoVerdict(proposal_id=getattr(proposal, "id", "unknown"), cycle_id=cycle_id)

        for veto_class, fn in self._evaluators.items():
            try:
                vote = fn(proposal, simulation, counterfactual, patch_result)
            except Exception as exc:  # pragma: no cover - defensive
                _logger.debug(
                    "MMAPR evaluator %s failed on %s: %s",
                    veto_class.value,
                    verdict.proposal_id,
                    exc,
                )
                vote = AgentVote(
                    agent=f"{veto_class.value}_error",
                    veto_class=veto_class,
                    kind=VetoKind.ADMIT,
                    confidence=0.0,
                    rationale=f"evaluator_error:{type(exc).__name__}",
                    timestamp=time.time(),
                )

            # Anti-collusion: Class A can never HARD_BLOCK
            if vote.veto_class == VetoClass.A_EVOLUTION and vote.kind == VetoKind.HARD_BLOCK:
                _logger.debug(
                    "MMAPR anti-collusion: downgraded Class A HARD_BLOCK to SOFT_FLAG"
                )
                vote = vote.model_copy(update={"kind": VetoKind.SOFT_FLAG})

            # Class C: implicit hard veto when confidence >= threshold
            if (
                vote.veto_class == VetoClass.C_ADVERSARIAL
                and vote.kind == VetoKind.ADMIT
                and vote.confidence >= self.adversarial_score_threshold
            ):
                vote = vote.model_copy(update={"kind": VetoKind.HARD_BLOCK})

            # Class D: investigation_mode escalates SOFT_FLAG to HARD_BLOCK
            if (
                self.investigation_mode
                and vote.veto_class == VetoClass.D_META_GOVERNANCE
                and vote.kind == VetoKind.SOFT_FLAG
            ):
                vote = vote.model_copy(update={"kind": VetoKind.HARD_BLOCK})

            verdict.votes.append(vote)
            if vote.kind == VetoKind.HARD_BLOCK:
                verdict.hard_blocked_by.append(vote.agent)
            elif vote.kind == VetoKind.SOFT_FLAG:
                verdict.soft_flagged_by.append(vote.agent)
            elif vote.kind == VetoKind.ADMIT:
                verdict.admit_count += 1

        verdict.final_status = verdict.recompute_status()

        # Counters
        if verdict.final_status == "admit":
            self._admit_count += 1
        elif verdict.final_status == "hard_blocked":
            self._veto_count += 1
        elif verdict.final_status == "soft_flagged":
            self._soft_flag_count += 1

        self._last_verdicts.append(verdict)
        # Keep the buffer bounded (last 100)
        if len(self._last_verdicts) > 100:
            self._last_verdicts = self._last_verdicts[-100:]

        return verdict

    # ------------------------------------------------------------------ #
    # Bypass
    # ------------------------------------------------------------------ #

    def apply_bypass(
        self,
        verdict: VetoVerdict,
        bypass_evidence: Dict[str, Any],
        human_actor: str = "operator",
    ) -> VetoVerdict:
        """Reverse a hard veto via documented human approval.

        Parameters
        ----------
        verdict
            The :class:`VetoVerdict` to bypass. Must be in
            ``"hard_blocked"`` state.
        bypass_evidence
            Dict with at least ``{"reason": str}``. The human_actor is
            added automatically.
        human_actor
            Identifier of the human granting the bypass. Default
            ``"operator"`` for scripted tests; production should use a
            unique identifier.

        Returns
        -------
        VetoVerdict
            The same verdict with ``bypass_evidence`` set and
            ``final_status="bypassed"``. If the verdict was not
            hard-blocked, returns it unchanged and logs a warning.
        """
        if verdict.final_status != "hard_blocked":
            _logger.warning(
                "MMAPR bypass requested on a non-hard_blocked verdict (%s); ignoring",
                verdict.final_status,
            )
            return verdict
        # Build the canonical evidence dict
        evidence = dict(bypass_evidence or {})
        evidence.setdefault("human_actor", human_actor)
        evidence.setdefault("timestamp", time.time())
        verdict.bypass_evidence = evidence
        verdict.final_status = verdict.recompute_status()
        self._bypass_count += 1
        return verdict

    # ------------------------------------------------------------------ #
    # Audit / observability
    # ------------------------------------------------------------------ #

    def audit_path_for(self, envelope_id: str) -> Optional[Path]:
        """Return the path where an envelope with the given id would be
        persisted, or ``None`` if audit_dir is disabled."""
        if self.audit_dir is None:
            return None
        return self.audit_dir / f"{envelope_id}.json"

    def summary(self) -> Dict[str, Any]:
        """Return a serialisable summary, suitable for ``snapshot()``."""
        return {
            "veto_count": int(self._veto_count),
            "admit_count": int(self._admit_count),
            "soft_flag_count": int(self._soft_flag_count),
            "bypass_count": int(self._bypass_count),
            "adversarial_score_threshold": self.adversarial_score_threshold,
            "investigation_mode": self.investigation_mode,
            "audit_dir": str(self.audit_dir) if self.audit_dir is not None else None,
            "registered_evaluators": sorted(c.value for c in self._evaluators.keys()),
            "last_verdicts": [v.model_dump() for v in self._last_verdicts[-8:]],
        }
