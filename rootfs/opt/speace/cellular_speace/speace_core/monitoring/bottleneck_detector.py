"""Bottleneck Detector — identifies reasoning, memory, and planning bottlenecks.

Automatically detects:
  - Reasoning bottleneck: slow program induction, excessive candidate exploration
  - Memory bottleneck: VFS index growth, failure record accumulation
  - Planning bottleneck: composition depth limits, search space explosion

Integrates with the monitoring system and can trigger regulation proposals.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

BOTTLENECK_REPORT_DIR = Path("data/bottleneck_reports")


class BottleneckType:
    REASONING = "reasoning"
    MEMORY = "memory"
    PLANNING = "planning"


@dataclass
class Bottleneck:
    bottleneck_type: str
    component: str
    severity: float  # 0.0-1.0
    metric_name: str
    metric_value: float
    threshold: float
    description: str
    suggested_action: str
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


@dataclass
class BottleneckReport:
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    bottlenecks: List[Bottleneck] = field(default_factory=list)
    tick: int = 0
    reasoning_score: float = 0.0
    memory_score: float = 0.0
    planning_score: float = 0.0


class BottleneckDetector:
    """Monitors system performance and detects bottlenecks."""

    def __init__(self, directory: str | Path = BOTTLENECK_REPORT_DIR) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

        # Thresholds
        self.REASONING_MS_THRESHOLD = 10000.0  # 10s induction time → warning
        self.REASONING_MS_CRITICAL = 30000.0  # 30s → critical
        self.CANDIDATE_EXPLOSION_THRESHOLD = 500  # >500 candidates → planning bottleneck
        self.VFS_INDEX_SIZE_WARN = 10000  # 10k entries → memory warning
        self.VFS_INDEX_SIZE_CRIT = 50000  # 50k entries → critical
        self.TICK_LATENCY_WARN = 2000  # 2s tick → warning
        self.TICK_LATENCY_CRIT = 5000  # 5s → critical

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_bottlenecks(
        self,
        tick: int = 0,
        arc_induction_time_ms: float = 0.0,
        arc_candidates: int = 0,
        vfs_index_size: int = 0,
        tick_latency_ms: float = 0.0,
        failure_count: int = 0,
        composition_depth: int = 0,
    ) -> BottleneckReport:
        bottlenecks: List[Bottleneck] = []

        # 1. Reasoning bottleneck
        reason_sev = self._check_reasoning(
            bottlenecks, arc_induction_time_ms, arc_candidates, failure_count
        )

        # 2. Memory bottleneck
        mem_sev = self._check_memory(
            bottlenecks, vfs_index_size, failure_count
        )

        # 3. Planning bottleneck
        plan_sev = self._check_planning(
            bottlenecks, composition_depth, arc_candidates, tick_latency_ms
        )

        report = BottleneckReport(
            tick=tick,
            bottlenecks=bottlenecks,
            reasoning_score=1.0 - reason_sev,
            memory_score=1.0 - mem_sev,
            planning_score=1.0 - plan_sev,
        )

        if bottlenecks:
            self._save_report(report)

        return report

    # ------------------------------------------------------------------
    # Internal checks
    # ------------------------------------------------------------------

    def _check_reasoning(
        self,
        bottlenecks: List[Bottleneck],
        induction_time_ms: float,
        candidates: int,
        failure_count: int,
    ) -> float:
        severity = 0.0

        if induction_time_ms >= self.REASONING_MS_CRITICAL:
            sev = min(1.0, induction_time_ms / (self.REASONING_MS_CRITICAL * 2))
            severity = max(severity, sev)
            bottlenecks.append(Bottleneck(
                bottleneck_type=BottleneckType.REASONING,
                component="program_induction",
                severity=sev,
                metric_name="induction_time_ms",
                metric_value=induction_time_ms,
                threshold=self.REASONING_MS_CRITICAL,
                description=f"Program induction took {induction_time_ms:.0f}ms (critical threshold: {self.REASONING_MS_CRITICAL:.0f}ms)",
                suggested_action="ridurre profondità composizione o limitare candidati",
            ))
        elif induction_time_ms >= self.REASONING_MS_THRESHOLD:
            sev = 0.5 * induction_time_ms / self.REASONING_MS_CRITICAL
            severity = max(severity, sev)
            bottlenecks.append(Bottleneck(
                bottleneck_type=BottleneckType.REASONING,
                component="program_induction",
                severity=sev,
                metric_name="induction_time_ms",
                metric_value=induction_time_ms,
                threshold=self.REASONING_MS_THRESHOLD,
                description=f"Program induction slow: {induction_time_ms:.0f}ms",
                suggested_action="monitorare; ottimizzare se persistente",
            ))

        if failure_count > 5:
            sev = min(0.5, failure_count / 20)
            severity = max(severity, sev)
            bottlenecks.append(Bottleneck(
                bottleneck_type=BottleneckType.REASONING,
                component="failure_accumulation",
                severity=sev,
                metric_name="failure_count",
                metric_value=float(failure_count),
                threshold=5.0,
                description=f"{failure_count} failure records accumulated — primitive library may be insufficient",
                suggested_action="aggiungere nuove primitive o raffinare parametri brute-force",
            ))

        return severity

    def _check_memory(
        self,
        bottlenecks: List[Bottleneck],
        vfs_index_size: int,
        failure_count: int,
    ) -> float:
        severity = 0.0

        if vfs_index_size >= self.VFS_INDEX_SIZE_CRIT:
            sev = min(1.0, vfs_index_size / (self.VFS_INDEX_SIZE_CRIT * 2))
            severity = max(severity, sev)
            bottlenecks.append(Bottleneck(
                bottleneck_type=BottleneckType.MEMORY,
                component="vfs_index",
                severity=sev,
                metric_name="vfs_index_size",
                metric_value=float(vfs_index_size),
                threshold=float(self.VFS_INDEX_SIZE_CRIT),
                description=f"VFS index at {vfs_index_size} entries (critical limit: {self.VFS_INDEX_SIZE_CRIT})",
                suggested_action="comprimere indici inattivi o aumentare limite memoria",
            ))
        elif vfs_index_size >= self.VFS_INDEX_SIZE_WARN:
            sev = 0.3 * vfs_index_size / self.VFS_INDEX_SIZE_CRIT
            severity = max(severity, sev)
            bottlenecks.append(Bottleneck(
                bottleneck_type=BottleneckType.MEMORY,
                component="vfs_index",
                severity=sev,
                metric_name="vfs_index_size",
                metric_value=float(vfs_index_size),
                threshold=float(self.VFS_INDEX_SIZE_WARN),
                description=f"VFS index size {vfs_index_size} approaching limit",
                suggested_action="monitorare crescita indice",
            ))

        return severity

    def _check_planning(
        self,
        bottlenecks: List[Bottleneck],
        composition_depth: int,
        candidates: int,
        tick_latency_ms: float,
    ) -> float:
        severity = 0.0

        if candidates >= self.CANDIDATE_EXPLOSION_THRESHOLD:
            sev = min(0.8, candidates / 2000)
            severity = max(severity, sev)
            bottlenecks.append(Bottleneck(
                bottleneck_type=BottleneckType.PLANNING,
                component="candidate_explosion",
                severity=sev,
                metric_name="candidate_count",
                metric_value=float(candidates),
                threshold=float(self.CANDIDATE_EXPLOSION_THRESHOLD),
                description=f"Candidate explosion: {candidates} candidates (limit: {self.CANDIDATE_EXPLOSION_THRESHOLD})",
                suggested_action="aumentare max_candidates o migliorare pruning early-stop",
            ))

        if tick_latency_ms >= self.TICK_LATENCY_CRIT:
            sev = min(1.0, tick_latency_ms / (self.TICK_LATENCY_CRIT * 2))
            severity = max(severity, sev)
            bottlenecks.append(Bottleneck(
                bottleneck_type=BottleneckType.PLANNING,
                component="tick_latency",
                severity=sev,
                metric_name="tick_latency_ms",
                metric_value=tick_latency_ms,
                threshold=float(self.TICK_LATENCY_CRIT),
                description=f"Tick latency {tick_latency_ms:.0f}ms (critical: {self.TICK_LATENCY_CRIT}ms)",
                suggested_action="ridurre carico per-tick o parallelizzare moduli",
            ))

        return severity

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_report(self, report: BottleneckReport) -> None:
        path = self.directory / f"bottleneck_report_tick_{report.tick}.json"
        data = asdict(report)
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        latest = self.directory / "latest_bottleneck_report.json"
        latest.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
