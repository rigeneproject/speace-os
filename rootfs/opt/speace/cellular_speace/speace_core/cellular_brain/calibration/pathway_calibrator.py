import copy
import json
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import (
    BenchmarkResult,
    NeuroFunctionalBenchmark,
)
from speace_core.cellular_brain.calibration.homeostatic_calibrator import HomeostaticCalibrator
from speace_core.dna.models import SharedGenome
from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator


class PathwayCalibrationProfile(BaseModel):
    profile_id: str
    name: str
    inter_region_plasticity_enabled: bool = True
    region_signal_routing_enabled: bool = False
    trigger_mode: str = "hard_spike"
    ltp_rate: float = 0.05
    ltd_rate: float = 0.03
    min_strength: float = 0.0
    max_strength: float = 1.0
    stdp_window: int = 1
    energy_cost_per_update: float = 0.001
    confidence_modulation_strength: float = 1.0
    energy_modulation_strength: float = 1.0
    # T29 — tuning profile ID (e.g. "t0", "t1", ...)
    tuner_profile_id: Optional[str] = None
    description: str = ""


class PathwayCalibrationResult(BaseModel):
    profile: PathwayCalibrationProfile
    benchmark_metrics: Dict[str, Any] = Field(default_factory=dict)
    speace_cognitive_score: float = 0.0
    coherence_phi: float = 0.0
    energy_efficiency: float = 0.0
    mean_pathway_strength: float = 0.0
    reinforced_pathways: int = 0
    weakened_pathways: int = 0
    pathway_energy_cost: float = 0.0
    regional_signal_flow_score: float = 0.0
    inter_region_plasticity_events: int = 0
    routed_signals: int = 0
    delivered_signals: int = 0
    blocked_signals: int = 0
    routing_energy_cost: float = 0.0
    active_inter_region_pathways: int = 0
    region_plasticity_triggers: int = 0
    soft_activation_triggers: int = 0
    routing_aware_triggers: int = 0
    temporal_correlation_triggers: int = 0
    region_causal_score: float = 0.0
    trigger_to_update_ratio: float = 0.0
    regression_score: float = 0.0
    distance_from_baseline: float = 0.0
    # T29 — tuning metrics
    tuning_accepted_updates: int = 0
    tuning_skipped_updates: int = 0
    tuning_rolled_back_updates: int = 0
    tuning_pathway_utility_score: float = 0.0
    # T30 — utility learning metrics
    mean_pathway_utility: float = 0.0
    best_pathway_utility: float = 0.0
    worst_pathway_utility: float = 0.0
    rewarded_pathways: int = 0
    penalized_pathways: int = 0
    pathway_reward_mean: float = 0.0
    pathway_cost_mean: float = 0.0
    utility_gated_updates: int = 0
    utility_skipped_updates: int = 0
    passed: bool = True
    failure_reason: Optional[str] = None


class PathwayAuditReport(BaseModel):
    audit_id: str
    created_at: str
    baseline_metrics: Dict[str, Any] = Field(default_factory=dict)
    profile_results: List[PathwayCalibrationResult] = Field(default_factory=list)
    best_profile: Optional[PathwayCalibrationProfile] = None
    verdict: str = "insufficient_evidence"
    json_report_path: Optional[str] = None
    markdown_report_path: Optional[str] = None


