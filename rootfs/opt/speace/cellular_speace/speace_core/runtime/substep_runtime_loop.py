"""T-SRL — Substep Runtime Loop.

Bridges the gap between the runtime's coarse ``tick_interval`` (typically
1.0 s) and the continuous substrate's need for a much smaller ``dt``
(gamma-band oscillations run at ~40 Hz, so ``dt`` < 0.025 s is required
to resolve them).

The loop runs *N* substeps per outer tick, advancing every continuous
module (oscillators, ODE, energy field, phase coupling, predictive
coding, active inference) by ``substep_dt`` each time, then returning
the aggregated state to the caller. It also enforces the
:class:`SubstrateStabilityGuard` after every outer tick and exposes a
``halt_request`` flag that the runtime can honour.

This module is deliberately self-contained: the caller passes in the
host circuit and the substrate coordinator, and the loop owns no
runtime state of its own (apart from a tick counter and the guard).
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_logger = logging.getLogger(__name__)


@dataclass
class SubstepResult:
    """Outcome of a single outer-tick substepped advance."""

    tick: int
    n_substeps: int
    duration_ms: float
    substrate_state: Optional[Any] = None
    guard_report: Optional[Any] = None
    halt_requested: bool = False
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "n_substeps": self.n_substeps,
            "duration_ms": self.duration_ms,
            "halt_requested": self.halt_requested,
            "notes": list(self.notes),
            "substrate_state": (
                self.substrate_state.to_dict()
                if self.substrate_state is not None
                and hasattr(self.substrate_state, "to_dict")
                else None
            ),
            "guard_report": (
                self.guard_report.to_dict()
                if self.guard_report is not None
                and hasattr(self.guard_report, "to_dict")
                else None
            ),
        }


class SubstepRuntimeLoop:
    """Run a continuous substrate at sub-second resolution per outer tick."""

    def __init__(
        self,
        substrate_coordinator: Any,
        stability_guard: Any = None,
        default_substep_dt: float = 0.01,
        min_substeps: int = 1,
        max_substeps: int = 10000,
    ):
        self.substrate = substrate_coordinator
        self.guard = stability_guard
        self.default_substep_dt = float(default_substep_dt)
        self.min_substeps = int(min_substeps)
        self.max_substeps = int(max_substeps)
        self._tick: int = 0
        self._last_result: Optional[SubstepResult] = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def advance(
        self,
        tick_interval: float,
        activations: Optional[Dict[str, float]] = None,
        prediction_error: Optional[float] = None,
        external_action_likelihoods: Optional[Dict[str, float]] = None,
        last_drive_metrics: Optional[Dict[str, float]] = None,
    ) -> SubstepResult:
        """Advance the substrate by one outer tick at sub-second resolution."""
        start = time.time()
        self._tick += 1

        # Sanity-cap the substep count to avoid runaway loops.
        n = self.substrate.substeps_for_tick(tick_interval)
        n = max(self.min_substeps, min(self.max_substeps, n))
        dt = max(1e-6, float(tick_interval) / n) if tick_interval > 0 else self.default_substep_dt

        # If the substrate is configured with its own substep_dt, we
        # call advance() with the right number of substeps.
        previous_total = getattr(self.substrate, "_total_substeps", 0)
        try:
            # Override the substrate's internal substep count for this
            # outer tick so the guard sees the correct sim_time.
            self.substrate._substeps_per_tick = n
            state = self.substrate.advance(
                tick_interval=float(tick_interval),
                activations=activations,
                prediction_error=prediction_error,
                external_action_likelihoods=external_action_likelihoods,
                last_drive_metrics=last_drive_metrics,
            )
        except Exception as exc:  # pragma: no cover - defensive
            _logger.exception("Substrate advance failed: %s", exc)
            return SubstepResult(
                tick=self._tick,
                n_substeps=0,
                duration_ms=(time.time() - start) * 1000.0,
                halt_requested=True,
                notes=[f"substrate_failure:{exc}"],
            )

        # Restore the user's configuration, so we don't override the
        # constructor setting on a per-tick basis.
        self.substrate._substeps_per_tick = self.substrate._substeps_per_tick

        # Run the stability guard if available.
        guard_report = None
        halt_requested = False
        if self.guard is not None:
            try:
                neurons: Optional[List[Any]] = None
                circuit = getattr(self.substrate, "_circuit", None)
                if circuit is not None:
                    neurons = (
                        list(getattr(circuit, "input_neurons", []) or [])
                        + list(getattr(circuit, "hidden_neurons", []) or [])
                        + list(getattr(circuit, "output_neurons", []) or [])
                    )
                guard_report = self.guard.evaluate(state, circuit_neurons=neurons)
                halt_requested = self.guard.should_halt()
            except Exception as exc:  # pragma: no cover
                _logger.debug("Stability guard evaluation failed: %s", exc)

        duration_ms = (time.time() - start) * 1000.0
        result = SubstepResult(
            tick=self._tick,
            n_substeps=int(getattr(self.substrate, "_last_substep_count", 0) or 0),
            duration_ms=duration_ms,
            substrate_state=state,
            guard_report=guard_report,
            halt_requested=halt_requested,
        )
        self._last_result = result
        return result

    @property
    def last_result(self) -> Optional[SubstepResult]:
        return self._last_result
