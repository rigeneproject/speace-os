"""GOAPActionRegistry — maps SPEACE capabilities to GOAP actions (T166).

Actions are tagged simulate-only or propose-external. External actions require
human approval via the existing governance pipeline.
"""

from typing import Any, Callable, Dict, List, Optional

from speace_core.cellular_brain.cognition.goap_planner import GOAPAction


class GOAPActionRegistry:
    """Registry of GOAP actions backed by existing SPEACE modules."""

    def __init__(self) -> None:
        self._actions: Dict[str, GOAPAction] = {}
        self._module_backends: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {}

    def register(
        self,
        name: str,
        preconditions: Dict[str, Any],
        effects: Dict[str, Any],
        cost: float = 1.0,
        simulate_only: bool = True,
        module_backend: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> None:
        action = GOAPAction(
            name=name,
            preconditions=preconditions,
            effects=effects,
            cost=cost,
            simulate_only=simulate_only,
            execution_fn=module_backend,
        )
        self._actions[name] = action
        if module_backend is not None:
            self._module_backends[name] = module_backend

    def get_action(self, name: str) -> Optional[GOAPAction]:
        return self._actions.get(name)

    def list_actions(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": a.name,
                "preconditions": a.preconditions,
                "effects": a.effects,
                "cost": a.cost,
                "simulate_only": a.simulate_only,
            }
            for a in self._actions.values()
        ]

    def build_default_registry(self) -> None:
        """Populate registry with standard SPEACE-mapped actions."""
        self.register(
            name="observe_sensor",
            preconditions={"sensor_data_fresh": False},
            effects={"sensor_data_fresh": True, "prediction_error": "reduced"},
            cost=1.0,
            simulate_only=True,
        )
        self.register(
            name="query_memory",
            preconditions={"memory_queried": False},
            effects={"memory_queried": True, "uncertainty": "reduced"},
            cost=1.0,
            simulate_only=True,
        )
        self.register(
            name="request_clarification",
            preconditions={"clarification_needed": True},
            effects={"clarification_needed": False, "social_interaction": "increased"},
            cost=2.0,
            simulate_only=False,
        )
        self.register(
            name="run_counterfactual",
            preconditions={"hypothesis_ready": True},
            effects={"hypothesis_tested": True, "prediction_error": "reduced"},
            cost=3.0,
            simulate_only=True,
        )
        self.register(
            name="trigger_metacognitive_review",
            preconditions={"metacognition_active": False},
            effects={"metacognition_active": True, "strategy_evaluated": True},
            cost=2.0,
            simulate_only=True,
        )
        self.register(
            name="adjust_attention",
            preconditions={"attention_focused": False},
            effects={"attention_focused": True, "coherence": "increased"},
            cost=1.0,
            simulate_only=True,
        )

    def snapshot(self) -> Dict[str, Any]:
        return {
            "registered_actions": self.list_actions(),
            "count": len(self._actions),
        }
