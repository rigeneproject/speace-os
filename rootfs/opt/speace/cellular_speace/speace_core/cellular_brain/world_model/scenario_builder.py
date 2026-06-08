import random
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.world_model.world_model_models import (
    WorldConstraint,
    WorldEntity,
    WorldModelSnapshot,
    WorldScenario,
    WorldZone,
)


class ScenarioBuilder:
    """Builds simulated scenarios from snapshots. Blocks real actions."""

    def __init__(self, seed: int = 42):
        self._seed = seed
        self._rng = random.Random(seed)

    def build_baseline_scenario(self, snapshot: WorldModelSnapshot) -> WorldScenario:
        return WorldScenario(
            scenario_id=f"sc_baseline_{snapshot.snapshot_id}",
            name="baseline",
            initial_state_id=snapshot.snapshot_id,
            horizon_ticks=5,
            perturbations=[],
            simulated_actions=[],
        )

    def build_stress_scenario(self, snapshot: WorldModelSnapshot) -> WorldScenario:
        perturbations = []
        for z in snapshot.zones:
            perturbations.append({
                "type": "pressure_spike",
                "target_zone_id": z.zone_id,
                "delta_infrastructure": self._rng.uniform(0.2, 0.5),
                "delta_energy": self._rng.uniform(0.1, 0.4),
            })
        return WorldScenario(
            scenario_id=f"sc_stress_{snapshot.snapshot_id}",
            name="stress",
            initial_state_id=snapshot.snapshot_id,
            horizon_ticks=5,
            perturbations=perturbations,
            simulated_actions=[],
        )

    def build_conflict_scenario(self, snapshot: WorldModelSnapshot) -> WorldScenario:
        perturbations = []
        if len(snapshot.entities) >= 2:
            e1 = snapshot.entities[0]
            e2 = snapshot.entities[1]
            perturbations.append({
                "type": "state_conflict",
                "entity_a": e1.entity_id,
                "entity_b": e2.entity_id,
                "conflict_key": "status",
                "value_a": "active",
                "value_b": "inactive",
            })
        return WorldScenario(
            scenario_id=f"sc_conflict_{snapshot.snapshot_id}",
            name="conflict",
            initial_state_id=snapshot.snapshot_id,
            horizon_ticks=5,
            perturbations=perturbations,
            simulated_actions=[],
        )

    def build_energy_scarcity_scenario(self, snapshot: WorldModelSnapshot) -> WorldScenario:
        perturbations = []
        for z in snapshot.zones:
            perturbations.append({
                "type": "energy_scarcity",
                "target_zone_id": z.zone_id,
                "delta_energy": -self._rng.uniform(0.3, 0.7),
            })
        return WorldScenario(
            scenario_id=f"sc_energy_scarcity_{snapshot.snapshot_id}",
            name="energy_scarcity",
            initial_state_id=snapshot.snapshot_id,
            horizon_ticks=5,
            perturbations=perturbations,
            simulated_actions=[],
        )

    def build_safety_hazard_scenario(self, snapshot: WorldModelSnapshot) -> WorldScenario:
        perturbations = []
        for e in snapshot.entities:
            if e.safety_relevance > 0.3:
                perturbations.append({
                    "type": "safety_hazard",
                    "target_entity_id": e.entity_id,
                    "delta_safety": self._rng.uniform(0.3, 0.8),
                })
        return WorldScenario(
            scenario_id=f"sc_safety_{snapshot.snapshot_id}",
            name="safety_hazard",
            initial_state_id=snapshot.snapshot_id,
            horizon_ticks=5,
            perturbations=perturbations,
            simulated_actions=[],
        )

    def validate_scenario_read_only(self, scenario: WorldScenario) -> tuple[bool, Optional[str]]:
        for action in scenario.simulated_actions:
            action_type = action.get("type", "")
            if action_type in ("actuate", "command", "write", "control", "patch", "deploy"):
                return False, f"real_action_detected:{action_type}"
            if action.get("target_real", False):
                return False, "real_target_flag_set"
        return True, None

    def build_scenario_from_profile(
        self,
        snapshot: WorldModelSnapshot,
        scenario_type: str,
        conflict_level: float = 0.0,
        uncertainty_level: float = 0.0,
    ) -> WorldScenario:
        if scenario_type == "stress":
            scenario = self.build_stress_scenario(snapshot)
        elif scenario_type == "conflict":
            scenario = self.build_conflict_scenario(snapshot)
        elif scenario_type == "scarcity":
            scenario = self.build_energy_scarcity_scenario(snapshot)
        elif scenario_type == "safety":
            scenario = self.build_safety_hazard_scenario(snapshot)
        else:
            scenario = self.build_baseline_scenario(snapshot)

        if conflict_level > 0.0:
            scenario.perturbations.append({
                "type": "injected_conflict",
                "level": conflict_level,
            })
        if uncertainty_level > 0.0:
            scenario.perturbations.append({
                "type": "injected_uncertainty",
                "level": uncertainty_level,
            })
        return scenario
