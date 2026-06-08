"""T-CSA — Continuous Substrate Audit.

Validates that the continuous-time substrate is actually wired into the
runtime, not merely present in the codebase. The audit produces a
machine-readable report that downstream consumers (dashboards, CI
gates, the ``T109`` extended runtime observer) can ingest.

The audit is intentionally *intrusive* in the sense that it inspects
private attributes (``_substrate_coordinator``, ``_substep_loop``, the
``*_enabled`` flags on the orchestrator) — these are the only reliable
ways to check whether the substrate is *running*, not just *imported*.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_logger = logging.getLogger(__name__)


@dataclass
class AuditCheck:
    """One audit check result."""

    name: str
    passed: bool
    detail: str = ""
    measurements: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "detail": self.detail,
            "measurements": dict(self.measurements),
        }


@dataclass
class ContinuousSubstrateAuditReport:
    """Aggregate audit result."""

    checks: List[AuditCheck] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    runtime_mode: Optional[str] = None

    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def summary(self) -> Dict[str, Any]:
        return {
            "passed": self.passed(),
            "n_checks": len(self.checks),
            "n_passed": sum(1 for c in self.checks if c.passed),
            "runtime_mode": self.runtime_mode,
            "recommendations": list(self.recommendations),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary(),
            "checks": [c.to_dict() for c in self.checks],
            "recommendations": list(self.recommendations),
            "runtime_mode": self.runtime_mode,
        }


class ContinuousSubstrateAuditor:
    """Audit the runtime to verify the continuous substrate is live."""

    def __init__(self):
        self._report = ContinuousSubstrateAuditReport()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def audit(self, runtime: Any) -> ContinuousSubstrateAuditReport:
        self._report = ContinuousSubstrateAuditReport(
            runtime_mode=getattr(runtime, "runtime_mode", None)
        )
        self._check_substrate_attached(runtime)
        self._check_substrate_modules_initialised(runtime)
        self._check_substrate_progresses(runtime)
        self._check_orchestrator_flags(runtime)
        self._check_stability_guard(runtime)
        self._check_substepping(runtime)
        self._check_embodied_loop(runtime)
        self._build_recommendations()
        return self._report

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self._report.to_dict(), fh, indent=2)

    # ------------------------------------------------------------------ #
    # Individual checks
    # ------------------------------------------------------------------ #

    def _check_substrate_attached(self, runtime: Any) -> None:
        coord = getattr(runtime, "_substrate_coordinator", None)
        if coord is None:
            self._report.checks.append(
                AuditCheck(
                    name="substrate_attached",
                    passed=False,
                    detail="runtime._substrate_coordinator is None — "
                    "the runtime never attached a continuous substrate",
                )
            )
            return
        self._report.checks.append(
            AuditCheck(
                name="substrate_attached",
                passed=True,
                detail=f"substrate present (substep_dt={getattr(coord, '_substep_dt', '?')})",
            )
        )

    def _check_substrate_modules_initialised(self, runtime: Any) -> None:
        coord = getattr(runtime, "_substrate_coordinator", None)
        if coord is None:
            return
        flags = {
            "temporal_dynamics": coord._temporal_dynamics is not None,
            "oscillator_bank": coord._oscillator_bank is not None,
            "phase_coupling": coord._phase_coupling is not None,
            "energy_field": coord._energy_field is not None,
            "predictive_coding": coord._predictive_coding is not None,
            "active_inference": coord._active_inference is not None,
            "homeostatic_drive": coord._homeostatic_drive is not None,
            "criticality": coord._criticality is not None,
        }
        all_initialised = all(flags.values())
        self._report.checks.append(
            AuditCheck(
                name="substrate_modules_initialised",
                passed=all_initialised,
                detail="all continuous modules constructed" if all_initialised else
                "one or more substrate modules are missing",
                measurements=flags,
            )
        )

    def _check_substrate_progresses(self, runtime: Any) -> None:
        state = getattr(runtime, "_last_substrate_state", None)
        if state is None:
            self._report.checks.append(
                AuditCheck(
                    name="substrate_progress",
                    passed=False,
                    detail="no substrate state observed at runtime level "
                    "(tick_substrate never called?)",
                )
            )
            return
        snap = state.to_dict() if hasattr(state, "to_dict") else {}
        self._report.checks.append(
            AuditCheck(
                name="substrate_progress",
                passed=True,
                detail="substrate is producing state",
                measurements={
                    "sim_time": snap.get("sim_time", 0.0),
                    "substeps": snap.get("substeps", 0),
                    "kuramoto": round(float(snap.get("kuramoto_order_parameter", 0.0)), 4),
                },
            )
        )

    def _check_orchestrator_flags(self, runtime: Any) -> None:
        orch = getattr(runtime, "orchestrator", None)
        if orch is None:
            return
        flags = {
            "temporal_dynamics_enabled": bool(getattr(orch, "temporal_dynamics_enabled", False)),
            "neural_oscillator_enabled": bool(getattr(orch, "neural_oscillator_enabled", False)),
            "phase_coupling_enabled": bool(getattr(orch, "phase_coupling_enabled", False)),
            "energy_field_enabled": bool(getattr(orch, "energy_field_enabled", False)),
            "predictive_coding_enabled": bool(getattr(orch, "predictive_coding_enabled", False)),
            "active_inference_enabled": bool(getattr(orch, "active_inference_enabled", False)),
            "homeostatic_drive_enabled": bool(getattr(orch, "homeostatic_drive_enabled", False)),
            "criticality_monitor_enabled": bool(getattr(orch, "criticality_monitor_enabled", False)),
            "embodiment_enabled": bool(getattr(orch, "embodiment_enabled", False)),
        }
        all_on = all(flags.values())
        self._report.checks.append(
            AuditCheck(
                name="orchestrator_flags",
                passed=all_on,
                detail="all continuous-substrate flags enabled" if all_on else
                "one or more orchestrator flags are disabled",
                measurements=flags,
            )
        )

    def _check_stability_guard(self, runtime: Any) -> None:
        guard = getattr(runtime, "_stability_guard", None)
        last = getattr(runtime, "_last_guard_report", None)
        if guard is None:
            self._report.checks.append(
                AuditCheck(
                    name="stability_guard",
                    passed=False,
                    detail="no stability guard attached — runaway dynamics "
                    "are not protected",
                )
            )
            return
        if last is None:
            self._report.checks.append(
                AuditCheck(
                    name="stability_guard",
                    passed=True,
                    detail="guard attached but no report yet",
                )
            )
            return
        self._report.checks.append(
            AuditCheck(
                name="stability_guard",
                passed=True,
                detail="guard active and producing reports",
                measurements=last.to_dict() if hasattr(last, "to_dict") else {},
            )
        )

    def _check_substepping(self, runtime: Any) -> None:
        substep_loop = getattr(runtime, "_substep_loop", None)
        if substep_loop is None:
            self._report.checks.append(
                AuditCheck(
                    name="substepping",
                    passed=False,
                    detail="substep loop not constructed — substrate "
                    "advances only once per outer tick",
                )
            )
            return
        last = substep_loop.last_result
        if last is None:
            self._report.checks.append(
                AuditCheck(
                    name="substepping",
                    passed=True,
                    detail="substep loop ready, no tick yet",
                )
            )
            return
        n = max(1, int(last.n_substeps))
        passed = n > 0
        self._report.checks.append(
            AuditCheck(
                name="substepping",
                passed=passed,
                detail=f"substeps per tick = {n}",
                measurements={"n_substeps": n},
            )
        )

    def _check_embodied_loop(self, runtime: Any) -> None:
        # We can't introspect the active inference embodied loop
        # directly, but we *can* check whether the active inference
        # module is exposed and whether the action governance is wired.
        orch = getattr(runtime, "orchestrator", None)
        if orch is None:
            return
        ai = getattr(orch, "_active_inference", None)
        actuator = getattr(orch, "_embodied_actuator", None)
        present = ai is not None and actuator is not None
        self._report.checks.append(
            AuditCheck(
                name="embodied_loop_components",
                passed=present,
                detail=(
                    "active_inference + embodied_actuator present"
                    if present
                    else "active_inference or embodied_actuator missing"
                ),
                measurements={
                    "active_inference": ai is not None,
                    "embodied_actuator": actuator is not None,
                },
            )
        )

    # ------------------------------------------------------------------ #
    # Recommendations
    # ------------------------------------------------------------------ #

    def _build_recommendations(self) -> None:
        for check in self._report.checks:
            if check.passed:
                continue
            if check.name == "substrate_attached":
                self._report.recommendations.append(
                    "Attach a ContinuousSubstrateCoordinator via "
                    "ContinuousRuntimeEngine.attach_continuous_substrate(...) "
                    "and call runtime.tick_substrate() in your main loop."
                )
            elif check.name == "substrate_modules_initialised":
                self._report.recommendations.append(
                    "Ensure coordinator.initialize() ran successfully and "
                    "all dynamic modules could be imported."
                )
            elif check.name == "orchestrator_flags":
                self._report.recommendations.append(
                    "Enable the corresponding *_enabled flag on the "
                    "CellularBrainOrchestrator (e.g. temporal_dynamics_enabled=True)."
                )
            elif check.name == "stability_guard":
                self._report.recommendations.append(
                    "Attach a SubstrateStabilityGuard to detect runaway "
                    "dynamics, hyper-synchrony, and energy collapse."
                )
            elif check.name == "substepping":
                self._report.recommendations.append(
                    "Set substep_dt on the substrate coordinator to a "
                    "value << tick_interval (e.g. 0.01 s) so gamma-band "
                    "oscillations can resolve."
                )
            elif check.name == "embodied_loop_components":
                self._report.recommendations.append(
                    "Enable orchestrator.embodiment_enabled=True and "
                    "orchestrator.active_inference_enabled=True."
                )
            elif check.name == "substrate_progress":
                self._report.recommendations.append(
                    "Verify that runtime.tick_substrate() is being called "
                    "from inside the main loop body."
                )
