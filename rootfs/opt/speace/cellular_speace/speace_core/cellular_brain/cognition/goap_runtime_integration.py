"""GOAPRuntimeIntegration — runs GOAP inside the runtime tick (T166).

Triggered when BT layer returns FAILURE or low-confidence proposals.
Produces plans that are simulated, evaluated by the metacognitive bridge,
and then submitted as proposals to the governance pipeline.
"""

import time
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.cognition.goap_action_registry import GOAPActionRegistry
from speace_core.cellular_brain.cognition.goap_metacognitive_bridge import GOAPMetacognitiveBridge
from speace_core.cellular_brain.cognition.goap_planner import GOAPPlanner, GoalState
from speace_core.cellular_brain.experience.temporal_narrative_engine import TemporalNarrativeEngine


class GOAPRuntimeIntegration:
    """Lightweight GOAP proposer integrated into the runtime tick."""

    def __init__(
        self,
        registry: Optional[GOAPActionRegistry] = None,
        bridge: Optional[GOAPMetacognitiveBridge] = None,
        narrative_engine: Optional[TemporalNarrativeEngine] = None,
        max_planning_ms: float = 50.0,
    ) -> None:
        self._registry = registry or GOAPActionRegistry()
        self._registry.build_default_registry()
        self._planner = GOAPPlanner(actions=list(self._registry._actions.values()))
        self._planner._max_planning_ms = max_planning_ms
        self._bridge = bridge or GOAPMetacognitiveBridge()
        self._narrative_engine = narrative_engine
        self._proposals: List[Dict[str, Any]] = []
        self._last_plan: Optional[Dict[str, Any]] = None
        self._tick_count: int = 0

    # ------------------------------------------------------------------ #
    # Tick
    # ------------------------------------------------------------------ #

    def tick(
        self,
        context: Dict[str, Any],
        goal_predicates: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Run GOAP for the given goal (or default), evaluate, and surface proposals."""
        self._tick_count += 1
        self._proposals.clear()

        # Default goal: reduce prediction error if not specified
        if goal_predicates is None:
            goal_predicates = {"prediction_error": "reduced"}

        goal = GoalState(goal_predicates)
        initial_state = context.get("world_state", {})

        # Run planner
        plan = self._planner.plan(initial_state, goal)
        self._last_plan = plan

        # Evaluate via metacognitive bridge
        evaluation = self._bridge.evaluate_plan(plan, initial_state)

        if plan is not None and evaluation.get("proceed", False):
            # Build proposal from plan
            proposal = {
                "source_layer": "goap",
                "proposal_type": "goal_plan",
                "description": f"GOAP plan for goal {goal_predicates}: {' → '.join(plan['actions'])}",
                "params": {
                    "goal": goal_predicates,
                    "actions": plan["actions"],
                    "total_cost": plan["total_cost"],
                    "simulated_only": plan.get("simulated_only", True),
                },
                "priority": 6,
                "confidence": evaluation["confidence"],
                "simulate_only": plan.get("simulated_only", True),
            }
            self._proposals.append(proposal)
        elif plan is not None and not evaluation.get("proceed", False):
            # Plan exists but confidence too low — log and suggest fallback
            if self._narrative_engine is not None:
                try:
                    self._narrative_engine.record(
                        event_type="goap_plan_rejected",
                        description=f"GOAP plan rejected: {evaluation.get('reason')}",
                        importance=4,
                        metadata={
                            "goal": goal_predicates,
                            "confidence": evaluation["confidence"],
                            "strategy_fit": evaluation["strategy_fit"],
                        },
                    )
                except Exception:
                    pass

        return list(self._proposals)

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def snapshot(self) -> Dict[str, Any]:
        return {
            "last_plan": self._last_plan,
            "proposal_count": len(self._proposals),
            "tick_count": self._tick_count,
            "planner": self._planner.snapshot(),
            "bridge": self._bridge.snapshot(),
            "registry": self._registry.snapshot(),
        }
