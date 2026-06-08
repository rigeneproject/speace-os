"""TaskGenerator — creates the per-cycle task list and the AGI plan.

Generates tasks for ``TaskCreate``-style tracking (persisted to
``data/daemon_tasks.jsonl``) and feeds the EngineeringPlan. All output
is *advisory* — no autonomous code execution.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Catalogue of generic next-iteration task templates.
TASK_TEMPLATES: List[Dict[str, str]] = [
    {
        "title": "Run neurofunctional benchmark cycle",
        "category": "benchmark",
        "priority": "high",
    },
    {
        "title": "Execute ARC-AGI subset pass",
        "category": "arc_agi",
        "priority": "high",
    },
    {
        "title": "Update Knowledge Graph with new proposals",
        "category": "knowledge_graph",
        "priority": "medium",
    },
    {
        "title": "Regenerate Engineering Plan toward AGI",
        "category": "engineering_plan",
        "priority": "medium",
    },
    {
        "title": "Diagnose compartments with alert status",
        "category": "diagnostics",
        "priority": "high",
    },
    {
        "title": "Count neurons/synapses and snapshot activation",
        "category": "neuron_synapse",
        "priority": "medium",
    },
    {
        "title": "Detect and propose fixes for runtime errors",
        "category": "error_correction",
        "priority": "high",
    },
    {
        "title": "Review pending diffs for regressions",
        "category": "regression",
        "priority": "medium",
    },
]


class TaskGenerator:
    """Emit a task list per cycle and persist it."""

    def __init__(self, data_root: str | Path = "data") -> None:
        self.data_root = Path(data_root)
        self.tasks_path = self.data_root / "daemon_tasks.jsonl"
        self.tasks_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def next_iteration(
        self,
        cycle_id: Optional[str] = None,
        diagnostics: Optional[Dict[str, Any]] = None,
        agi_percentage: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Return a list of tasks for the current iteration."""
        cycle_id = cycle_id or f"cycle-{uuid.uuid4().hex[:6]}"
        diagnostics = diagnostics or {}
        tasks: List[Dict[str, Any]] = []
        for tpl in TASK_TEMPLATES:
            task = dict(tpl)
            task["task_id"] = f"task-{uuid.uuid4().hex[:8]}"
            task["cycle_id"] = cycle_id
            task["created_at"] = datetime.now(timezone.utc).isoformat()
            task["status"] = "pending"
            task["context"] = {
                "agi_percentage": float(agi_percentage),
                "diagnostics_alert": int(diagnostics.get("alert", 0)),
            }
            tasks.append(task)

        # Compartment-targeted tasks
        for name, comp in (diagnostics.get("compartments") or {}).items():
            if comp.get("status") == "alert":
                tasks.append(
                    {
                        "task_id": f"task-{uuid.uuid4().hex[:8]}",
                        "cycle_id": cycle_id,
                        "title": f"Investigate alert in compartment: {name}",
                        "category": "diagnostics",
                        "priority": "high",
                        "status": "pending",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "context": {"compartment": name, "compartment_status": comp},
                    }
                )

        self._append(tasks)
        return tasks

    def load_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.tasks_path.exists():
            return []
        out: List[Dict[str, Any]] = []
        try:
            with self.tasks_path.open("r", encoding="utf-8") as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        out.append(json.loads(ln))
                    except json.JSONDecodeError:
                        continue
        except OSError as exc:  # pragma: no cover
            logger.warning("load_history: %s", exc)
        return out[-limit:]

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _append(self, tasks: List[Dict[str, Any]]) -> None:
        try:
            with self.tasks_path.open("a", encoding="utf-8") as f:
                for t in tasks:
                    f.write(json.dumps(t) + "\n")
        except OSError as exc:  # pragma: no cover
            logger.warning("append tasks: %s", exc)
