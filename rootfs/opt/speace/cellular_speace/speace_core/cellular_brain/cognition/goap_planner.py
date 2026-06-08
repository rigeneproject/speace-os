"""GOAPPlanner — Goal-Oriented Action Planning for SPEACE (T166).

Implements A* search over a discrete action graph. Plans are simulated in
WorldModelSandbox before approval; no autonomous execution.
"""

from __future__ import annotations

import heapq
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class GoalState:
    """Desired world-state predicates."""

    def __init__(self, predicates: Dict[str, Any]) -> None:
        self.predicates = dict(predicates)

    def is_satisfied(self, state: Dict[str, Any]) -> bool:
        for k, v in self.predicates.items():
            if state.get(k) != v:
                return False
        return True


class GOAPAction:
    """A discrete action with preconditions, effects, and cost."""

    def __init__(
        self,
        name: str,
        preconditions: Dict[str, Any],
        effects: Dict[str, Any],
        cost: float = 1.0,
        simulate_only: bool = True,
        execution_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> None:
        self.name = name
        self.preconditions = dict(preconditions)
        self.effects = dict(effects)
        self.cost = cost
        self.simulate_only = simulate_only
        self.execution_fn = execution_fn

    def is_applicable(self, state: Dict[str, Any]) -> bool:
        for k, v in self.preconditions.items():
            if state.get(k) != v:
                return False
        return True

    def apply(self, state: Dict[str, Any]) -> Dict[str, Any]:
        new_state = dict(state)
        new_state.update(self.effects)
        return new_state


class GOAPPlanner:
    """A* planner for goal-oriented action planning."""

    def __init__(self, actions: Optional[List[GOAPAction]] = None) -> None:
        self.actions = actions or []
        self._plan_cache: Dict[str, Any] = {}
        self._max_planning_ms: float = 50.0

    def add_action(self, action: GOAPAction) -> None:
        self.actions.append(action)

    def plan(
        self,
        initial_state: Dict[str, Any],
        goal: GoalState,
    ) -> Optional[Dict[str, Any]]:
        """Run A* search and return a plan dict, or None if no plan found."""
        start_time = time.time()

        # A* structures
        open_set: List[Tuple[float, int, Dict[str, Any], List[GOAPAction]]] = []
        counter = 0
        heapq.heappush(open_set, (0.0, counter, dict(initial_state), []))

        visited: Set[str] = set()

        while open_set:
            elapsed_ms = (time.time() - start_time) * 1000.0
            if elapsed_ms > self._max_planning_ms:
                return None  # timeout

            f_score, _, current_state, path = heapq.heappop(open_set)
            state_key = str(sorted(current_state.items()))
            if state_key in visited:
                continue
            visited.add(state_key)

            if goal.is_satisfied(current_state):
                return {
                    "goal": goal.predicates,
                    "actions": [a.name for a in path],
                    "total_cost": f_score,
                    "depth": len(path),
                    "simulated_only": all(a.simulate_only for a in path),
                }

            for action in self.actions:
                if action.is_applicable(current_state):
                    new_state = action.apply(current_state)
                    new_path = path + [action]
                    g_score = sum(a.cost for a in new_path)
                    h_score = self._heuristic(new_state, goal)
                    counter += 1
                    heapq.heappush(open_set, (g_score + h_score, counter, new_state, new_path))

        return None

    @staticmethod
    def _heuristic(state: Dict[str, Any], goal: GoalState) -> float:
        """Simple heuristic: count of unsatisfied predicates."""
        return float(sum(1 for k, v in goal.predicates.items() if state.get(k) != v))

    def snapshot(self) -> Dict[str, Any]:
        return {
            "action_count": len(self.actions),
            "max_planning_ms": self._max_planning_ms,
        }
