"""UtilityArbitrationEngine — maps drive vector to module priority weights (T165).

Reads the current drive state and organism FSM state, then produces normalized
module_priority_weights. Safety-critical modules (EmergencyHaltGate,
CausalLearningAuditor) have a hard floor and cannot be zeroed.
"""

from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.regulation.utility_drive_system import UtilityDriveSystem


class UtilityArbitrationEngine:
    """Arbitrates module scheduling priority based on dynamic drives."""

    # Modules that must always retain at least this weight
    SAFETY_MODULES: Dict[str, float] = {
        "causal_learning_auditor": 0.10,
        "homeostasis_engine": 0.10,
    }

    # Default module registry: module_id -> list of (drive_name, weight_factor)
    DEFAULT_MODULE_DRIVE_MAP: Dict[str, List[tuple[str, float]]] = {
        "infant_curiosity_layer": [("exploration", 1.0), ("prediction_error_reduction", 0.5)],
        "cyber_physical_sensor_array": [("exploration", 0.8), ("prediction_error_reduction", 0.4)],
        "homeostasis_engine": [("stability", 1.0), ("energy_conservation", 0.6)],
        "causal_learning_auditor": [("stability", 0.7), ("prediction_error_reduction", 0.6)],
        "global_workspace": [("stability", 0.5), ("exploration", 0.5)],
        "dialogue_manager": [("social_interaction", 1.0)],
        "distributed_latent_sync": [("social_interaction", 0.6), ("stability", 0.3)],
        "metacognitive_monitor": [("stability", 0.4), ("prediction_error_reduction", 0.4)],
        "reflective_narrative_generator": [("rest", 0.5), ("stability", 0.3)],
        "episodic_memory_consolidation": [("rest", 0.8), ("stability", 0.4)],
    }

    def __init__(
        self,
        drive_system: Optional[UtilityDriveSystem] = None,
        module_drive_map: Optional[Dict[str, List[tuple[str, float]]]] = None,
    ) -> None:
        self._drive_system = drive_system or UtilityDriveSystem()
        self._module_drive_map = module_drive_map or dict(self.DEFAULT_MODULE_DRIVE_MAP)
        self._weights: Dict[str, float] = {mod: 0.1 for mod in self._module_drive_map}
        self._tick_count: int = 0

    # ------------------------------------------------------------------ #
    # Tick
    # ------------------------------------------------------------------ #

    def tick(
        self,
        organism_state: str = "awake",
    ) -> Dict[str, float]:
        """Recompute module priority weights from current drive vector.

        Returns normalized weights that sum to 1.0.
        """
        self._tick_count += 1
        drives = self._drive_system._drives

        raw_weights: Dict[str, float] = {}
        for module, drive_bindings in self._module_drive_map.items():
            score = 0.0
            total_factor = 0.0
            for drive_name, factor in drive_bindings:
                score += drives.get(drive_name, 0.0) * factor
                total_factor += factor
            if total_factor > 0:
                raw_weights[module] = score / total_factor
            else:
                raw_weights[module] = 0.0

        # Apply organism-state overrides
        if organism_state == "overloaded":
            raw_weights["homeostasis_engine"] = max(raw_weights.get("homeostasis_engine", 0.0), 0.8)
            raw_weights["infant_curiosity_layer"] = raw_weights.get("infant_curiosity_layer", 0.0) * 0.2
        elif organism_state == "resting":
            raw_weights["episodic_memory_consolidation"] = max(raw_weights.get("episodic_memory_consolidation", 0.0), 0.7)
            raw_weights["infant_curiosity_layer"] = raw_weights.get("infant_curiosity_layer", 0.0) * 0.3
        elif organism_state == "exploring":
            raw_weights["infant_curiosity_layer"] = max(raw_weights.get("infant_curiosity_layer", 0.0), 0.7)
            raw_weights["cyber_physical_sensor_array"] = max(raw_weights.get("cyber_physical_sensor_array", 0.0), 0.6)

        # Enforce safety floors
        for module, floor in self.SAFETY_MODULES.items():
            if module in raw_weights:
                raw_weights[module] = max(raw_weights[module], floor)

        # Normalize to sum 1.0
        total = sum(raw_weights.values())
        if total > 0:
            self._weights = {k: v / total for k, v in raw_weights.items()}
        else:
            n = len(raw_weights)
            self._weights = {k: 1.0 / n for k in raw_weights}

        return dict(self._weights)

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get_weight(self, module: str) -> float:
        return self._weights.get(module, 0.0)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "weights": dict(self._weights),
            "drive_snapshot": self._drive_system.snapshot(),
            "tick_count": self._tick_count,
            "safety_floors": dict(self.SAFETY_MODULES),
        }
