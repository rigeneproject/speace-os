"""T-Phase 8B — Safety Officer (Class C) for MM-APR.

This module fills the second Class C evaluator slot of the
``HardVetoRouter``. The Safety Officer monitors **runtime metrics** for
signs of instability, drift, or memory growth that would make an
adoption unsafe.

The four monitors
-----------------

1. **Φ stability drift**: the kuramoto order parameter / coherence_phi
   must not drop by more than ``phi_drift_threshold`` between the
   baseline and the current snapshot. Default threshold 0.2.
2. **Entropy drift**: the ``total_free_energy`` (interpreted as
   surprise) must not rise above ``free_energy_threshold``.
3. **Memory growth**: the difference between current and baseline
   ``semantic_assembly_count`` (or other memory counters) must stay
   within ``memory_growth_threshold``.
4. **Rollback integrity**: if a previous patch result is supplied and
   its verdict is one of ``PATCH_ROLLED_BACK`` /
   ``PATCH_REJECTED_UNSAFE`` / ``PATCH_FAILED``, the officer emits a
   hard veto — the system is in an unstable state.

The officer returns an :class:`AgentVote` whose ``kind`` is
``HARD_BLOCK`` if any monitor fails. Otherwise it emits ``ADMIT``
with a confidence equal to the maximum severity across monitors.

The class follows the same ``(proposal, simulation, counterfactual,
patch_result) -> AgentVote`` signature as the other evaluators so it
can be slotted into ``HardVetoRouter`` directly.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.self_improvement.mmapr_veto_router import (
    AgentVote,
    VetoClass,
    VetoKind,
)


# ------------------------------------------------------------------ #
# Report
# ------------------------------------------------------------------ #


class SafetyReport(BaseModel):
    """Outcome of the safety officer's monitor suite."""

    proposal_id: str
    safe: bool = True
    severity: float = 0.0
    triggered_monitors: List[str] = Field(default_factory=list)
    monitor_values: Dict[str, float] = Field(default_factory=dict)
    rationale: str = ""
    timestamp: float = Field(default_factory=time.time)


# ------------------------------------------------------------------ #
# Safety Officer
# ------------------------------------------------------------------ #


