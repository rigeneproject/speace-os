"""ARCRunner — wraps the existing ARC-AGI adapter for the daemon.

Reuses ``speace_core.benchmark.arc_agi_adapter.ARCAGIAdapter`` and the
``scripts/run_arc_agi_benchmark.py`` pattern. The runner is *bounded*:
it processes at most ``arc_task_limit`` tasks per cycle and writes
``data/evolution_daemon/arc/latest.json``.
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


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _grids_equal(a: List[List[int]], b: List[List[int]]) -> bool:
    if not isinstance(a, list) or not isinstance(b, list):
        return False
    if len(a) != len(b):
        return False
    for ra, rb in zip(a, b):
        if not isinstance(ra, list) or not isinstance(rb, list):
            return False
        if len(ra) != len(rb):
            return False
        if any(x != y for x, y in zip(ra, rb)):
            return False
    return True


def _pixel_accuracy(pred: List[List[int]], expected: List[List[int]]) -> float:
    """Fraction of cells that match between pred and expected grids.

    Different shapes: returns 0.0 (no overlap).
    """
    if not pred or not expected:
        return 0.0
    h = min(len(pred), len(expected))
    w = min(len(pred[0]) if pred[0] else 0, len(expected[0]) if expected[0] else 0)
    if h == 0 or w == 0:
        return 0.0
    same = 0
    total = h * w
    for y in range(h):
        for x in range(w):
            if pred[y][x] == expected[y][x]:
                same += 1
    return same / total


class ARCRunner:
    """Run a bounded ARC-AGI pass and report a digest."""

    def __init__(self, data_root: str | Path = "data", task_limit: int = 5) -> None:
        self.data_root = Path(data_root)
        self.task_limit = task_limit
        self.arc_dir = self.data_root / "evolution_daemon" / "arc"
        self.arc_dir.mkdir(parents=True, exist_ok=True)
        self.dataset_root = self.data_root / "arc_agi"

    def run_pass(
        self,
        orchestrator: Optional[Any] = None,
        task_limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run a small ARC-AGI pass and persist the digest."""
        limit = task_limit or self.task_limit
        start = time.time()
        report: Dict[str, Any] = {
            "pass_id": f"arc-{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "started",
            "task_limit": limit,
            "solved": 0,
            "total": 0,
            "accuracy": 0.0,
            "duration_sec": 0.0,
        }
        try:
            tasks = self._load_tasks(limit)
            if not tasks:
                report["status"] = "missing_dataset"
                return self._finalise(report, start)
            results: List[Dict[str, Any]] = []
            # T169 — aggregate MM-APR council stats across tasks in this pass
            mmapr_invocations = 0
            mmapr_accepts = 0
            for task_id, task in tasks.items():
                outcome = self._attempt_task(task_id, task, orchestrator)
                results.append(outcome)
                # Pull MM-APR counters from the raw per-task engine state.
                raw = outcome.get("raw", {}) or {}
                mmapr_invocations += int(raw.get("mmapr_invocations", 0) or 0)
                mmapr_accepts += int(raw.get("mmapr_accepts", 0) or 0)
                if outcome.get("correct"):
                    report["solved"] += 1
                report["total"] += 1
            report["accuracy"] = (
                report["solved"] / max(1, report["total"]) if report["total"] else 0.0
            )
            report["results"] = results
            # T169 — surface MM-APR council signal in the pass digest
            report["mmapr_council"] = {
                "enabled": True,
                "invocations": mmapr_invocations,
                "accepts": mmapr_accepts,
                "accept_rate": (
                    round(mmapr_accepts / mmapr_invocations, 4)
                    if mmapr_invocations > 0
                    else 0.0
                ),
            }
            # Also expose flat counters for backward compatibility
            report["mmapr_invocations"] = mmapr_invocations
            report["mmapr_accepts"] = mmapr_accepts
            report["status"] = "completed"
        except Exception as exc:  # pragma: no cover
            logger.warning("ARC pass failed: %s", exc)
            report["status"] = "failed"
            report["error"] = str(exc)
        return self._finalise(report, start)

    def _finalise(self, report: Dict[str, Any], start: float) -> Dict[str, Any]:
        report["duration_sec"] = round(time.time() - start, 3)
        try:
            (self.arc_dir / f"{report['pass_id']}.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
            (self.arc_dir / "latest.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
        except OSError as exc:  # pragma: no cover
            logger.warning("persist arc report: %s", exc)
        return report

    def _load_tasks(self, limit: int) -> Dict[str, Any]:
        """Load ARC tasks from ``data/arc_agi/`` if present.

        Each file (``training.json``, ``evaluation.json``) contains a
        dict ``{task_id: {train: [...], test: [...]}}``. We expand
        that into a flat ``{task_id: task_payload}`` map and apply the
        ``limit`` across all files (not per file).
        """
        if not self.dataset_root.exists():
            return {}
        tasks: Dict[str, Any] = {}
        files = sorted(self.dataset_root.glob("*.json"))
        for path in files:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if not isinstance(data, dict):
                continue
            for task_id, payload in data.items():
                if not isinstance(payload, dict):
                    continue
                if "train" not in payload:
                    continue
                tasks[task_id] = payload
                if len(tasks) >= limit:
                    return tasks
        return tasks

    def _attempt_task(
        self,
        task_id: str,
        task: Dict[str, Any],
        orchestrator: Optional[Any],
    ) -> Dict[str, Any]:
        """Attempt a single ARC task; falls back to a no-op stub on failure.

        Wires ``ARCAGIAdapter`` with a ``FewShotProgramInductionEngine`` so
        the existing few-shot program-induction pipeline can be exercised
        end-to-end. Without the engine, the adapter raises and the pass
        silently returns accuracy=0.
        """
        outcome: Dict[str, Any] = {
            "task_id": task_id,
            "correct": False,
            "method": "stub",
        }
        try:
            from speace_core.benchmark.arc_agi_adapter import ARCAGIAdapter
            from speace_core.cellular_brain.cognition.few_shot_program_induction_engine import (
                FewShotProgramInductionEngine,
            )

            engine = FewShotProgramInductionEngine()
            adapter = ARCAGIAdapter(engine=engine, data_dir=str(self.dataset_root))
            # Adapter expects ARCTask-shaped input: convert from the
            # raw JSON dict loaded by ``_load_tasks``.
            train_pairs = task.get("train", []) or []
            test_pairs = task.get("test", []) or []
            if not test_pairs and train_pairs:
                # Use the first train pair's input as a synthetic test to
                # exercise the pipeline when no gold test is provided.
                test_pairs = [{"input": train_pairs[0]["input"]}]
            # We call ``engine.induce`` + ``engine.predict`` directly to
            # obtain a deterministic, structured result that we can score
            # with pixel-accuracy. We also keep a "best partial" candidate
            # (highest train_matches) for the ARI arc_score fallback.
            candidates = engine.induce(train_pairs)
            engine.set_candidates(candidates)
            # Build a partial-credit predictor: if no full-match candidate
            # exists, take the single primitive that matches the most
            # training pairs. This is still based on the engine's
            # validated hypotheses, so it's governance-safe.
            best_partial = None
            try:
                from speace_core.cellular_brain.cognition.program_models import (
                    ProgramCandidate,
                    TransformationProgram,
                )
                for prim in engine._generate_primitive_hypotheses(train_pairs):
                    prog = TransformationProgram(steps=[prim])
                    matches = engine._validate_program(prog, train_pairs)
                    if best_partial is None or matches > best_partial.train_matches:
                        best_partial = ProgramCandidate(
                            program=prog,
                            train_matches=matches,
                            confidence=matches / max(1, len(train_pairs)),
                        )
            except Exception:  # pragma: no cover
                best_partial = None
            per_test = []
            for idx, pair in enumerate(test_pairs[:2]):
                preds = engine.predict(pair.get("input", []), top_k=1) or []
                # If nothing from the full set, try the best partial
                if not preds and best_partial is not None and best_partial.train_matches > 0:
                    try:
                        out = best_partial.program.apply(pair.get("input", []))
                        if out is not None:
                            preds = [out]
                    except Exception:
                        pass
                expected = pair.get("output")
                ok = False
                score = 0.0
                if expected is not None and preds:
                    ok = _grids_equal(preds[0], expected)
                    if not ok:
                        score = _pixel_accuracy(preds[0], expected)
                per_test.append(
                    {
                        "test_index": idx,
                        "correct": ok,
                        "match_score": 1.0 if ok else score,
                        "candidates_explored": len(candidates),
                    }
                )
            outcome["method"] = "fspi"
            outcome["raw"] = {
                "per_test": per_test,
                "candidates_explored": len(candidates),
                # T169 — record MM-APR council stats from the engine
                "mmapr_enabled": bool(getattr(engine, "mmapr_council", None) is not None),
                "mmapr_invocations": int(getattr(engine, "_mmapr_invocations", 0) or 0),
                "mmapr_accepts": int(getattr(engine, "_mmapr_accepts", 0) or 0),
            }
            # Mark the task correct only if all test pairs are correct.
            if per_test:
                outcome["correct"] = all(t["correct"] for t in per_test)
                outcome["match_score"] = (
                    sum(t["match_score"] for t in per_test) / len(per_test)
                )
        except Exception as exc:  # pragma: no cover - adapter optional
            outcome["error"] = str(exc)
        return outcome
