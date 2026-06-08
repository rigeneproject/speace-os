"""Capability Gap Analyzer — asks 'what can't I do?' each cycle.

Not 'what should I refactor?' but 'what capability is missing entirely?'
Identifies gaps by analyzing:
  - ARC-AGI failure patterns (which transformations are absent)
  - Primitive coverage (which grid patterns have no matching primitive)
  - Composition failures (which multi-step patterns can't be expressed)

Outputs a structured gap report that feeds into primitive discovery.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

GAP_REPORT_DIR = Path("data/capability_gaps")


@dataclass
class CapabilityGap:
    domain: str  # "arc_agi_primitive", "arc_agi_composition", "vfs", "reasoning"
    description: str
    missing_capability: str
    evidence: str
    frequency: int = 1
    suggested_primitive: str = ""
    first_seen: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    last_seen: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


@dataclass
class CapabilityGapReport:
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    gaps: List[CapabilityGap] = field(default_factory=list)
    tick: int = 0


class CapabilityGapAnalyzer:
    """Analyzes what the system cannot do, focusing on missing capabilities."""

    def __init__(self, directory: str | Path = GAP_REPORT_DIR) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._gaps: Dict[str, CapabilityGap] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_arc_failures(self, failure_summary: Dict[str, Any]) -> List[CapabilityGap]:
        """From Failure Memory summary, identify capability gaps."""
        new_gaps: List[CapabilityGap] = []
        patterns = failure_summary.get("failure_patterns", {})
        causes = failure_summary.get("failure_causes", {})

        # If many no_candidates failures → missing primitive coverage
        no_cand = patterns.get("no_candidates", 0)
        if no_cand >= 1:
            gap = CapabilityGap(
                domain="arc_agi_primitive",
                description=f"{no_cand} tasks have no matching primitive or composition",
                missing_capability="primitive_coverage",
                evidence=f"failure_pattern=no_candidates count={no_cand}",
                frequency=no_cand,
                suggested_primitive="auto_discover",
            )
            self._upsert_gap(gap)
            new_gaps.append(gap)

        near_miss = patterns.get("near_match", 0)
        if near_miss >= 1:
            gap = CapabilityGap(
                domain="arc_agi_composition",
                description=f"{near_miss} tasks matched partially but not exactly",
                missing_capability="composition_refinement",
                evidence=f"failure_pattern=near_match count={near_miss}",
                frequency=near_miss,
                suggested_primitive="param_variant_search",
            )
            self._upsert_gap(gap)
            new_gaps.append(gap)

        return new_gaps

    def analyze_primitive_coverage(
        self, registry_names: Set[str], task_inputs: List[List[List[int]]]
    ) -> List[CapabilityGap]:
        """Analyze which grid patterns have no matching primitive."""
        new_gaps: List[CapabilityGap] = []
        # Detect size-change gaps
        for grid in task_inputs:
            h, w = len(grid), len(grid[0])
            if h != w and "tile_to_target_size" not in registry_names:
                gap = CapabilityGap(
                    domain="arc_agi_primitive",
                    description="Non-square grids may need dimension-specific tiling",
                    missing_capability="non_square_tiling",
                    evidence=f"grid_shape=({h},{w})",
                    suggested_primitive="tile_to_target_size",
                )
                self._upsert_gap(gap)
                new_gaps.append(gap)
                break
        return new_gaps

    def generate_report(self, tick: int = 0) -> CapabilityGapReport:
        return CapabilityGapReport(
            tick=tick,
            gaps=list(self._gaps.values()),
        )

    def get_gaps_by_domain(self) -> Dict[str, List[CapabilityGap]]:
        domains: Dict[str, List[CapabilityGap]] = {}
        for gap in self._gaps.values():
            domains.setdefault(gap.domain, []).append(gap)
        return domains

    def save_report(self, report: CapabilityGapReport) -> None:
        path = self.directory / f"gap_report_tick_{report.tick}.json"
        data = asdict(report)
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        # Also save latest
        latest = self.directory / "latest_gap_report.json"
        latest.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _upsert_gap(self, gap: CapabilityGap) -> None:
        key = f"{gap.domain}:{gap.missing_capability}"
        if key in self._gaps:
            existing = self._gaps[key]
            existing.frequency += 1
            existing.last_seen = gap.last_seen
        else:
            self._gaps[key] = gap

    def _load(self) -> None:
        latest = self.directory / "latest_gap_report.json"
        if latest.exists():
            try:
                data = json.loads(latest.read_text(encoding="utf-8"))
                for g in data.get("gaps", []):
                    gap = CapabilityGap(**g)
                    self._gaps[f"{gap.domain}:{gap.missing_capability}"] = gap
            except Exception as exc:
                logger.debug("Could not load previous gap report: %s", exc)
