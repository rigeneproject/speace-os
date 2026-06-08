"""EngineeringPlan — regenerable plan for SPEACE → AGI.

Stored as ``data/engineering_plan.json``. Each cycle the daemon
re-derives a plan from:
  - the current AGI %
  - the diagnostics state
  - the latest proposals
  - the static milestones below
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


MILESTONES: List[Dict[str, Any]] = [
    {"id": "M-AGI-10", "label": "AGI % ≥ 10 — operational cognition loop"},
    {"id": "M-AGI-25", "label": "AGI % ≥ 25 — multi-axis reasoning"},
    {"id": "M-AGI-50", "label": "AGI % ≥ 50 — fluid concept integration"},
    {"id": "M-AGI-75", "label": "AGI % ≥ 75 — robust abstraction & transfer"},
    {"id": "M-AGI-100", "label": "AGI % = 100 — full self-directed cognition"},
]


class EngineeringPlan:
    """Read/write/regenerate the SPEACE → AGI engineering plan."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def regenerate(
        self,
        agi_percentage: float,
        diagnostics: Optional[Dict[str, Any]] = None,
        proposals: Optional[List[Dict[str, Any]]] = None,
        ari_percentage: Optional[float] = None,
        ari_components: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        diagnostics = diagnostics or {}
        proposals = proposals or []

        plan = {
            "version": 2,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "current_agi_percentage": float(agi_percentage),
            "current_ari_percentage": (
                float(ari_percentage) if ari_percentage is not None else None
            ),
            "milestones": self._milestone_progress(agi_percentage),
            "ari_roadmap": self._ari_roadmap(ari_components or {}),
            "capability_gaps": self._capability_gaps(ari_components or {}, diagnostics),
            "next_objectives": self._next_objectives(
                agi_percentage, diagnostics, ari_components or {}
            ),
            "open_proposals": [
                {
                    "proposal_id": p.get("proposal_id", ""),
                    "title": p.get("title", ""),
                    "category": p.get("category", ""),
                }
                for p in proposals
            ],
            "constraints": [
                "T104 governance: human approval for all changes",
                "Log + proposal only (no auto-apply)",
                "Cycle interval: 300 s",
                "Budget: 40% benchmark/diagnostics, 40% cognitive dev, 20% refactor",
            ],
        }
        self._write(plan)
        return plan

    def read(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"version": 0, "current_agi_percentage": 0.0, "milestones": []}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"version": 0, "current_agi_percentage": 0.0, "milestones": []}

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _milestone_progress(self, agi: float) -> List[Dict[str, Any]]:
        out = []
        for m in MILESTONES:
            threshold = float(m["id"].split("-")[-1])
            out.append(
                {
                    **m,
                    "threshold": threshold,
                    "achieved": agi >= threshold,
                }
            )
        return out

    def _next_objectives(
        self,
        agi: float,
        diagnostics: Dict[str, Any],
        ari_components: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        ari_components = ari_components or {}
        objs: List[Dict[str, Any]] = []
        compartments = diagnostics.get("compartments") or {}
        for name, comp in compartments.items():
            if comp.get("status") in ("watch", "alert"):
                objs.append(
                    {
                        "title": f"Stabilise {name} compartment",
                        "category": "diagnostics",
                        "rationale": f"Status={comp.get('status')}",
                    }
                )
        # ARI axis prioritisation (highest-impact first)
        ari_order = [
            ("arc_score", 0.20),
            ("generalization", 0.15),
            ("memory_integration", 0.15),
            ("self_improvement", 0.10),
            ("planning", 0.10),
            ("robustness", 0.10),
            ("knowledge_graph_coherence", 0.10),
            ("autonomy", 0.10),
        ]
        targets = {
            "arc_score": 0.30,
            "generalization": 0.85,
            "memory_integration": 0.85,
            "self_improvement": 0.60,
            "planning": 0.85,
            "robustness": 0.95,
            "knowledge_graph_coherence": 0.85,
            "autonomy": 0.90,
        }
        for axis, weight in ari_order:
            cur = float(ari_components.get(axis, 0.0) or 0.0)
            if cur < targets[axis]:
                objs.append(
                    {
                        "title": f"ARI axis '{axis}': lift from {cur:.2f} to ≥{targets[axis]:.2f}",
                        "category": "ari_alignment",
                        "weight": weight,
                        "rationale": f"weight={weight}, current={cur:.2f}",
                    }
                )
        if not objs:
            objs.append(
                {
                    "title": "Push abstraction transfer & self-directed learning",
                    "category": "research",
                    "rationale": "All ARI axes near target",
                }
            )
        return objs

    # ------------------------------------------------------------------ #
    # ARI roadmap + capability gaps (version 2)
    # ------------------------------------------------------------------ #
    ARI_TARGETS: Dict[str, Dict[str, Any]] = {
        "arc_score": {
            "current_target": 0.30,
            "next_target": 0.50,
            "rationale": "ARC is the highest-weighted ARI axis (0.20). 30%+ requires the FSPI engine to produce non-zero candidates on at least the trivial ARC primitives (rotate / flip / fill).",
        },
        "generalization": {
            "current_target": 0.85,
            "next_target": 0.95,
            "rationale": "Already strong. Keep AGI% variance low across cycles.",
        },
        "memory_integration": {
            "current_target": 0.85,
            "next_target": 0.95,
            "rationale": "Workspace active_items and ignition_score are both 0; needs the cognitive subsystem to feed live ignition events into the snapshot.",
        },
        "self_improvement": {
            "current_target": 0.60,
            "next_target": 0.80,
            "rationale": "Slope-based measure; improve by completing at least one cycle that produces a measurable AGI delta.",
        },
        "planning": {
            "current_target": 0.85,
            "next_target": 0.95,
            "rationale": "Task generator already produces 8 well-prioritised tasks per cycle.",
        },
        "robustness": {
            "current_target": 0.95,
            "next_target": 1.00,
            "rationale": "No errors observed. Maintain during refactors.",
        },
        "knowledge_graph_coherence": {
            "current_target": 0.85,
            "next_target": 0.95,
            "rationale": "Recency OK (0.80 from cycle activity). Density can grow by adding per-module dependencies and capability gap nodes.",
        },
        "autonomy": {
            "current_target": 0.90,
            "next_target": 1.00,
            "rationale": "Runtime reports 'started'; full autonomy means orchestrator+runtime stay up across cycles without restart.",
        },
    }

    def _ari_roadmap(self, comps: Dict[str, float]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for axis, t in self.ARI_TARGETS.items():
            cur = float(comps.get(axis, 0.0) or 0.0)
            out.append(
                {
                    "axis": axis,
                    "current": round(cur, 4),
                    "current_target": t["current_target"],
                    "next_target": t["next_target"],
                    "rationale": t["rationale"],
                }
            )
        return out

    def _capability_gaps(
        self, comps: Dict[str, float], diagnostics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        gaps: List[Dict[str, Any]] = []
        # Compartment-level
        compartments = diagnostics.get("compartments") or {}
        for name, comp in compartments.items():
            if comp.get("status") in ("watch", "alert", "idle", "no_data"):
                gaps.append(
                    {
                        "gap_id": f"compartment:{name}",
                        "title": f"Stabilise {name} compartment",
                        "severity": (
                            "high"
                            if comp.get("status") == "alert"
                            else "medium"
                            if comp.get("status") == "watch"
                            else "low"
                        ),
                        "category": "diagnostics",
                        "rationale": f"status={comp.get('status')}",
                    }
                )
        # ARI axis-level
        for axis, t in self.ARI_TARGETS.items():
            cur = float(comps.get(axis, 0.0) or 0.0)
            if cur < t["current_target"]:
                gaps.append(
                    {
                        "gap_id": f"ari-axis:{axis}",
                        "title": f"Improve ARI axis '{axis}' (current {cur:.2f} < target {t['current_target']:.2f})",
                        "severity": "high" if cur + 0.2 < t["current_target"] else "medium",
                        "category": "ari_alignment",
                        "rationale": t["rationale"],
                    }
                )
        return gaps

    def _write(self, plan: Dict[str, Any]) -> None:
        try:
            self.path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        except OSError as exc:  # pragma: no cover
            logger.warning("write engineering plan: %s", exc)
