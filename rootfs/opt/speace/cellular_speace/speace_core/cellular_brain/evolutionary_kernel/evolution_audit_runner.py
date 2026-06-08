import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.evolutionary_kernel.edd_cvt_kernel import (
    EDDCVTEvolutionaryKernel,
)
from speace_core.cellular_brain.evolutionary_kernel.evolutionary_cycle_models import (
    EDDCVTMetrics,
    EvolutionPhase,
)
from speace_core.cellular_brain.memory.morphology_events import MorphologyEvent, MorphologyEventType
from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator


class EvolutionAuditProfile(BaseModel):
    name: str
    description: str
    edd_cvt_kernel_enabled: bool = False
    self_organization_controller_enabled: bool = False
    perturbation_recovery_audit_enabled: bool = False
    brainstem_controller_enabled: bool = False
    region_stability_controller_enabled: bool = False
    cycle_count: int = 3
    cycle_interval_ticks: int = 5


class EvolutionProfileResult(BaseModel):
    profile_name: str
    metrics: EDDCVTMetrics = Field(default_factory=EDDCVTMetrics)
    mean_fitness_score: float = 0.0
    final_entropy_delta: float = 0.0
    reconfiguration_rate: float = 0.0
    safety_pass_rate: float = 0.0
    rollback_rate: float = 0.0
    cycles_completed: int = 0
    verdict: str = ""
    recommendation: str = ""


