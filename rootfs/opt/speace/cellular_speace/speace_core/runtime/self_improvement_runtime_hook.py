"""Self-Improvement Runtime Hook.

Glue layer between the persistent ContinuousRuntimeEngine and SPEACE's
self-improvement / auto-design infrastructure.

Why this exists
---------------
The ``ContinuousRuntimeEngine`` (T109) drives a long-lived persistent
loop on top of the continuous substrate (oscillators, energy field,
phase coupling, predictive coding, active inference, etc.). All of the
substrate's state is observable: the ``SubstepResult.substrate_state``
exposes ``kuramoto_order_parameter``, ``mean_energy_field``,
``total_free_energy``, ``branching_ratio``, ``fatigue_count`` and the
``drives`` / ``modulations`` dictionaries.

SPEACE also has a *mature* self-improvement stack (``SelfImprovementLoop``,
``LimitationDetector``, ``ArchitectureRewriter``, ``CounterfactualSandbox``,
``ArchitecturePatchExecutor``, ``OutcomeTracker``, ``ProposalLearningEngine``,
``EvolutionaryMemoryGovernor``). But it was previously invoked only by
external scripts / tests — it was not wired into the runtime loop.

This module closes that loop. It runs an *observation cycle* every
``cycle_interval_ticks`` outer ticks:

  1. **Observe** the substrate state and the orchestrator's last
     metrics, build a ``metrics`` dict consumable by
     :class:`LimitationDetector`.
  2. **Identify** limitations via
     :meth:`SelfImprovementLoop.run_detection_cycle`.
  3. **Learn** from the cycle's outcome by recording it in
     :class:`OutcomeTracker` and updating the
     :class:`ProposalLearningEngine`.
  4. **Consolidate** by promoting the cycle result to the
     :class:`EvolutionaryMemoryGovernor` (when one is attached).
  5. **Audit** by writing a per-cycle JSON report and updating the
     hook's ``summary()`` view, which the runtime can surface in its
     ``snapshot()``.

This module is **opt-in** and has no circular dependencies: it imports
the self-improvement modules, but the runtime does *not* import this
module. ``attach_self_improvement_hook()`` is the only entry point the
runtime exposes.

Design constraints
------------------
* All public methods are safe to call concurrently from one asyncio
  loop (the hook stores a small mutable counter / last-tick cache, and
  writes reports under an ``os.makedirs(exist_ok=True)``).
* The hook never raises — every internal error is logged and the
  cycle is marked ``FAILED`` so the outer runtime is never crashed
  by an observability hook.
* The hook is **observational and learning** by default. The
  ``ArchitecturePatchExecutor`` (when enabled in the underlying
  ``SelfImprovementLoop``) only mutates *allowlisted* flags /
  profiles / numerics, so a successful ``PROPOSAL_ACCEPTED_FOR_NEXT_TASK``
  verdict never produces a dangerous mutation by itself.

See ``tests/test_self_improvement_runtime_hook.py`` for the
end-to-end demo.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

_logger = logging.getLogger(__name__)


# Window size used to compute deltas (phi_delta, cognitive_delta, etc.)
# over the most recent N substrate snapshots.
_METRIC_WINDOW = 5


class SelfImprovementRuntimeHook:
    """Observe the substrate, run the self-improvement loop, learn, consolidate.

    Parameters
    ----------
    self_improvement_loop
        The :class:`SelfImprovementLoop` to invoke. Must already be
        configured (episodic policy, counterfactual sandbox, patch
        executor) — this hook does not own those flags.
    outcome_tracker
        :class:`OutcomeTracker` used to record each proposal outcome
        produced by a cycle.
    evolutionary_memory_governor
        Optional :class:`EvolutionaryMemoryGovernor`. When supplied,
        every cycle result is ingested into the evolutionary memory
        store.
    cycle_interval_ticks
        Number of outer ticks between two consecutive cycles. Set to
        ``1`` to run a cycle every outer tick (useful for tests).
    report_dir
        Directory in which per-cycle JSON reports are written.
    metric_window
        Size of the rolling window used to compute phi/cognitive/energy
        deltas. Defaults to 5.
    """

    #: Recognised final verdicts, mirroring ``SelfImprovementLoop``.
    _VALID_VERDICTS = {
        "NO_LIMITATION_DETECTED",
        "LIMITATION_DETECTED_NO_SAFE_PATCH",
        "PROPOSAL_ACCEPTED_FOR_NEXT_TASK",
        "REGRESSION_BLOCKED",
        "SAFE_PROPOSAL_GENERATED",
        "FAILED",
    }

    def __init__(
        self,
        self_improvement_loop: Any,
        outcome_tracker: Any,
        evolutionary_memory_governor: Optional[Any] = None,
        cycle_interval_ticks: int = 30,
        report_dir: str = "reports/self_improvement_runtime",
        metric_window: int = _METRIC_WINDOW,
    ):
        if cycle_interval_ticks < 1:
            raise ValueError("cycle_interval_ticks must be >= 1")
        if metric_window < 1:
            raise ValueError("metric_window must be >= 1")
        self.loop = self_improvement_loop
        self.outcome_tracker = outcome_tracker
        self.governor = evolutionary_memory_governor
        self.cycle_interval_ticks = int(cycle_interval_ticks)
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.metric_window = int(metric_window)

        # Internal state
        self._last_cycle_tick: int = -10**9
        self._cycles_run: int = 0
        self._accepted_total: int = 0
        self._rejected_total: int = 0
        self._last_verdict: str = "PENDING"
        self._last_tick: int = 0
        self._last_cycle_id: Optional[str] = None
        self._last_summary: Dict[str, Any] = {}
        self._history: Deque[Dict[str, Any]] = deque(maxlen=64)
        # Rolling window of substrate snapshots for delta computation
        self._substrate_window: Deque[Dict[str, float]] = deque(maxlen=self.metric_window)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def tick(
        self,
        tick: int,
        orchestrator: Any,
        substrate_state: Optional[Any] = None,
    ) -> Optional[Dict[str, Any]]:
        """Run one observation cycle if ``cycle_interval_ticks`` has elapsed.

        Returns the cycle result dict, or ``None`` if the interval has
        not yet elapsed (i.e. the hook is in cooldown).
        """
        if tick - self._last_cycle_tick < self.cycle_interval_ticks:
            return None
        self._last_cycle_tick = int(tick)
        self._last_tick = int(tick)

        try:
            metrics = self._collect_metrics(tick, orchestrator, substrate_state)
            self._substrate_window.append(
                {
                    "kuramoto": float(metrics.get("kuramoto_order_parameter", 0.0)),
                    "mean_energy": float(metrics.get("mean_energy_field", 0.0)),
                    "free_energy": float(metrics.get("total_free_energy", 0.0)),
                    "branching": float(metrics.get("branching_ratio", 0.0)),
                    "phi": float(metrics.get("coherence_phi", 0.0)),
                    "cognitive": float(metrics.get("cognitive_score", 0.0)),
                    "energy_efficiency": float(metrics.get("energy_efficiency", 0.0)),
                }
            )
            # Enrich with rolling-window deltas
            metrics.update(self._compute_deltas())

            # 1+2. Detect + propose via the canonical loop
            result = self.loop.run_detection_cycle(metrics)
            cycle_dict = result.model_dump() if hasattr(result, "model_dump") else dict(result)

            verdict = str(cycle_dict.get("final_verdict", "FAILED"))
            if verdict not in self._VALID_VERDICTS:
                verdict = "FAILED"
            self._last_verdict = verdict
            self._last_cycle_id = str(cycle_dict.get("cycle_id", uuid.uuid4().hex[:8]))
            self._cycles_run += 1

            accepted = list(cycle_dict.get("accepted_proposals", []) or [])
            rejected = list(cycle_dict.get("rejected_proposals", []) or [])
            self._accepted_total += len(accepted)
            self._rejected_total += len(rejected)

            # 3. Learn: record each proposal outcome in the OutcomeTracker
            # and update the learning engine.
            diagnoses = cycle_dict.get("diagnoses", []) or []
            primary_category = (
                str(diagnoses[0].get("primary_category", "unknown"))
                if diagnoses
                else "unknown"
            )
            for proposal_id in accepted + rejected:
                try:
                    outcome = self.outcome_tracker.record_outcome(
                        proposal_id=proposal_id,
                        limitation_type=primary_category,
                        task_id=f"runtime_cycle_{tick}",
                        audit_verdict=verdict,
                        metrics=metrics,
                    )
                    self.loop.learn_from_outcome(outcome)
                except Exception as exc:  # pragma: no cover - defensive
                    _logger.debug("Outcome recording failed for %s: %s", proposal_id, exc)

            # 4. Consolidate: promote the cycle into evolutionary memory.
            if self.governor is not None:
                try:
                    self._consolidate(result, cycle_dict, metrics)
                except Exception as exc:  # pragma: no cover - defensive
                    _logger.debug("Evolutionary memory consolidation failed: %s", exc)

            # 5. Audit: write JSON report + update summary.
            self._write_report(tick, cycle_dict, metrics)
            self._last_summary = {
                "cycle_id": self._last_cycle_id,
                "tick": int(tick),
                "verdict": verdict,
                "proposals": len(cycle_dict.get("proposals", []) or []),
                "diagnoses": len(diagnoses),
                "accepted": len(accepted),
                "rejected": len(rejected),
                "counterfactual_verdict": cycle_dict.get("counterfactual_verdict", ""),
                "patch_verdict": cycle_dict.get("patch_verdict", "") or "",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._history.append(self._last_summary)
            return cycle_dict
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception("Self-improvement runtime hook tick failed: %s", exc)
            self._last_verdict = "FAILED"
            self._cycles_run += 1
            return {"final_verdict": "FAILED", "error": str(exc), "tick": int(tick)}

    def summary(self) -> Dict[str, Any]:
        """Return a serialisable summary, suitable for ``snapshot()``."""
        return {
            "cycles_run": int(self._cycles_run),
            "last_verdict": str(self._last_verdict),
            "last_tick": int(self._last_tick),
            "last_cycle_id": self._last_cycle_id,
            "accepted_total": int(self._accepted_total),
            "rejected_total": int(self._rejected_total),
            "cycle_interval_ticks": int(self.cycle_interval_ticks),
            "metric_window": int(self.metric_window),
            "last_summary": dict(self._last_summary),
            "recent_cycles": list(self._history)[-8:],
        }

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _collect_metrics(
        self,
        tick: int,
        orchestrator: Any,
        substrate_state: Optional[Any],
    ) -> Dict[str, Any]:
        """Translate the substrate + orchestrator state into a metrics dict.

        The dict is consumable by :meth:`LimitationDetector.detect_from_metrics`
        which reads keys such as ``cognitive_delta``, ``phi_delta``,
        ``energy_delta``, ``semantic_recall_success_rate``, etc. We
        populate the keys that are *observable* from the continuous
        substrate and the orchestrator's last-metrics view; the rest
        are left at their natural defaults (0.0) so the detector can
        short-circuit on absent signals.
        """
        metrics: Dict[str, Any] = {
            "tick": int(tick),
            # Continuous substrate signals
            "kuramoto_order_parameter": 0.0,
            "mean_energy_field": 0.0,
            "total_free_energy": 0.0,
            "branching_ratio": 0.0,
            "fatigue_count": 0,
            "drives": {},
            "modulations": {},
            "selected_action": None,
            # Detector-friendly keys (filled by delta computation if window is warm)
            "cognitive_delta": 0.0,
            "phi_delta": 0.0,
            "energy_delta": 0.0,
            "cognitive_score": 0.0,
            "coherence_phi": 0.0,
            "energy_efficiency": 0.0,
            # Memory / semantic keys (filled from orchestrator if available)
            "semantic_recall_success_rate": 0.0,
            "semantic_assembly_count": 0,
            "semantic_association_count": 0,
            "region_signal_routing_enabled": False,
            "regional_signal_flow_score": 0.0,
            "inter_region_plasticity_enabled": False,
            "inter_region_plasticity_events": 0,
            "brainstem_suppression_cost": 0.0,
            "cellular_resilience_score": 0.0,
            "benchmark_stagnation_score": 0.0,
        }

        # 1. Pull from substrate state if present
        if substrate_state is not None and hasattr(substrate_state, "to_dict"):
            try:
                snap = substrate_state.to_dict()
                metrics["kuramoto_order_parameter"] = float(snap.get("kuramoto_order_parameter", 0.0))
                metrics["mean_energy_field"] = float(snap.get("mean_energy_field", 0.0))
                metrics["total_free_energy"] = float(snap.get("total_free_energy", 0.0))
                metrics["branching_ratio"] = float(snap.get("branching_ratio", 0.0))
                metrics["fatigue_count"] = int(snap.get("fatigue_count", 0))
                metrics["drives"] = dict(snap.get("drives", {}) or {})
                metrics["modulations"] = dict(snap.get("modulations", {}) or {})
                metrics["selected_action"] = snap.get("selected_action")
                # The continuous substrate uses "coherence_phi" interchangeably
                # with the kuramoto order parameter for *signal-level*
                # coherence, so we surface it directly.
                metrics["coherence_phi"] = metrics["kuramoto_order_parameter"]
                metrics["energy_efficiency"] = max(0.0, 1.0 - metrics["total_free_energy"])
            except Exception as exc:  # pragma: no cover - defensive
                _logger.debug("Substrate state extraction failed: %s", exc)

        # 2. Pull from the orchestrator's last metrics view if available
        if orchestrator is not None:
            try:
                last = getattr(orchestrator, "latest_metrics", None)
                if last is not None:
                    if hasattr(last, "coherence_phi"):
                        metrics["coherence_phi"] = float(last.coherence_phi or 0.0)
                    if hasattr(last, "mean_energy"):
                        metrics["mean_energy_field"] = float(last.mean_energy or 0.0)
                    if hasattr(last, "energy_efficiency"):
                        metrics["energy_efficiency"] = float(last.energy_efficiency or 0.0)
                    if hasattr(last, "cognitive_score"):
                        metrics["cognitive_score"] = float(last.cognitive_score or 0.0)
            except Exception as exc:  # pragma: no cover - defensive
                _logger.debug("Orchestrator metrics extraction failed: %s", exc)

            # Boolean feature flags: surfaced as 'enabled' for the detector.
            for src_key, dst_key in (
                ("semantic_memory_enabled", "semantic_memory_enabled"),
                ("region_signal_routing_enabled", "region_signal_routing_enabled"),
                ("inter_region_plasticity_enabled", "inter_region_plasticity_enabled"),
            ):
                if hasattr(orchestrator, src_key):
                    metrics[dst_key] = bool(getattr(orchestrator, src_key))

        return metrics

    def _compute_deltas(self) -> Dict[str, float]:
        """Compute phi/cognitive/energy deltas over the rolling window.

        Returns 0.0 deltas when the window is not yet warm (fewer than
        2 snapshots), so the detector sees a *neutral* view until the
        hook has had time to observe trends.
        """
        out: Dict[str, float] = {
            "phi_delta": 0.0,
            "cognitive_delta": 0.0,
            "energy_delta": 0.0,
            "kuramoto_delta": 0.0,
            "branching_delta": 0.0,
        }
        if len(self._substrate_window) < 2:
            return out
        first = self._substrate_window[0]
        last = self._substrate_window[-1]
        out["phi_delta"] = float(last["phi"] - first["phi"])
        out["cognitive_delta"] = float(last["cognitive"] - first["cognitive"])
        out["energy_delta"] = float(last["mean_energy"] - first["mean_energy"])
        out["kuramoto_delta"] = float(last["kuramoto"] - first["kuramoto"])
        out["branching_delta"] = float(last["branching"] - first["branching"])
        return out

    def _consolidate(
        self,
        result: Any,
        cycle_dict: Dict[str, Any],
        metrics: Dict[str, Any],
    ) -> None:
        """Promote the cycle result to the evolutionary memory store."""
        from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_models import (
            EvolutionaryMemoryRecord,
        )

        cycle_id = str(cycle_dict.get("cycle_id", uuid.uuid4().hex[:8]))
        diagnoses = cycle_dict.get("diagnoses", []) or []
        primary_category = (
            str(diagnoses[0].get("primary_category", "unknown"))
            if diagnoses
            else "unknown"
        )
        verdict = str(cycle_dict.get("final_verdict", "FAILED"))
        # Map acceptance verdict to a coarse safety score: accepted
        # proposals are *proposed* safe by the executor, but the
        # governor's policy is conservative, so we use 0.6 as a default
        # starting point and let the consolidation policy decide.
        safety = 0.6
        if verdict == "PROPOSAL_ACCEPTED_FOR_NEXT_TASK":
            safety = 0.75
        elif verdict in ("REGRESSION_BLOCKED", "FAILED"):
            safety = 0.3
        elif verdict == "NO_LIMITATION_DETECTED":
            safety = 0.65

        record = EvolutionaryMemoryRecord(
            record_id=f"rt_{cycle_id}",
            source_cycle_id=cycle_id,
            source_task="runtime_self_improvement_hook",
            source_profile="runtime_hook",
            fitness_delta=float(metrics.get("kuramoto_delta", 0.0) or 0.0),
            phi_delta=float(metrics.get("phi_delta", 0.0) or 0.0),
            energy_delta=float(metrics.get("energy_delta", 0.0) or 0.0),
            cognitive_delta=float(metrics.get("cognitive_delta", 0.0) or 0.0),
            regression_score=0.0 if verdict != "REGRESSION_BLOCKED" else 1.0,
            safety_score=float(safety),
            confidence=float(cycle_dict.get("counterfactual_verdict", "") == "SAFE" and 0.7 or 0.4),
            reuse_count=0,
            status="volatile",
            metadata={
                "verdict": verdict,
                "primary_category": primary_category,
                "accepted": list(cycle_dict.get("accepted_proposals", []) or []),
                "rejected": list(cycle_dict.get("rejected_proposals", []) or []),
                "counterfactual_verdict": cycle_dict.get("counterfactual_verdict", ""),
                "patch_verdict": cycle_dict.get("patch_verdict", "") or "",
            },
        )
        try:
            self.governor.ingest_cycle_result(record)
        except AttributeError:
            # Fall back to the store-level add_record path
            store = getattr(self.governor, "store", None)
            if store is not None and hasattr(store, "add_record"):
                store.add_record(record)

    def _write_report(
        self,
        tick: int,
        cycle_dict: Dict[str, Any],
        metrics: Dict[str, Any],
    ) -> Path:
        """Write a per-cycle JSON report and return its path."""
        report = {
            "tick": int(tick),
            "cycle_id": cycle_dict.get("cycle_id"),
            "final_verdict": cycle_dict.get("final_verdict"),
            "accepted_proposals": list(cycle_dict.get("accepted_proposals", []) or []),
            "rejected_proposals": list(cycle_dict.get("rejected_proposals", []) or []),
            "diagnoses": cycle_dict.get("diagnoses", []) or [],
            "counterfactual_verdict": cycle_dict.get("counterfactual_verdict", ""),
            "patch_verdict": cycle_dict.get("patch_verdict", "") or "",
            "metrics_observed": {
                k: v for k, v in metrics.items()
                if k in {
                    "kuramoto_order_parameter",
                    "mean_energy_field",
                    "total_free_energy",
                    "branching_ratio",
                    "phi_delta",
                    "cognitive_delta",
                    "energy_delta",
                    "selected_action",
                }
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        path = self.report_dir / f"cycle_{tick:06d}_{uuid.uuid4().hex[:6]}.json"
        try:
            with path.open("w", encoding="utf-8") as fh:
                json.dump(report, fh, ensure_ascii=False, indent=2, default=str)
        except Exception as exc:  # pragma: no cover - defensive
            _logger.warning("Failed to write self-improvement hook report: %s", exc)
        return path
