import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from speace_core.cellular_brain.metabolism.cognitive_cost_model import CognitiveCostModel
from speace_core.cellular_brain.metabolism.metabolic_governor import MetabolicGovernor
from speace_core.cellular_brain.metabolism.metabolic_models import (
    MetabolicAuditResult,
    MetabolicDecision,
    MetabolicMode,
    MetabolicState,
)
from speace_core.cellular_brain.metabolism.resource_budget import ResourceBudgetManager


class MetabolicAudit:
    """T58 — Audit del metabolismo computazionale con profili di stress."""

    def __init__(self, governor: MetabolicGovernor, seed: int = 42):
        self.governor = governor
        self.seed = seed
        random.seed(seed)

    def build_default_profiles(self) -> List[Dict[str, Any]]:
        return [
            {"name": "normal_operation", "energy": 1.0, "safety_score": 0.9, "description": "Energia sufficiente"},
            {"name": "energy_scarcity", "energy": 0.25, "safety_score": 0.6, "description": "Energia bassa"},
            {"name": "evolutionary_cost_spike", "energy": 0.7, "safety_score": 0.8, "evo_cost_mult": 3.0},
            {"name": "memory_pressure", "energy": 0.6, "safety_score": 0.7, "memory_cost_mult": 2.5},
            {"name": "safety_priority_stress", "energy": 0.3, "safety_score": 0.95},
            {"name": "background_overconsumption", "energy": 0.5, "safety_score": 0.8, "bg_cost_mult": 4.0},
            {"name": "recovery_mode_after_stress", "energy": 0.8, "safety_score": 0.85, "mode_hint": "recovery"},
            {"name": "critical_energy_collapse", "energy": 0.05, "safety_score": 0.5},
            {"name": "over_throttling_detection", "energy": 0.4, "safety_score": 0.9, "throttle_all": True},
            {"name": "full_metabolic_realistic_profile", "energy": 0.65, "safety_score": 0.75, "mixed": True},
        ]

    def run_profile(self, profile: Dict[str, Any]) -> MetabolicAuditResult:
        # Reset governor per profilo isolato
        self.governor = MetabolicGovernor(
            budget_manager=ResourceBudgetManager(total_budget=profile.get("energy", 1.0)),
            cost_model=CognitiveCostModel(),
        )

        # Prepara costi
        cost_model = self.governor.cost_model
        for p in cost_model.list_profiles():
            mult = 1.0
            if p.module_name == "evolutionary_kernel" and profile.get("evo_cost_mult"):
                mult = profile["evo_cost_mult"]
            if p.module_name == "memory" and profile.get("memory_cost_mult"):
                mult = profile["memory_cost_mult"]
            if p.module_name == "background_maintenance" and profile.get("bg_cost_mult"):
                mult = profile["bg_cost_mult"]
            if profile.get("mixed"):
                mult = random.uniform(0.5, 2.5)
            cost_model.update_cost_profile(p.module_name, p.base_cost * mult)

        initial = self.governor.capture_metabolic_state(profile.get("safety_score", 0.8))

        # Esegui ciclo
        cycle_result = self.governor.run_metabolic_cycle(safety_score=profile.get("safety_score", 0.8))

        final = self.governor.capture_metabolic_state(profile.get("safety_score", 0.8))

        # Calcola metriche
        energy_saved = max(0.0, initial.energy_reserve - final.energy_reserve)
        cognitive_preservation = max(0.0, 1.0 - final.throttling_level)
        safety_preservation = final.safety_preservation_score
        recovery_support = 1.0 if final.mode in (MetabolicMode.RECOVERY.value, MetabolicMode.NORMAL.value) else 0.5
        over_throttling = max(0.0, final.throttling_level - 0.5)
        starvation = max(0.0, final.starvation_risk)

        governance = self._compute_governance_score(
            resource_allocation_efficiency=final.resource_allocation_efficiency,
            safety_preservation=safety_preservation,
            critical_protection=final.critical_function_protection_score,
            recovery_support=recovery_support,
            cognitive_efficiency=self.governor.cost_model.compute_cost_efficiency(),
            energy_saved=energy_saved,
            starvation_risk=starvation,
            over_throttling=over_throttling,
            overconsumption=final.overconsumption_risk,
        )

        verdict = self._compute_verdict(
            governance=governance,
            starvation=starvation,
            over_throttling=over_throttling,
            overconsumption=final.overconsumption_risk,
            mode=final.mode,
            safety_budget=self.governor.budget_manager.budget.module_allocations.get("safety_reserve", 0.0),
            recovery_budget=self.governor.budget_manager.budget.module_allocations.get("recovery_reserve", 0.0),
        )

        return MetabolicAuditResult(
            profile_name=profile["name"],
            initial_state=initial,
            final_state=final,
            decisions=self.governor._decisions,
            energy_saved_score=energy_saved,
            cognitive_preservation_score=cognitive_preservation,
            safety_preservation_score=safety_preservation,
            recovery_support_score=recovery_support,
            over_throttling_score=over_throttling,
            starvation_score=starvation,
            metabolic_governance_score=governance,
            verdict=verdict,
        )

    def run_audit_suite(self) -> List[MetabolicAuditResult]:
        profiles = self.build_default_profiles()
        return [self.run_profile(p) for p in profiles]

    @staticmethod
    def _compute_governance_score(
        resource_allocation_efficiency: float,
        safety_preservation: float,
        critical_protection: float,
        recovery_support: float,
        cognitive_efficiency: float,
        energy_saved: float,
        starvation_risk: float,
        over_throttling: float,
        overconsumption: float,
    ) -> float:
        score = (
            0.25 * resource_allocation_efficiency
            + 0.20 * safety_preservation
            + 0.15 * critical_protection
            + 0.15 * recovery_support
            + 0.10 * cognitive_efficiency
            + 0.10 * max(0.0, min(1.0, energy_saved))
            - 0.15 * starvation_risk
            - 0.10 * over_throttling
            - 0.10 * overconsumption
        )
        return max(0.0, min(1.0, score))

    @staticmethod
    def _compute_verdict(
        governance: float,
        starvation: float,
        over_throttling: float,
        overconsumption: float,
        mode: str,
        safety_budget: float,
        recovery_budget: float,
    ) -> str:
        if starvation >= 0.5:
            return "RESOURCE_STARVATION_DETECTED"
        if safety_budget < 0.05:
            return "SAFETY_BUDGET_VIOLATION"
        if recovery_budget < 0.03 and mode in (MetabolicMode.STRESS.value, MetabolicMode.CRITICAL.value):
            return "RECOVERY_BUDGET_VIOLATION"
        if over_throttling >= 0.5:
            return "OVER_THROTTLING_DETECTED"
        if overconsumption >= 0.5:
            return "ENERGY_BUDGET_OVERFLOW"
        if governance >= 0.70 and mode not in (MetabolicMode.CRITICAL.value,):
            return "METABOLIC_GOVERNANCE_VALIDATED"
        if governance >= 0.45:
            return "METABOLIC_SAFE_BUT_PASSIVE"
        return "INSUFFICIENT_EVIDENCE"

    def generate_json_report(self, results: List[MetabolicAuditResult], path: Path) -> Path:
        data = [r.model_dump() for r in results]
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def generate_markdown_report(self, results: List[MetabolicAuditResult], path: Path) -> Path:
        lines = ["# T58 — Metabolic Resource Governance Audit Report", f"**Profiles:** {len(results)}", ""]
        for r in results:
            lines.append(f"## {r.profile_name}")
            lines.append(f"- Mode: {r.final_state.mode}")
            lines.append(f"- Governance Score: {r.metabolic_governance_score:.4f}")
            lines.append(f"- Verdict: `{r.verdict}`")
            lines.append(f"- Energy Reserve: {r.final_state.energy_reserve:.4f}")
            lines.append(f"- Starvation Risk: {r.final_state.starvation_risk:.4f}")
            lines.append(f"- Over-throttling: {r.over_throttling_score:.4f}")
            lines.append("")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
