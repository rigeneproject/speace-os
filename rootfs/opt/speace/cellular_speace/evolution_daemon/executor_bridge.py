"""ExecutorBridge — bridges daemon cycles to the existing SPEACE
self-improvement machinery.

Wraps ``SelfImprovementLoop`` and ``ProposalStore`` to provide a single
``execute_cycle`` entry point that the daemon can call without knowing
the internal wiring.

Per T104 governance, the bridge does *not* auto-apply patches — it
produces proposals and persists them.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExecutorBridge:
    """Thin facade over the existing self-improvement loop."""

    def __init__(self, orchestrator: Optional[Any] = None) -> None:
        self.orchestrator = orchestrator
        self._loop: Optional[Any] = None

    # ------------------------------------------------------------------ #
    # Lazy wiring
    # ------------------------------------------------------------------ #
    def _get_loop(self) -> Any:
        if self._loop is None:
            from speace_core.cellular_brain.self_improvement.self_improvement_loop import (
                SelfImprovementLoop,
            )

            self._loop = SelfImprovementLoop(orchestrator=self.orchestrator)
        return self._loop

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def execute_cycle(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Run a single self-improvement detection cycle.

        Returns the cycle result as a dict (or a stub when the orchestrator
        is missing).
        """
        try:
            loop = self._get_loop()
            result = loop.run_detection_cycle(metrics=metrics)
            return {
                "cycle_id": getattr(result, "cycle_id", "n/a"),
                "diagnoses": len(getattr(result, "diagnoses", []) or []),
                "proposals": len(getattr(result, "proposals", []) or []),
                "accepted": len(getattr(result, "accepted", []) or []),
                "rejected": len(getattr(result, "rejected", []) or []),
                "verdict": getattr(result, "verdict", ""),
            }
        except Exception as exc:  # pragma: no cover
            logger.warning("executor_bridge cycle failed: %s", exc)
            return {"status": "stub", "diagnoses": 0, "proposals": 0, "error": str(exc)}
