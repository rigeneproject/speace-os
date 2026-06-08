"""CognitiveNurseryScenarioBuilder — structured virtual scenarios for infant learning (T168).

Provides safe, pedagogical environments: falling objects, agent approach, tool use,
hidden object. Each scenario defines controllable variables and expected causal chains.
"""

import uuid
from typing import Any, Dict, List, Optional


class NurseryScenario:
    """A single scenario template with variables and expected causal chain."""

    def __init__(
        self,
        scenario_id: str,
        name: str,
        description: str,
        variables: Dict[str, Any],
        expected_chain: List[str],
    ) -> None:
        self.scenario_id = scenario_id
        self.name = name
        self.description = description
        self.variables = dict(variables)
        self.expected_chain = list(expected_chain)

    def instantiate(self, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return an instantiated scenario run config."""
        run_id = f"nursery_{uuid.uuid4().hex[:8]}"
        instance = dict(self.variables)
        if overrides:
            instance.update(overrides)
        return {
            "run_id": run_id,
            "scenario_id": self.scenario_id,
            "name": self.name,
            "variables": instance,
            "expected_chain": self.expected_chain,
            "status": "ready",
        }

    def snapshot(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "variables": self.variables,
            "expected_chain": self.expected_chain,
        }


class CognitiveNurseryScenarioBuilder:
    """Registry and builder for nursery scenarios."""

    def __init__(self) -> None:
        self._scenarios: Dict[str, NurseryScenario] = {}
        self._build_defaults()

    def _build_defaults(self) -> None:
        self.register(
            NurseryScenario(
                scenario_id="falling_objects",
                name="Falling Objects",
                description="Object released from height falls due to gravity; collision produces sound.",
                variables={
                    "gravity": 9.8,
                    "object_mass": 1.0,
                    "release_height": 2.0,
                    "surface_elasticity": 0.3,
                },
                expected_chain=[
                    "release_object",
                    "object_falls",
                    "collision_with_surface",
                    "sound_emitted",
                ],
            )
        )
        self.register(
            NurseryScenario(
                scenario_id="agent_approach",
                name="Agent Approach",
                description="Virtual agent moves toward or away; social proximity changes.",
                variables={
                    "agent_speed": 1.0,
                    "initial_distance": 5.0,
                    "direction": "toward",
                    "agent_drive": "curiosity",
                },
                expected_chain=[
                    "agent_perceives_target",
                    "agent_moves",
                    "distance_changes",
                    "proximity_event",
                ],
            )
        )
        self.register(
            NurseryScenario(
                scenario_id="tool_use",
                name="Tool Use",
                description="Object manipulation to reach a goal (e.g. push box to get food).",
                variables={
                    "tool_type": "stick",
                    "target_distance": 3.0,
                    "obstacle_present": True,
                },
                expected_chain=[
                    "agent_perceives_goal",
                    "agent_selects_tool",
                    "agent_applies_tool",
                    "goal_reached",
                ],
            )
        )
        self.register(
            NurseryScenario(
                scenario_id="hidden_object",
                name="Hidden Object",
                description="Object permanence test: object hidden, agent must remember location.",
                variables={
                    "hiding_duration": 5.0,
                    "distraction_count": 2,
                    "object_type": "ball",
                },
                expected_chain=[
                    "object_visible",
                    "object_hidden",
                    "distraction_events",
                    "agent_queries_memory",
                    "object_revealed",
                ],
            )
        )

    def register(self, scenario: NurseryScenario) -> None:
        self._scenarios[scenario.scenario_id] = scenario

    def list_scenarios(self) -> List[Dict[str, Any]]:
        return [s.snapshot() for s in self._scenarios.values()]

    def get(self, scenario_id: str) -> Optional[NurseryScenario]:
        return self._scenarios.get(scenario_id)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "scenario_count": len(self._scenarios),
            "scenarios": self.list_scenarios(),
        }
