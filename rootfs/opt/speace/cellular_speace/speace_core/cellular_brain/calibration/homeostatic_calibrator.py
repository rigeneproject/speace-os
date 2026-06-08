import copy
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import (
    BenchmarkResult,
    NeuroFunctionalBenchmark,
)
from speace_core.cellular_brain.regulation.energy_control_agent import EnergyControlAgent
from speace_core.dna.models import SharedGenome
from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator


class CalibrationProfile(BaseModel):
    profile_id: str
    name: str
    # Orchestrator flags
    energy_control_enabled: bool = True
    stdp_enabled: bool = True
    inhibition_enabled: bool = True
    community_detection_enabled: bool = True
    confidence_enabled: bool = True
    region_architecture_enabled: bool = True
    # EnergyControlAgent state-profile overrides
    state_profiles: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    # Explicit overrides for InhibitionEngine or other modules could go here
    description: str = ""


class CalibrationResult(BaseModel):
    profile: CalibrationProfile
    benchmark_metrics: Dict[str, Any] = Field(default_factory=dict)
    cognitive_score: float = 0.0
    coherence_phi: float = 0.0
    energy_efficiency: float = 0.0
    functional_improvement: float = 0.0
    meta_cognitive_score: Optional[float] = None
    regression_score: float = 0.0
    distance_from_baseline: float = 0.0
    passed: bool = True
    failure_reason: Optional[str] = None


class CalibrationAuditReport(BaseModel):
    audit_id: str
    created_at: str
    baseline_metrics: Dict[str, Any] = Field(default_factory=dict)
    profile_results: List[CalibrationResult] = Field(default_factory=list)
    best_profile: Optional[CalibrationProfile] = None
    best_regression_score: Optional[float] = None
    verdict: str = "insufficient_evidence"
    json_report_path: Optional[str] = None
    markdown_report_path: Optional[str] = None


