import copy
import json
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import (
    BenchmarkResult,
    NeuroFunctionalBenchmark,
)
from speace_core.cellular_brain.calibration.homeostatic_calibrator import HomeostaticCalibrator
from speace_core.dna.models import SharedGenome
from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator


class DeepRegionAuditProfile(BaseModel):
    profile_id: str
    name: str
    deep_regions_enabled: bool = True
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
    tuner_profile_id: Optional[str] = None
    region_stability_controller_enabled: bool = False
    description: str = ""

    model_config = ConfigDict(extra="allow")


class DeepRegionAuditResult(BaseModel):
    profile: DeepRegionAuditProfile
    benchmark_metrics: Dict[str, Any] = Field(default_factory=dict)
    cognitive_score: float = 0.0
    phi: float = 0.0
    energy_efficiency: float = 0.0
    functional_improvement: float = 0.0
    mean_pathway_utility: float = 0.0
    deep_region_signal_flow: float = 0.0
    region_role_alignment_score: float = 0.0
    region_specialization_diversity: float = 0.0
    limbic_salience_score: float = 0.0
    cerebellar_error_correction_score: float = 0.0
    default_mode_consolidation_score: float = 0.0
    brainstem_homeostatic_stability_score: float = 0.0
    deep_region_cost: float = 0.0
    deep_region_benefit: float = 0.0
    deep_region_net_gain: float = 0.0
    cognitive_score_delta: float = 0.0
    phi_delta: float = 0.0
    energy_efficiency_delta: float = 0.0
    functional_improvement_delta: float = 0.0
    pathway_utility_delta: float = 0.0
    passed: bool = True
    failure_reason: Optional[str] = None


class DeepRegionAuditReport(BaseModel):
    audit_id: str
    created_at: str
    baseline_result: DeepRegionAuditResult = Field(default_factory=lambda: DeepRegionAuditResult(profile=DeepRegionAuditProfile(profile_id="baseline", name="baseline")))
    profile_results: List[DeepRegionAuditResult] = Field(default_factory=list)
    best_profile: Optional[DeepRegionAuditProfile] = None
    verdict: str = "INSUFFICIENT_EVIDENCE"
    json_report_path: Optional[str] = None
    markdown_report_path: Optional[str] = None


