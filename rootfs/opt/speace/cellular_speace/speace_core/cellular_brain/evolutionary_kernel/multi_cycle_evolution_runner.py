import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.evolutionary_kernel.edd_cvt_kernel import (
    EDDCVTEvolutionaryKernel,
)
from speace_core.cellular_brain.evolutionary_kernel.evolutionary_cycle_models import (
    EDDCVTMetrics,
    EvolutionCycleResult,
)
from speace_core.cellular_brain.memory.morphology_events import MorphologyEvent, MorphologyEventType
from speace_core.dna.parser import load_genome

if TYPE_CHECKING:
    from speace_core.orchestrator import CellularBrainOrchestrator


class CycleMemoryEntry(BaseModel):
    cycle_number: int
    generation_id: str
    fitness_score: float = 0.0
    entropy_delta: float = 0.0
    reconfiguration_applied: bool = False
    safety_passed: bool = False
    rollback_triggered: bool = False
    parameter_state: Dict[str, float] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ConsolidatedMemory(BaseModel):
    total_cycles: int = 0
    successful_cycles: int = 0
    mean_fitness_score: float = 0.0
    mean_entropy_delta: float = 0.0
    best_fitness_score: float = 0.0
    best_cycle_number: int = 0
    worst_fitness_score: float = 0.0
    worst_cycle_number: int = 0
    parameter_trend: Dict[str, List[float]] = Field(default_factory=dict)
    recovery_pattern_found: bool = False
    regression_pattern_found: bool = False
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MultiCycleEvolutionResult(BaseModel):
    run_id: str = Field(default_factory=lambda: f"mce_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
    cycle_results: List[EvolutionCycleResult] = Field(default_factory=list)
    memory_entries: List[CycleMemoryEntry] = Field(default_factory=list)
    consolidated: ConsolidatedMemory = Field(default_factory=ConsolidatedMemory)
    cumulative_learning_score: float = 0.0
    verdict: str = ""
    recommendation: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MultiCycleEvolutionRunner:
    """T56 — Autonomous Multi-Cycle Evolution With Memory Consolidation."""

    REPORT_DIR = Path("reports/evolutionary_kernel")

    def __init__(
        self,
        orchestrator: "CellularBrainOrchestrator",
        cycle_count: int = 10,
        cycle_interval_ticks: int = 5,
        max_variants_per_cycle: int = 3,
        safety_threshold: float = 0.0,
        memory_window: int = 5,
    ):
        self.orch = orchestrator
        self.cycle_count = cycle_count
        self.cycle_interval_ticks = cycle_interval_ticks
        self.max_variants_per_cycle = max_variants_per_cycle
        self.safety_threshold = safety_threshold
        self.memory_window = memory_window
        self.REPORT_DIR.mkdir(parents=True, exist_ok=True)

        self.kernel = EDDCVTEvolutionaryKernel(
            orchestrator=orchestrator,
            enabled=True,
            cycle_interval_ticks=cycle_interval_ticks,
            max_variants_per_cycle=max_variants_per_cycle,
            safety_threshold=safety_threshold,
        )
        self._results: List[MultiCycleEvolutionResult] = []

    # ------------------------------------------------------------------ #
    # Run
    # ------------------------------------------------------------------ #

    async def run(self) -> MultiCycleEvolutionResult:
        cycle_results: List[EvolutionCycleResult] = []
        memory_entries: List[CycleMemoryEntry] = []
        tick = 0

        for i in range(self.cycle_count):
            tick += self.cycle_interval_ticks
            result = await self.kernel.tick(tick)
            if result is None:
                result = await self.kernel.run_cycle(tick)
            if result is not None:
                cycle_results.append(result)
                entry = CycleMemoryEntry(
                    cycle_number=result.cycle_number,
                    generation_id=result.generation_id,
                    fitness_score=result.fitness_score,
                    entropy_delta=result.entropy_delta,
                    reconfiguration_applied=result.reconfiguration_applied,
                    safety_passed=result.safety_passed,
                    rollback_triggered=result.rollback_triggered,
                    parameter_state=self._extract_parameters(),
                )
                memory_entries.append(entry)
                self._log_event(
                    MorphologyEventType.EPISODE_EVENT_RECORDED,
                    result.generation_id,
                    f"cycle_{result.cycle_number}",
                )

        consolidated = self._consolidate(memory_entries)
        learning_score = self._compute_learning_score(consolidated)
        verdict, recommendation = self._compute_verdict(consolidated, learning_score)

        mce_result = MultiCycleEvolutionResult(
            cycle_results=cycle_results,
            memory_entries=memory_entries,
            consolidated=consolidated,
            cumulative_learning_score=learning_score,
            verdict=verdict,
            recommendation=recommendation,
        )
        self._results.append(mce_result)
        self._log_event(MorphologyEventType.EPISODE_CLOSED, mce_result.run_id, verdict)
        return mce_result

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _extract_parameters(self) -> Dict[str, float]:
        return getattr(self.orch, "_edd_cvt_parameters", {})

    def _consolidate(self, entries: List[CycleMemoryEntry]) -> ConsolidatedMemory:
        if not entries:
            return ConsolidatedMemory()

        fitness_scores = [e.fitness_score for e in entries]
        entropy_deltas = [e.entropy_delta for e in entries]
        best_idx = max(range(len(fitness_scores)), key=lambda i: fitness_scores[i])
        worst_idx = min(range(len(fitness_scores)), key=lambda i: fitness_scores[i])

        parameter_trend: Dict[str, List[float]] = {}
        for e in entries:
            for k, v in e.parameter_state.items():
                parameter_trend.setdefault(k, []).append(v)

        # Detect patterns
        recovery_pattern = any(
            entries[i].fitness_score > entries[i - 1].fitness_score and not entries[i].rollback_triggered
            for i in range(1, len(entries))
        )
        regression_pattern = any(
            entries[i].fitness_score < entries[i - 1].fitness_score or entries[i].rollback_triggered
            for i in range(1, len(entries))
        )

        return ConsolidatedMemory(
            total_cycles=len(entries),
            successful_cycles=sum(1 for e in entries if e.reconfiguration_applied and e.safety_passed),
            mean_fitness_score=sum(fitness_scores) / len(fitness_scores),
            mean_entropy_delta=sum(entropy_deltas) / len(entropy_deltas),
            best_fitness_score=fitness_scores[best_idx],
            best_cycle_number=entries[best_idx].cycle_number,
            worst_fitness_score=fitness_scores[worst_idx],
            worst_cycle_number=entries[worst_idx].cycle_number,
            parameter_trend=parameter_trend,
            recovery_pattern_found=recovery_pattern,
            regression_pattern_found=regression_pattern,
        )

    @staticmethod
    def _compute_learning_score(consolidated: ConsolidatedMemory) -> float:
        if consolidated.total_cycles == 0:
            return 0.0
        score = (
            0.30 * consolidated.mean_fitness_score
            + 0.25 * max(0.0, 1.0 - abs(consolidated.mean_entropy_delta))
            + 0.20 * (consolidated.best_fitness_score - consolidated.worst_fitness_score)
            + 0.15 * (consolidated.successful_cycles / consolidated.total_cycles)
            + 0.10 * (1.0 if consolidated.recovery_pattern_found else 0.0)
        )
        return max(0.0, min(1.0, score))

    @staticmethod
    def _compute_verdict(consolidated: ConsolidatedMemory, learning_score: float) -> tuple[str, str]:
        if consolidated.total_cycles == 0:
            return "INSUFFICIENT_EVIDENCE", "No cycles completed."
        if consolidated.regression_pattern_found and learning_score < 0.3:
            return "REGRESSION_DETECTED", "Regression pattern with low learning. Halt evolution."
        if learning_score >= 0.70 and consolidated.recovery_pattern_found:
            return "MULTI_CYCLE_EVOLUTION_VALIDATED", "Cumulative evolution validated. Continue."
        if learning_score >= 0.45:
            return "MULTI_CYCLE_EVOLUTION_PARTIAL", "Partial learning. Continue with monitoring."
        return "INSUFFICIENT_LEARNING", "Insufficient cumulative learning. Review parameters."

    def _log_event(self, event_type: MorphologyEventType, source_id: str, detail: str) -> None:
        if hasattr(self.orch, "memory") and self.orch.memory is not None:
            event = MorphologyEvent(
                event_id=f"t56_{source_id}",
                event_type=event_type,
                source_id=source_id,
                metadata={"detail": detail},
            )
            self.orch.memory.events.append(event)

    # ------------------------------------------------------------------ #
    # Reports
    # ------------------------------------------------------------------ #

    def generate_json_report(self, result: MultiCycleEvolutionResult) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.REPORT_DIR / f"t56_multi_cycle_{timestamp}.json"
        path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return path

    def generate_markdown_report(self, result: MultiCycleEvolutionResult) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.REPORT_DIR / f"t56_multi_cycle_{timestamp}.md"
        c = result.consolidated
        lines = [
            "# T56 — Autonomous Multi-Cycle Evolution Report",
            f"**Run ID:** {result.run_id}",
            f"**Date:** {result.timestamp}",
            f"**Verdict:** `{result.verdict}`",
            f"**Cumulative Learning Score:** {result.cumulative_learning_score:.4f}",
            "",
            "## Consolidated Memory",
            f"- Total Cycles: {c.total_cycles}",
            f"- Successful Cycles: {c.successful_cycles}",
            f"- Mean Fitness: {c.mean_fitness_score:.4f}",
            f"- Mean Entropy Delta: {c.mean_entropy_delta:.4f}",
            f"- Best Fitness: {c.best_fitness_score:.4f} (cycle {c.best_cycle_number})",
            f"- Worst Fitness: {c.worst_fitness_score:.4f} (cycle {c.worst_cycle_number})",
            f"- Recovery Pattern Found: {c.recovery_pattern_found}",
            f"- Regression Pattern Found: {c.regression_pattern_found}",
            "",
            "## Parameter Trends",
        ]
        for param, values in c.parameter_trend.items():
            lines.append(f"- {param}: {values}")
        lines.append("")
        lines.append("## Cycle Details")
        for r in result.cycle_results:
            lines.append(
                f"- Cycle {r.cycle_number}: fitness={r.fitness_score:.4f}"
                f" entropy_delta={r.entropy_delta:.4f}"
                f" reconfigured={r.reconfiguration_applied}"
                f" safe={r.safety_passed}"
            )
        lines.append("")
        lines.append("---")
        lines.append("*Generated by MultiCycleEvolutionRunner (T56)*")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
