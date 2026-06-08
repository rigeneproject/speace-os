import asyncio
import json
import math
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.analysis.deep_region_audit import (
    DeepRegionAuditProfile,
    DeepRegionAuditor,
)
from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import (
    NeuroFunctionalBenchmark,
)
from speace_core.dna.models import SharedGenome
from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator


class LongHorizonTrajectoryPoint(BaseModel):
    """Snapshot of metrics at a specific tick horizon."""

    tick: int
    cognitive_score: float = 0.0
    phi: float = 0.0
    energy_efficiency: float = 0.0
    suppression_cost: float = 0.0
    net_gain: float = 0.0
    brainstem_state: str = "stable"
    state_distribution: Dict[str, int] = Field(default_factory=dict)
    functional_improvement: float = 0.0


class LongHorizonProfileResult(BaseModel):
    """Results for a single profile across all horizons."""

    profile: DeepRegionAuditProfile
    trajectory_points: List[LongHorizonTrajectoryPoint] = Field(default_factory=list)
    # Slopes
    net_gain_slope: float = 0.0
    cognitive_score_slope: float = 0.0
    phi_slope: float = 0.0
    energy_slope: float = 0.0
    suppression_cost_slope: float = 0.0
    # State metrics over time
    protective_state_ratio_over_time: float = 0.0
    corrective_state_ratio_over_time: float = 0.0
    emergency_state_ratio_over_time: float = 0.0
    state_entropy: float = 0.0
    # Temporal recovery
    recovery_latency_ticks: int = -1
    stabilization_tick: int = -1
    gain_effect_accumulation: float = 0.0
    long_horizon_recovery_score: float = 0.0
    passed: bool = True
    failure_reason: Optional[str] = None


class LongHorizonAuditResult(BaseModel):
    """Top-level result container for the long-horizon audit suite."""

    audit_id: str
    created_at: str
    profile_results: List[LongHorizonProfileResult] = Field(default_factory=list)
    baseline_profile_id: Optional[str] = None
    verdict: str = "INSUFFICIENT_EVIDENCE"
    json_report_path: Optional[str] = None
    markdown_report_path: Optional[str] = None