class T55BAggregateVerdict(BaseModel):
    overall_verdict: str
    can_proceed_to_t56: bool = False
    recommendation: str = ""
    profile_results: List[EvolutionProfileResult] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EvolutionAuditRunner:
    """T55B — EDD-CVT Autonomous Evolution Audit across multiple profiles."""

    REPORT_DIR = Path("reports/evolutionary_kernel")

    PROFILES: List[EvolutionAuditProfile] = [
        EvolutionAuditProfile(
            name="baseline_no_t55",
            description="No T55 kernel; baseline orchestrator only.",
            edd_cvt_kernel_enabled=False,
            cycle_count=0,
        ),
        EvolutionAuditProfile(
            name="t55_kernel_only",
            description="T55 kernel only without supporting controllers.",
            edd_cvt_kernel_enabled=True,
            cycle_count=3,
        ),
        EvolutionAuditProfile(
            name="t55_plus_t53",
            description="T55 + T53 self-organization controllers.",
            edd_cvt_kernel_enabled=True,
            self_organization_controller_enabled=True,
            cycle_count=3,
        ),
        EvolutionAuditProfile(
            name="t55_plus_t54",
            description="T55 + T54 perturbation recovery audit.",
            edd_cvt_kernel_enabled=True,
            perturbation_recovery_audit_enabled=True,
            cycle_count=3,
        ),
        EvolutionAuditProfile(
            name="t55_plus_recovery_policy",
            description="T55 + brainstem + stability recovery policy.",
            edd_cvt_kernel_enabled=True,
            brainstem_controller_enabled=True,
            region_stability_controller_enabled=True,
            cycle_count=3,
        ),
        EvolutionAuditProfile(
            name="full_evolution_stack",
            description="Full evolution stack with all controllers.",
            edd_cvt_kernel_enabled=True,
            self_organization_controller_enabled=True,
            perturbation_recovery_audit_enabled=True,
            brainstem_controller_enabled=True,
            region_stability_controller_enabled=True,
            cycle_count=5,
        ),
    ]

    def __init__(self, genome_path: str = "speace_core/dna/genome/default_genome.yaml"):
        self.genome_path = genome_path
        self.REPORT_DIR.mkdir(parents=True, exist_ok=True)

    def _build_orchestrator(self, profile: EvolutionAuditProfile) -> CellularBrainOrchestrator:
        genome = load_genome(self.genome_path)
        orch = CellularBrainOrchestrator.build_mvp(genome)
        orch.edd_cvt_kernel_enabled = profile.edd_cvt_kernel_enabled
        orch.brainstem_controller_enabled = profile.brainstem_controller_enabled
        orch.region_stability_controller_enabled = profile.region_stability_controller_enabled
        orch.perturbation_recovery_audit_enabled = profile.perturbation_recovery_audit_enabled
        return orch

    async def run_profile(self, profile: EvolutionAuditProfile) -> EvolutionProfileResult:
        if profile.cycle_count == 0 or not profile.edd_cvt_kernel_enabled:
            return EvolutionProfileResult(
                profile_name=profile.name,
                verdict="NO_OP",
                recommendation="T55 disabled or cycle count zero.",
            )

        orch = self._build_orchestrator(profile)
        kernel = EDDCVTEvolutionaryKernel(
            orchestrator=orch,
            enabled=True,
            cycle_interval_ticks=profile.cycle_interval_ticks,
            max_variants_per_cycle=2,
            safety_threshold=0.0,
        )

        tick = 0
        for _ in range(profile.cycle_count):
            tick += profile.cycle_interval_ticks
            await kernel.tick(tick)

        metrics = kernel.get_metrics()
        verdict, recommendation = self._compute_verdict(metrics)

        return EvolutionProfileResult(
            profile_name=profile.name,
            metrics=metrics,
            mean_fitness_score=metrics.mean_fitness_score,
            final_entropy_delta=metrics.mean_entropy_delta,
            reconfiguration_rate=metrics.reconfiguration_rate,
            safety_pass_rate=metrics.safety_pass_rate,
            rollback_rate=metrics.rollback_rate,
            cycles_completed=metrics.total_cycles,
            verdict=verdict,
            recommendation=recommendation,
        )

    @staticmethod
    def _compute_verdict(metrics: EDDCVTMetrics) -> tuple[str, str]:
        if metrics.total_cycles == 0:
            return "INSUFFICIENT_EVIDENCE", "No cycles completed."
        if metrics.failed_cycles > metrics.successful_cycles:
            return "EVOLUTION_COLLAPSE", "More failures than successes. Do not proceed to T56."
        if metrics.rollback_rate > 0.5:
            return "HIGH_ROLLBACK", "Excessive rollbacks. Tune T55 before T56."
        if metrics.mean_fitness_score >= 0.65 and metrics.safety_pass_rate >= 0.75:
            return "EVOLUTION_VALIDATED", "Proceed to T56."
        if metrics.mean_fitness_score >= 0.45 and metrics.safety_pass_rate >= 0.5:
            return "EVOLUTION_PARTIAL", "Proceed to T56 with conservative cycles."
        return "INSUFFICIENT_EVIDENCE", "Insufficient evidence. Do not proceed to T56."

    async def run_suite(self) -> T55BAggregateVerdict:
        profile_results: List[EvolutionProfileResult] = []
        for profile in self.PROFILES:
            result = await self.run_profile(profile)
            profile_results.append(result)

        overall = self._compute_aggregate_verdict(profile_results)
        overall.profile_results = profile_results
        return overall

    @staticmethod
    def _compute_aggregate_verdict(profile_results: List[EvolutionProfileResult]) -> T55BAggregateVerdict:
        active = [p for p in profile_results if p.cycles_completed > 0]
        if not active:
            return T55BAggregateVerdict(
                overall_verdict="INSUFFICIENT_EVIDENCE",
                can_proceed_to_t56=False,
                recommendation="No profile completed any cycles.",
            )

        verdicts = {p.verdict for p in active}
        if "EVOLUTION_COLLAPSE" in verdicts or "HIGH_ROLLBACK" in verdicts:
            return T55BAggregateVerdict(
                overall_verdict="BLOCK_T56",
                can_proceed_to_t56=False,
                recommendation="Collapse or high rollback detected. Do not proceed to T56.",
            )

        mean_fitness = sum(p.mean_fitness_score for p in active) / len(active)
        mean_safety = sum(p.safety_pass_rate for p in active) / len(active)

        if mean_fitness >= 0.65 and mean_safety >= 0.75:
            return T55BAggregateVerdict(
                overall_verdict="PROCEED_T56",
                can_proceed_to_t56=True,
                recommendation="Evolution validated across profiles. Proceed to T56.",
            )

        if mean_fitness >= 0.45 and mean_safety >= 0.5:
            return T55BAggregateVerdict(
                overall_verdict="PROCEED_T56_CONSERVATIVE",
                can_proceed_to_t56=True,
                recommendation="Partial evolution success. Proceed to T56 conservatively.",
            )

        return T55BAggregateVerdict(
            overall_verdict="INSUFFICIENT_EVIDENCE",
            can_proceed_to_t56=False,
            recommendation="Insufficient aggregate evidence. Do not proceed to T56.",
        )

    def generate_json_report(self, verdict: T55BAggregateVerdict) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.REPORT_DIR / f"t55b_audit_{timestamp}.json"
        path.write_text(verdict.model_dump_json(indent=2), encoding="utf-8")
        return path

    def generate_markdown_report(self, verdict: T55BAggregateVerdict) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.REPORT_DIR / f"t55b_audit_{timestamp}.md"
        lines = [
            "# T55B — EDD-CVT Autonomous Evolution Audit Report",
            f"**Date:** {verdict.timestamp}",
            f"**Overall Verdict:** `{verdict.overall_verdict}`",
            f"**Can Proceed to T56:** {verdict.can_proceed_to_t56}",
            "",
            f"**Recommendation:** {verdict.recommendation}",
            "",
            "## Profile Results",
            "| Profile | Cycles | Fitness | Reconfig Rate | Safety Rate | Rollback Rate | Verdict |",
            "|---|---|---|---|---|---|---|",
        ]
        for p in verdict.profile_results:
            lines.append(
                f"| {p.profile_name} | {p.cycles_completed} | {p.mean_fitness_score:.3f} |"
                f" {p.reconfiguration_rate:.3f} | {p.safety_pass_rate:.3f} |"
                f" {p.rollback_rate:.3f} | {p.verdict} |"
            )
        lines.append("")
        lines.append("---")
        lines.append("*Generated by EvolutionAuditRunner (T55B)*")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
