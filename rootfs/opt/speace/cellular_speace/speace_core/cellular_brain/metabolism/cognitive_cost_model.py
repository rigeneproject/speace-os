from typing import Dict, List, Optional

from speace_core.cellular_brain.metabolism.metabolic_models import CognitiveCostProfile


class CognitiveCostModel:
    """T58 — Stima e traccia costo cognitivo per modulo."""

    DEFAULT_BASE_COSTS = {
        "safety": 0.05,
        "memory": 0.04,
        "self_organization": 0.05,
        "evolutionary_kernel": 0.08,
        "evolutionary_memory": 0.03,
        "routing": 0.03,
        "repair": 0.04,
        "defense": 0.03,
        "benchmark": 0.02,
        "background_maintenance": 0.01,
    }

    def __init__(self):
        self._profiles: Dict[str, CognitiveCostProfile] = {}
        for module, cost in self.DEFAULT_BASE_COSTS.items():
            self._profiles[module] = CognitiveCostProfile(
                module_name=module,
                base_cost=cost,
                resource_class=module,
            )

    def estimate_module_cost(self, module_name: str, metrics: Optional[Dict[str, float]] = None) -> float:
        profile = self._profiles.get(module_name)
        if profile is None:
            return 0.0
        base = profile.base_cost
        if metrics is None:
            return base
        multiplier = 1.0
        # Costo scala con attività
        activity = metrics.get("activity_level", 0.5)
        multiplier += activity * 0.5
        # Costo scala con carico memoria
        memory_pressure = metrics.get("memory_pressure", 0.0)
        multiplier += memory_pressure * 0.3
        return base * max(0.5, min(3.0, multiplier))

    def update_cost_profile(self, module_name: str, observed_cost: float) -> None:
        profile = self._profiles.setdefault(
            module_name,
            CognitiveCostProfile(module_name=module_name, base_cost=observed_cost),
        )
        profile.last_cycle_cost = observed_cost
        if profile.peak_cost < observed_cost:
            profile.peak_cost = observed_cost
        # Rolling average EMA
        alpha = 0.3
        profile.rolling_average_cost = (
            alpha * observed_cost + (1 - alpha) * profile.rolling_average_cost
        )

    def compute_total_cognitive_cost(self, active_modules: Optional[List[str]] = None) -> float:
        total = 0.0
        modules = active_modules or list(self._profiles.keys())
        for name in modules:
            p = self._profiles.get(name)
            if p is not None:
                total += p.rolling_average_cost if p.rolling_average_cost > 0 else p.base_cost
        return total

    def compute_cost_efficiency(self) -> float:
        total_cost = 0.0
        weighted_usefulness = 0.0
        for p in self._profiles.values():
            cost = p.rolling_average_cost if p.rolling_average_cost > 0 else p.base_cost
            total_cost += cost
            weighted_usefulness += p.usefulness_score * cost
        if total_cost == 0.0:
            return 1.0
        return max(0.0, min(1.0, weighted_usefulness / total_cost))

    def detect_cost_spike(self, module_name: str, threshold: float = 2.0) -> bool:
        profile = self._profiles.get(module_name)
        if profile is None or profile.rolling_average_cost == 0.0:
            return False
        ratio = profile.last_cycle_cost / max(1e-9, profile.rolling_average_cost)
        return ratio > threshold

    def list_profiles(self) -> List[CognitiveCostProfile]:
        return list(self._profiles.values())
