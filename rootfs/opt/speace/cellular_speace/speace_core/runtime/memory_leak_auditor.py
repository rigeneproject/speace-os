"""MemoryLeakAuditor — detect and diagnose memory leaks during long runs (T113).

Tracks object growth, file-descriptor usage, and cumulative data-structure
sizes. Read-only; produces diagnostic snapshots.
"""

import gc
import json
import logging
import pathlib
import time
from collections import Counter
from typing import Any, Dict, List, Optional


class MemoryLeakAuditor:
    """Audits memory usage over extended runtime sessions."""

    # Cap on retained reports to prevent unbounded growth between
    # save_reports() calls (operator may forget to flush for hours).
    _MAX_RETAINED_REPORTS = 256

    def __init__(
        self,
        sample_interval_seconds: float = 300.0,
        top_objects: int = 20,
        narrative_engine: Any = None,
    ) -> None:
        self.sample_interval_seconds = sample_interval_seconds
        self.top_objects = top_objects
        self.narrative_engine = narrative_engine
        self._last_sample_at: float = 0.0
        self._baseline: Optional[Dict[str, Any]] = None
        self._reports: List[Dict[str, Any]] = []
        self._tracemalloc_started: bool = False

    # ------------------------------------------------------------------ #
    # Sampling
    # ------------------------------------------------------------------ #

    def sample(self, orchestrator: Any) -> Optional[Dict[str, Any]]:
        now = time.time()
        if (now - self._last_sample_at) < self.sample_interval_seconds:
            return None
        self._last_sample_at = now

        report = self._build_report(orchestrator)
        self._reports.append(report)
        # Bound retained reports to avoid unbounded growth between flushes.
        if len(self._reports) > self._MAX_RETAINED_REPORTS:
            # Keep the baseline (oldest) and trim the tail to the cap.
            self._reports = self._reports[-self._MAX_RETAINED_REPORTS :]

        if self._baseline is None:
            self._baseline = report

        if self.narrative_engine is not None:
            try:
                self.narrative_engine.record(
                    event_type="memory_leak_audit",
                    description=f"T113 audit: rss={report['rss_mb']:.1f}MB, growth={report['rss_growth_mb']:.1f}MB, leaks={len(report['suspected_leaks'])}",
                    importance=5,
                    metadata=report,
                )
            except Exception:
                logging.getLogger(__name__).warning("Narrative record failed during memory leak audit", exc_info=True)

        return report

    # ------------------------------------------------------------------ #
    # Report construction
    # ------------------------------------------------------------------ #

    def _build_report(self, orchestrator: Any) -> Dict[str, Any]:
        rss_mb = self._current_rss_mb()
        rss_growth = rss_mb - (self._baseline["rss_mb"] if self._baseline else rss_mb)

        # Object count by type
        obj_counts = self._count_objects()
        baseline_counts = self._baseline.get("object_counts", {}) if self._baseline else {}
        growth_counts = {
            k: obj_counts.get(k, 0) - baseline_counts.get(k, 0)
            for k in set(obj_counts) | set(baseline_counts)
        }
        top_growth = sorted(growth_counts.items(), key=lambda x: x[1], reverse=True)[: self.top_objects]

        # Suspected leaks: objects growing > 20%
        suspected_leaks: List[Dict[str, Any]] = []
        for typ, delta in top_growth:
            if delta <= 0:
                continue
            baseline = baseline_counts.get(typ, 0)
            if baseline > 0 and delta / baseline > 0.20:
                suspected_leaks.append({"type": typ, "delta": delta, "baseline": baseline})

        # File descriptor usage (best effort)
        fd_count = self._count_file_descriptors()

        # Orchestrator-specific cumulative structures
        cumulative = self._audit_cumulative_structures(orchestrator)

        report = {
            "timestamp": time.time(),
            "rss_mb": rss_mb,
            "rss_growth_mb": rss_growth,
            "object_counts": obj_counts,
            "top_growth": [(t, int(c)) for t, c in top_growth],
            "suspected_leaks": suspected_leaks,
            "file_descriptors": fd_count,
            "cumulative_structures": cumulative,
            "leak_detected": len(suspected_leaks) > 0 or rss_growth > 512,
        }
        return report

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _current_rss_mb() -> float:
        try:
            import psutil
            return psutil.Process().memory_info().rss / (1024 * 1024)
        except Exception:
            return 0.0

    @staticmethod
    def _count_objects() -> Dict[str, int]:
        gc.collect()
        counts: Counter[str] = Counter()
        for obj in gc.get_objects():
            try:
                counts[type(obj).__name__] += 1
            except Exception:
                # Some objects (e.g. those with broken __name__, slots-only C types)
                # can fail introspection; skip them silently rather than crash
                # the audit. We do NOT log here because exceptions at this
                # frequency would flood the logs.
                continue
        return dict(counts)

    @staticmethod
    def _count_file_descriptors() -> int:
        try:
            import psutil
            return psutil.Process().num_fds()
        except Exception:
            return 0

    @staticmethod
    def _audit_cumulative_structures(orchestrator: Any) -> Dict[str, int]:
        """Audit known cumulative data structures in SPEACE."""
        result: Dict[str, int] = {}
        metrics_log = getattr(orchestrator, "metrics_log", [])
        result["metrics_log_len"] = len(metrics_log)

        narrative = getattr(orchestrator, "_narrative_engine", None)
        if narrative is not None:
            result["narrative_events"] = len(getattr(narrative, "_events", []))

        dialogue = getattr(orchestrator, "_dialogue_history", None)
        if dialogue is not None:
            result["dialogue_turns"] = len(getattr(dialogue, "_turns", []))

        proposals = getattr(orchestrator, "_regulation_proposal_builder", None)
        if proposals is not None:
            result["regulation_proposals"] = len(getattr(proposals, "_proposals", []))

        memory = getattr(orchestrator, "_memory", None)
        if memory is not None:
            result["memory_events"] = len(getattr(memory, "events", []))

        return result

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def latest_report(self) -> Optional[Dict[str, Any]]:
        return self._reports[-1] if self._reports else None

    def summary(self) -> Dict[str, Any]:
        report = self.latest_report()
        return {
            "latest_report": report,
            "total_audits": len(self._reports),
            "baseline_set": self._baseline is not None,
        }

    def save_reports(self, path: str = "data/runtime/memory_leak_audit.jsonl") -> None:
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            for report in self._reports:
                f.write(json.dumps(report, ensure_ascii=False) + "\n")
        self._reports.clear()
