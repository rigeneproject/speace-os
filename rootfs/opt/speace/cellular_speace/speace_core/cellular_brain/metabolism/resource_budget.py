from typing import Dict, Optional

from speace_core.cellular_brain.metabolism.metabolic_models import ResourceBudget


class ResourceBudgetManager:
    """T58 — Gestisce budget energetico globale e allocazioni per modulo."""

    DEFAULT_HARD_CAPS = {
        "safety": 0.30,
        "memory": 0.25,
        "self_organization": 0.20,
        "evolutionary_kernel": 0.15,
        "evolutionary_memory": 0.10,
        "routing": 0.20,
        "repair": 0.15,
        "defense": 0.15,
        "benchmark": 0.10,
        "background_maintenance": 0.10,
    }

    DEFAULT_SOFT_CAPS = {
        "safety": 0.20,
        "memory": 0.15,
        "self_organization": 0.12,
        "evolutionary_kernel": 0.08,
        "evolutionary_memory": 0.05,
        "routing": 0.12,
        "repair": 0.10,
        "defense": 0.10,
        "benchmark": 0.05,
        "background_maintenance": 0.05,
    }

    def __init__(self, total_budget: float = 1.0):
        self.budget = ResourceBudget(
            total_energy_budget=total_budget,
            available_energy=total_budget,
            hard_caps=dict(self.DEFAULT_HARD_CAPS),
            soft_caps=dict(self.DEFAULT_SOFT_CAPS),
        )
        self._allocate_reserved()

    def _allocate_reserved(self) -> None:
        safety = self.budget.reserved_safety_budget
        recovery = self.budget.reserved_recovery_budget
        self.budget.module_allocations["safety_reserve"] = safety
        self.budget.module_allocations["recovery_reserve"] = recovery
        self.budget.available_energy = max(
            0.0, self.budget.total_energy_budget - safety - recovery
        )

    def create_default_budget(self) -> ResourceBudget:
        self.__init__(self.budget.total_energy_budget)
        return self.budget

    def allocate(self, module_name: str, amount: float) -> float:
        hard = self.budget.hard_caps.get(module_name, amount)
        capped = min(amount, hard)
        if capped > self.budget.available_energy:
            capped = self.budget.available_energy
        self.budget.module_allocations[module_name] = (
            self.budget.module_allocations.get(module_name, 0.0) + capped
        )
        self.budget.available_energy = max(0.0, self.budget.available_energy - capped)
        return capped

    def release(self, module_name: str, amount: float) -> float:
        current = self.budget.module_allocations.get(module_name, 0.0)
        released = min(amount, current)
        self.budget.module_allocations[module_name] = current - released
        self.budget.available_energy = min(
            self.budget.total_energy_budget,
            self.budget.available_energy + released,
        )
        return released

    def get_available_energy(self) -> float:
        return self.budget.available_energy

    def enforce_caps(self) -> Dict[str, float]:
        trimmed: Dict[str, float] = {}
        for module, allocation in list(self.budget.module_allocations.items()):
            hard = self.budget.hard_caps.get(module)
            if hard is not None and allocation > hard:
                excess = allocation - hard
                self.budget.module_allocations[module] = hard
                self.budget.available_energy = min(
                    self.budget.total_energy_budget,
                    self.budget.available_energy + excess,
                )
                trimmed[module] = excess
        return trimmed

    def reserve_for_safety(self, amount: Optional[float] = None) -> float:
        target = amount if amount is not None else self.budget.reserved_safety_budget
        current = self.budget.module_allocations.get("safety_reserve", 0.0)
        delta = target - current
        if delta > 0:
            delta = min(delta, self.budget.available_energy)
            self.budget.module_allocations["safety_reserve"] = current + delta
            self.budget.available_energy -= delta
        return self.budget.module_allocations["safety_reserve"]

    def reserve_for_recovery(self, amount: Optional[float] = None) -> float:
        target = amount if amount is not None else self.budget.reserved_recovery_budget
        current = self.budget.module_allocations.get("recovery_reserve", 0.0)
        delta = target - current
        if delta > 0:
            delta = min(delta, self.budget.available_energy)
            self.budget.module_allocations["recovery_reserve"] = current + delta
            self.budget.available_energy -= delta
        return self.budget.module_allocations["recovery_reserve"]

    def snapshot(self) -> ResourceBudget:
        return self.budget.model_copy()
