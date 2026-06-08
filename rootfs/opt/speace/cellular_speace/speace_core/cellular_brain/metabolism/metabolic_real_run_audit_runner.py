import json
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.metabolism.cognitive_cost_model import CognitiveCostModel
from speace_core.cellular_brain.metabolism.metabolic_governor import MetabolicGovernor
from speace_core.cellular_brain.metabolism.metabolic_models import (
    MetabolicMode,
    MetabolicRealRunProfile,
    MetabolicRealRunProfileResult,
    MetabolicRealRunSuiteResult,
    MetabolicState,
)
from speace_core.cellular_brain.metabolism.resource_budget import ResourceBudgetManager


class MetabolicRealRunAuditRunner:
    """T58B — Real-run audit runner for metabolic resource governance."""

    def __init__(
        self,
        governor: Optional[MetabolicGovernor] = None,
        seed: int = 42,
        reports_dir: str = "reports/metabolism",
    ):
        self.governor = governor or MetabolicGovernor()
        self.seed = seed
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        random.seed(seed)

    # ------------------------------------------------------------------ #
    # Profiles
    # ------------------------------------------------------------------ #

    def build_default_profiles(self) -> List[MetabolicRealRunProfile]:
        return [
            MetabolicRealRunProfile(
                name="real_baseline_normal_operation",
                description="Carico normale, atteso NORMAL",
                duration_cycles=5,
                workload_mix={"safety": 0.15, "memory": 0.15, "routing": 0.10, "background_maintenance": 0.05},
                initial_energy=1.0,
                expected_mode=MetabolicMode.NORMAL.value,
            ),
            MetabolicRealRunProfile(
                name="real_evolutionary_kernel_cost_spike",
                description="T55/T56 simulano costo elevato, throttling evolutivo prima di safety",
                duration_cycles=5,
                workload_mix={"evolutionary_kernel": 0.40, "evolutionary_memory": 0.20, "safety": 0.15, "memory": 0.15},
                initial_energy=0.8,
                expected_risk_type="REAL_RUN_EVOLUTIONARY_COST_UNBOUNDED",
            ),
            MetabolicRealRunProfile(
                name="real_self_organization_pressure",
                description="T53 richiede energia per stabilizzazione",
                duration_cycles=5,
                workload_mix={"self_organization": 0.35, "safety": 0.20, "routing": 0.15, "memory": 0.15},
                initial_energy=0.7,
            ),
            MetabolicRealRunProfile(
                name="real_recovery_after_perturbation",
                description="Scenario post T54/T54B, recovery budget protetto",
                duration_cycles=5,
                workload_mix={"repair": 0.30, "safety": 0.25, "defense": 0.15, "memory": 0.15},
                initial_energy=0.6,
            ),
            MetabolicRealRunProfile(
                name="real_memory_governance_pressure",
                description="T57/T57B richiedono consolidamento memoria",
                duration_cycles=5,
                workload_mix={"memory": 0.30, "evolutionary_memory": 0.25, "safety": 0.20, "background_maintenance": 0.10},
                initial_energy=0.75,
            ),
            MetabolicRealRunProfile(
                name="real_sustained_energy_scarcity",
                description="Energia bassa per piu cicli",
                duration_cycles=8,
                workload_mix={"safety": 0.20, "memory": 0.15, "routing": 0.10, "evolutionary_kernel": 0.10},
                initial_energy=0.25,
                expected_mode=MetabolicMode.CONSERVATION.value,
            ),
            MetabolicRealRunProfile(
                name="real_background_overconsumption",
                description="benchmark/background consumano troppo",
                duration_cycles=5,
                workload_mix={"benchmark": 0.30, "background_maintenance": 0.25, "safety": 0.20, "memory": 0.15},
                initial_energy=0.6,
            ),
            MetabolicRealRunProfile(
                name="real_critical_energy_collapse",
                description="Energia sotto soglia critica",
                duration_cycles=5,
                workload_mix={"safety": 0.25, "repair": 0.20, "defense": 0.15, "routing": 0.10},
                initial_energy=0.05,
                expected_mode=MetabolicMode.CRITICAL.value,
            ),
            MetabolicRealRunProfile(
                name="real_over_throttling_guard",
                description="Throttling troppo aggressivo causa perdita cognitiva",
                duration_cycles=5,
                workload_mix={"benchmark": 0.40, "evolutionary_kernel": 0.30, "background_maintenance": 0.20},
                initial_energy=0.15,
                expected_risk_type="REAL_RUN_OVER_THROTTLING_DETECTED",
            ),
            MetabolicRealRunProfile(
                name="real_full_organismic_mix",
                description="Mix realistico evolution, memory, self-organization, recovery, routing, benchmark",
                duration_cycles=7,
                workload_mix={
                    "evolutionary_kernel": 0.15,
                    "memory": 0.15,
                    "self_organization": 0.10,
                    "repair": 0.10,
                    "routing": 0.10,
                    "safety": 0.15,
                    "benchmark": 0.10,
                    "background_maintenance": 0.05,
                },
                initial_energy=0.65,
            ),
            MetabolicRealRunProfile(
                name="real_budget_leakage_profile",
                description="Consumo non registrato o allocazioni incoerenti",
                duration_cycles=5,
                workload_mix={"benchmark": 0.20, "background_maintenance": 0.20, "safety": 0.15},
                initial_energy=0.5,
                expected_risk_type="REAL_RUN_BUDGET_LEAKAGE_DETECTED",
            ),
        ]

    # ------------------------------------------------------------------ #
    # Real metrics loader
    # ------------------------------------------------------------------ #

    def load_real_metrics_if_available(self) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {}
        report_dir = Path("reports/metabolism")
        if not report_dir.exists():
            return metrics
        for path in sorted(report_dir.glob("t57b_audit_*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    metrics["t57b"] = data
            except Exception:
                continue
        for path in sorted(report_dir.glob("t58_audit_*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    metrics["t58"] = data
            except Exception:
                continue
        return metrics

    # ------------------------------------------------------------------ #
    # Synthetic workload
    # ------------------------------------------------------------------ #

    def build_synthetic_workload_for_profile(
        self,
        profile: MetabolicRealRunProfile,
    ) -> Dict[str, float]:
        mix = dict(profile.workload_mix)
        # Introduce small noise
        for k in mix:
            mix[k] = max(0.0, mix[k] + random.uniform(-0.02, 0.02))
        return mix

    # ------------------------------------------------------------------ #
    # Profile execution
    # ------------------------------------------------------------------ #

    def run_profile(
        self,
        profile: MetabolicRealRunProfile,
    ) -> MetabolicRealRunProfileResult:
        # Reset governor per profilo isolato
        self.governor = MetabolicGovernor(
            budget_manager=ResourceBudgetManager(total_budget=profile.initial_energy),
            cost_model=CognitiveCostModel(),
        )

        real_metrics = self.load_real_metrics_if_available() if profile.requires_real_reports else {}
        workload = self.build_synthetic_workload_for_profile(profile)

        # Prepara costi iniziali
        for module, intensity in workload.items():
            base = self.governor.cost_model._profiles.get(module, CognitiveCostModel.DEFAULT_BASE_COSTS.get(module, 0.01))
            if hasattr(base, "base_cost"):
                base_cost = base.base_cost
            else:
                base_cost = base if isinstance(base, float) else 0.01
            self.governor.cost_model.update_cost_profile(module, base_cost * (1 + intensity * 3))

        pressures: List[float] = []
        throttles: List[float] = []
        safety_scores: List[float] = []
        recovery_scores: List[float] = []
        critical_scores: List[float] = []
        evo_throttle_count = 0
        memory_starvation = 0
        safety_starvation = 0
        recovery_starvation = 0
        over_throttle = 0
        under_throttle = 0
        budget_overflow = 0
        budget_leakage = 0

        for _ in range(profile.duration_cycles):
            safety_score = random.uniform(0.6, 1.0) if profile.initial_energy > 0.3 else random.uniform(0.3, 0.7)
            result = self.governor.run_metabolic_cycle(safety_score=safety_score)
            state = self.governor.capture_metabolic_state(safety_score)

            pressures.append(state.metabolic_pressure)
            throttles.append(state.throttling_level)
            safety_scores.append(state.safety_preservation_score)
            recovery_scores.append(1.0 if state.mode in (MetabolicMode.RECOVERY.value, MetabolicMode.NORMAL.value) else 0.5)
            critical_scores.append(state.critical_function_protection_score)

            for d in self.governor._decisions:
                if d.action == "throttle_evolutionary":
                    evo_throttle_count += 1
                if d.target_module in ("memory", "evolutionary_memory") and state.starvation_risk > 0.3:
                    memory_starvation += 1
                if d.target_module == "safety" and state.starvation_risk > 0.3:
                    safety_starvation += 1
                if d.target_module == "repair" and state.starvation_risk > 0.3:
                    recovery_starvation += 1

            if state.throttling_level > 0.5:
                over_throttle += 1
            if state.throttling_level < 0.05 and state.metabolic_pressure > 0.5:
                under_throttle += 1
            if state.overconsumption_risk > 0.3:
                budget_overflow += 1

        # Budget leakage detection
        budget = self.governor.budget_manager.budget
        total_allocated = sum(budget.module_allocations.values())
        leakage = abs(total_allocated + budget.available_energy - budget.total_energy_budget)
        if leakage > 0.01:
            budget_leakage += 1

        avg_pressure = sum(pressures) / max(1, len(pressures))
        avg_throttle = sum(throttles) / max(1, len(throttles))
        avg_safety = sum(safety_scores) / max(1, len(safety_scores))
        avg_recovery = sum(recovery_scores) / max(1, len(recovery_scores))
        avg_critical = sum(critical_scores) / max(1, len(critical_scores))

        resource_efficiency = budget.available_energy / max(1e-9, budget.total_energy_budget)
        cognitive_preservation = max(0.0, 1.0 - avg_throttle)
        evolutionary_cost_control = 1.0 if evo_throttle_count > 0 else 0.5
        budget_integrity = max(0.0, 1.0 - budget_leakage)
        starvation_score = max(0.0, min(1.0, sum(pressures) / max(1, len(pressures)) if pressures else 0.0))
        over_throttle_score = avg_throttle
        under_throttle_score = 1.0 - avg_throttle if avg_throttle < 0.1 and avg_pressure > 0.5 else 0.0
        budget_leakage_score = budget_leakage / max(1, profile.duration_cycles)

        real_run_score = self._compute_real_run_score(
            safety_preservation=avg_safety,
            recovery_support=avg_recovery,
            critical_protection=avg_critical,
            resource_efficiency=resource_efficiency,
            cognitive_preservation=cognitive_preservation,
            evolutionary_cost_control=evolutionary_cost_control,
            budget_integrity=budget_integrity,
            starvation=starvation_score,
            over_throttling=over_throttle_score,
            under_throttling=under_throttle_score,
            budget_leakage=budget_leakage_score,
        )

        verdict = self._compute_verdict(
            score=real_run_score,
            safety_starvation=safety_starvation,
            recovery_starvation=recovery_starvation,
            memory_starvation=memory_starvation,
            budget_leakage=budget_leakage,
            budget_overflow=budget_overflow,
            evo_throttle=evo_throttle_count,
            over_throttle=over_throttle,
            under_throttle=under_throttle,
            mode=state.mode,
        )

        return MetabolicRealRunProfileResult(
            profile_name=profile.name,
            cycles_run=profile.duration_cycles,
            initial_energy=profile.initial_energy,
            final_energy=budget.available_energy,
            average_metabolic_pressure=avg_pressure,
            average_throttling_level=avg_throttle,
            average_safety_preservation_score=avg_safety,
            average_recovery_support_score=avg_recovery,
            average_critical_function_protection_score=avg_critical,
            evolutionary_throttle_count=evo_throttle_count,
            memory_starvation_count=memory_starvation,
            safety_starvation_count=safety_starvation,
            recovery_starvation_count=recovery_starvation,
            over_throttling_count=over_throttle,
            under_throttling_count=under_throttle,
            budget_overflow_count=budget_overflow,
            budget_leakage_count=budget_leakage,
            real_run_metabolic_score=real_run_score,
            verdict=verdict,
        )

    def run_audit_suite(self) -> MetabolicRealRunSuiteResult:
        profiles = self.build_default_profiles()
        results: List[MetabolicRealRunProfileResult] = []
        total_cycles = 0
        total_evo_throttle = 0
        total_safety_starvation = 0
        total_recovery_starvation = 0
        total_memory_starvation = 0
        total_budget_overflow = 0
        total_budget_leakage = 0

        for profile in profiles:
            result = self.run_profile(profile)
            results.append(result)
            total_cycles += result.cycles_run
            total_evo_throttle += result.evolutionary_throttle_count
            total_safety_starvation += result.safety_starvation_count
            total_recovery_starvation += result.recovery_starvation_count
            total_memory_starvation += result.memory_starvation_count
            total_budget_overflow += result.budget_overflow_count
            total_budget_leakage += result.budget_leakage_count

        aggregate_metabolic = sum(r.real_run_metabolic_score for r in results) / max(1, len(results))
        aggregate_safety = sum(r.average_safety_preservation_score for r in results) / max(1, len(results))
        aggregate_recovery = sum(r.average_recovery_support_score for r in results) / max(1, len(results))
        aggregate_critical = sum(r.average_critical_function_protection_score for r in results) / max(1, len(results))
        aggregate_efficiency = sum(r.final_energy for r in results) / max(1, len(results))

        aggregate_verdict = self.compute_aggregate_verdict(results)
        proceed_to_t59 = aggregate_verdict in (
            "METABOLIC_REAL_RUN_VALIDATED",
            "METABOLIC_REAL_RUN_SAFE_BUT_PASSIVE",
        ) and total_safety_starvation == 0 and total_budget_leakage == 0 and aggregate_metabolic >= 0.70

        return MetabolicRealRunSuiteResult(
            profile_count=len(profiles),
            total_cycles_run=total_cycles,
            aggregate_metabolic_score=aggregate_metabolic,
            aggregate_safety_preservation_score=aggregate_safety,
            aggregate_recovery_support_score=aggregate_recovery,
            aggregate_critical_function_protection_score=aggregate_critical,
            aggregate_resource_efficiency_score=aggregate_efficiency,
            total_evolutionary_throttle_count=total_evo_throttle,
            total_safety_starvation_count=total_safety_starvation,
            total_recovery_starvation_count=total_recovery_starvation,
            total_memory_starvation_count=total_memory_starvation,
            total_budget_overflow_count=total_budget_overflow,
            total_budget_leakage_count=total_budget_leakage,
            aggregate_verdict=aggregate_verdict,
            proceed_to_t59=proceed_to_t59,
            profile_results=results,
        )

    @staticmethod
    def _compute_real_run_score(
        safety_preservation: float,
        recovery_support: float,
        critical_protection: float,
        resource_efficiency: float,
        cognitive_preservation: float,
        evolutionary_cost_control: float,
        budget_integrity: float,
        starvation: float,
        over_throttling: float,
        under_throttling: float,
        budget_leakage: float,
    ) -> float:
        score = (
            0.22 * safety_preservation
            + 0.18 * recovery_support
            + 0.18 * critical_protection
            + 0.15 * resource_efficiency
            + 0.10 * cognitive_preservation
            + 0.10 * evolutionary_cost_control
            + 0.07 * budget_integrity
            - 0.15 * starvation
            - 0.12 * over_throttling
            - 0.10 * under_throttling
            - 0.10 * budget_leakage
        )
        return max(0.0, min(1.0, score))

    @staticmethod
    def _compute_verdict(
        score: float,
        safety_starvation: int,
        recovery_starvation: int,
        memory_starvation: int,
        budget_leakage: int,
        budget_overflow: int,
        evo_throttle: int,
        over_throttle: int,
        under_throttle: int,
        mode: str,
    ) -> str:
        if safety_starvation > 0:
            return "REAL_RUN_SAFETY_STARVED"
        if recovery_starvation > 0 and mode in (MetabolicMode.STRESS.value, MetabolicMode.CRITICAL.value):
            return "REAL_RUN_RECOVERY_STARVED"
        if memory_starvation > 0:
            return "REAL_RUN_MEMORY_STARVED"
        if budget_leakage > 0:
            return "REAL_RUN_BUDGET_LEAKAGE_DETECTED"
        if budget_overflow > 0:
            return "REAL_RUN_ENERGY_BUDGET_OVERFLOW"
        if evo_throttle == 0 and mode == MetabolicMode.CRITICAL.value:
            return "REAL_RUN_EVOLUTIONARY_COST_UNBOUNDED"
        if over_throttle >= 2:
            return "REAL_RUN_OVER_THROTTLING_DETECTED"
        if under_throttle >= 2:
            return "REAL_RUN_UNDER_THROTTLING_DETECTED"
        if score >= 0.70:
            return "METABOLIC_REAL_RUN_VALIDATED"
        if score >= 0.45:
            return "METABOLIC_REAL_RUN_SAFE_BUT_PASSIVE"
        return "METABOLIC_REAL_RUN_INSUFFICIENT_EVIDENCE"

    def compute_aggregate_verdict(
        self,
        results: List[MetabolicRealRunProfileResult],
    ) -> str:
        unsafe = sum(1 for r in results if r.verdict == "REAL_RUN_SAFETY_STARVED")
        recovery = sum(1 for r in results if r.verdict == "REAL_RUN_RECOVERY_STARVED")
        memory = sum(1 for r in results if r.verdict == "REAL_RUN_MEMORY_STARVED")
        leakage = sum(1 for r in results if r.verdict == "REAL_RUN_BUDGET_LEAKAGE_DETECTED")
        overflow = sum(1 for r in results if r.verdict == "REAL_RUN_ENERGY_BUDGET_OVERFLOW")
        evo = sum(1 for r in results if r.verdict == "REAL_RUN_EVOLUTIONARY_COST_UNBOUNDED")
        over = sum(1 for r in results if r.verdict == "REAL_RUN_OVER_THROTTLING_DETECTED")
        under = sum(1 for r in results if r.verdict == "REAL_RUN_UNDER_THROTTLING_DETECTED")
        critical = sum(1 for r in results if r.verdict == "REAL_RUN_CRITICAL_FUNCTION_STARVED")

        if unsafe > 0:
            return "REAL_RUN_SAFETY_STARVED"
        if recovery > 0:
            return "REAL_RUN_RECOVERY_STARVED"
        if memory > 0:
            return "REAL_RUN_MEMORY_STARVED"
        if leakage > 0:
            return "REAL_RUN_BUDGET_LEAKAGE_DETECTED"
        if overflow > 0:
            return "REAL_RUN_ENERGY_BUDGET_OVERFLOW"
        if evo > 0:
            return "REAL_RUN_EVOLUTIONARY_COST_UNBOUNDED"
        if over > 0:
            return "REAL_RUN_OVER_THROTTLING_DETECTED"
        if under > 0:
            return "REAL_RUN_UNDER_THROTTLING_DETECTED"
        if critical > 0:
            return "REAL_RUN_CRITICAL_FUNCTION_STARVED"

        scores = [r.real_run_metabolic_score for r in results if r.cycles_run > 0]
        mean_score = sum(scores) / max(1, len(scores))
        if mean_score >= 0.70:
            return "METABOLIC_REAL_RUN_VALIDATED"
        if mean_score >= 0.45:
            return "METABOLIC_REAL_RUN_SAFE_BUT_PASSIVE"
        return "METABOLIC_REAL_RUN_INSUFFICIENT_EVIDENCE"

    # ------------------------------------------------------------------ #
    # Reports
    # ------------------------------------------------------------------ #

    def generate_json_report(self, suite_result: MetabolicRealRunSuiteResult) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.reports_dir / f"t58b_audit_{timestamp}.json"
        path.write_text(suite_result.model_dump_json(indent=2), encoding="utf-8")
        return str(path)

    def generate_markdown_report(self, suite_result: MetabolicRealRunSuiteResult) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.reports_dir / f"t58b_audit_{timestamp}.md"
        lines = [
            "# T58B — Metabolic Resource Governance Real-Run Audit Report",
            f"**Date:** {timestamp}",
            f"**Aggregate Verdict:** `{suite_result.aggregate_verdict}`",
            f"**Proceed to T59:** {suite_result.proceed_to_t59}",
            "",
            "## Aggregate Metrics",
            f"- Profiles Run: {suite_result.profile_count}",
            f"- Total Cycles: {suite_result.total_cycles_run}",
            f"- Aggregate Metabolic Score: {suite_result.aggregate_metabolic_score:.4f}",
            f"- Safety Preservation: {suite_result.aggregate_safety_preservation_score:.4f}",
            f"- Recovery Support: {suite_result.aggregate_recovery_support_score:.4f}",
            f"- Critical Protection: {suite_result.aggregate_critical_function_protection_score:.4f}",
            f"- Resource Efficiency: {suite_result.aggregate_resource_efficiency_score:.4f}",
            f"- Evolutionary Throttles: {suite_result.total_evolutionary_throttle_count}",
            f"- Safety Starvations: {suite_result.total_safety_starvation_count}",
            f"- Recovery Starvations: {suite_result.total_recovery_starvation_count}",
            f"- Memory Starvations: {suite_result.total_memory_starvation_count}",
            f"- Budget Overflow: {suite_result.total_budget_overflow_count}",
            f"- Budget Leakage: {suite_result.total_budget_leakage_count}",
            "",
            "## Profile Results",
        ]
        for r in suite_result.profile_results:
            lines.append(f"### {r.profile_name}")
            lines.append(f"- Cycles: {r.cycles_run}")
            lines.append(f"- Metabolic Score: {r.real_run_metabolic_score:.4f}")
            lines.append(f"- Avg Pressure: {r.average_metabolic_pressure:.4f}")
            lines.append(f"- Avg Throttle: {r.average_throttling_level:.4f}")
            lines.append(f"- Evo Throttles: {r.evolutionary_throttle_count}")
            lines.append(f"- Verdict: `{r.verdict}`")
            lines.append("")
        lines.append("---")
        lines.append("*Generated by MetabolicRealRunAuditRunner (T58B)*")
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)
