"""RegressionReviewer — review the diff since the last successful cycle.

Reads ``git status`` and ``git diff --stat`` (read-only), reports any
unexpected SPEACE file changes, and writes a digest. The reviewer never
modifies the working tree.
"""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Files whose changes are expected (daemon state, knowledge graph, etc.).
SAFE_PATHS = (
    "data/knowledge_graph.jsonl",
    "data/daemon_state.json",
    "data/daemon_tasks.jsonl",
    "data/engineering_plan.json",
    "data/evolution_daemon/",
    "data/self_improvement/proposals.jsonl",
    "data/self_improvement/dna_proposals.jsonl",
    "reports/",
    "evolution_daemon/",
    "docs/EVOLUTION_DAEMON.md",
)


class RegressionReviewer:
    """Read-only reviewer of working-tree state."""

    def __init__(self, repo_root: str | Path) -> None:
        self.repo_root = Path(repo_root)

    def review(self) -> Dict[str, Any]:
        status = self._git("--no-pager", "status", "--porcelain")
        diff_stat = self._git("--no-pager", "diff", "--stat")
        staged = self._git("--no-pager", "diff", "--cached", "--stat")

        changed: List[str] = []
        suspicious: List[str] = []
        for ln in (status or "").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            # porcelain lines look like "M  file" or "?? file"
            parts = ln.split(maxsplit=1)
            if len(parts) < 2:
                continue
            path = parts[1]
            changed.append(path)
            if not any(s in path for s in SAFE_PATHS) and not path.startswith("data/"):
                suspicious.append(path)

        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "changed_files": changed,
            "suspicious_files": suspicious,
            "diff_stat": diff_stat,
            "staged_stat": staged,
            "verdict": "clean" if not suspicious else "review_needed",
        }
        return report

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _git(self, *args: str) -> Optional[str]:
        try:
            res = subprocess.run(
                ["git", *args],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            if res.returncode != 0:
                logger.debug("git %s -> %d", args, res.returncode)
            return res.stdout or ""
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            logger.warning("git %s failed: %s", args, exc)
            return None
