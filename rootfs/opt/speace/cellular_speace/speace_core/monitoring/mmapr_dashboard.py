"""T-Phase 9 — MM-APR Supervision Dashboard.

This module builds a *serialisable* report describing the current
state of the MM-APR subsystem. It is the supervision view described in
``docs/AUTOMIGLIORMENTO DI SPEACE.md`` (lines 396-418 of that document):

* Current Phase, Iteration, Uptime
* Last Proposal + Agent Verdicts
* Fitness Trend (placeholder — real fitness lives in the long-horizon
  audit, which is wired in later phases)
* Memory status counts (STABLE / PROBATIONARY / DEPRECATED)
* Next Governance hint
* ASCII rendering for human inspection
* Markdown rendering for inclusion in CI artifacts

The dashboard is **observational** — it never mutates the underlying
state. It reads from:

* a :class:`HardVetoRouter` instance (Phase 8C)
* an :class:`EvolutionaryMemoryGovernor` instance
* a :class:`SelfImprovementRuntimeHook` instance (for the recent-cycle
  view)

All inputs are optional: the dashboard degrades gracefully when a
component is missing.
"""
from __future__ import annotations

import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------ #
# Pydantic models
# ------------------------------------------------------------------ #


class DashboardVetoDistribution(BaseModel):
    """How many vetoes were cast by each epistemic class."""

    class_a: int = 0
    class_b: int = 0
    class_c: int = 0
    class_d: int = 0
    total: int = 0


class DashboardMemoryCounts(BaseModel):
    """Counts of records per status in the evolutionary memory store."""

    stable: int = 0
    probationary: int = 0
    deprecated: int = 0
    forgotten: int = 0
    quarantined: int = 0
    volatile: int = 0
    experimental: int = 0
    total: int = 0


class DashboardFitnessTrend(BaseModel):
    """Last-N fitness samples (placeholder for the long-horizon audit)."""

    samples: List[float] = Field(default_factory=list)
    delta: float = 0.0
    trend: str = "stable"  # "stable" | "improving" | "degrading"


class DashboardReport(BaseModel):
    """Top-level supervision report."""

    generated_at: float = Field(default_factory=time.time)
    iteration: int = 0
    uptime_seconds: float = 0.0
    last_proposal: Optional[Dict[str, Any]] = None
    agent_verdicts: DashboardVetoDistribution = Field(default_factory=DashboardVetoDistribution)
    fitness_trend: DashboardFitnessTrend = Field(default_factory=DashboardFitnessTrend)
    memory_counts: DashboardMemoryCounts = Field(default_factory=DashboardMemoryCounts)
    cycle_count: int = 0
    veto_rate: float = 0.0
    rollback_rate: float = 0.0
    next_governance_in_seconds: float = 0.0
    health: str = "ok"  # "ok" | "warning" | "critical"

    # ------------------------------------------------------------------ #
    # Renderings
    # ------------------------------------------------------------------ #

    def to_ascii(self) -> str:
        """Return a human-readable ASCII rendering, mirroring the
        dashboard mock in the design doc. All non-ASCII characters
        are replaced with ASCII fallbacks so the output is safe to
        print on Windows cp1252 terminals."""
        av = self.agent_verdicts
        mc = self.memory_counts
        ft = self.fitness_trend
        recent = ft.samples[-7:] if ft.samples else []
        if recent:
            days = "  ".join(f"d{i+1}: {v:.3f}" for i, v in enumerate(recent))
            delta_pct = ft.delta * 100.0
            trend_arrow = "^" if ft.delta > 0 else ("v" if ft.delta < 0 else "->")
        else:
            days = "  (no samples yet)"
            delta_pct = 0.0
            trend_arrow = "-"

        bar_veto = "#" * min(av.total, 40)
        bar_zero = "." * max(0, 40 - min(av.total, 40))

        return (
            "+-- SPEACE MM-APR Supervision Dashboard "
            "-----------------------------+\n"
            f"| Health: {self.health.upper():9s}  "
            f"| Iteration: {self.iteration:5d}     "
            f"| Uptime: {self.uptime_seconds/3600:.1f}h  |\n"
            f"| Cycle count: {self.cycle_count:5d}     "
            f"| Veto rate: {self.veto_rate*100:5.1f}%   "
            f"| Rollback: {self.rollback_rate*100:5.1f}%  |\n"
            "+-- Veto distribution (per class) -----------------------+\n"
            f"|   Class A (Evolution):     {av.class_a:3d}                       |\n"
            f"|   Class B (Verification):  {av.class_b:3d}                       |\n"
            f"|   Class C (Adversarial):   {av.class_c:3d}  <- veto-capable      |\n"
            f"|   Class D (Meta-Govern):   {av.class_d:3d}                       |\n"
            f"|   Total vetoes:            {av.total:3d}                       |\n"
            f"|   {bar_veto}{bar_zero}  |\n"
            "+-- Memory status counts --------------------------------+\n"
            f"|   STABLE: {mc.stable:3d}   PROBATIONARY: {mc.probationary:3d}   "
            f"DEPRECATED: {mc.deprecated:3d}   |\n"
            f"|   FORGOTTEN: {mc.forgotten:3d}   QUARANTINED: {mc.quarantined:3d}   "
            f"VOLATILE: {mc.volatile:3d}   |\n"
            f"+-- Fitness trend (last {len(recent)} samples) "
            "-------------------------------+\n"
            f"|   {days}                                       |\n"
            f"|   Delta: {delta_pct:+.1f}% {trend_arrow}                            "
            "                      |\n"
            f"+-- Next governance in: {self.next_governance_in_seconds/3600:.1f}h "
            "----------------------------+"
        )

    def to_markdown(self) -> str:
        """Return a markdown rendering suitable for CI artifacts.
        All non-ASCII characters are replaced with ASCII fallbacks."""
        av = self.agent_verdicts
        mc = self.memory_counts
        ft = self.fitness_trend
        return (
            "# SPEACE MM-APR Supervision Report\n\n"
            f"- **Health**: `{self.health}`\n"
            f"- **Iteration**: {self.iteration}\n"
            f"- **Uptime**: {self.uptime_seconds/3600:.1f}h\n"
            f"- **Cycle count**: {self.cycle_count}\n"
            f"- **Veto rate**: {self.veto_rate*100:.1f}%\n"
            f"- **Rollback rate**: {self.rollback_rate*100:.1f}%\n\n"
            "## Veto distribution (per epistemic class)\n\n"
            "| Class | Count |\n"
            "|-------|-------|\n"
            f"| A - Evolution | {av.class_a} |\n"
            f"| B - Verification | {av.class_b} |\n"
            f"| C - Adversarial | {av.class_c} |\n"
            f"| D - Meta-Governance | {av.class_d} |\n"
            f"| **Total** | **{av.total}** |\n\n"
            "## Memory status counts\n\n"
            "| Status | Count |\n"
            "|--------|-------|\n"
            f"| STABLE | {mc.stable} |\n"
            f"| PROBATIONARY | {mc.probationary} |\n"
            f"| DEPRECATED | {mc.deprecated} |\n"
            f"| FORGOTTEN | {mc.forgotten} |\n"
            f"| QUARANTINED | {mc.quarantined} |\n"
            f"| VOLATILE | {mc.volatile} |\n"
            f"| EXPERIMENTAL | {mc.experimental} |\n"
            f"| **Total** | **{mc.total}** |\n\n"
            "## Fitness trend\n\n"
            f"- Samples: `{ft.samples}`\n"
            f"- Delta: **{ft.delta:+.4f}** ({ft.trend})\n"
        )


