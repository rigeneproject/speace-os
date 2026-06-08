from typing import Any, Dict, List

from speace_core.cellular_brain.organism.organism_models import OrganismState


class OrganismStateSynthesizer:
    """T59 — Sintetizza lo stato globale dell'organismo dai sottosistemi."""

    def synthesize_state(self, metrics: Dict[str, Any], tick: int = 0) -> OrganismState:
        state = OrganismState(tick=tick)

        # Metabolic mode
        state.metabolic_mode = metrics.get("metabolic_mode", "normal")
        state.global_energy_reserve = metrics.get("global_energy_reserve", 1.0)

        # Health e coherence
        state.global_health_score = self.compute_global_health_score(metrics)
        state.global_coherence_phi = metrics.get("global_coherence_phi", 0.0)

        # Pressures
        state.criticality_score = metrics.get("criticality_score", 0.0)
        state.recovery_pressure = self.compute_recovery_pressure(metrics)
        state.evolutionary_pressure = metrics.get("evolutionary_pressure", 0.0)
        state.memory_governance_score = metrics.get("memory_governance_score", 1.0)
        state.safety_risk_score = metrics.get("safety_risk_score", 0.0)

        # Subsystems
        active = metrics.get("active_subsystems", [])
        degraded = metrics.get("degraded_subsystems", [])
        state.active_subsystems = active if isinstance(active, list) else []
        state.degraded_subsystems = degraded if isinstance(degraded, list) else []

        state.metadata = {"synthesized": True, "raw_keys": list(metrics.keys())}
        return state

    def compute_global_health_score(self, metrics: Dict[str, Any]) -> float:
        scores = []
        if "subsystem_health_scores" in metrics:
            scores = metrics["subsystem_health_scores"]
        elif "health_score" in metrics:
            scores = [metrics["health_score"]]
        if not scores:
            return 1.0
        return sum(scores) / max(1, len(scores))

    def compute_recovery_pressure(self, metrics: Dict[str, Any]) -> float:
        recovery_load = metrics.get("recovery_load", 0.0)
        repair_count = metrics.get("repair_count", 0)
        return min(1.0, recovery_load + repair_count * 0.05)

    def compute_evolutionary_pressure(self, metrics: Dict[str, Any]) -> float:
        evo_cost = metrics.get("evolutionary_cost", 0.0)
        mutation_rate = metrics.get("mutation_rate", 0.0)
        return min(1.0, evo_cost + mutation_rate)

    def compute_safety_risk_score(self, metrics: Dict[str, Any]) -> float:
        safety_failures = metrics.get("safety_failures", 0)
        alert_count = metrics.get("alert_count", 0)
        return min(1.0, safety_failures * 0.2 + alert_count * 0.1)

    def detect_state_conflicts(self, state: OrganismState) -> List[str]:
        conflicts: List[str] = []
        if state.recovery_pressure > 0.5 and state.evolutionary_pressure > 0.5:
            conflicts.append("recovery_evolution_conflict")
        if state.safety_risk_score > 0.5 and state.global_health_score > 0.8:
            conflicts.append("safety_health_mismatch")
        if state.metabolic_mode in ("critical", "stress") and state.evolutionary_pressure > 0.3:
            conflicts.append("evolution_under_critical_metabolism")
        return conflicts
