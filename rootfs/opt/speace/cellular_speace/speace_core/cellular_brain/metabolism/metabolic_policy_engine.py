from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.metabolism.metabolic_models import (
    MetabolicDecision,
    MetabolicMode,
    MetabolicState,
    ResourceBudget,
)


class MetabolicPolicyEngine:
    """T58 — Decide modalità metabolica, throttling e protezione funzioni critiche."""

    MODE_THRESHOLDS = {
        MetabolicMode.CRITICAL: 0.90,
        MetabolicMode.STRESS: 0.70,
        MetabolicMode.CONSERVATION: 0.45,
        MetabolicMode.RECOVERY: -0.10,
    }

    CRITICAL_MODULES = {"safety", "repair", "defense", "routing"}
    EVOLUTIONARY_MODULES = {"evolutionary_kernel", "evolutionary_memory"}
    THROTTLEABLE_MODULES = {"benchmark", "background_maintenance", "evolutionary_kernel", "evolutionary_memory"}

    def classify_mode(self, metabolic_pressure: float, energy_reserve: float) -> str:
        if energy_reserve <= 0.05 or metabolic_pressure >= self.MODE_THRESHOLDS[MetabolicMode.CRITICAL]:
            return MetabolicMode.CRITICAL.value
        if metabolic_pressure >= self.MODE_THRESHOLDS[MetabolicMode.STRESS]:
            return MetabolicMode.STRESS.value
        if metabolic_pressure >= self.MODE_THRESHOLDS[MetabolicMode.CONSERVATION]:
            return MetabolicMode.CONSERVATION.value
        if metabolic_pressure <= self.MODE_THRESHOLDS[MetabolicMode.RECOVERY]:
            return MetabolicMode.RECOVERY.value
        return MetabolicMode.NORMAL.value

    def apply_throttling(
        self,
        budget: ResourceBudget,
        mode: str,
        costs: Dict[str, float],
    ) -> List[MetabolicDecision]:
        decisions: List[MetabolicDecision] = []
        if mode in (MetabolicMode.NORMAL.value, MetabolicMode.RECOVERY.value):
            return decisions

        throttle_factors = {
            MetabolicMode.CONSERVATION.value: 0.7,
            MetabolicMode.STRESS.value: 0.4,
            MetabolicMode.CRITICAL.value: 0.1,
        }
        factor = throttle_factors.get(mode, 1.0)

        for module, cost in costs.items():
            if module in self.CRITICAL_MODULES:
                continue
            if module not in self.THROTTLEABLE_MODULES and mode != MetabolicMode.CRITICAL.value:
                continue

            new_allocation = cost * factor
            current = budget.module_allocations.get(module, 0.0)
            if new_allocation < current:
                decisions.append(
                    MetabolicDecision(
                        decision_id=f"throttle_{module}",
                        target_module=module,
                        action="throttle",
                        previous_allocation=current,
                        new_allocation=new_allocation,
                        reason=f"Mode={mode}, factor={factor}",
                        reversible=True,
                        expected_energy_delta=current - new_allocation,
                    )
                )
        return decisions

    def protect_critical_functions(
        self,
        budget: ResourceBudget,
        mode: str,
    ) -> List[MetabolicDecision]:
        decisions: List[MetabolicDecision] = []
        if mode not in (MetabolicMode.STRESS.value, MetabolicMode.CRITICAL.value):
            return decisions

        for module in self.CRITICAL_MODULES:
            current = budget.module_allocations.get(module, 0.0)
            min_safe = budget.soft_caps.get(module, 0.05)
            if current < min_safe:
                needed = min_safe - current
                if budget.available_energy >= needed:
                    decisions.append(
                        MetabolicDecision(
                            decision_id=f"protect_{module}",
                            target_module=module,
                            action="protect",
                            previous_allocation=current,
                            new_allocation=min_safe,
                            reason=f"Critical protection in {mode}",
                            reversible=False,
                            safety_impact=0.1,
                            expected_energy_delta=-needed,
                        )
                    )
        return decisions

    def limit_evolutionary_costs(
        self,
        budget: ResourceBudget,
        mode: str,
        evolutionary_cost: float,
    ) -> List[MetabolicDecision]:
        decisions: List[MetabolicDecision] = []
        if mode in (MetabolicMode.NORMAL.value, MetabolicMode.RECOVERY.value):
            return decisions

        max_evo = {
            MetabolicMode.CONSERVATION.value: 0.08,
            MetabolicMode.STRESS.value: 0.03,
            MetabolicMode.CRITICAL.value: 0.0,
        }.get(mode, 1.0)

        for module in self.EVOLUTIONARY_MODULES:
            current = budget.module_allocations.get(module, 0.0)
            if current > max_evo:
                new_alloc = max_evo
                decisions.append(
                    MetabolicDecision(
                        decision_id=f"limit_evo_{module}",
                        target_module=module,
                        action="throttle_evolutionary",
                        previous_allocation=current,
                        new_allocation=new_alloc,
                        reason=f"Mode={mode}, max_evo={max_evo}",
                        reversible=True,
                        expected_energy_delta=current - new_alloc,
                    )
                )
        return decisions

    def compute_metabolic_pressure(
        self,
        total_cost: float,
        total_budget: float,
        safety_score: float,
    ) -> float:
        if total_budget <= 0.0:
            return 1.0
        base_pressure = total_cost / total_budget
        # La pressione metabolica è attenuata se safety è alta
        adjusted = base_pressure * (1.5 - safety_score)
        return max(0.0, min(1.0, adjusted))
