"""BenchmarkRunner — neurofunctional + ARC-AGI benchmark orchestration.

Wraps the existing ``NeuroFunctionalBenchmark`` (in
``speace_core/cellular_brain/benchmark``) and computes an aggregate
AGI-percentage from component scores.

The runner never mutates production code: it is read-only or operates
inside the existing benchmark sandbox.
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


# Each component contributes 0..1; weight is the AGI-% weight (sum = 1.0).
AGI_COMPONENTS: Dict[str, float] = {
    "adaptation_after_error": 0.20,
    "useful_neurogenesis": 0.15,
    "useful_apoptosis": 0.10,
    "differentiation_consistency": 0.10,
    "morphological_memory_trace": 0.10,
    "arc_agi_subset": 0.25,
    "regulation_stability": 0.10,
}


class BenchmarkRunner:
    """Run neurofunctional cases + ARC subset, return an AGI %."""

    CASES: List[str] = [
        "adaptation_after_error",
        "useful_neurogenesis",
        "useful_apoptosis",
        "differentiation_consistency",
        "morphological_memory_trace",
    ]

    def __init__(self, data_root: str | Path = "data") -> None:
        self.data_root = Path(data_root)
        self.reports_dir = self.data_root / "evolution_daemon" / "benchmarks"
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # AGI percentage
    # ------------------------------------------------------------------ #
    def compute_agi_percentage(self, components: Dict[str, float]) -> float:
        """Return a 0..100 AGI-% from per-component scores (each 0..1)."""
        score = 0.0
        for k, weight in AGI_COMPONENTS.items():
            score += weight * max(0.0, min(1.0, components.get(k, 0.0)))
        return round(score * 100.0, 2)

    async def run_agi_percentage_async(
        self,
        orchestrator: Optional[Any] = None,
        arc_results: Optional[Dict[str, Any]] = None,
        regulation_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Async variant: runs neurofunctional cases in the current loop."""
        components: Dict[str, float] = {}
        details: Dict[str, Any] = {}
        if orchestrator is not None:
            try:
                components, details = await self._run_neurofunctional(orchestrator)
            except Exception as exc:  # pragma: no cover
                logger.warning("neurofunctional benchmark failed: %s", exc)
                components = {}
        if regulation_score is None:
            regulation_score = self._read_regulation_score()
        components["regulation_stability"] = float(regulation_score)
        if arc_results is None:
            arc_results = self._read_arc_results()
        components["arc_agi_subset"] = _arc_to_score(arc_results)
        details["arc_agi_subset"] = arc_results
        for k in self.CASES:
            components.setdefault(k, 0.0)
        components.setdefault("arc_agi_subset", 0.0)
        components.setdefault("regulation_stability", 0.0)
        agi = self.compute_agi_percentage(components)
        report = {
            "report_id": f"agi-{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agi_percentage": agi,
            "components": {k: round(v, 4) for k, v in components.items()},
            "weights": AGI_COMPONENTS,
            "details": details,
        }
        try:
            (self.reports_dir / f"{report['report_id']}.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
            (self.reports_dir / "latest.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
        except OSError as exc:  # pragma: no cover
            logger.warning("persist benchmark report: %s", exc)
        return report

    def run_agi_percentage(
        self,
        orchestrator: Optional[Any] = None,
        arc_results: Optional[Dict[str, Any]] = None,
        regulation_score: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Run all benchmark components and return AGI %.

        Tries to use the in-memory ``orchestrator`` when available; falls
        back to a static scoreboard (read from latest reports) otherwise.
        """
        components: Dict[str, float] = {}
        details: Dict[str, Any] = {}

        if orchestrator is not None:
            try:
                components, details = asyncio_run(
                    self._run_neurofunctional(orchestrator)
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("neurofunctional benchmark failed: %s", exc)
                components = {}

        # Regulation score
        if regulation_score is None:
            regulation_score = self._read_regulation_score()
        components["regulation_stability"] = float(regulation_score)

        # ARC results
        if arc_results is None:
            arc_results = self._read_arc_results()
        arc_score = _arc_to_score(arc_results)
        components["arc_agi_subset"] = arc_score
        details["arc_agi_subset"] = arc_results

        # Fill missing components from last known report
        for k in self.CASES:
            components.setdefault(k, 0.0)
        components.setdefault("arc_agi_subset", 0.0)
        components.setdefault("regulation_stability", 0.0)

        agi = self.compute_agi_percentage(components)
        report = {
            "report_id": f"agi-{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agi_percentage": agi,
            "components": {k: round(v, 4) for k, v in components.items()},
            "weights": AGI_COMPONENTS,
            "details": details,
        }
        # Persist report
        try:
            with (self.reports_dir / f"{report['report_id']}.json").open(
                "w", encoding="utf-8"
            ) as f:
                json.dump(report, f, indent=2)
            latest = self.reports_dir / "latest.json"
            latest.write_text(json.dumps(report, indent=2))
        except OSError as exc:  # pragma: no cover
            logger.warning("persist benchmark report: %s", exc)
        return report

    # ------------------------------------------------------------------ #
    # Neurofunctional
    # ------------------------------------------------------------------ #
    async def _run_neurofunctional(self, orchestrator: Any) -> Any:
        from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import (
            NeuroFunctionalBenchmark,
        )

        bench = NeuroFunctionalBenchmark(orchestrator=orchestrator)
        components: Dict[str, float] = {}
        details: Dict[str, Any] = {}
        for case in self.CASES:
            try:
                res = await bench.run_case(case_name=case)
                acc = float(res.metrics.accuracy_score or 0.0)
                phi = float(res.metrics.coherence_phi or 0.0)
                score = max(0.0, min(1.0, 0.6 * acc + 0.4 * max(0.0, min(1.0, phi))))
                components[case] = score
                details[case] = {
                    "accuracy": acc,
                    "coherence_phi": phi,
                    "morphological_stability": float(
                        res.metrics.morphological_stability or 0.0
                    ),
                }
            except Exception as exc:  # pragma: no cover
                logger.warning("case %s failed: %s", case, exc)
                components[case] = 0.0
                details[case] = {"error": str(exc)}
        return components, details

    # ------------------------------------------------------------------ #
    # ARC + regulation helpers
    # ------------------------------------------------------------------ #
    def _read_arc_results(self) -> Dict[str, Any]:
        path = self.data_root / "evolution_daemon" / "arc" / "latest.json"
        if not path.exists():
            return {"status": "missing", "accuracy": 0.0}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"status": "missing", "accuracy": 0.0}

    def _read_regulation_score(self) -> float:
        """Compute regulation stability score in [0,1].

        A higher score means a more stable regulation compartment. The
        JSONL stream stores ``severity`` as a non-negative real number
        that may exceed 1.0 (the value reflects the magnitude of the
        intervention's required dampening). We map severity → score
        via ``score = 1 / (1 + severity)`` (smooth, saturating) and
        weight the most recent entries more heavily than older ones.
        """
        path = self.data_root / "regulation" / "stabilizer_interventions.jsonl"
        if not path.exists():
            return 0.0
        try:
            severities: List[float] = []
            weights: List[float] = []
            with path.open("r", encoding="utf-8") as f:
                for ln in f:
                    try:
                        obj = json.loads(ln)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    try:
                        s = float(obj.get("severity", 0.0) or 0.0)
                    except (TypeError, ValueError):
                        continue
                    severities.append(s)
                    weights.append(1.0)
            if not severities:
                return 0.0
            # Decay the tail of the list (most recent entries are at
            # the end of the JSONL).
            tail = severities[-200:]
            w_tail = [1.0 + i * 0.01 for i in range(len(tail))]
            total = sum(w * (1.0 / (1.0 + s)) for s, w in zip(tail, w_tail))
            denom = sum(w_tail) or 1.0
            return max(0.0, min(1.0, total / denom))
        except OSError:
            return 0.0


# --------------------------------------------------------------------------- #
# Sync helper: run async coroutine in a private loop.
# --------------------------------------------------------------------------- #
def asyncio_run(coro: Any) -> Any:
    import asyncio

    try:
        loop = asyncio.new_event_loop()
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.close()
        except Exception:  # pragma: no cover
            pass


def _arc_to_score(arc: Dict[str, Any]) -> float:
    if not arc:
        return 0.0
    if arc.get("status") in ("missing", "failed"):
        return 0.0
    acc = float(arc.get("accuracy", 0.0) or 0.0)
    solved = int(arc.get("solved", 0) or 0)
    total = max(1, int(arc.get("total", 1) or 1))
    rate = solved / total
    return max(0.0, min(1.0, 0.5 * acc + 0.5 * rate))


def _grids_equal(a: Any, b: Any) -> bool:
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


def _pixel_accuracy(pred: Any, target: Any) -> float:
    if not isinstance(pred, list) or not isinstance(target, list):
        return 0.0
    if len(pred) != len(target):
        return 0.0
    total = 0
    correct = 0
    for rp, rt in zip(pred, target):
        if not isinstance(rp, list) or not isinstance(rt, list) or len(rp) != len(rt):
            return 0.0
        total += len(rp)
        correct += sum(1 for p, t in zip(rp, rt) if p == t)
    return correct / total if total > 0 else 0.0