class LongHorizonAdaptationAuditor:
    """T40 — Long-Horizon Neurocellular Adaptation Audit.

    Executes profiles across multiple tick horizons (5, 25, 50, 100, 250)
    to observe cumulative effects of brainstem gain coupling, routing,
    stability, and deep-region plasticity.
    """

    HORIZONS: List[int] = [5, 25, 50, 100, 250]

    def __init__(
        self,
        genome: Optional[Dict[str, Any]] = None,
        report_dir: str = "reports/long_horizon",
        seed: int = 42,
        benchmark_case: str = "morphological_memory_trace",
        horizons: Optional[List[int]] = None,
    ):
        self._seed = seed
        self.benchmark_case = benchmark_case
        self.HORIZONS = horizons or [5, 25, 50, 100, 250]
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self._deep_auditor = DeepRegionAuditor(
            genome=genome,
            seed=seed,
            n_adaptive_cycles=5,
            benchmark_case=benchmark_case,
        )

    # ------------------------------------------------------------------ #
    # Profile presets
    # ------------------------------------------------------------------ #

    @staticmethod
    def default_profiles() -> List[DeepRegionAuditProfile]:
        """Return the standard T40 profile set."""
        base = {
            "trigger_mode": "hybrid",
            "tuner_profile_id": "t9",
        }
        return [
            DeepRegionAuditProfile(
                profile_id="lh0",
                name="baseline_four_region",
                deep_regions_enabled=False,
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=False,
                region_stability_controller_enabled=False,
                description="4-region baseline without deep regions",
            ),
            DeepRegionAuditProfile(
                profile_id="lh1",
                name="deep_regions_static",
                deep_regions_enabled=True,
                inter_region_plasticity_enabled=False,
                region_signal_routing_enabled=False,
                region_stability_controller_enabled=False,
                description="Deep regions present but routing and plasticity disabled",
            ),
            DeepRegionAuditProfile(
                profile_id="lh2",
                name="deep_regions_routing_stability",
                deep_regions_enabled=True,
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                region_stability_controller_enabled=True,
                description="Deep regions + routing + stability controller",
                **base,
            ),
            DeepRegionAuditProfile(
                profile_id="lh3",
                name="brainstem_no_gain",
                deep_regions_enabled=True,
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                region_stability_controller_enabled=True,
                brainstem_controller_enabled=True,
                brainstem_gain_controller_enabled=False,
                description="Brainstem enabled without adaptive gain controller",
                **base,
            ),
            DeepRegionAuditProfile(
                profile_id="lh4",
                name="brainstem_gain_t38",
                deep_regions_enabled=True,
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                region_stability_controller_enabled=True,
                brainstem_controller_enabled=True,
                brainstem_gain_controller_enabled=True,
                brainstem_gain_profile="balanced",
                description="Brainstem with T38 gain sensitivity tuning (balanced)",
                **base,
            ),
            DeepRegionAuditProfile(
                profile_id="lh5",
                name="brainstem_gain_coupling_t39",
                deep_regions_enabled=True,
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                region_stability_controller_enabled=True,
                brainstem_controller_enabled=True,
                brainstem_gain_controller_enabled=True,
                brainstem_gain_profile="cognitive_preserving",
                description="Brainstem with T39 gain input coupling (cognitive preserving)",
                **base,
            ),
            DeepRegionAuditProfile(
                profile_id="lh6",
                name="full_organism_gain_coupled",
                deep_regions_enabled=True,
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                region_stability_controller_enabled=True,
                deep_region_routing_calibrator_enabled=True,
                brainstem_controller_enabled=True,
                brainstem_gain_controller_enabled=True,
                brainstem_gain_profile="cognitive_preserving",
                t34_profile_id="p3",
                description="Full organism: deep regions + routing + stability + T34 + T39 gain coupling",
                **base,
            ),
        ]

    # ------------------------------------------------------------------ #
    # Orchestrator helpers
    # ------------------------------------------------------------------ #

    def _apply_profile(self, profile: DeepRegionAuditProfile, orch: CellularBrainOrchestrator) -> None:
        """Apply profile settings including brainstem and gain configuration."""
        self._deep_auditor.apply_homeostatic_baseline(orch)
        self._deep_auditor.apply_profile(profile, orch)

        extra = getattr(profile, "__pydantic_extra__", {}) or {}

        # Brainstem controller
        enabled = extra.get("brainstem_controller_enabled", False)
        orch.brainstem_controller_enabled = enabled
        gain_enabled = extra.get("brainstem_gain_controller_enabled", False)
        orch.brainstem_gain_controller_enabled = gain_enabled

        if enabled:
            orch.model_post_init(None)
            bsc = getattr(orch, "_brainstem_controller", None)
            if bsc is not None:
                for key in [
                    "brainstem_phi_threshold_stable",
                    "brainstem_phi_threshold_watchful",
                    "brainstem_phi_threshold_corrective",
                    "brainstem_phi_threshold_protective",
                    "brainstem_energy_threshold_emergency",
                    "brainstem_instability_threshold_watchful",
                    "brainstem_instability_threshold_corrective",
                    "brainstem_instability_threshold_protective",
                    "brainstem_instability_threshold_emergency",
                ]:
                    if key in extra:
                        short = key.replace("brainstem_", "")
                        if hasattr(bsc, short):
                            setattr(bsc, short, extra[key])

        # Gain preset
        gain_profile = extra.get("brainstem_gain_profile", None)
        if gain_enabled and gain_profile:
            bgc = getattr(orch, "_brainstem_gain_controller", None)
            if bgc is not None and hasattr(bgc, "apply_preset"):
                bgc.apply_preset(gain_profile)

        # T34 deep-region routing calibrator
        t34_id = extra.get("t34_profile_id", None)
        dr_enabled = extra.get("deep_region_routing_calibrator_enabled", False)
        if (dr_enabled or t34_id is not None) and getattr(orch, "_region_signal_router", None) is not None:
            from speace_core.cellular_brain.regions.deep_region_routing_calibrator import (
                DeepRegionRoutingCalibrator,
            )
            defaults = {p.profile_id: p for p in DeepRegionRoutingCalibrator.build_default_profiles()}
            t34_profile = defaults.get(t34_id or "p3", defaults.get("p4"))
            calibrator = DeepRegionRoutingCalibrator(profile=t34_profile)
            orch.deep_region_routing_calibrator_enabled = True
            orch._deep_region_routing_profile = t34_profile
            orch._deep_region_routing_calibrator = calibrator
            calibrator.apply_profile_to_router(orch._region_signal_router)

    # ------------------------------------------------------------------ #
    # Single profile run
    # ------------------------------------------------------------------ #

    async def run_profile(self, profile: DeepRegionAuditProfile) -> LongHorizonProfileResult:
        """Execute a single profile across all horizons and track trajectories."""
        result = LongHorizonProfileResult(profile=profile)
        pattern = [1.0 if i % 2 == 0 else 0.0 for i in range(10)]

        # Phase A: Benchmark runs for each horizon (fresh deterministic orchestrator per horizon)
        for h in self.HORIZONS:
            random.seed(self._seed)
            orch = self._deep_auditor.build_orchestrator(
                deep_regions_enabled=profile.deep_regions_enabled
            )
            self._apply_profile(profile, orch)
            benchmark = NeuroFunctionalBenchmark(orch)
            try:
                bm_result = await benchmark.run_case(
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
                    n_ticks=h,
                )
            except Exception as exc:
                result.failure_reason = str(exc)
                result.passed = False
                return result

            m = bm_result.metrics
            point = LongHorizonTrajectoryPoint(
                tick=h,
                cognitive_score=m.speace_cognitive_score,
                phi=m.coherence_phi,
                energy_efficiency=m.energy_efficiency,
                suppression_cost=m.suppression_cost,
                net_gain=0.0,
                brainstem_state=m.brainstem_state,
                state_distribution=m.brainstem_state_distribution,
                functional_improvement=m.functional_improvement,
            )
            result.trajectory_points.append(point)

        # Phase B: Tick-by-tick brainstem state tracking for recovery metrics
        await self._track_brainstem_states(profile, result)

        # Compute slopes (net_gain will be backfilled after baseline comparison)
        self._compute_slopes(result)
        self._compute_state_entropy_from_distribution(result)
        self._compute_recovery_and_stabilization(result)
        self._compute_long_horizon_recovery_score(result)

        return result

    # ------------------------------------------------------------------ #
    # Brainstem tick-by-tick tracking
    # ------------------------------------------------------------------ #

    async def _track_brainstem_states(
        self, profile: DeepRegionAuditProfile, result: LongHorizonProfileResult
    ) -> None:
        """Track brainstem state per tick up to the longest horizon."""
        random.seed(self._seed)
        orch = self._deep_auditor.build_orchestrator(
            deep_regions_enabled=profile.deep_regions_enabled
        )
        self._apply_profile(profile, orch)
        max_h = max(self.HORIZONS)
        states: List[str] = []
        for _ in range(max_h):
            await orch.run_ticks(1)
            bsc = getattr(orch, "_brainstem_controller", None)
            state_val = bsc._previous_state.value if bsc is not None and bsc._previous_state is not None else "stable"
            states.append(state_val)

        # recovery_latency: first tick exiting emergency/protective after being in one
        in_bad = False
        recovery_latency = -1
        for i, s in enumerate(states):
            if s in {"emergency", "protective"}:
                in_bad = True
            elif in_bad and s not in {"emergency", "protective"}:
                recovery_latency = i + 1
                break

        # stabilization_tick: first tick from which the system never returns to emergency/protective
        stabilization = -1
        for i in range(len(states)):
            if all(states[j] not in {"emergency", "protective"} for j in range(i, len(states))):
                stabilization = i + 1
                break

        result.recovery_latency_ticks = recovery_latency
        result.stabilization_tick = stabilization

        # Ratios
        from collections import Counter
        dist = Counter(states)
        total = len(states)
        result.protective_state_ratio_over_time = round(dist.get("protective", 0) / total, 4) if total else 0.0
        result.corrective_state_ratio_over_time = round(dist.get("corrective", 0) / total, 4) if total else 0.0
        result.emergency_state_ratio_over_time = round(dist.get("emergency", 0) / total, 4) if total else 0.0

        # State entropy (Shannon)
        probs = [c / total for c in dist.values() if c > 0]
        entropy = -sum(p * math.log2(p) for p in probs) if probs else 0.0
        result.state_entropy = round(entropy, 4)

    # ------------------------------------------------------------------ #
    # Slopes
    # ------------------------------------------------------------------ #

    @staticmethod
    def _linear_slope(points: List[LongHorizonTrajectoryPoint], attr: str) -> float:
        """Simple linear regression slope across trajectory points."""
        xs = [p.tick for p in points]
        ys = [getattr(p, attr) for p in points]
        n = len(xs)
        if n < 2:
            return 0.0
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        den = sum((x - mean_x) ** 2 for x in xs)
        if den == 0:
            return 0.0
        return round(num / den, 6)

    def _compute_slopes(self, result: LongHorizonProfileResult) -> None:
        result.net_gain_slope = self._linear_slope(result.trajectory_points, "net_gain")
        result.cognitive_score_slope = self._linear_slope(result.trajectory_points, "cognitive_score")
        result.phi_slope = self._linear_slope(result.trajectory_points, "phi")
        result.energy_slope = self._linear_slope(result.trajectory_points, "energy_efficiency")
        result.suppression_cost_slope = self._linear_slope(result.trajectory_points, "suppression_cost")

    # ------------------------------------------------------------------ #
    # State entropy (fallback from distribution if tracking missing)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_state_entropy_from_distribution(result: LongHorizonProfileResult) -> None:
        if result.state_entropy > 0:
            return
        # Derive from the final trajectory point state distribution
        if result.trajectory_points:
            dist = result.trajectory_points[-1].state_distribution
            total = sum(dist.values())
            if total > 0:
                probs = [c / total for c in dist.values() if c > 0]
                entropy = -sum(p * math.log2(p) for p in probs) if probs else 0.0
                result.state_entropy = round(entropy, 4)

    # ------------------------------------------------------------------ #
    # Recovery and stabilization
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_recovery_and_stabilization(result: LongHorizonProfileResult) -> None:
        # Intentional no-op: recovery/stabilization metrics are already computed
        # and stored inside result by _track_brainstem_states during the main loop.
        pass

    # ------------------------------------------------------------------ #
    # Long-horizon recovery score
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_long_horizon_recovery_score(result: LongHorizonProfileResult) -> None:
        score = (
            0.25 * result.cognitive_score_slope
            + 0.25 * result.phi_slope
            + 0.20 * result.energy_slope
            + 0.15 * max(0.0, -result.suppression_cost_slope)
            + 0.15 * result.state_entropy
        )
        result.long_horizon_recovery_score = round(score, 4)

    # ------------------------------------------------------------------ #
    # Verdict
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_verdict(results: List[LongHorizonProfileResult]) -> str:
        valid = [r for r in results if r.passed]
        if not valid:
            return "INSUFFICIENT_EVIDENCE"

        baseline = next((r for r in valid if r.profile.profile_id == "lh0"), None)
        best = max(valid, key=lambda r: r.long_horizon_recovery_score)

        # Regression check
        if baseline and best.cognitive_score_slope < baseline.cognitive_score_slope - 0.001:
            return "LONG_HORIZON_REGRESSION"

        # Strong
        if best.long_horizon_recovery_score > 0.01:
            t39 = next((r for r in valid if r.profile.profile_id == "lh5"), None)
            if t39 and t39.long_horizon_recovery_score > 0.01:
                return "LONG_HORIZON_RECOVERY_VALIDATED"
            return "PARTIAL_TEMPORAL_RECOVERY"

        # Minimum
        if best.net_gain_slope > 0 or best.suppression_cost_slope < 0 or best.recovery_latency_ticks > 0:
            if best.long_horizon_recovery_score > 0.0:
                return "SHORT_RUN_ONLY_EFFECT"

        if best.state_entropy > 0.3 and best.long_horizon_recovery_score <= 0.0:
            return "PERSISTENT_NEUTRALITY"

        return "INSTABILITY_ACCUMULATION"

    # ------------------------------------------------------------------ #
    # Suite run
    # ------------------------------------------------------------------ #

    async def run_audit_suite(
        self, profiles: Optional[List[DeepRegionAuditProfile]] = None
    ) -> LongHorizonAuditResult:
        profs = profiles or self.default_profiles()
        results: List[LongHorizonProfileResult] = []
        for p in profs:
            res = await self.run_profile(p)
            results.append(res)

        # Backfill net_gain vs baseline for every trajectory point
        baseline = next((r for r in results if r.profile.profile_id == "lh0"), None)
        if baseline:
            for r in results:
                for bp, rp in zip(baseline.trajectory_points, r.trajectory_points):
                    rp.net_gain = (
                        0.30 * (rp.cognitive_score - bp.cognitive_score)
                        + 0.25 * (rp.phi - bp.phi)
                        + 0.20 * (rp.functional_improvement - bp.functional_improvement)
                        + 0.15 * (rp.cognitive_score - bp.cognitive_score)
                        + 0.10 * (rp.energy_efficiency - bp.energy_efficiency)
                    )
            # Recompute net_gain slopes after backfill
            for r in results:
                r.net_gain_slope = self._linear_slope(r.trajectory_points, "net_gain")
                self._compute_long_horizon_recovery_score(r)

        verdict = self._compute_verdict(results)

        report = LongHorizonAuditResult(
            audit_id=f"lh_{uuid.uuid4().hex[:8]}",
            created_at=datetime.now(timezone.utc).isoformat(),
            profile_results=results,
            baseline_profile_id=baseline.profile.profile_id if baseline else None,
            verdict=verdict,
        )

        json_path = self._generate_json_report(report)
        md_path = self._generate_markdown_report(report)
        report.json_report_path = str(json_path)
        report.markdown_report_path = str(md_path)
        return report

    # ------------------------------------------------------------------ #
    # Reporting
    # ------------------------------------------------------------------ #

    def _generate_json_report(self, report: LongHorizonAuditResult) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.report_dir / f"long_horizon_audit_{ts}.json"
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return path

    def _generate_markdown_report(self, report: LongHorizonAuditResult) -> Path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.report_dir / f"long_horizon_audit_{ts}.md"
        lines = [
            "# T40 — Long-Horizon Neurocellular Adaptation Audit",
            "",
            f"**Audit ID:** {report.audit_id}",
            f"**Verdict:** {report.verdict}",
            f"**Baseline Profile:** {report.baseline_profile_id or 'N/A'}",
            "",
            "## Profile x Horizon Matrix",
            "",
            "| Profile | 5t | 25t | 50t | 100t | 250t |",
            "|---|---|---|---|---|---|",
        ]
        for r in report.profile_results:
            vals = [f"{tp.cognitive_score:.4f}" for tp in r.trajectory_points]
            lines.append(f"| {r.profile.name} | {' | '.join(vals)} |")

        lines.extend([
            "",
            "## Slopes",
            "",
            "| Profile | net_gain | cognitive | phi | energy | suppression |",
            "|---|---|---|---|---|---|",
        ])
        for r in report.profile_results:
            lines.append(
                f"| {r.profile.name} | {r.net_gain_slope:+.6f} | {r.cognitive_score_slope:+.6f} | "
                f"{r.phi_slope:+.6f} | {r.energy_slope:+.6f} | {r.suppression_cost_slope:+.6f} |"
            )

        lines.extend([
            "",
            "## State Distribution & Recovery",
            "",
            "| Profile | protective | corrective | emergency | entropy | recovery_latency | stabilization | recovery_score |",
            "|---|---|---|---|---|---|---|---|",
        ])
        for r in report.profile_results:
            lines.append(
                f"| {r.profile.name} | {r.protective_state_ratio_over_time:.4f} | "
                f"{r.corrective_state_ratio_over_time:.4f} | {r.emergency_state_ratio_over_time:.4f} | "
                f"{r.state_entropy:.4f} | {r.recovery_latency_ticks} | {r.stabilization_tick} | "
                f"{r.long_horizon_recovery_score:.4f} |"
            )

        lines.extend([
            "",
            "---",
            "*Generated by T40 Long-Horizon Adaptation Audit*",
        ])
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
