import copy
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from speace_core.cellular_brain.analysis.recovery_policy_selector import (
    RecoveryPolicy,
    RegressionGuardThresholds,
)
from speace_core.cellular_brain.analysis.regression_guard import RegressionGuard
from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import (
    NeuroFunctionalBenchmark,
)
from speace_core.dna.models import SharedGenome
from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator


class CellularResilienceProfile(BaseModel):
    """Configuration for a single cellular resilience audit profile."""

    profile_id: str
    name: str
    cellular_defense_enabled: bool = False
    cellular_repair_enabled: bool = False
    cellular_epigenetics_enabled: bool = False
    stress_injection: str = "none"
    n_ticks: int = 25
    description: str = ""

    model_config = ConfigDict(extra="allow")


class CellularResilienceMetrics(BaseModel):
    """Metrics extracted for a single profile run."""

    cognitive_score: float = 0.0
    coherence_phi: float = 0.0
    energy_efficiency: float = 0.0
    mean_cellular_stress: float = 0.0
    mean_damage_score: float = 0.0
    repair_success_rate: float = 0.0
    repair_failure_rate: float = 0.0
    cellular_survival_score: float = 0.0
    cellular_self_repair_score: float = 0.0
    cellular_defense_score: float = 0.0
    cellular_resilience_score: float = 0.0
    epigenetic_adaptation_score: float = 0.0
    quarantined_cells: int = 0
    immune_alerts: int = 0
    plasticity_locks: int = 0
    routing_blocks: int = 0
    cognitive_delta: float = 0.0
    phi_delta: float = 0.0
    energy_delta: float = 0.0
    regression_guard: Dict[str, Any] = Field(default_factory=dict)


class CellularResilienceProfileResult(BaseModel):
    """Result of running one profile."""

    profile: CellularResilienceProfile
    metrics: CellularResilienceMetrics = Field(default_factory=CellularResilienceMetrics)
    passed: bool = True


class CellularResilienceAuditReport(BaseModel):
    """Top-level audit report container."""

    audit_id: str
    created_at: str
    baseline_result: CellularResilienceProfileResult = Field(
        default_factory=lambda: CellularResilienceProfileResult(
            profile=CellularResilienceProfile(profile_id="baseline", name="baseline")
        )
    )
    profile_results: List[CellularResilienceProfileResult] = Field(default_factory=list)
    best_profile: Optional[str] = None
    verdict: str = "INSUFFICIENT_EVIDENCE"
    json_report_path: Optional[str] = None
    markdown_report_path: Optional[str] = None


