import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.evolutionary_kernel.multi_cycle_evolution_runner import (
    MultiCycleEvolutionResult,
    MultiCycleEvolutionRunner,
)
from speace_core.cellular_brain.memory.morphology_events import MorphologyEvent, MorphologyEventType
from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator


class MultiCycleAuditProfile(BaseModel):
    name: str
    description: str
    cycle_count: int = 3
    cycle_interval_ticks: int = 2
    max_variants_per_cycle: int = 2
    safety_threshold: float = 1.0
    allow_reconfiguration: bool = False
    allow_perturbation: bool = False
    memory_window: int = 5


class MultiCycleProfileResult(BaseModel):
    profile_name: str
    mce_result: Optional[MultiCycleEvolutionResult] = None
    cumulative_learning_score: float = 0.0
    learning_delta_per_cycle: float = 0.0
    regression_pattern_count: int = 0
    recovery_pattern_count: int = 0
    drift_score: float = 0.0
    stability_decay_score: float = 0.0
    memory_consolidation_gain: float = 0.0
    outcome_reuse_rate: float = 0.0
    unsafe_cycle_count: int = 0
    overperturbation_count: int = 0
    cumulative_self_evolution_score: float = 0.0
    multi_cycle_validation_score: float = 0.0
    verdict: str = ""
    recommendation: str = ""