class DeepRegionAuditor:
    """Audit functional impact of deep regions (T31) vs 4-region baseline (T32)."""

    def __init__(
        self,
        genome: Optional[Dict[str, Any]] = None,
        report_dir: str = "reports/deep_regions",
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
    def default_profiles() -> List[DeepRegionAuditProfile]:
        return [
            DeepRegionAuditProfile(
                profile_id="d0",
                name="four_region_baseline",
                deep_regions_enabled=False,
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=False,
                description="4-region baseline without deep regions",
            ),
            DeepRegionAuditProfile(
                profile_id="d1",
                name="deep_regions_static",
                deep_regions_enabled=True,
                inter_region_plasticity_enabled=False,
                region_signal_routing_enabled=False,
                description="Deep regions present but routing and plasticity disabled",
            ),
            DeepRegionAuditProfile(
                profile_id="d2",
                name="deep_regions_routing_only",
                deep_regions_enabled=True,
                inter_region_plasticity_enabled=False,
                region_signal_routing_enabled=True,
                description="Deep regions + signal routing, no plasticity",
            ),
            DeepRegionAuditProfile(
                profile_id="d3",
                name="deep_regions_routing_plasticity",
                deep_regions_enabled=True,
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                trigger_mode="hybrid",
                description="Deep regions + routing + plasticity (hybrid trigger)",
            ),
            DeepRegionAuditProfile(
                profile_id="d4",
                name="deep_regions_full_utility",
                deep_regions_enabled=True,
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                trigger_mode="hybrid",
                tuner_profile_id="t9",
                description="Deep regions + routing + T29 tuning + T30 utility learning",
            ),
            DeepRegionAuditProfile(
                profile_id="d5",
                name="deep_regions_energy_soft",
                deep_regions_enabled=True,
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                trigger_mode="hybrid",
                ltp_rate=0.02,
                ltd_rate=0.01,
                energy_cost_per_update=0.0005,
                energy_modulation_strength=1.5,
                description="Deep regions with soft energy conservative settings",
            ),
            DeepRegionAuditProfile(
                profile_id="d6",
                name="deep_regions_energy_medium",
                deep_regions_enabled=True,
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                trigger_mode="hybrid",
                ltp_rate=0.04,
                ltd_rate=0.025,
                energy_cost_per_update=0.0008,
                energy_modulation_strength=1.2,
                description="Deep regions with medium energy conservative settings",
            ),
            DeepRegionAuditProfile(
                profile_id="d7",
                name="deep_regions_brainstem_priority",
                deep_regions_enabled=True,
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                trigger_mode="hybrid",
                ltp_rate=0.03,
                ltd_rate=0.02,
                energy_cost_per_update=0.0005,
                energy_modulation_strength=2.0,
                description="Deep regions prioritizing brainstem energy modulation",
            ),
            DeepRegionAuditProfile(
                profile_id="d8",
                name="deep_regions_default_mode_low_activity",
                deep_regions_enabled=True,
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                trigger_mode="hybrid",
                ltp_rate=0.03,
                ltd_rate=0.02,
                energy_cost_per_update=0.0005,
                description="Deep regions with lower plasticity to reduce default mode over-activation",
            ),
            DeepRegionAuditProfile(
                profile_id="d9",
                name="deep_regions_limbic_soft_salience",
                deep_regions_enabled=True,
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                trigger_mode="hybrid",
                ltp_rate=0.06,
                ltd_rate=0.04,
                confidence_modulation_strength=1.5,
                description="Deep regions with softer limbic salience via confidence modulation",
            ),
        ]

    # ------------------------------------------------------------------ #
    # Orchestrator factory
    # ------------------------------------------------------------------ #

    def build_orchestrator(self, deep_regions_enabled: bool = True) -> CellularBrainOrchestrator:
        random.seed(self._seed)
        genome_dict = copy.deepcopy(self.genome)
        if not deep_regions_enabled:
            deep_region_ids = {"limbic", "cerebellar", "default_mode", "brainstem_homeostatic"}
            if "brain_regions" in genome_dict:
                genome_dict["brain_regions"] = {
                    k: v for k, v in genome_dict["brain_regions"].items()
                    if k not in deep_region_ids
                }
            deep_neuron_types = {"limbic_neuron", "cerebellar_neuron", "default_mode_neuron", "brainstem_neuron"}
            if "cell_differentiation_rules" in genome_dict:
                genome_dict["cell_differentiation_rules"] = {
                    k: v for k, v in genome_dict["cell_differentiation_rules"].items()
                    if k not in deep_neuron_types
                }
        genome = SharedGenome(**genome_dict)
        orch = CellularBrainOrchestrator.build_mvp(genome)
        orch.deep_regions_enabled = deep_regions_enabled
        # Reset any stale neuron.region assignments from the initial post_init
        for neuron in orch.circuit.hidden_neurons:
            if hasattr(neuron, "region"):
                neuron.region = None
        # Force re-init of region registry with the correct deep_regions flag
        if orch.region_architecture_enabled:
            from speace_core.cellular_brain.regions.region_factory import RegionFactory
            orch._region_registry = RegionFactory.build_from_genome(
                orch.circuit, orch.genome.model_dump(), seed=42, deep_regions_enabled=deep_regions_enabled
            )
        return orch

    @staticmethod
    def apply_homeostatic_baseline(orch: CellularBrainOrchestrator) -> None:
        profiles = HomeostaticCalibrator.default_profiles()
        energy_medium = next((p for p in profiles if p.name == "energy_medium"), None)
        if energy_medium is not None:
            HomeostaticCalibrator.apply_profile_to_orchestrator(energy_medium, orch)
        else:
            orch.energy_control_enabled = True

    @staticmethod
    def apply_profile(profile: DeepRegionAuditProfile, orch: CellularBrainOrchestrator) -> None:
        from speace_core.cellular_brain.regions.pathway_plasticity_tuner import PathwayPlasticityTuner
        orch.inter_region_plasticity_enabled = profile.inter_region_plasticity_enabled
        orch.region_signal_routing_enabled = profile.region_signal_routing_enabled
        orch.region_stability_controller_enabled = profile.region_stability_controller_enabled
        if profile.region_stability_controller_enabled and orch._region_stability_controller is None:
            from speace_core.cellular_brain.regions.region_stability_controller import RegionLevelStabilityController
            orch._region_stability_controller = RegionLevelStabilityController()
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

    async def run_profile(self, profile: DeepRegionAuditProfile) -> DeepRegionAuditResult:
        orch = self.build_orchestrator(deep_regions_enabled=profile.deep_regions_enabled)
        self.apply_homeostatic_baseline(orch)
        self.apply_profile(profile, orch)
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
            return DeepRegionAuditResult(
                profile=profile,
                benchmark_metrics={},
                passed=False,
                failure_reason=str(exc),
            )

        m = result.metrics
        bm = m.model_dump()
        deep_metrics: Dict[str, Any] = {}
        if orch._region_registry is not None:
            from speace_core.cellular_brain.regions.deep_region_specialization import DeepRegionSpecialization
            deep_metrics = DeepRegionSpecialization.compute_deep_region_metrics(orch._region_registry)

        return DeepRegionAuditResult(
            profile=profile,
            benchmark_metrics=bm,
            cognitive_score=m.speace_cognitive_score,
            phi=m.coherence_phi,
            energy_efficiency=m.energy_efficiency,
            functional_improvement=m.functional_improvement,
            mean_pathway_utility=m.mean_pathway_utility,
            deep_region_signal_flow=m.deep_region_signal_flow,
            region_role_alignment_score=m.region_role_alignment_score,
            region_specialization_diversity=m.region_specialization_diversity,
            limbic_salience_score=m.limbic_salience_score,
            cerebellar_error_correction_score=m.cerebellar_error_correction_score,
            default_mode_consolidation_score=m.default_mode_consolidation_score,
            brainstem_homeostatic_stability_score=m.brainstem_homeostatic_stability_score,
            deep_region_cost=m.routing_energy_cost + m.pathway_energy_cost,
            deep_region_benefit=m.regional_signal_flow_score + m.functional_improvement,
            passed=True,
        )

    # ------------------------------------------------------------------ #
    # Suite run
    # ------------------------------------------------------------------ #

    async def run_audit_suite(
        self, profiles: Optional[List[DeepRegionAuditProfile]] = None
    ) -> DeepRegionAuditReport:
        profs = profiles or self.default_profiles()

        # Baseline: four_region_baseline
        baseline_profile = DeepRegionAuditProfile(
            profile_id="baseline",
            name="four_region_baseline",
            deep_regions_enabled=False,
            inter_region_plasticity_enabled=True,
            region_signal_routing_enabled=False,
        )
        baseline_result = await self.run_profile(baseline_profile)
        baseline_metrics = baseline_result.benchmark_metrics

        results: List[DeepRegionAuditResult] = []
        for p in profs:
            res = await self.run_profile(p)
            res.cognitive_score_delta = res.cognitive_score - baseline_result.cognitive_score
            res.phi_delta = res.phi - baseline_result.phi
            res.energy_efficiency_delta = res.energy_efficiency - baseline_result.energy_efficiency
            res.functional_improvement_delta = res.functional_improvement - baseline_result.functional_improvement
            res.pathway_utility_delta = res.mean_pathway_utility - baseline_result.mean_pathway_utility
            res.deep_region_net_gain = self.compute_deep_region_net_gain(res, baseline_result)
            results.append(res)

        verdict = self._compute_verdict(results, baseline_result)
        best = self._select_best_profile(results)

        report = DeepRegionAuditReport(
            audit_id=f"dra_{uuid.uuid4().hex[:8]}",
            created_at=datetime.now(timezone.utc).isoformat(),
            baseline_result=baseline_result,
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
    def compute_deep_region_net_gain(
        result: DeepRegionAuditResult, baseline: DeepRegionAuditResult
    ) -> float:
        score = (
            0.30 * result.cognitive_score_delta
            + 0.25 * result.phi_delta
            + 0.20 * result.functional_improvement_delta
            + 0.15 * result.pathway_utility_delta
            + 0.10 * result.energy_efficiency_delta
        )
        return round(score, 4)

    @staticmethod
    def _select_best_profile(results: List[DeepRegionAuditResult]) -> Optional[DeepRegionAuditResult]:
        passed = [r for r in results if r.passed and r.profile.deep_regions_enabled]
        if not passed:
            return None
        return max(passed, key=lambda r: r.deep_region_net_gain)

    @staticmethod
    def _compute_verdict(
        results: List[DeepRegionAuditResult], baseline: DeepRegionAuditResult
    ) -> str:
        passed = [r for r in results if r.passed]
        if not passed:
            return "INSUFFICIENT_EVIDENCE"

        deep_passed = [r for r in passed if r.profile.deep_regions_enabled]
        if not deep_passed:
            return "INSUFFICIENT_EVIDENCE"

        b_cog = baseline.cognitive_score
        b_phi = baseline.phi
        b_ene = baseline.energy_efficiency

        # Check regressions first
        for r in deep_passed:
            if r.energy_efficiency < b_ene * 0.8 and r.deep_region_cost > 0.01:
                return "DEEP_REGION_ENERGY_REGRESSION"
            if r.phi < b_phi * 0.8:
                return "DEEP_REGION_PHI_REGRESSION"
            if r.cognitive_score < b_cog * 0.8:
                return "DEEP_REGION_COGNITIVE_REGRESSION"

        # Check for net positive effect
        has_positive = any(r.deep_region_net_gain > 0.0 for r in deep_passed)
        if has_positive:
            return "DEEP_REGIONS_VALIDATED"

        # Check for no functional effect despite activation
        any_active = any(r.deep_region_signal_flow > 0 for r in deep_passed)
        if any_active:
            return "DEEP_REGION_NO_EFFECT"

        # Check for neutral effect (no regression, but no gain and no activity)
        no_regression = all(
            r.cognitive_score >= b_cog * 0.95
            and r.phi >= b_phi * 0.95
            and r.energy_efficiency >= b_ene * 0.95
            for r in deep_passed
        )
        if no_regression:
            return "DEEP_REGIONS_NEUTRAL"

        return "INSUFFICIENT_EVIDENCE"

    # ------------------------------------------------------------------ #
    # Reports
    # ------------------------------------------------------------------ #

    def generate_json_report(self, report: DeepRegionAuditReport) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"deep_region_audit_{timestamp}.json"
        path = self.report_dir / filename
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return path

    def generate_markdown_report(self, report: DeepRegionAuditReport) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"deep_region_audit_{timestamp}.md"
        path = self.report_dir / filename

        b = report.baseline_result
        lines: List[str] = [
            "# SPEACE T32 — Deep Region Functional Audit Report",
            "",
            f"**Audit ID:** {report.audit_id}",
            f"**Date:** {report.created_at}",
            f"**Profiles tested:** {len(report.profile_results)}",
            f"**Verdict:** {report.verdict}",
            "",
            "## Baseline (4-Region)",
            f"- Cognitive score: {b.cognitive_score:.4f}",
            f"- Coherence Phi: {b.phi:.4f}",
            f"- Energy efficiency: {b.energy_efficiency:.4f}",
            f"- Functional improvement: {b.functional_improvement:.4f}",
            f"- Pathway utility: {b.mean_pathway_utility:.4f}",
            "",
            "## Comparative Results",
            "",
            "| Profile | Deep | Cognitive | Phi | Energy | Flow | Limbic | Cerebellar | Default | Brainstem | Net Gain | Passed |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]

        for r in report.profile_results:
            lines.append(
                f"| {r.profile.name} | "
                f"{'Yes' if r.profile.deep_regions_enabled else 'No'} | "
                f"{r.cognitive_score:.4f} | "
                f"{r.phi:.4f} | "
                f"{r.energy_efficiency:.4f} | "
                f"{r.deep_region_signal_flow:.4f} | "
                f"{r.limbic_salience_score:.4f} | "
                f"{r.cerebellar_error_correction_score:.4f} | "
                f"{r.default_mode_consolidation_score:.4f} | "
                f"{r.brainstem_homeostatic_stability_score:.4f} | "
                f"{r.deep_region_net_gain:.4f} | "
                f"{'PASS' if r.passed else 'FAIL'} |"
            )

        if report.best_profile is not None:
            best_result = next(
                (r for r in report.profile_results if r.profile.profile_id == report.best_profile.profile_id), None
            )
            lines.extend([
                "",
                "## Best Profile",
                f"- **Name:** {report.best_profile.name}",
                f"- **Description:** {report.best_profile.description}",
            ])
            if best_result is not None:
                lines.extend([
                    f"- **Net gain:** {best_result.deep_region_net_gain:.4f}",
                    f"- **Cognitive delta:** {best_result.cognitive_score_delta:.4f}",
                    f"- **Phi delta:** {best_result.phi_delta:.4f}",
                    f"- **Energy delta:** {best_result.energy_efficiency_delta:.4f}",
                ])

        lines.extend([
            "",
            "---",
            "*Generated by DeepRegionAuditor v0.4*",
        ])

        path.write_text("\n".join(lines), encoding="utf-8")
        return path