class CellularResilienceAuditor:
    """T42C — Validate the cellular adaptive defense & repair layer."""

    def __init__(
        self,
        genome: Optional[Dict[str, Any]] = None,
        report_dir: str = "reports/cellular_resilience",
        seed: int = 42,
        benchmark_case: str = "morphological_memory_trace",
        baseline_policy: Optional[RecoveryPolicy] = None,
    ):
        self._seed = seed
        self.benchmark_case = benchmark_case
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.baseline_policy = baseline_policy

        if genome is not None:
            self.genome = genome
        else:
            loaded = load_genome("speace_core/dna/genome/default_genome.yaml")
            self.genome = loaded.model_dump()

    # ------------------------------------------------------------------ #
    # Profile presets
    # ------------------------------------------------------------------ #

    @staticmethod
    def default_profiles() -> List[CellularResilienceProfile]:
        return [
            CellularResilienceProfile(
                profile_id="cr0",
                name="cellular_defense_repair_off",
                description="T42 completely disabled",
            ),
            CellularResilienceProfile(
                profile_id="cr1",
                name="repair_only",
                cellular_repair_enabled=True,
                description="Only repair enabled",
            ),
            CellularResilienceProfile(
                profile_id="cr2",
                name="defense_only",
                cellular_defense_enabled=True,
                description="Only defense enabled",
            ),
            CellularResilienceProfile(
                profile_id="cr3",
                name="epigenetic_only",
                cellular_epigenetics_enabled=True,
                description="Only epigenetics enabled",
            ),
            CellularResilienceProfile(
                profile_id="cr4",
                name="repair_defense",
                cellular_repair_enabled=True,
                cellular_defense_enabled=True,
                description="Repair + defense",
            ),
            CellularResilienceProfile(
                profile_id="cr5",
                name="repair_defense_epigenetic",
                cellular_repair_enabled=True,
                cellular_defense_enabled=True,
                cellular_epigenetics_enabled=True,
                description="Repair + defense + epigenetic",
            ),
            CellularResilienceProfile(
                profile_id="cr6",
                name="full_cellular_resilience",
                cellular_repair_enabled=True,
                cellular_defense_enabled=True,
                cellular_epigenetics_enabled=True,
                description="Full T42 stack",
            ),
            CellularResilienceProfile(
                profile_id="cr7",
                name="stress_high_activation",
                cellular_repair_enabled=True,
                cellular_defense_enabled=True,
                cellular_epigenetics_enabled=True,
                stress_injection="high_activation",
                description="Full stack + high activation stress",
            ),
            CellularResilienceProfile(
                profile_id="cr8",
                name="stress_low_energy",
                cellular_repair_enabled=True,
                cellular_defense_enabled=True,
                cellular_epigenetics_enabled=True,
                stress_injection="low_energy",
                description="Full stack + low energy stress",
            ),
            CellularResilienceProfile(
                profile_id="cr9",
                name="stress_routing_overload",
                cellular_repair_enabled=True,
                cellular_defense_enabled=True,
                cellular_epigenetics_enabled=True,
                stress_injection="routing_overload",
                description="Full stack + routing overload",
            ),
            CellularResilienceProfile(
                profile_id="cr10",
                name="stress_plasticity_instability",
                cellular_repair_enabled=True,
                cellular_defense_enabled=True,
                cellular_epigenetics_enabled=True,
                stress_injection="plasticity_instability",
                description="Full stack + plasticity instability",
            ),
        ]

    # ------------------------------------------------------------------ #
    # Orchestrator factory
    # ------------------------------------------------------------------ #

    def _build_orchestrator(self) -> CellularBrainOrchestrator:
        random.seed(self._seed)
        genome = SharedGenome(**copy.deepcopy(self.genome))
        orch = CellularBrainOrchestrator.build_mvp(genome)
        return orch

    @staticmethod
    def _apply_profile(
        orch: CellularBrainOrchestrator, profile: CellularResilienceProfile
    ) -> None:
        orch.cellular_adaptive_defense_enabled = profile.cellular_defense_enabled
        orch.cellular_repair_enabled = profile.cellular_repair_enabled
        orch.cellular_epigenetics_enabled = profile.cellular_epigenetics_enabled
        orch.model_post_init(None)

    @staticmethod
    def _inject_stress(orch: CellularBrainOrchestrator, injection_type: str) -> None:
        if injection_type == "none":
            return
        hidden = orch.circuit.hidden_neurons
        if not hidden:
            return
        for neuron in hidden:
            if injection_type == "high_activation":
                neuron.activation = 2.0
                neuron.consecutive_fires = 5
            elif injection_type == "low_energy":
                neuron.energy = 0.1
            elif injection_type == "routing_overload":
                neuron.targets = [f"t{i}" for i in range(8)]
            elif injection_type == "plasticity_instability":
                neuron.plasticity_rate = 1.0
                if not hasattr(neuron, "error_history"):
                    neuron.error_history = []
                neuron.error_history.extend([0.5] * 3)

    async def _run_profile(
        self, profile: CellularResilienceProfile
    ) -> CellularResilienceProfileResult:
        orch = self._build_orchestrator()
        self._apply_profile(orch, profile)
        self._inject_stress(orch, profile.stress_injection)

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
                inter_region_plasticity_enabled=True,
                region_signal_routing_enabled=True,
                input_pattern=pattern,
                target_output=pattern,
                n_ticks=profile.n_ticks,
            )
            metrics = result.metrics
        except Exception:
            return CellularResilienceProfileResult(
                profile=profile,
                passed=False,
            )

        m = metrics.model_dump() if hasattr(metrics, "model_dump") else dict(metrics) if metrics else {}

        defense_result = getattr(orch, "_last_cellular_defense_result", None)
        quarantined = getattr(defense_result, "quarantined_count", 0) if defense_result else 0
        immune_alerts = getattr(defense_result, "immune_alert_count", 0) if defense_result else 0
        plasticity_locks = getattr(defense_result, "plasticity_lock_count", 0) if defense_result else 0
        routing_blocks = getattr(defense_result, "routing_block_count", 0) if defense_result else 0

        resilience_metrics = CellularResilienceMetrics(
            cognitive_score=m.get("cognitive_score", 0.0),
            coherence_phi=m.get("coherence_phi", 0.0),
            energy_efficiency=m.get("energy_efficiency", 0.0),
            mean_cellular_stress=m.get("mean_cellular_stress", 0.0),
            mean_damage_score=m.get("mean_damage_score", 0.0),
            repair_success_rate=m.get("repair_success_rate", 0.0),
            repair_failure_rate=m.get("repair_failure_rate", 0.0),
            cellular_survival_score=m.get("cellular_survival_score", 0.0),
            cellular_self_repair_score=m.get("cellular_self_repair_score", 0.0),
            cellular_defense_score=m.get("cellular_defense_score", 0.0),
            cellular_resilience_score=m.get("cellular_resilience_score", 0.0),
            epigenetic_adaptation_score=m.get("epigenetic_adaptation_score", 0.0),
            quarantined_cells=quarantined,
            immune_alerts=immune_alerts,
            plasticity_locks=plasticity_locks,
            routing_blocks=routing_blocks,
        )

        rg = RegressionGuard.evaluate_benchmark_metrics(
            resilience_metrics, policy=self.baseline_policy
        )
        resilience_metrics.regression_guard = rg.model_dump()

        return CellularResilienceProfileResult(
            profile=profile,
            metrics=resilience_metrics,
            passed=rg.verdict not in ("POLICY_UNSAFE", "POLICY_MAJOR_REGRESSION"),
        )

    async def run_audit_suite(
        self, profiles: Optional[List[CellularResilienceProfile]] = None
    ) -> CellularResilienceAuditReport:
        if profiles is None:
            profiles = self.default_profiles()

        audit_id = f"t42c-{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(timezone.utc).isoformat()

        baseline_profile = profiles[0]
        baseline_result = await self._run_profile(baseline_profile)

        profile_results: List[CellularResilienceProfileResult] = []
        for profile in profiles[1:]:
            result = await self._run_profile(profile)
            result.metrics.cognitive_delta = (
                result.metrics.cognitive_score - baseline_result.metrics.cognitive_score
            )
            result.metrics.phi_delta = (
                result.metrics.coherence_phi - baseline_result.metrics.coherence_phi
            )
            result.metrics.energy_delta = (
                result.metrics.energy_efficiency - baseline_result.metrics.energy_efficiency
            )
            profile_results.append(result)

        best_profile = self._select_best_profile(profile_results)
        verdict = self._compute_verdict(baseline_result, profile_results, best_profile)

        report = CellularResilienceAuditReport(
            audit_id=audit_id,
            created_at=created_at,
            baseline_result=baseline_result,
            profile_results=profile_results,
            best_profile=best_profile,
            verdict=verdict,
        )

        report.json_report_path = str(self._generate_json_report(report))
        report.markdown_report_path = str(self._generate_markdown_report(report))
        return report

    # ------------------------------------------------------------------ #
    # Verdict & scoring
    # ------------------------------------------------------------------ #

    @staticmethod
    def _select_best_profile(
        profile_results: List[CellularResilienceProfileResult],
    ) -> Optional[str]:
        scored = []
        for r in profile_results:
            if not r.passed:
                continue
            score = (
                r.metrics.cellular_resilience_score * 0.25
                + r.metrics.cellular_survival_score * 0.20
                + r.metrics.cognitive_score * 0.20
                + (1.0 - r.metrics.mean_cellular_stress) * 0.15
                + (1.0 - r.metrics.mean_damage_score) * 0.15
                + r.metrics.energy_efficiency * 0.05
            )
            scored.append((score, r.profile.name))
        if not scored:
            return None
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    @staticmethod
    def _compute_verdict(
        baseline: CellularResilienceProfileResult,
        profile_results: List[CellularResilienceProfileResult],
        best_profile_name: Optional[str],
    ) -> str:
        if not profile_results:
            return "INSUFFICIENT_EVIDENCE"

        full_profiles = [
            r
            for r in profile_results
            if r.profile.name in ("full_cellular_resilience", "repair_defense_epigenetic")
        ]
        if not full_profiles:
            full_profiles = profile_results

        avg_repair_success = sum(r.metrics.repair_success_rate for r in full_profiles) / max(
            1, len(full_profiles)
        )
        avg_repair_failure = sum(r.metrics.repair_failure_rate for r in full_profiles) / max(
            1, len(full_profiles)
        )
        avg_resilience = sum(r.metrics.cellular_resilience_score for r in full_profiles) / max(
            1, len(full_profiles)
        )
        avg_cognitive = sum(r.metrics.cognitive_score for r in full_profiles) / max(
            1, len(full_profiles)
        )
        avg_energy = sum(r.metrics.energy_efficiency for r in full_profiles) / max(
            1, len(full_profiles)
        )

        baseline_cognitive = baseline.metrics.cognitive_score
        baseline_energy = baseline.metrics.energy_efficiency

        cognitive_regression = avg_cognitive < baseline_cognitive * 0.85
        energy_regression = avg_energy < baseline_energy * 0.85

        if cognitive_regression:
            return "CELLULAR_COGNITIVE_REGRESSION"
        if energy_regression:
            return "CELLULAR_ENERGY_REGRESSION"

        if avg_repair_success < 0.20 and avg_repair_failure > 0.50:
            return "CELLULAR_REPAIR_WEAK"

        defense_overactive = any(
            r.metrics.plasticity_locks > 0
            and r.metrics.cognitive_score < baseline_cognitive * 0.90
            for r in profile_results
        )
        if defense_overactive:
            return "CELLULAR_DEFENSE_OVERACTIVE"

        epi_profiles = [r for r in profile_results if r.profile.cellular_epigenetics_enabled]
        if epi_profiles and all(
            r.metrics.epigenetic_adaptation_score < 0.01 for r in epi_profiles
        ):
            return "CELLULAR_EPIGENETIC_NO_EFFECT"

        if avg_resilience > baseline.metrics.cellular_resilience_score:
            return "CELLULAR_RESILIENCE_VALIDATED"

        return "INSUFFICIENT_EVIDENCE"

    # ------------------------------------------------------------------ #
    # Report generation
    # ------------------------------------------------------------------ #

    def _generate_json_report(self, report: CellularResilienceAuditReport) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.report_dir / f"cellular_resilience_audit_{timestamp}.json"
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return path

    def _generate_markdown_report(self, report: CellularResilienceAuditReport) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.report_dir / f"cellular_resilience_audit_{timestamp}.md"
        lines = [
            "# T42C — Cellular Resilience Audit Report",
            "",
            f"**Audit ID:** {report.audit_id}",
            f"**Created At:** {report.created_at}",
            f"**Verdict:** {report.verdict}",
            "",
            "## Baseline Profile",
            f"- **Profile:** {report.baseline_result.profile.name}",
            f"- **Cognitive Score:** {report.baseline_result.metrics.cognitive_score:.4f}",
            f"- **Coherence Φ:** {report.baseline_result.metrics.coherence_phi:.4f}",
            f"- **Energy Efficiency:** {report.baseline_result.metrics.energy_efficiency:.4f}",
            f"- **Mean Cellular Stress:** {report.baseline_result.metrics.mean_cellular_stress:.4f}",
            f"- **Mean Damage Score:** {report.baseline_result.metrics.mean_damage_score:.4f}",
            f"- **Cellular Resilience Score:** {report.baseline_result.metrics.cellular_resilience_score:.4f}",
            "",
            "## Profile Results",
            "",
            "| Profile | Stress | Damage | Repair Succ | Repair Fail | Survival | Defense | Resilience | Epigenetic | Quar | Imm | Plast | Route | Cog Δ | Φ Δ | Energy Δ | Passed |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in report.profile_results:
            m = r.metrics
            lines.append(
                f"| {r.profile.name} | {m.mean_cellular_stress:.4f} | {m.mean_damage_score:.4f} | "
                f"{m.repair_success_rate:.4f} | {m.repair_failure_rate:.4f} | {m.cellular_survival_score:.4f} | "
                f"{m.cellular_defense_score:.4f} | {m.cellular_resilience_score:.4f} | {m.epigenetic_adaptation_score:.4f} | "
                f"{m.quarantined_cells} | {m.immune_alerts} | {m.plasticity_locks} | {m.routing_blocks} | "
                f"{m.cognitive_delta:+.4f} | {m.phi_delta:+.4f} | {m.energy_delta:+.4f} | {r.passed} |"
            )
        lines.extend([
            "",
            "## Best Profile",
            f"{report.best_profile or 'None'}",
            "",
            "---",
            "*Generated by T42C Cellular Resilience Auditor*",
        ])
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