# ------------------------------------------------------------------ #
# Builder
# ------------------------------------------------------------------ #


class MMAPRSupervisionDashboard:
    """Builds a :class:`DashboardReport` from runtime components.

    Parameters
    ----------
    router
        Optional :class:`HardVetoRouter`.
    governor
        Optional :class:`EvolutionaryMemoryGovernor`.
    hook
        Optional :class:`SelfImprovementRuntimeHook`.
    audit_dir
        Optional path used to count persisted envelopes.
    iteration
        Logical iteration counter (incremented externally).
    uptime_seconds
        Wall-clock uptime in seconds.
    fitness_samples
        Optional list of recent fitness scores (e.g. from the
        long-horizon audit).
    governance_interval_seconds
        Interval at which ``run_governance_cycle`` is scheduled.
        Default 7 days (per the design doc).
    """

    def __init__(
        self,
        router: Optional[Any] = None,
        governor: Optional[Any] = None,
        hook: Optional[Any] = None,
        audit_dir: Optional[Path] = None,
        iteration: int = 0,
        uptime_seconds: float = 0.0,
        fitness_samples: Optional[List[float]] = None,
        governance_interval_seconds: float = 7 * 24 * 3600.0,
    ):
        self.router = router
        self.governor = governor
        self.hook = hook
        self.audit_dir = Path(audit_dir) if audit_dir is not None else None
        self.iteration = int(iteration)
        self.uptime_seconds = float(uptime_seconds)
        self.fitness_samples = list(fitness_samples or [])
        self.governance_interval_seconds = float(governance_interval_seconds)

    # ------------------------------------------------------------------ #
    # Build report
    # ------------------------------------------------------------------ #

    def build_report(self) -> DashboardReport:
        agent_verdicts = self._veto_distribution()
        memory_counts = self._memory_counts()
        fitness_trend = self._fitness_trend()
        cycle_count = self._cycle_count()
        total_vetoes = agent_verdicts.total
        veto_rate = (total_vetoes / cycle_count) if cycle_count > 0 else 0.0
        rollback_rate = self._rollback_rate(cycle_count)
        # Health: critical if veto_rate > 0.6 OR memory total == 0 with cycle > 0
        if cycle_count > 0 and veto_rate > 0.6:
            health = "critical"
        elif cycle_count > 0 and memory_counts.total == 0:
            health = "warning"
        else:
            health = "ok"
        # Next governance: a static "in N hours" — we don't track
        # when the last governance ran in this version; the report
        # is the value the operator would see.
        return DashboardReport(
            iteration=self.iteration,
            uptime_seconds=self.uptime_seconds,
            last_proposal=self._last_proposal(),
            agent_verdicts=agent_verdicts,
            fitness_trend=fitness_trend,
            memory_counts=memory_counts,
            cycle_count=cycle_count,
            veto_rate=veto_rate,
            rollback_rate=rollback_rate,
            next_governance_in_seconds=self.governance_interval_seconds,
            health=health,
        )

    # ------------------------------------------------------------------ #
    # Persist
    # ------------------------------------------------------------------ #

    def render(self) -> str:
        """Build the report and return the ASCII rendering."""
        return self.build_report().to_ascii()

    def render_markdown(self) -> str:
        """Build the report and return the Markdown rendering."""
        return self.build_report().to_markdown()

    def save(self, output_path: Path) -> Path:
        """Build the report, write both ASCII and Markdown to disk.

        ``output_path`` is the *base* path; the function writes
        ``{output_path}.md`` and ``{output_path}.txt``. Returns the
        path of the markdown file.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report = self.build_report()
        md_path = output_path.with_suffix(".md")
        txt_path = output_path.with_suffix(".txt")
        md_path.write_text(report.to_markdown(), encoding="utf-8")
        txt_path.write_text(report.to_ascii(), encoding="utf-8")
        return md_path

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _veto_distribution(self) -> DashboardVetoDistribution:
        if self.router is None:
            return DashboardVetoDistribution()
        # Aggregate over recent verdicts in router summary
        recent = list(getattr(self.router, "_last_verdicts", []) or [])
        counter: Counter = Counter()
        for v in recent:
            for blocker in v.hard_blocked_by:
                # We don't have class info from the agent name alone;
                # but every vote carries its veto_class. So scan votes.
                pass
            for vote in v.votes:
                if vote.kind.value == "hard_block":
                    # Map agent name to class via vote.veto_class
                    counter[vote.veto_class.value] += 1
        return DashboardVetoDistribution(
            class_a=counter.get("A_evolution", 0),
            class_b=counter.get("B_verification", 0),
            class_c=counter.get("C_adversarial", 0),
            class_d=counter.get("D_meta_governance", 0),
            total=sum(counter.values()),
        )

    def _memory_counts(self) -> DashboardMemoryCounts:
        if self.governor is None:
            return DashboardMemoryCounts()
        try:
            records = self.governor.store.list_records()
        except Exception:
            return DashboardMemoryCounts()
        c = Counter(r.status for r in records)
        counts = DashboardMemoryCounts(
            stable=c.get("stable", 0),
            probationary=c.get("probationary", 0),
            deprecated=c.get("deprecated", 0),
            forgotten=c.get("forgotten", 0),
            quarantined=c.get("quarantined", 0),
            volatile=c.get("volatile", 0),
            experimental=c.get("experimental", 0),
            total=sum(c.values()),
        )
        return counts

    def _fitness_trend(self) -> DashboardFitnessTrend:
        samples = self.fitness_samples
        if not samples:
            return DashboardFitnessTrend()
        delta = samples[-1] - samples[0] if len(samples) >= 2 else 0.0
        if delta > 0.001:
            trend = "improving"
        elif delta < -0.001:
            trend = "degrading"
        else:
            trend = "stable"
        return DashboardFitnessTrend(samples=samples, delta=delta, trend=trend)

    def _cycle_count(self) -> int:
        if self.hook is not None:
            try:
                return int(self.hook.summary().get("cycles_run", 0))
            except Exception:
                return 0
        if self.router is not None:
            try:
                # First try the router's own counters (set by route())
                total = (
                    int(self.router._veto_count)
                    + int(self.router._admit_count)
                    + int(self.router._soft_flag_count)
                )
                if total > 0:
                    return total
                # Fall back to the size of the verdicts buffer
                return len(list(getattr(self.router, "_last_verdicts", []) or []))
            except Exception:
                return 0
        return 0

    def _rollback_rate(self, cycle_count: int) -> float:
        # Read from the evolutionary memory store when available
        if self.governor is None or cycle_count == 0:
            return 0.0
        try:
            records = self.governor.store.list_records()
        except Exception:
            return 0.0
        rollbacks = sum(1 for r in records if r.status == "deprecated")
        return rollbacks / max(1, len(records))

    def _last_proposal(self) -> Optional[Dict[str, Any]]:
        if self.hook is None:
            return None
        try:
            last = self.hook.summary().get("last_summary", {}) or {}
            if not last:
                return None
            return dict(last)
        except Exception:
            return None