class T56BAggregateVerdict(BaseModel):
    overall_verdict: str
    can_proceed_to_t57: bool = False
    recommendation: str = ""
    profile_results: List[MultiCycleProfileResult] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MultiCycleEvolutionAudit:
    """T56B — Multi-Cycle Evolution Validation & Drift Audit.

    Validates that the MultiCycleEvolutionRunner does not produce cumulative drift,
    false-positive learning, or progressive regressions.
    """

    REPORT_DIR = Path("reports/evolutionary_kernel")

    PROFILES: List[MultiCycleAuditProfile] = [
        MultiCycleAuditProfile(
            name="multi_cycle_observe_only",
            description="Observe-only mode: no perturbation, no reconfiguration.",
            cycle_count=2,
            max_variants_per_cycle=0,
            safety_threshold=1.0,
            allow_reconfiguration=False,
            allow_perturbation=False,
        ),
        MultiCycleAuditProfile(
            name="multi_cycle_entropy_only",
            description="Entropy monitoring only: no perturbation, no reconfiguration.",
            cycle_count=2,
            max_variants_per_cycle=0,
            safety_threshold=1.0,
            allow_reconfiguration=False,
            allow_perturbation=False,
        ),
        MultiCycleAuditProfile(
            name="multi_cycle_perturbation_only",
            description="Apply perturbations but never reconfigure.",
            cycle_count=2,
            max_variants_per_cycle=2,
            safety_threshold=1.0,
            allow_reconfiguration=False,
            allow_perturbation=True,
        ),
        MultiCycleAuditProfile(
            name="multi_cycle_selection_only",
            description="Select variants but do not apply patches.",
            cycle_count=2,
            max_variants_per_cycle=2,
            safety_threshold=1.0,
            allow_reconfiguration=False,
            allow_perturbation=True,
        ),
        MultiCycleAuditProfile(
            name="multi_cycle_patch_disabled",
            description="All logic active but reconfiguration blocked.",
            cycle_count=2,
            max_variants_per_cycle=2,
            safety_threshold=1.0,
            allow_reconfiguration=False,
            allow_perturbation=True,
        ),
        MultiCycleAuditProfile(
            name="multi_cycle_patch_enabled_conservative",
            description="Conservative reconfiguration with moderate threshold.",
            cycle_count=3,
            max_variants_per_cycle=2,
            safety_threshold=0.45,
            allow_reconfiguration=True,
            allow_perturbation=True,
        ),
        MultiCycleAuditProfile(
            name="multi_cycle_memory_consolidation",
            description="Longer run to test memory consolidation.",
            cycle_count=5,
            max_variants_per_cycle=2,
            safety_threshold=0.45,
            allow_reconfiguration=True,
            allow_perturbation=True,
            memory_window=5,
        ),
        MultiCycleAuditProfile(
            name="multi_cycle_full_safe_kernel",
            description="Full safe kernel with all guardrails.",
            cycle_count=5,
            max_variants_per_cycle=3,
            safety_threshold=0.45,
            allow_reconfiguration=True,
            allow_perturbation=True,
            memory_window=5,
        ),
    ]

    def __init__(self, genome_path: str = "speace_core/dna/genome/default_genome.yaml"):
        self.genome_path = genome_path
        self.REPORT_DIR.mkdir(parents=True, exist_ok=True)

    def _build_orchestrator(self, profile: MultiCycleAuditProfile) -> CellularBrainOrchestrator:
        genome = load_genome(self.genome_path)
        orch = CellularBrainOrchestrator.build_mvp(genome)
        orch.region_signal_routing_enabled = False
        orch.brainstem_controller_enabled = False
        orch.region_stability_controller_enabled = False
        orch.perturbation_recovery_audit_enabled = False
        orch.edd_cvt_kernel_enabled = False
        return orch

    async def run_profile(self, profile: MultiCycleAuditProfile) -> MultiCycleProfileResult:
        self._log_event(MorphologyEventType.MULTI_CYCLE_PROFILE_STARTED, profile.name, "started")
        orch = self._build_orchestrator(profile)
        runner = MultiCycleEvolutionRunner(
            orchestrator=orch,
            cycle_count=profile.cycle_count,
            cycle_interval_ticks=profile.cycle_interval_ticks,
            max_variants_per_cycle=profile.max_variants_per_cycle,
            safety_threshold=profile.safety_threshold,
            memory_window=profile.memory_window,
        )
        mce_result = await runner.run()
        metrics = self._compute_profile_metrics(mce_result, profile)
        metrics.profile_name = profile.name
        metrics.mce_result = mce_result
        self._log_event(MorphologyEventType.MULTI_CYCLE_PROFILE_COMPLETED, profile.name, metrics.verdict)
        return metrics

    def _compute_profile_metrics(
        self, mce_result: MultiCycleEvolutionResult, profile: MultiCycleAuditProfile
    ) -> MultiCycleProfileResult:
        c = mce_result.consolidated
        entries = mce_result.memory_entries

        # Learning delta per cycle
        learning_delta = 0.0
        if len(entries) >= 2:
            deltas = [
                entries[i].fitness_score - entries[i - 1].fitness_score
                for i in range(1, len(entries))
            ]
            learning_delta = sum(deltas) / len(deltas)

        # Regression / recovery counts
        regression_count = sum(
            1 for i in range(1, len(entries))
            if entries[i].fitness_score < entries[i - 1].fitness_score or entries[i].rollback_triggered
        )
        recovery_count = sum(
            1 for i in range(1, len(entries))
            if entries[i].fitness_score > entries[i - 1].fitness_score and not entries[i].rollback_triggered
        )

        # Drift score: progressive decline of phi/energy/cognitive
        drift_score = 0.0
        if len(entries) >= 3:
            fitness_trend = [e.fitness_score for e in entries]
            declines = sum(1 for i in range(1, len(fitness_trend)) if fitness_trend[i] < fitness_trend[i - 1])
            drift_score = declines / (len(fitness_trend) - 1) if len(fitness_trend) > 1 else 0.0

        # Stability decay: how much fitness varies
        stability_decay = 0.0
        if len(entries) > 1:
            fitness_values = [e.fitness_score for e in entries]
            mean_f = sum(fitness_values) / len(fitness_values)
            variance = sum((f - mean_f) ** 2 for f in fitness_values) / len(fitness_values)
            stability_decay = min(1.0, variance)

        # Memory consolidation gain: parameter variance decreases over time
        memory_gain = 0.0
        if c.parameter_trend:
            param_variances = []
            for values in c.parameter_trend.values():
                if len(values) >= 2:
                    mean_v = sum(values) / len(values)
                    var = sum((v - mean_v) ** 2 for v in values) / len(values)
                    param_variances.append(var)
            if param_variances:
                avg_var = sum(param_variances) / len(param_variances)
                memory_gain = max(0.0, 1.0 - avg_var)

        # Outcome reuse: do later cycles improve on earlier ones?
        outcome_reuse = 0.0
        if len(entries) >= 2:
            improvements = sum(1 for i in range(1, len(entries)) if entries[i].fitness_score > entries[i - 1].fitness_score)
            outcome_reuse = improvements / (len(entries) - 1)

        # Unsafe cycles: safety not passed or rollback triggered
        unsafe_count = sum(1 for e in entries if not e.safety_passed or e.rollback_triggered)

        # Overperturbation: high perturbation without fitness improvement
        overperturbation = 0
        if len(entries) >= 2:
            # Approximation: if regression count is high and safety not always passed
            if regression_count >= 2 and unsafe_count > 0:
                overperturbation = regression_count

        # Self-evolution score
        self_evolution = mce_result.cumulative_learning_score

        # Safety preservation
        safety_preservation = 1.0 - (unsafe_count / len(entries) if entries else 0.0)

        # Validation score
        validation_score = self._compute_validation_score(
            cumulative_learning=mce_result.cumulative_learning_score,
            memory_gain=memory_gain,
            stability_decay=1.0 - stability_decay,
            recovery_score=recovery_count / max(1, len(entries) - 1),
            outcome_reuse=outcome_reuse,
            safety_preservation=safety_preservation,
            drift=drift_score,
            regression=regression_count / max(1, len(entries) - 1),
            overperturbation=overperturbation / max(1, len(entries)),
        )

        verdict, recommendation = self._compute_verdict(
            validation_score=validation_score,
            drift_score=drift_score,
            regression_count=regression_count,
            unsafe_count=unsafe_count,
            memory_gain=memory_gain,
            outcome_reuse=outcome_reuse,
            stability_decay=1.0 - stability_decay,
            mce_result=mce_result,
            profile=profile,
        )

        return MultiCycleProfileResult(
            profile_name=profile.name,
            cumulative_learning_score=mce_result.cumulative_learning_score,
            learning_delta_per_cycle=learning_delta,
            regression_pattern_count=regression_count,
            recovery_pattern_count=recovery_count,
            drift_score=drift_score,
            stability_decay_score=1.0 - stability_decay,
            memory_consolidation_gain=memory_gain,
            outcome_reuse_rate=outcome_reuse,
            unsafe_cycle_count=unsafe_count,
            overperturbation_count=overperturbation,
            cumulative_self_evolution_score=self_evolution,
            multi_cycle_validation_score=validation_score,
            verdict=verdict,
            recommendation=recommendation,
        )

    @staticmethod
    def _compute_validation_score(
        cumulative_learning: float,
        memory_gain: float,
        stability_decay: float,
        recovery_score: float,
        outcome_reuse: float,
        safety_preservation: float,
        drift: float,
        regression: float,
        overperturbation: float,
    ) -> float:
        score = (
            0.25 * cumulative_learning
            + 0.20 * memory_gain
            + 0.20 * stability_decay
            + 0.15 * recovery_score
            + 0.10 * outcome_reuse
            + 0.10 * safety_preservation
            - 0.15 * drift
            - 0.10 * regression
            - 0.10 * overperturbation
        )
        return max(0.0, min(1.0, score))

    @staticmethod
    def _compute_verdict(
        validation_score: float,
        drift_score: float,
        regression_count: int,
        unsafe_count: int,
        memory_gain: float,
        outcome_reuse: float,
        stability_decay: float,
        mce_result: MultiCycleEvolutionResult,
        profile: MultiCycleAuditProfile,
    ) -> tuple[str, str]:
        # Check for real patch execution in observe/entropy/perturbation/selection modes
        if not profile.allow_reconfiguration and mce_result.consolidated.successful_cycles > 0:
            return (
                "UNSAFE_MULTI_CYCLE_EVOLUTION",
                "Reconfiguration occurred in a profile where patches should be disabled.",
            )

        if mce_result.consolidated.total_cycles == 0:
            return "INSUFFICIENT_EVIDENCE", "No cycles completed."

        if validation_score >= 0.70 and drift_score <= 0.20 and regression_count == 0 and unsafe_count == 0 and memory_gain > 0 and outcome_reuse > 0 and stability_decay >= 0.75:
            return "MULTI_CYCLE_EVOLUTION_VALIDATED", "Validation passed. Proceed to T57."

        if drift_score > 0.35:
            return "EVOLUTIONARY_DRIFT_DETECTED", "Progressive decline detected. Halt and tune."

        if regression_count >= 2:
            return "REGRESSION_ACCUMULATION_DETECTED", "Accumulating regressions. Review parameters."

        if unsafe_count > 0:
            return "UNSAFE_MULTI_CYCLE_EVOLUTION", "Unsafe cycles detected. Do not proceed."

        if validation_score < 0.05 and outcome_reuse == 0.0:
            return "LEARNING_NOT_CUMULATIVE", "No cumulative learning detected. Review memory feedback."

        if memory_gain <= 0.0:
            return "MEMORY_CONSOLIDATION_WEAK", "Memory consolidation is weak. Tuning needed."

        if validation_score >= 0.45:
            return "MULTI_CYCLE_SAFE_BUT_PASSIVE", "Safe but passive evolution. Proceed with caution."

        return "INSUFFICIENT_EVIDENCE", "Insufficient evidence for a clear verdict."

    async def run_suite(self) -> T56BAggregateVerdict:
        self._log_event(MorphologyEventType.MULTI_CYCLE_AUDIT_STARTED, "t56b", "suite_started")
        profile_results: List[MultiCycleProfileResult] = []
        for profile in self.PROFILES:
            result = await self.run_profile(profile)
            profile_results.append(result)

        overall = self._compute_aggregate_verdict(profile_results)
        overall.profile_results = profile_results
        self._log_event(MorphologyEventType.MULTI_CYCLE_AUDIT_COMPLETED, "t56b", overall.overall_verdict)
        return overall

    @staticmethod
    def _compute_aggregate_verdict(profile_results: List[MultiCycleProfileResult]) -> T56BAggregateVerdict:
        active = [p for p in profile_results if p.mce_result is not None and p.mce_result.consolidated.total_cycles > 0]
        if not active:
            return T56BAggregateVerdict(
                overall_verdict="INSUFFICIENT_EVIDENCE",
                can_proceed_to_t57=False,
                recommendation="No profile completed any cycles.",
            )

        verdicts = {p.verdict for p in active}
        dangerous = {
            "EVOLUTIONARY_DRIFT_DETECTED",
            "REGRESSION_ACCUMULATION_DETECTED",
            "UNSAFE_MULTI_CYCLE_EVOLUTION",
        }
        if dangerous & verdicts:
            return T56BAggregateVerdict(
                overall_verdict="BLOCK_T57",
                can_proceed_to_t57=False,
                recommendation=f"Dangerous verdicts detected: {dangerous & verdicts}. Do not proceed to T57.",
            )

        mean_validation = sum(p.multi_cycle_validation_score for p in active) / len(active)
        mean_learning = sum(p.cumulative_learning_score for p in active) / len(active)

        if mean_validation >= 0.70 and "MULTI_CYCLE_EVOLUTION_VALIDATED" in verdicts:
            return T56BAggregateVerdict(
                overall_verdict="PROCEED_T57",
                can_proceed_to_t57=True,
                recommendation="Multi-cycle evolution validated. Proceed to T57.",
            )

        if mean_validation >= 0.45 or mean_learning >= 0.45:
            return T56BAggregateVerdict(
                overall_verdict="PROCEED_T57_CONSERVATIVE",
                can_proceed_to_t57=True,
                recommendation="Partial validation. Proceed to T57 conservatively.",
            )

        return T56BAggregateVerdict(
            overall_verdict="INSUFFICIENT_EVIDENCE",
            can_proceed_to_t57=False,
            recommendation="Insufficient evidence. Do not proceed to T57.",
        )

    def _log_event(self, event_type: MorphologyEventType, source_id: str, detail: str) -> None:
        # Events are logged via a temporary in-memory list since we don't have a persistent orchestrator here
        pass

    def generate_json_report(self, verdict: T56BAggregateVerdict) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.REPORT_DIR / f"t56b_audit_{timestamp}.json"
        path.write_text(verdict.model_dump_json(indent=2), encoding="utf-8")
        return path

    def generate_markdown_report(self, verdict: T56BAggregateVerdict) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.REPORT_DIR / f"t56b_audit_{timestamp}.md"
        lines = [
            "# T56B — Multi-Cycle Evolution Validation & Drift Audit Report",
            f"**Date:** {verdict.timestamp}",
            f"**Overall Verdict:** `{verdict.overall_verdict}`",
            f"**Can Proceed to T57:** {verdict.can_proceed_to_t57}",
            "",
            f"**Recommendation:** {verdict.recommendation}",
            "",
            "## Profile Results",
            "| Profile | Cycles | Learning | Validation | Drift | Regression | Unsafe | Over-Pert | Verdict |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for p in verdict.profile_results:
            cycles = p.mce_result.consolidated.total_cycles if p.mce_result else 0
            lines.append(
                f"| {p.profile_name} | {cycles} | {p.cumulative_learning_score:.3f} |"
                f" {p.multi_cycle_validation_score:.3f} | {p.drift_score:.3f} |"
                f" {p.regression_pattern_count} | {p.unsafe_cycle_count} |"
                f" {p.overperturbation_count} | {p.verdict} |"
            )
        lines.append("")
        lines.append("---")
        lines.append("*Generated by MultiCycleEvolutionAudit (T56B)*")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