class PathwayCalibrator:
    """Calibrate inter-region plasticity parameters against post-T23 baselines.

    Uses energy_medium as the fixed homeostatic baseline (T22 best profile).
    """

    def __init__(
        self,
        genome: Optional[Dict[str, Any]] = None,
        report_dir: str = "reports/pathway",
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
    def default_profiles() -> List[PathwayCalibrationProfile]:
        return [
            PathwayCalibrationProfile(
                profile_id="p0",
                name="inter_region_off",
                inter_region_plasticity_enabled=False,
                region_signal_routing_enabled=False,
                description="Disable inter-region plasticity and routing (baseline)",
            ),
            PathwayCalibrationProfile(
                profile_id="p1",
                name="routing_only",
                inter_region_plasticity_enabled=False,
                region_signal_routing_enabled=True,
                description="Enable routing only, no plasticity",
            ),
            PathwayCalibrationProfile(
                profile_id="p2",
                name="plasticity_without_routing",
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=False,
                trigger_mode="hard_spike",
                description="Enable plasticity without routing",
            ),
            PathwayCalibrationProfile(
                profile_id="p3",
                name="routing_plus_plasticity",
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                trigger_mode="hybrid",
                description="Enable both routing and plasticity (hybrid trigger)",
            ),
            PathwayCalibrationProfile(
                profile_id="p4",
                name="routing_plus_low_plasticity",
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                trigger_mode="hybrid",
                ltp_rate=0.02,
                ltd_rate=0.01,
                description="Routing + low LTP/LTD (hybrid trigger)",
            ),
            PathwayCalibrationProfile(
                profile_id="p5",
                name="routing_plus_medium_plasticity",
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                trigger_mode="hybrid",
                ltp_rate=0.04,
                ltd_rate=0.025,
                description="Routing + medium LTP/LTD (hybrid trigger)",
            ),
            PathwayCalibrationProfile(
                profile_id="p6",
                name="routing_plus_high_plasticity",
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                trigger_mode="hybrid",
                ltp_rate=0.08,
                ltd_rate=0.06,
                description="Routing + aggressive LTP/LTD (hybrid trigger)",
            ),
            PathwayCalibrationProfile(
                profile_id="p7",
                name="routing_plus_energy_conservative",
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                trigger_mode="hybrid",
                ltp_rate=0.03,
                ltd_rate=0.02,
                energy_cost_per_update=0.0005,
                energy_modulation_strength=1.5,
                description="Routing + conservative energy pathways (hybrid trigger)",
            ),
            # T29 — Pathway Plasticity Sensitivity Tuning profiles
            PathwayCalibrationProfile(
                profile_id="p8",
                name="routing_plus_tuning_default",
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                trigger_mode="hybrid",
                tuner_profile_id="t0",
                description="Routing + T29 default hybrid tuning (no guards)",
            ),
            PathwayCalibrationProfile(
                profile_id="p9",
                name="routing_plus_tuning_conservative_phi",
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                trigger_mode="hybrid",
                tuner_profile_id="t1",
                description="Routing + T29 conservative phi-guarded tuning",
            ),
            PathwayCalibrationProfile(
                profile_id="p10",
                name="routing_plus_tuning_full_guard",
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                trigger_mode="hybrid",
                tuner_profile_id="t9",
                description="Routing + T29 adaptive full-guard tuning (all guards + rollback)",
            ),
            # T30 — Pathway Utility Learning profiles
            PathwayCalibrationProfile(
                profile_id="p11",
                name="routing_plus_tuning_with_utility_learning",
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                trigger_mode="hybrid",
                tuner_profile_id="t9",
                description="Routing + T29 tuning + T30 utility learning reward modulation",
            ),
            PathwayCalibrationProfile(
                profile_id="p12",
                name="routing_plus_tuning_utility_negative_penalty",
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                trigger_mode="hybrid",
                tuner_profile_id="t9",
                description="Routing + T29 tuning + T30 aggressive utility penalty on negative pathways",
            ),
        ]

    # ------------------------------------------------------------------ #
    # Orchestrator factory
    # ------------------------------------------------------------------ #

    def build_orchestrator(self) -> CellularBrainOrchestrator:
        random.seed(self._seed)
        genome = SharedGenome(**self.genome)
        return CellularBrainOrchestrator.build_mvp(genome)

    @staticmethod
    def apply_homeostatic_baseline(orch: CellularBrainOrchestrator) -> None:
        """Apply energy_medium as the fixed metabolic baseline."""
        profiles = HomeostaticCalibrator.default_profiles()
        energy_medium = next((p for p in profiles if p.name == "energy_medium"), None)
        if energy_medium is not None:
            HomeostaticCalibrator.apply_profile_to_orchestrator(energy_medium, orch)
        else:
            # Fallback: at least ensure energy control is on with reasonable defaults
            orch.energy_control_enabled = True

    @staticmethod
    def apply_pathway_profile(
        profile: PathwayCalibrationProfile, orch: CellularBrainOrchestrator
    ) -> None:
        from speace_core.cellular_brain.regions.pathway_plasticity_tuner import PathwayPlasticityTuner
        orch.inter_region_plasticity_enabled = profile.inter_region_plasticity_enabled
        orch.region_signal_routing_enabled = profile.region_signal_routing_enabled
        if profile.inter_region_plasticity_enabled and orch._inter_region_plasticity is not None:
            engine = orch._inter_region_plasticity
            engine.ltp_rate = profile.ltp_rate
            engine.ltd_rate = profile.ltd_rate
            engine.min_strength = profile.min_strength
            engine.max_strength = profile.max_strength
            engine.stdp_window = profile.stdp_window
            engine.energy_cost_per_update = profile.energy_cost_per_update
            engine.confidence_modulation_strength = profile.confidence_modulation_strength
            engine.energy_modulation_strength = profile.energy_modulation_strength
            engine.trigger_mode = profile.trigger_mode
            engine._trigger.trigger_mode = profile.trigger_mode
            # T29 — attach tuning profile if specified
            if profile.tuner_profile_id is not None:
                all_tuner_profiles = PathwayPlasticityTuner.default_profiles()
                tuner_profile = next(
                    (p for p in all_tuner_profiles if p.profile_id == profile.tuner_profile_id), None
                )
                engine.tuner_profile = tuner_profile
            else:
                engine.tuner_profile = None

    # ------------------------------------------------------------------ #
    # Single profile run
    # ------------------------------------------------------------------ #

    async def run_profile(self, profile: PathwayCalibrationProfile) -> PathwayCalibrationResult:
        orch = self.build_orchestrator()
        self.apply_homeostatic_baseline(orch)
        self.apply_pathway_profile(profile, orch)
        benchmark = NeuroFunctionalBenchmark(orch)
        pattern = [1.0 if i % 2 == 0 else 0.0 for i in range(10)]

        try:
            result = await benchmark.run_case(
                self.benchmark_case,
                execution_mode="event_driven_burst",
                stdp_enabled=True,
                inhibition_enabled=True,
                energy_control_enabled=True,
                community_detection_enabled=True,
                confidence_enabled=True,
                inter_region_plasticity_enabled=profile.inter_region_plasticity_enabled,
                region_signal_routing_enabled=profile.region_signal_routing_enabled,
                input_pattern=pattern,
                target_output=pattern,
                n_ticks=self.n_adaptive_cycles,
            )
        except Exception as exc:
            return PathwayCalibrationResult(
                profile=profile,
                benchmark_metrics={},
                passed=False,
                failure_reason=str(exc),
            )

        m = result.metrics
        return PathwayCalibrationResult(
            profile=profile,
            benchmark_metrics=m.model_dump(),
            speace_cognitive_score=m.speace_cognitive_score,
            coherence_phi=m.coherence_phi,
            energy_efficiency=m.energy_efficiency,
            mean_pathway_strength=m.mean_pathway_strength,
            reinforced_pathways=m.reinforced_pathways,
            weakened_pathways=m.weakened_pathways,
            pathway_energy_cost=m.pathway_energy_cost,
            regional_signal_flow_score=m.regional_signal_flow_score,
            inter_region_plasticity_events=m.reinforced_pathways + m.weakened_pathways,
            routed_signals=m.routed_signals,
            delivered_signals=m.delivered_signals,
            blocked_signals=m.blocked_signals,
            routing_energy_cost=m.routing_energy_cost,
            active_inter_region_pathways=m.active_inter_region_pathways,
            tuning_accepted_updates=m.pathway_tuning_accepted_updates,
            tuning_skipped_updates=m.pathway_tuning_skipped_updates,
            tuning_rolled_back_updates=m.pathway_tuning_rolled_back_updates,
            tuning_pathway_utility_score=0.0,
            mean_pathway_utility=m.mean_pathway_utility,
            best_pathway_utility=m.best_pathway_utility,
            worst_pathway_utility=m.worst_pathway_utility,
            rewarded_pathways=m.rewarded_pathways,
            penalized_pathways=m.penalized_pathways,
            pathway_reward_mean=m.pathway_reward_mean,
            pathway_cost_mean=m.pathway_cost_mean,
            utility_gated_updates=m.utility_gated_updates,
            utility_skipped_updates=m.utility_skipped_updates,
            regression_score=0.0,
            distance_from_baseline=0.0,
            passed=True,
        )

    # ------------------------------------------------------------------ #
    # Suite run
    # ------------------------------------------------------------------ #

    async def run_pathway_calibration_suite(
        self, profiles: Optional[List[PathwayCalibrationProfile]] = None
    ) -> PathwayAuditReport:
        profs = profiles or self.default_profiles()

        # Baseline: run inter_region_off first
        baseline_profile = PathwayCalibrationProfile(
            profile_id="baseline",
            name="baseline_inter_region_off",
            inter_region_plasticity_enabled=False,
        )
        baseline_result = await self.run_profile(baseline_profile)
        baseline_metrics = baseline_result.benchmark_metrics

        results: List[PathwayCalibrationResult] = []
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

        report = PathwayAuditReport(
            audit_id=f"pw_{uuid.uuid4().hex[:8]}",
            created_at=datetime.now(timezone.utc).isoformat(),
            baseline_metrics=baseline_metrics,
            profile_results=results,
            best_profile=best.profile if best else None,
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
        result: PathwayCalibrationResult, baseline_metrics: Dict[str, Any]
    ) -> float:
        b_cog = baseline_metrics.get("speace_cognitive_score", 0.0)
        b_phi = baseline_metrics.get("coherence_phi", 0.0)
        b_ene = baseline_metrics.get("energy_efficiency", 0.0)
        b_flow = baseline_metrics.get("regional_signal_flow_score", 0.0)
        b_func = baseline_metrics.get("functional_improvement", 0.0)
        b_meta = baseline_metrics.get("meta_cognitive_score", 0.0)

        r_cog = result.speace_cognitive_score
        r_phi = result.coherence_phi
        r_ene = result.energy_efficiency
        r_flow = result.regional_signal_flow_score
        r_func = result.benchmark_metrics.get("functional_improvement", 0.0)
        r_meta = result.benchmark_metrics.get("meta_cognitive_score", 0.0)

        score = (
            0.25 * max(0.0, r_cog - b_cog)
            + 0.25 * max(0.0, r_phi - b_phi)
            + 0.20 * max(0.0, r_ene - b_ene)
            + 0.20 * max(0.0, r_flow - b_flow)
            + 0.10 * max(0.0, r_func - b_func)
            + 0.10 * max(0.0, r_meta - b_meta)
        )
        return max(0.0, min(1.0, score))

    @staticmethod
    def compute_distance_from_baseline(
        result: PathwayCalibrationResult, baseline_metrics: Dict[str, Any]
    ) -> float:
        b_cog = baseline_metrics.get("speace_cognitive_score", 0.0)
        b_phi = baseline_metrics.get("coherence_phi", 0.0)
        b_ene = baseline_metrics.get("energy_efficiency", 0.0)
        b_flow = baseline_metrics.get("regional_signal_flow_score", 0.0)
        return (
            abs(result.speace_cognitive_score - b_cog)
            + abs(result.coherence_phi - b_phi)
            + abs(result.energy_efficiency - b_ene)
            + abs(result.regional_signal_flow_score - b_flow)
        )

    @staticmethod
    def select_best_profile(
        results: List[PathwayCalibrationResult],
        baseline_metrics: Dict[str, Any],
    ) -> Optional[PathwayCalibrationResult]:
        passed = [r for r in results if r.passed]
        if not passed:
            return None

        has_improver = any(r.regression_score > 0.0 for r in passed)
        if has_improver:
            return max(passed, key=lambda r: r.regression_score)

        return min(passed, key=lambda r: r.distance_from_baseline)

    @staticmethod
    def _compute_verdict(
        results: List[PathwayCalibrationResult], baseline_metrics: Dict[str, Any]
    ) -> str:
        passed = [r for r in results if r.passed]
        if not passed:
            return "insufficient_evidence"

        # Baseline reference
        b_cog = baseline_metrics.get("speace_cognitive_score", 0.0)
        b_phi = baseline_metrics.get("coherence_phi", 0.0)
        b_ene = baseline_metrics.get("energy_efficiency", 0.0)

        # Profiles with routing enabled
        routing_on = [r for r in passed if r.profile.region_signal_routing_enabled]
        routing_off = [r for r in passed if not r.profile.region_signal_routing_enabled]

        # 1. Check for routing no effect: routing_on vs routing_off identical
        if routing_on and routing_off:
            off = routing_off[0]
            all_same = all(
                r.delivered_signals == 0 and r.regional_signal_flow_score == 0
                for r in routing_on
            )
            if all_same:
                return "routing_no_effect"

        # 2. Check for overplasticity in high_plasticity profile
        high_plasticity = next(
            (r for r in passed if r.profile.name == "routing_plus_high_plasticity"), None
        )
        if high_plasticity is not None:
            if high_plasticity.coherence_phi < b_phi * 0.8 or high_plasticity.speace_cognitive_score < b_cog * 0.8:
                return "pathway_overplasticity_detected"

        # 3. Check for energy regression caused by routing/plasticity
        for r in passed:
            total_routing_cost = r.routing_energy_cost + r.pathway_energy_cost
            if total_routing_cost > 0.01 and r.energy_efficiency < b_ene * 0.8:
                return "routing_energy_regression"

        # 4. Check for routing active but no plasticity events
        routing_active = any(r.delivered_signals > 0 for r in routing_on)
        plasticity_events = any(
            r.inter_region_plasticity_events > 0
            for r in passed
            if r.profile.inter_region_plasticity_enabled
        )
        if routing_active and not plasticity_events:
            return "routing_active_but_no_plasticity"

        # 5. Check for validated improvement with routing
        has_improver = any(r.regression_score > 0.0 for r in passed)
        if has_improver:
            best = max(passed, key=lambda r: r.regression_score)
            if (
                best.energy_efficiency >= b_ene * 0.9
                and best.regional_signal_flow_score > 0
                and best.inter_region_plasticity_events > 0
            ):
                return "routing_plasticity_validated"
            # Routing works, plasticity weak but present
            if best.regional_signal_flow_score > 0 and best.delivered_signals > 0:
                return "routing_validated_plasticity_weak"

        # 6. Fallback: routing works but insufficient functional evidence
        if routing_active and plasticity_events:
            return "routing_validated_plasticity_weak"

        return "insufficient_evidence"

    # ------------------------------------------------------------------ #
    # Reports
    # ------------------------------------------------------------------ #

    def generate_json_report(self, report: PathwayAuditReport) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"pathway_{timestamp}.json"
        path = self.report_dir / filename
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return path

    def generate_markdown_report(self, report: PathwayAuditReport) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"pathway_{timestamp}.md"
        path = self.report_dir / filename

        b = report.baseline_metrics
        lines: List[str] = [
            "# SPEACE Post-T25 T26 Regional Plasticity Audit Report (Routing Enabled)",
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
            f"- Regional signal flow: {b.get('regional_signal_flow_score', 0.0):.4f}",
            f"- Functional improvement: {b.get('functional_improvement', 0.0):.4f}",
            f"- Meta-cognitive score: {b.get('meta_cognitive_score', 0.0):.4f}",
            "",
            "## Comparative Results",
            "",
            "| Profile | Cognitive | Phi | Energy | Flow | Routed | Delivered | Plasticity Events | Accepted | Skipped | Rolled Back | Reg Score | Distance | Passed |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]

        for r in report.profile_results:
            lines.append(
                f"| {r.profile.name} | "
                f"{r.speace_cognitive_score:.4f} | "
                f"{r.coherence_phi:.4f} | "
                f"{r.energy_efficiency:.4f} | "
                f"{r.regional_signal_flow_score:.4f} | "
                f"{r.routed_signals} | "
                f"{r.delivered_signals} | "
                f"{r.inter_region_plasticity_events} | "
                f"{r.tuning_accepted_updates} | "
                f"{r.tuning_skipped_updates} | "
                f"{r.tuning_rolled_back_updates} | "
                f"{r.regression_score:.4f} | "
                f"{r.distance_from_baseline:.4f} | "
                f"{'PASS' if r.passed else 'FAIL'} |"
            )

        if report.best_profile is not None:
            lines.extend([
                "",
                "## Best Profile",
                f"- **Name:** {report.best_profile.name}",
                f"- **Regression score:** {report.best_profile.profile_id}",
                f"- **Description:** {report.best_profile.description}",
            ])

        lines.extend([
            "",
            "---",
            "*Generated by PathwayCalibrator v0.4*",
        ])

        path.write_text("\n".join(lines), encoding="utf-8")
        return path
