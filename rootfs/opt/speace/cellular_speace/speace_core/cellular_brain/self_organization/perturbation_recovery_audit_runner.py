import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from speace_core.cellular_brain.self_organization.perturbation_recovery_audit import (
    ControlledPerturbationRecoveryAudit,
    PerturbationRecoveryResult,
    PerturbationVerdict,
)
from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator


class PerturbationProfileConfig(BaseModel):
    name: str
    description: str
    region_stability_controller_enabled: bool = False
    brainstem_controller_enabled: bool = False
    brainstem_gain_controller_enabled: bool = False
    perturbation_recovery_audit_enabled: bool = True
    region_signal_routing_enabled: bool = True


class ProfileResult(BaseModel):
    profile_name: str
    results: List[PerturbationRecoveryResult]
    mean_recovery_score: float = 0.0
    min_recovery_score: float = 0.0
    validated_count: int = 0
    partial_count: int = 0
    collapse_count: int = 0
    over_suppression_count: int = 0
    no_effect_count: int = 0
    insufficient_count: int = 0
    worst_verdict: str = ""
    recommended_next_step: str = ""


class T54BAggregateVerdict(BaseModel):
    overall_verdict: str
    can_proceed_to_t55: bool = False
    t55_conservative_mode: bool = False
    recommendation: str = ""
    profile_results: List[ProfileResult] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PerturbationRecoveryAuditRunner:
    """T54B — Real-run Perturbation Recovery Audit across multiple profiles."""

    REPORT_DIR = Path("reports/perturbation_recovery")

    PROFILES: List[PerturbationProfileConfig] = [
        PerturbationProfileConfig(
            name="baseline_no_t53",
            description="No T53/T54 controllers enabled. Pure baseline.",
            region_stability_controller_enabled=False,
            brainstem_controller_enabled=False,
            brainstem_gain_controller_enabled=False,
            perturbation_recovery_audit_enabled=True,
            region_signal_routing_enabled=True,
        ),
        PerturbationProfileConfig(
            name="t53_controller_only",
            description="T53 self-organization concept only; no brainstem/stability.",
            region_stability_controller_enabled=False,
            brainstem_controller_enabled=False,
            brainstem_gain_controller_enabled=False,
            perturbation_recovery_audit_enabled=True,
            region_signal_routing_enabled=True,
        ),
        PerturbationProfileConfig(
            name="t53_plus_brainstem",
            description="T53 + Brainstem Functional Controller.",
            region_stability_controller_enabled=False,
            brainstem_controller_enabled=True,
            brainstem_gain_controller_enabled=False,
            perturbation_recovery_audit_enabled=True,
            region_signal_routing_enabled=True,
        ),
        PerturbationProfileConfig(
            name="t53_plus_stability",
            description="T53 + Region Stability Controller.",
            region_stability_controller_enabled=True,
            brainstem_controller_enabled=False,
            brainstem_gain_controller_enabled=False,
            perturbation_recovery_audit_enabled=True,
            region_signal_routing_enabled=True,
        ),
        PerturbationProfileConfig(
            name="t53_plus_recovery_policy",
            description="T53 + Brainstem + Stability (recovery policy stack).",
            region_stability_controller_enabled=True,
            brainstem_controller_enabled=True,
            brainstem_gain_controller_enabled=False,
            perturbation_recovery_audit_enabled=True,
            region_signal_routing_enabled=True,
        ),
        PerturbationProfileConfig(
            name="full_recovery_stack",
            description="Full T53 + T54 recovery stack with gain controller.",
            region_stability_controller_enabled=True,
            brainstem_controller_enabled=True,
            brainstem_gain_controller_enabled=True,
            perturbation_recovery_audit_enabled=True,
            region_signal_routing_enabled=True,
        ),
    ]

    def __init__(
        self,
        genome_path: str = "speace_core/dna/genome/default_genome.yaml",
        warmup_ticks: int = 3,
        perturbation_ticks: int = 5,
        recovery_ticks: int = 12,
    ):
        self.genome_path = genome_path
        self.warmup_ticks = warmup_ticks
        self.perturbation_ticks = perturbation_ticks
        self.recovery_ticks = recovery_ticks
        self.REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Profile execution
    # ------------------------------------------------------------------ #

    def _build_orchestrator(self, profile: PerturbationProfileConfig) -> CellularBrainOrchestrator:
        genome = load_genome(self.genome_path)
        orch = CellularBrainOrchestrator.build_mvp(genome)
        orch.region_signal_routing_enabled = profile.region_signal_routing_enabled
        orch.region_stability_controller_enabled = profile.region_stability_controller_enabled
        orch.brainstem_controller_enabled = profile.brainstem_controller_enabled
        orch.brainstem_gain_controller_enabled = profile.brainstem_gain_controller_enabled
        orch.perturbation_recovery_audit_enabled = profile.perturbation_recovery_audit_enabled
        return orch

    async def run_profile(self, profile: PerturbationProfileConfig) -> ProfileResult:
        orch = self._build_orchestrator(profile)
        audit = ControlledPerturbationRecoveryAudit(orchestrator=orch, seed=42)
        scenarios = audit.build_default_scenarios()
        results: List[PerturbationRecoveryResult] = []
        for scenario in scenarios:
            result = await audit.run_scenario(
                scenario,
                warmup_ticks=self.warmup_ticks,
                perturbation_ticks=self.perturbation_ticks,
                recovery_ticks=self.recovery_ticks,
            )
            results.append(result)

        scores = [r.post_perturbation_recovery_score for r in results]
        verdicts = [r.verdict for r in results]

        validated = sum(1 for v in verdicts if v == PerturbationVerdict.PERTURBATION_RECOVERY_VALIDATED)
        partial = sum(1 for v in verdicts if v == PerturbationVerdict.RECOVERY_PARTIAL)
        collapse = sum(
            1
            for v in verdicts
            if v in (PerturbationVerdict.PHI_COLLAPSE, PerturbationVerdict.ENERGY_COLLAPSE, PerturbationVerdict.COGNITIVE_COLLAPSE)
        )
        over_suppression = sum(1 for v in verdicts if v == PerturbationVerdict.OVER_SUPPRESSION)
        no_effect = sum(1 for v in verdicts if v == PerturbationVerdict.PERTURBATION_NO_EFFECT)
        insufficient = sum(1 for v in verdicts if v == PerturbationVerdict.INSUFFICIENT_EVIDENCE)

        worst = self._worst_verdict(verdicts)
        recommendation = self._profile_recommendation(worst, scores)

        return ProfileResult(
            profile_name=profile.name,
            results=results,
            mean_recovery_score=sum(scores) / len(scores) if scores else 0.0,
            min_recovery_score=min(scores) if scores else 0.0,
            validated_count=validated,
            partial_count=partial,
            collapse_count=collapse,
            over_suppression_count=over_suppression,
            no_effect_count=no_effect,
            insufficient_count=insufficient,
            worst_verdict=worst.value if worst else "",
            recommended_next_step=recommendation,
        )

    # ------------------------------------------------------------------ #
    # Verdict helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _worst_verdict(verdicts: List[PerturbationVerdict]) -> PerturbationVerdict | None:
        priority = [
            PerturbationVerdict.PHI_COLLAPSE,
            PerturbationVerdict.ENERGY_COLLAPSE,
            PerturbationVerdict.COGNITIVE_COLLAPSE,
            PerturbationVerdict.UNSAFE_RECOVERY,
            PerturbationVerdict.OVER_SUPPRESSION,
            PerturbationVerdict.RECOVERY_SLOW,
            PerturbationVerdict.INSUFFICIENT_EVIDENCE,
            PerturbationVerdict.RECOVERY_PARTIAL,
            PerturbationVerdict.PERTURBATION_NO_EFFECT,
            PerturbationVerdict.PERTURBATION_RECOVERY_VALIDATED,
        ]
        for v in priority:
            if v in verdicts:
                return v
        return verdicts[0] if verdicts else None

    @staticmethod
    def _profile_recommendation(worst: PerturbationVerdict | None, scores: List[float]) -> str:
        if worst in (PerturbationVerdict.PHI_COLLAPSE, PerturbationVerdict.ENERGY_COLLAPSE, PerturbationVerdict.COGNITIVE_COLLAPSE):
            return "BLOCK_T55"
        if worst == PerturbationVerdict.OVER_SUPPRESSION:
            return "TUNE_T53"
        if worst == PerturbationVerdict.PERTURBATION_NO_EFFECT:
            return "INCREASE_STRENGTH"
        mean_score = sum(scores) / len(scores) if scores else 0.0
        if mean_score >= 0.65:
            return "PROCEED_T55"
        if mean_score >= 0.45:
            return "PROCEED_T55_CONSERVATIVE"
        return "BLOCK_T55"

    # ------------------------------------------------------------------ #
    # Suite
    # ------------------------------------------------------------------ #

    async def run_suite(self) -> T54BAggregateVerdict:
        profile_results: List[ProfileResult] = []
        for profile in self.PROFILES:
            result = await self.run_profile(profile)
            profile_results.append(result)

        overall = self._compute_aggregate_verdict(profile_results)
        overall.profile_results = profile_results
        return overall

    @staticmethod
    def _compute_aggregate_verdict(profile_results: List[ProfileResult]) -> T54BAggregateVerdict:
        all_recommendations = {p.recommended_next_step for p in profile_results}

        if "BLOCK_T55" in all_recommendations:
            return T54BAggregateVerdict(
                overall_verdict="BLOCK_T55",
                can_proceed_to_t55=False,
                t55_conservative_mode=False,
                recommendation="At least one profile detected collapse. Do not proceed to T55.",
            )

        if "TUNE_T53" in all_recommendations:
            return T54BAggregateVerdict(
                overall_verdict="TUNE_T53",
                can_proceed_to_t55=False,
                t55_conservative_mode=False,
                recommendation="Over-suppression detected in at least one profile. Tune T53 before T55.",
            )

        mean_scores = [p.mean_recovery_score for p in profile_results]
        global_mean = sum(mean_scores) / len(mean_scores) if mean_scores else 0.0

        if global_mean >= 0.65 and "PROCEED_T55" in all_recommendations:
            return T54BAggregateVerdict(
                overall_verdict="PROCEED_T55",
                can_proceed_to_t55=True,
                t55_conservative_mode=False,
                recommendation="Recovery validated across profiles. Proceed to T55 normally.",
            )

        if global_mean >= 0.45:
            return T54BAggregateVerdict(
                overall_verdict="PROCEED_T55_CONSERVATIVE",
                can_proceed_to_t55=True,
                t55_conservative_mode=True,
                recommendation="Partial recovery. Proceed to T55 with conservative perturbations.",
            )

        return T54BAggregateVerdict(
            overall_verdict="INSUFFICIENT_EVIDENCE",
            can_proceed_to_t55=False,
            t55_conservative_mode=False,
            recommendation="Insufficient recovery evidence. Do not proceed to T55.",
        )

    # ------------------------------------------------------------------ #
    # Reports
    # ------------------------------------------------------------------ #

    def generate_json_report(self, verdict: T54BAggregateVerdict) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.REPORT_DIR / f"t54b_audit_{timestamp}.json"
        path.write_text(verdict.model_dump_json(indent=2), encoding="utf-8")
        return path

    def generate_markdown_report(self, verdict: T54BAggregateVerdict) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.REPORT_DIR / f"t54b_audit_{timestamp}.md"
        lines = [
            "# T54B — Real-run Perturbation Recovery Audit Report",
            f"**Date:** {verdict.timestamp}",
            f"**Overall Verdict:** `{verdict.overall_verdict}`",
            f"**Can Proceed to T55:** {verdict.can_proceed_to_t55}",
            f"**Conservative Mode:** {verdict.t55_conservative_mode}",
            "",
            f"**Recommendation:** {verdict.recommendation}",
            "",
            "## Profile Results",
            "| Profile | Mean Score | Min Score | Validated | Partial | Collapse | Over-Suppression | Worst Verdict | Next Step |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for p in verdict.profile_results:
            lines.append(
                f"| {p.profile_name} | {p.mean_recovery_score:.3f} | {p.min_recovery_score:.3f} |"
                f" {p.validated_count} | {p.partial_count} | {p.collapse_count} |"
                f" {p.over_suppression_count} | {p.worst_verdict} | {p.recommended_next_step} |"
            )
        lines.append("")
        lines.append("## Scenario Details")
        for p in verdict.profile_results:
            lines.append(f"### {p.profile_name}")
            for r in p.results:
                lines.append(
                    f"- {r.scenario_name}: score={r.post_perturbation_recovery_score:.4f}"
                    f" verdict={r.verdict.value} latency={r.recovery_latency_ticks}"
                )
            lines.append("")
        lines.append("---")
        lines.append("*Generated by PerturbationRecoveryAuditRunner (T54B)*")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
