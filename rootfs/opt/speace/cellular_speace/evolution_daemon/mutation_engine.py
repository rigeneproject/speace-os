"""MutationEngine — proposes refactors / DNA / architectural changes.

This engine is *advisory only*: it never mutates source code. All
proposals are emitted as ``ArchitectureRewriteProposal`` instances via
``ProposalStore`` (existing) and saved to
``data/self_improvement/proposals.jsonl`` for human review (T124).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Heuristic refactor candidates — produced on every cycle. They are
# *suggestions*, not patches.
REFACTOR_CATALOG: List[Dict[str, str]] = [
    {
        "id": "refactor-extract-config-loader",
        "title": "Extract genome loader into reusable helper",
        "rationale": "Repeated boilerplate ``load_genome(...)`` in CLI + scripts.",
        "files_hint": "speace_core/cli.py, scripts/*.py",
    },
    {
        "id": "refactor-merge-stdp-config",
        "title": "Merge STDP plasticity toggles into a single dataclass",
        "rationale": "Multiple boolean flags scattered across orchestrator.",
        "files_hint": "speace_core/orchestrator.py",
    },
    {
        "id": "refactor-cache-dashboard-reader",
        "title": "Cache DashboardStateReader per request",
        "rationale": "Avoid re-instantiating per HTTP call.",
        "files_hint": "speace_core/dashboard/server.py",
    },
]


class MutationEngine:
    """Generates proposals via heuristics + LimitationDetector.

    The output of ``propose_refactors`` is a list of dictionaries, each
    representing a proposal. They are also forwarded to
    ``ProposalStore`` if available.
    """

    def __init__(self, data_root: str | Path = "data") -> None:
        self.data_root = Path(data_root)
        self.proposals_log = self.data_root / "self_improvement" / "proposals.jsonl"
        self.proposals_log.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Refactor proposals
    # ------------------------------------------------------------------ #
    def propose_refactors(
        self,
        metrics: Optional[Dict[str, Any]] = None,
        diagnostics: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Emit a set of refactor proposals for the cycle."""
        metrics = metrics or {}
        diagnostics = diagnostics or {}
        proposals: List[Dict[str, Any]] = []

        for base in REFACTOR_CATALOG:
            p = dict(base)
            p["proposal_id"] = f"proposal-{uuid.uuid4().hex[:8]}"
            p["created_at"] = datetime.now(timezone.utc).isoformat()
            p["category"] = "refactor"
            p["auto_apply"] = False
            p["status"] = "pending_human_approval"
            p["trigger"] = "evolution_daemon_heuristic"
            p["context"] = {
                "coherence_phi": float(metrics.get("coherence_phi", 0.0)),
                "diagnostics_alert": int(diagnostics.get("alert", 0)),
            }
            proposals.append(p)

        # Dynamic proposals derived from diagnostics
        compartments = (diagnostics or {}).get("compartments", {}) or {}
        for name, comp in compartments.items():
            if comp.get("status") == "alert":
                proposals.append(
                    {
                        "proposal_id": f"proposal-{uuid.uuid4().hex[:8]}",
                        "title": f"Investigate compartment {name}",
                        "rationale": f"Compartment {name} in alert state.",
                        "category": "investigation",
                        "files_hint": f"speace_core/cellular_brain/.../{name}",
                        "auto_apply": False,
                        "status": "pending_human_approval",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "trigger": "diagnostic_alert",
                    }
                )

        self._append_to_log(proposals)
        return proposals

    # ------------------------------------------------------------------ #
    # Limitation-detector bridge
    # ------------------------------------------------------------------ #
    def detect_limitations(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Bridge to ``LimitationDetector`` if present, else empty list."""
        try:
            from speace_core.cellular_brain.self_improvement.limitation_detector import (
                LimitationDetector,
            )

            detector = LimitationDetector()
            signals = detector.detect_from_metrics(metrics)
            return [
                {
                    "category": getattr(s, "category", "unknown"),
                    "urgency": float(getattr(s, "urgency", 0.0)),
                    "message": getattr(s, "message", ""),
                }
                for s in signals
            ]
        except Exception as exc:  # pragma: no cover
            logger.debug("limitation_detector not available: %s", exc)
            return []

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _append_to_log(self, proposals: List[Dict[str, Any]]) -> None:
        try:
            with self.proposals_log.open("a", encoding="utf-8") as f:
                for p in proposals:
                    f.write(json.dumps(p) + "\n")
        except OSError as exc:  # pragma: no cover
            logger.warning("append proposals: %s", exc)