class HomeostaticCalibrator:
    """Calibrate SPEACE homeostatic parameters to reduce systemic regression."""

    def __init__(
        self,
        genome: Optional[Dict[str, Any]] = None,
        report_dir: str = "reports/calibration",
        seed: int = 42,
        n_adaptive_cycles: int = 5,
        benchmark_case: str = "morphological_memory_trace",
    ):
        self._seed = seed
        self.n_adaptive_cycles = n_adaptive_cycles
        self.benchmark_case = benchmark_case
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)

        if genome is not None:
            self.genome = genome
        else:
            loaded = load_genome("speace_core/dna/genome/default_genome.yaml")
            self.genome = loaded.model_dump()

    # ------------------------------------------------------------------ #
    # Profile presets
    # ------------------------------------------------------------------ #

    @staticmethod
    def default_profiles() -> List[CalibrationProfile]:
        return [
            CalibrationProfile(
                profile_id="p0",
                name="current_full_organism",
                description="Current default energy control settings",
            ),
            CalibrationProfile(
                profile_id="p1",
                name="energy_control_off",
                energy_control_enabled=False,
                description="Disable energy control entirely",
            ),
            CalibrationProfile(
                profile_id="p2",
                name="energy_soft",
                state_profiles={
                    "critical_low": {
                        "burst_size_multiplier": 0.50,
                        "stdp_rate_multiplier": 0.25,
                        "plasticity_rate_multiplier": 0.25,
                        "neurogenesis_allowance_multiplier": 0.25,
                        "inhibition_decay_multiplier": 1.5,
                        "apoptosis_pressure_multiplier": 0.25,
                    },
                    "low": {
                        "burst_size_multiplier": 0.75,
                        "stdp_rate_multiplier": 0.75,
                        "plasticity_rate_multiplier": 0.75,
                        "neurogenesis_allowance_multiplier": 0.50,
                        "inhibition_decay_multiplier": 1.25,
                        "apoptosis_pressure_multiplier": 0.75,
                    },
                },
                description="Reduce aggressive conservation by 50%",
            ),
            CalibrationProfile(
                profile_id="p3",
                name="energy_medium",
                state_profiles={
                    "critical_low": {
                        "burst_size_multiplier": 0.375,
                        "stdp_rate_multiplier": 0.125,
                        "plasticity_rate_multiplier": 0.125,
                        "neurogenesis_allowance_multiplier": 0.125,
                        "inhibition_decay_multiplier": 1.75,
                        "apoptosis_pressure_multiplier": 0.125,
                    },
                    "low": {
                        "burst_size_multiplier": 0.625,
                        "stdp_rate_multiplier": 0.625,
                        "plasticity_rate_multiplier": 0.625,
                        "neurogenesis_allowance_multiplier": 0.25,
                        "inhibition_decay_multiplier": 1.375,
                        "apoptosis_pressure_multiplier": 0.625,
                    },
                },
                description="Reduce aggressive conservation by 25%",
            ),
            CalibrationProfile(
                profile_id="p4",
                name="energy_strict",
                state_profiles={
                    "critical_low": {
                        "burst_size_multiplier": 0.125,
                        "stdp_rate_multiplier": 0.0,
                        "plasticity_rate_multiplier": 0.0,
                        "neurogenesis_allowance_multiplier": 0.0,
                        "inhibition_decay_multiplier": 2.5,
                        "apoptosis_pressure_multiplier": 0.0,
                    },
                    "low": {
                        "burst_size_multiplier": 0.375,
                        "stdp_rate_multiplier": 0.25,
                        "plasticity_rate_multiplier": 0.25,
                        "neurogenesis_allowance_multiplier": 0.0,
                        "inhibition_decay_multiplier": 1.75,
                        "apoptosis_pressure_multiplier": 0.25,
                    },
                },
                description="More aggressive conservation than default",
            ),
            CalibrationProfile(
                profile_id="p5",
                name="stdp_preserved_energy_soft",
                state_profiles={
                    "critical_low": {
                        "burst_size_multiplier": 0.50,
                        "stdp_rate_multiplier": 0.75,
                        "plasticity_rate_multiplier": 0.25,
                        "neurogenesis_allowance_multiplier": 0.25,
                        "inhibition_decay_multiplier": 1.5,
                        "apoptosis_pressure_multiplier": 0.25,
                    },
                    "low": {
                        "burst_size_multiplier": 0.75,
                        "stdp_rate_multiplier": 1.0,
                        "plasticity_rate_multiplier": 0.75,
                        "neurogenesis_allowance_multiplier": 0.50,
                        "inhibition_decay_multiplier": 1.25,
                        "apoptosis_pressure_multiplier": 0.75,
                    },
                },
                description="Preserve STDP even when energy is soft",
            ),
            CalibrationProfile(
                profile_id="p6",
                name="inhibition_soft_decay_soft",
                state_profiles={
                    "critical_low": {
                        "burst_size_multiplier": 0.50,
                        "stdp_rate_multiplier": 0.25,
                        "plasticity_rate_multiplier": 0.25,
                        "neurogenesis_allowance_multiplier": 0.25,
                        "inhibition_decay_multiplier": 1.0,
                        "apoptosis_pressure_multiplier": 0.25,
                    },
                    "low": {
                        "burst_size_multiplier": 0.75,
                        "stdp_rate_multiplier": 0.75,
                        "plasticity_rate_multiplier": 0.75,
                        "neurogenesis_allowance_multiplier": 0.50,
                        "inhibition_decay_multiplier": 1.0,
                        "apoptosis_pressure_multiplier": 0.75,
                    },
                },
                description="Softer inhibition decay to avoid under-stimulation",
            ),
            CalibrationProfile(
                profile_id="p7",
                name="neurogenesis_preserved_energy_soft",
                state_profiles={
                    "critical_low": {
                        "burst_size_multiplier": 0.50,
                        "stdp_rate_multiplier": 0.25,
                        "plasticity_rate_multiplier": 0.25,
                        "neurogenesis_allowance_multiplier": 0.50,
                        "inhibition_decay_multiplier": 1.5,
                        "apoptosis_pressure_multiplier": 0.25,
                    },
                    "low": {
                        "burst_size_multiplier": 0.75,
                        "stdp_rate_multiplier": 0.75,
                        "plasticity_rate_multiplier": 0.75,
                        "neurogenesis_allowance_multiplier": 0.75,
                        "inhibition_decay_multiplier": 1.25,
                        "apoptosis_pressure_multiplier": 0.75,
                    },
                },
                description="Preserve neurogenesis even in low energy",
            ),
        ]

    # ------------------------------------------------------------------ #
    # Orchestrator factory
    # ------------------------------------------------------------------ #

    def build_orchestrator(self) -> CellularBrainOrchestrator:
        genome = SharedGenome(**self.genome)
        return CellularBrainOrchestrator.build_mvp(genome)

    @staticmethod
    def apply_profile_to_orchestrator(
        profile: CalibrationProfile, orch: CellularBrainOrchestrator
    ) -> None:
        orch.energy_control_enabled = profile.energy_control_enabled
        orch.stdp_enabled = profile.stdp_enabled
        orch.inhibition_enabled = profile.inhibition_enabled
        orch.community_detection_enabled = profile.community_detection_enabled
        orch.confidence_enabled = profile.confidence_enabled
        orch.region_architecture_enabled = profile.region_architecture_enabled

        if profile.state_profiles and orch._energy_control is not None:
            base = EnergyControlAgent.DEFAULT_STATE_PROFILES
            merged: Dict[str, Dict[str, float]] = {}
            for state, defaults in base.items():
                merged[state] = dict(defaults)
                if state in profile.state_profiles:
                    merged[state].update(profile.state_profiles[state])
            orch._energy_control.state_profiles = merged

    # ------------------------------------------------------------------ #
    # Single profile run
    # ------------------------------------------------------------------ #

    async def run_profile(self, profile: CalibrationProfile) -> CalibrationResult:
        orch = self.build_orchestrator()
        self.apply_profile_to_orchestrator(profile, orch)
        benchmark = NeuroFunctionalBenchmark(orch)
        pattern = [1.0 if i % 2 == 0 else 0.0 for i in range(10)]

        try:
            result = await benchmark.run_case(
                self.benchmark_case,
                execution_mode="event_driven_burst",
                stdp_enabled=profile.stdp_enabled,
                inhibition_enabled=profile.inhibition_enabled,
                energy_control_enabled=profile.energy_control_enabled,
                community_detection_enabled=profile.community_detection_enabled,
                confidence_enabled=profile.confidence_enabled,
                input_pattern=pattern,
                target_output=pattern,
                n_ticks=self.n_adaptive_cycles,
            )
        except Exception as exc:
            return CalibrationResult(
                profile=profile,
                benchmark_metrics={},
                passed=False,
                failure_reason=str(exc),
            )

        m = result.metrics
        return CalibrationResult(
            profile=profile,
            benchmark_metrics=m.model_dump(),
            cognitive_score=m.speace_cognitive_score,
            coherence_phi=m.coherence_phi,
            energy_efficiency=m.energy_efficiency,
            functional_improvement=m.functional_improvement,
            meta_cognitive_score=m.meta_cognitive_score,
            regression_score=0.0,
            distance_from_baseline=0.0,
            passed=True,
        )

    # ------------------------------------------------------------------ #
    # Suite run
    # ------------------------------------------------------------------ #

    async def run_calibration_suite(
        self, profiles: Optional[List[CalibrationProfile]] = None
    ) -> CalibrationAuditReport:
        profs = profiles or self.default_profiles()

        # Baseline: run current full organism first to capture baseline metrics
        baseline_profile = CalibrationProfile(
            profile_id="baseline",
            name="baseline_current_full_organism",
            energy_control_enabled=True,
        )
        baseline_result = await self.run_profile(baseline_profile)
        baseline_metrics = baseline_result.benchmark_metrics

        results: List[CalibrationResult] = []
        for p in profs:
            res = await self.run_profile(p)
            res.regression_score = self.compute_regression_score(
                res, baseline_metrics
            )
            res.distance_from_baseline = self.compute_distance_from_baseline(
                res, baseline_metrics
            )
            results.append(res)

        best = self.select_best_profile(results, baseline_metrics)
        verdict = self._compute_verdict(results, baseline_metrics)

        report = CalibrationAuditReport(
            audit_id=f"cal_{uuid.uuid4().hex[:8]}",
            created_at=datetime.now(timezone.utc).isoformat(),
            baseline_metrics=baseline_metrics,
            profile_results=results,
            best_profile=best.profile if best else None,
            best_regression_score=best.regression_score if best else None,
            verdict=verdict,
        )

        json_path = self.generate_json_report(report)
        md_path = self.generate_markdown_report(report)
        report.json_report_path = str(json_path)
        report.markdown_report_path = str(md_path)

        return report

    # ------------------------------------------------------------------ #
    # Scoring
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_regression_score(
        result: CalibrationResult, baseline_metrics: Dict[str, Any]
    ) -> float:
        b_cog = baseline_metrics.get("speace_cognitive_score", 0.0)
        b_phi = baseline_metrics.get("coherence_phi", 0.0)
        b_ene = baseline_metrics.get("energy_efficiency", 0.0)
        r_cog = result.cognitive_score
        r_phi = result.coherence_phi
        r_ene = result.energy_efficiency
        r_func = result.functional_improvement
        r_meta = result.meta_cognitive_score or 0.0

        score = (
            0.30 * max(0.0, r_cog - b_cog)
            + 0.25 * max(0.0, r_phi - b_phi)
            + 0.20 * max(0.0, r_ene - b_ene)
            + 0.15 * max(0.0, r_func)
            + 0.10 * max(0.0, r_meta)
        )
        return max(0.0, min(1.0, score))

    @staticmethod
    def compute_distance_from_baseline(
        result: CalibrationResult, baseline_metrics: Dict[str, Any]
    ) -> float:
        b_cog = baseline_metrics.get("speace_cognitive_score", 0.0)
        b_phi = baseline_metrics.get("coherence_phi", 0.0)
        b_ene = baseline_metrics.get("energy_efficiency", 0.0)
        return (
            abs(result.cognitive_score - b_cog)
            + abs(result.coherence_phi - b_phi)
            + abs(result.energy_efficiency - b_ene)
        )

    @staticmethod
    def select_best_profile(
        results: List[CalibrationResult],
        baseline_metrics: Dict[str, Any],
    ) -> Optional[CalibrationResult]:
        passed = [r for r in results if r.passed]
        if not passed:
            return None

        # If any profile improves over baseline, pick highest regression_score
        has_improver = any(r.regression_score > 0.0 for r in passed)
        if has_improver:
            return max(passed, key=lambda r: r.regression_score)

        # Otherwise pick the one with smallest distance from baseline (least regressive)
        return min(passed, key=lambda r: r.distance_from_baseline)

    @staticmethod
    def _compute_verdict(
        results: List[CalibrationResult], baseline_metrics: Dict[str, Any]
    ) -> str:
        passed = [r for r in results if r.passed]
        if not passed:
            return "insufficient_evidence"

        has_improver = any(r.regression_score > 0.0 for r in passed)
        if has_improver:
            return "regression_reduced"

        # Check if at least one profile is less regressive than current default
        baseline_dist = None
        for r in passed:
            if r.profile.name == "current_full_organism":
                baseline_dist = r.distance_from_baseline
                break

        if baseline_dist is not None:
            better = [r for r in passed if r.distance_from_baseline < baseline_dist]
            if better:
                return "partially_stabilized"

        return "regression_persists"

    # ------------------------------------------------------------------ #
    # Reports
    # ------------------------------------------------------------------ #

    def generate_json_report(self, report: CalibrationAuditReport) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"calibration_{timestamp}.json"
        path = self.report_dir / filename
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return path

    def generate_markdown_report(self, report: CalibrationAuditReport) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"calibration_{timestamp}.md"
        path = self.report_dir / filename

        b = report.baseline_metrics
        lines: List[str] = [
            "# SPEACE Homeostatic Calibration Report",
            "",
            f"**Audit ID:** {report.audit_id}",
            f"**Date:** {report.created_at}",
            f"**Profiles tested:** {len(report.profile_results)}",
            f"**Verdict:** {report.verdict.upper()}",
            "",
            "## Baseline Metrics",
            f"- Cognitive score: {b.get('speace_cognitive_score', 0.0):.4f}",
            f"- Coherence Phi: {b.get('coherence_phi', 0.0):.4f}",
            f"- Energy efficiency: {b.get('energy_efficiency', 0.0):.4f}",
            f"- Functional improvement: {b.get('functional_improvement', 0.0):.4f}",
            f"- Meta-cognitive score: {b.get('meta_cognitive_score', 0.0):.4f}",
            "",
            "## Comparative Results",
            "",
            "| Profile | Cognitive | Phi | Energy | Reg Score | Distance | Passed |",
            "|---|---|---|---|---|---|---|",
        ]

        for r in report.profile_results:
            lines.append(
                f"| {r.profile.name} | "
                f"{r.cognitive_score:.4f} | "
                f"{r.coherence_phi:.4f} | "
                f"{r.energy_efficiency:.4f} | "
                f"{r.regression_score:.4f} | "
                f"{r.distance_from_baseline:.4f} | "
                f"{'PASS' if r.passed else 'FAIL'} |"
            )

        if report.best_profile is not None:
            lines.extend([
                "",
                "## Best Profile",
                f"- **Name:** {report.best_profile.name}",
                f"- **Regression score:** {report.best_regression_score}",
                f"- **Description:** {report.best_profile.description}",
            ])

        lines.extend([
            "",
            "---",
            "*Generated by HomeostaticCalibrator v0.3*",
        ])

        path.write_text("\n".join(lines), encoding="utf-8")
        return path
