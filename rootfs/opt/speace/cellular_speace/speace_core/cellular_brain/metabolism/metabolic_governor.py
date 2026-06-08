import uuid
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.metabolism.cognitive_cost_model import CognitiveCostModel
from speace_core.cellular_brain.metabolism.energy_accounting import EnergyAccountingLedger
from speace_core.cellular_brain.metabolism.metabolic_models import (
    MetabolicDecision,
    MetabolicMode,
    MetabolicState,
    ResourceBudget,
)
from speace_core.cellular_brain.metabolism.metabolic_policy_engine import MetabolicPolicyEngine
from speace_core.cellular_brain.metabolism.resource_budget import ResourceBudgetManager


class MetabolicGovernor:
    """T58 — Orchestrator del metabolismo computazionale."""

    def __init__(
        self,
        budget_manager: Optional[ResourceBudgetManager] = None,
        cost_model: Optional[CognitiveCostModel] = None,
        policy_engine: Optional[MetabolicPolicyEngine] = None,
        ledger: Optional[EnergyAccountingLedger] = None,
    ):
        self.budget_manager = budget_manager or ResourceBudgetManager()
        self.cost_model = cost_model or CognitiveCostModel()
        self.policy_engine = policy_engine or MetabolicPolicyEngine()
        self.ledger = ledger or EnergyAccountingLedger()
        self._decisions: List[MetabolicDecision] = []

    # ------------------------------------------------------------------ #
    # State capture
    # ------------------------------------------------------------------ #

    def capture_metabolic_state(self, safety_score: float = 0.8) -> MetabolicState:
        budget = self.budget_manager.budget
        total_cost = self.cost_model.compute_total_cognitive_cost()
        pressure = self.policy_engine.compute_metabolic_pressure(
            total_cost, budget.total_energy_budget, safety_score
        )
        mode = self.policy_engine.classify_mode(pressure, budget.available_energy / max(1e-9, budget.total_energy_budget))
        efficiency = budget.available_energy / max(1e-9, budget.total_energy_budget)

        # Calcola protection score
        critical_min = 0.0
        critical_allocated = 0.0
        for mod in self.policy_engine.CRITICAL_MODULES:
            cap = budget.soft_caps.get(mod, 0.05)
            alloc = budget.module_allocations.get(mod, 0.0)
            critical_min += cap
            critical_allocated += min(alloc, cap)
        protection_score = critical_allocated / max(1e-9, critical_min) if critical_min > 0 else 1.0

        return MetabolicState(
            mode=mode,
            energy_reserve=budget.available_energy / max(1e-9, budget.total_energy_budget),
            metabolic_pressure=pressure,
            resource_allocation_efficiency=efficiency,
            cognitive_cost_total=total_cost,
            safety_preservation_score=safety_score,
            critical_function_protection_score=min(1.0, protection_score),
            throttling_level=0.0,
            starvation_risk=max(0.0, 1.0 - efficiency - safety_score),
            overconsumption_risk=max(0.0, total_cost - budget.available_energy) / max(1e-9, budget.total_energy_budget),
        )

    # ------------------------------------------------------------------ #
    # Cycle
    # ------------------------------------------------------------------ #

    def run_metabolic_cycle(self, safety_score: float = 0.8) -> Dict[str, Any]:
        state = self.capture_metabolic_state(safety_score)
        budget = self.budget_manager.budget
        costs: Dict[str, float] = {}
        for p in self.cost_model.list_profiles():
            costs[p.module_name] = p.rolling_average_cost if p.rolling_average_cost > 0 else p.base_cost

        # Throttling
        throttle_decisions = self.policy_engine.apply_throttling(budget, state.mode, costs)
        for d in throttle_decisions:
            self.budget_manager.release(d.target_module, d.previous_allocation - d.new_allocation)
            self.ledger.record_saving(d.target_module, d.previous_allocation - d.new_allocation, d.reason)

        # Critical protection
        protect_decisions = self.policy_engine.protect_critical_functions(budget, state.mode)
        for d in protect_decisions:
            allocated = self.budget_manager.allocate(d.target_module, d.new_allocation - d.previous_allocation)
            if allocated > 0:
                self.ledger.record_consumption(d.target_module, allocated, d.reason)

        # Evolutionary limit
        evo_cost = sum(
            costs.get(m, 0.0) for m in self.policy_engine.EVOLUTIONARY_MODULES
        )
        evo_decisions = self.policy_engine.limit_evolutionary_costs(budget, state.mode, evo_cost)
        for d in evo_decisions:
            self.budget_manager.release(d.target_module, d.previous_allocation - d.new_allocation)
            self.ledger.record_saving(d.target_module, d.previous_allocation - d.new_allocation, d.reason)

        all_decisions = throttle_decisions + protect_decisions + evo_decisions
        self._decisions.extend(all_decisions)

        # Aggiorna throttling level
        state.throttling_level = len(throttle_decisions) / max(1, len(costs))

        return {
            "mode": state.mode,
            "energy_reserve": state.energy_reserve,
            "metabolic_pressure": state.metabolic_pressure,
            "throttling_level": state.throttling_level,
            "decisions": len(all_decisions),
            "throttle_decisions": len(throttle_decisions),
            "protect_decisions": len(protect_decisions),
            "evo_decisions": len(evo_decisions),
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def get_metabolic_state(self) -> MetabolicState:
        return self.capture_metabolic_state()

    def generate_metabolic_report(self) -> Dict[str, Any]:
        return {
            "budget": self.budget_manager.budget.model_dump(),
            "total_cost": self.cost_model.compute_total_cognitive_cost(),
            "cost_efficiency": self.cost_model.compute_cost_efficiency(),
            "net_energy_delta": self.ledger.compute_net_energy_delta(),
            "decision_count": len(self._decisions),
        }