class SafetyOfficer:
    """Class C evaluator: runtime safety monitoring.

    Parameters
    ----------
    baseline_metrics
        Optional dict of baseline metric values. The officer compares
        incoming metrics against this baseline. If ``None``, only
        absolute thresholds are enforced.
    phi_drift_threshold
        Maximum allowed |phi - baseline.phi| before a veto.
        Default 0.2.
    free_energy_threshold
        Maximum allowed ``total_free_energy``. Default 0.4.
    memory_growth_threshold
        Maximum allowed memory growth in arbitrary units.
        Default 1000.
    unsafe_patch_verdicts
        Patch verdicts that immediately trigger a veto.
        Default: ``{"PATCH_ROLLED_BACK", "PATCH_REJECTED_UNSAFE",
        "PATCH_FAILED"}``.
    """

    _DEFAULT_UNSAFE_VERDICTS = {
        "PATCH_ROLLED_BACK",
        "PATCH_REJECTED_UNSAFE",
        "PATCH_FAILED",
    }

    def __init__(
        self,
        baseline_metrics: Optional[Dict[str, float]] = None,
        phi_drift_threshold: float = 0.2,
        free_energy_threshold: float = 0.4,
        memory_growth_threshold: float = 1000.0,
        unsafe_patch_verdicts: Optional[List[str]] = None,
    ):
        self.baseline_metrics = dict(baseline_metrics or {}) or None
        self.phi_drift_threshold = float(phi_drift_threshold)
        self.free_energy_threshold = float(free_energy_threshold)
        self.memory_growth_threshold = float(memory_growth_threshold)
        self.unsafe_patch_verdicts = set(
            unsafe_patch_verdicts or self._DEFAULT_UNSAFE_VERDICTS
        )
        self._reports: List[SafetyReport] = []

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def monitor(
        self,
        proposal: Any,
        simulation: Any = None,
        counterfactual: Any = None,
        patch_result: Any = None,
        current_metrics: Optional[Dict[str, float]] = None,
    ) -> SafetyReport:
        """Run all four monitors. ``current_metrics`` is optional but
        recommended; if absent, only the patch_result monitor is
        consulted."""
        # Resolve the proposal id
        if hasattr(proposal, "id"):
            proposal_id = str(proposal.id)
        elif isinstance(proposal, dict):
            proposal_id = str(proposal.get("id", "unknown"))
        else:
            proposal_id = "unknown"

        triggered: List[str] = []
        values: Dict[str, float] = {}
        max_severity = 0.0

        # 1. Phi stability drift
        baseline_phi = self._baseline_get("coherence_phi", "kuramoto_order_parameter")
        if baseline_phi is not None and current_metrics:
            cur_phi = (
                current_metrics.get("coherence_phi")
                if current_metrics.get("coherence_phi") is not None
                else current_metrics.get("kuramoto_order_parameter")
            )
            if cur_phi is not None:
                drift = abs(float(baseline_phi) - float(cur_phi))
                values["phi_drift"] = drift
                if drift > self.phi_drift_threshold:
                    triggered.append("phi_stability_drift")
                    max_severity = max(max_severity, drift)

        # 2. Free-energy / entropy drift
        if current_metrics:
            fe = current_metrics.get("total_free_energy")
            if fe is not None:
                values["total_free_energy"] = float(fe)
                if float(fe) > self.free_energy_threshold:
                    triggered.append("free_energy_overflow")
                    max_severity = max(max_severity, float(fe))

        # 3. Memory growth
        if current_metrics:
            cur_mem = current_metrics.get("semantic_assembly_count")
            if cur_mem is not None:
                base_mem = self._baseline_get("semantic_assembly_count")
                if base_mem is not None:
                    growth = float(cur_mem) - float(base_mem)
                    values["memory_growth"] = growth
                    if abs(growth) > self.memory_growth_threshold:
                        triggered.append("memory_growth")
                        max_severity = max(max_severity, abs(growth) / 1000.0)

        # 4. Rollback integrity
        patch_verdict = self._extract_patch_verdict(patch_result)
        if patch_verdict in self.unsafe_patch_verdicts:
            triggered.append("rollback_integrity_breach")
            values["patch_verdict"] = 1.0
            max_severity = max(max_severity, 1.0)

        safe = len(triggered) == 0
        report = SafetyReport(
            proposal_id=proposal_id,
            safe=safe,
            severity=float(max_severity) if not safe else 0.0,
            triggered_monitors=triggered,
            monitor_values=values,
            rationale=(
                "all monitors passed" if safe
                else f"triggered: {triggered}"
            ),
        )
        self._reports.append(report)
        if len(self._reports) > 100:
            self._reports = self._reports[-100:]
        return report

    def __call__(
        self,
        proposal: Any,
        simulation: Any = None,
        counterfactual: Any = None,
        patch_result: Any = None,
        current_metrics: Optional[Dict[str, float]] = None,
    ) -> AgentVote:
        """Class C slot signature: return an ``AgentVote``.

        ``current_metrics`` is passed as a keyword argument so the
        router's evaluator call-site (which only forwards
        proposal/simulation/counterfactual/patch_result) still works
        when ``current_metrics`` is ``None``. Production code can
        pass a fresh metrics dict directly to this method.
        """
        report = self.monitor(
            proposal, simulation, counterfactual, patch_result,
            current_metrics=current_metrics,
        )
        kind = VetoKind.ADMIT if report.safe else VetoKind.HARD_BLOCK
        return AgentVote(
            agent="safety_officer",
            veto_class=VetoClass.C_ADVERSARIAL,
            kind=kind,
            confidence=report.severity,
            rationale=report.rationale,
            evidence={
                "triggered_monitors": report.triggered_monitors,
                "monitor_values": report.monitor_values,
            },
            timestamp=time.time(),
        )

    def summary(self) -> Dict[str, Any]:
        return {
            "phi_drift_threshold": self.phi_drift_threshold,
            "free_energy_threshold": self.free_energy_threshold,
            "memory_growth_threshold": self.memory_growth_threshold,
            "unsafe_patch_verdicts": sorted(self.unsafe_patch_verdicts),
            "reports_count": len(self._reports),
            "unsafe_count": sum(1 for r in self._reports if not r.safe),
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _baseline_get(self, *keys: str) -> Optional[float]:
        if not self.baseline_metrics:
            return None
        for k in keys:
            v = self.baseline_metrics.get(k)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    continue
        return None

    @staticmethod
    def _extract_patch_verdict(patch_result: Any) -> Optional[str]:
        if patch_result is None:
            return None
        if isinstance(patch_result, dict):
            return patch_result.get("verdict")
        return getattr(patch_result, "verdict", None)
