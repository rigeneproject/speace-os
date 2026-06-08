"""BehaviorTreeCore — lightweight tick-based behavior tree engine for SPEACE (T164).

Provides Selector, Sequence, Action, Condition, Inverter, Succeeder nodes.
Execution is tick-based and returns SUCCESS / FAILURE / RUNNING.
Stateful nodes may persist across ticks.
"""

from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class NodeStatus(Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"


class BTNode:
    """Base class for all behavior tree nodes."""

    def __init__(self, name: str = "") -> None:
        self.name = name or self.__class__.__name__
        self._status: NodeStatus = NodeStatus.FAILURE

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        raise NotImplementedError

    def reset(self) -> None:
        self._status = NodeStatus.FAILURE

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name!r})"


class Selector(BTNode):
    """Selector (fallback): returns SUCCESS on first child that succeeds.
    Tries children left-to-right until one returns SUCCESS or RUNNING.
    """

    def __init__(self, name: str = "", children: Optional[List[BTNode]] = None) -> None:
        super().__init__(name)
        self.children = children or []
        self._running_child_idx: int = 0

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        for idx in range(self._running_child_idx, len(self.children)):
            child = self.children[idx]
            status = child.tick(context)
            if status == NodeStatus.SUCCESS:
                self._running_child_idx = 0
                self._status = NodeStatus.SUCCESS
                return self._status
            elif status == NodeStatus.RUNNING:
                self._running_child_idx = idx
                self._status = NodeStatus.RUNNING
                return self._status
            # FAILURE → try next child
        self._running_child_idx = 0
        self._status = NodeStatus.FAILURE
        return self._status

    def reset(self) -> None:
        super().reset()
        self._running_child_idx = 0
        for child in self.children:
            child.reset()


class Sequence(BTNode):
    """Sequence: returns FAILURE on first child that fails.
    Runs children left-to-right until one returns FAILURE or RUNNING.
    All must succeed for Sequence to succeed.
    """

    def __init__(self, name: str = "", children: Optional[List[BTNode]] = None) -> None:
        super().__init__(name)
        self.children = children or []
        self._running_child_idx: int = 0

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        for idx in range(self._running_child_idx, len(self.children)):
            child = self.children[idx]
            status = child.tick(context)
            if status == NodeStatus.FAILURE:
                self._running_child_idx = 0
                self._status = NodeStatus.FAILURE
                return self._status
            elif status == NodeStatus.RUNNING:
                self._running_child_idx = idx
                self._status = NodeStatus.RUNNING
                return self._status
            # SUCCESS → continue to next child
        self._running_child_idx = 0
        self._status = NodeStatus.SUCCESS
        return self._status

    def reset(self) -> None:
        super().reset()
        self._running_child_idx = 0
        for child in self.children:
            child.reset()


class Action(BTNode):
    """Leaf action node that executes a callable."""

    def __init__(
        self,
        name: str = "",
        fn: Optional[Callable[[Dict[str, Any]], NodeStatus]] = None,
    ) -> None:
        super().__init__(name)
        self.fn = fn

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        if self.fn is None:
            self._status = NodeStatus.FAILURE
            return self._status
        try:
            self._status = self.fn(context)
        except Exception:
            self._status = NodeStatus.FAILURE
        return self._status


class Condition(BTNode):
    """Leaf condition node that evaluates a predicate."""

    def __init__(
        self,
        name: str = "",
        predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ) -> None:
        super().__init__(name)
        self.predicate = predicate

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        if self.predicate is None:
            self._status = NodeStatus.FAILURE
            return self._status
        try:
            result = self.predicate(context)
            self._status = NodeStatus.SUCCESS if result else NodeStatus.FAILURE
        except Exception:
            self._status = NodeStatus.FAILURE
        return self._status


class Inverter(BTNode):
    """Decorator that inverts the result of its single child.
    SUCCESS → FAILURE, FAILURE → SUCCESS, RUNNING stays RUNNING.
    """

    def __init__(self, name: str = "", child: Optional[BTNode] = None) -> None:
        super().__init__(name)
        self.child = child

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        if self.child is None:
            self._status = NodeStatus.FAILURE
            return self._status
        status = self.child.tick(context)
        if status == NodeStatus.SUCCESS:
            self._status = NodeStatus.FAILURE
        elif status == NodeStatus.FAILURE:
            self._status = NodeStatus.SUCCESS
        else:
            self._status = status
        return self._status

    def reset(self) -> None:
        super().reset()
        if self.child is not None:
            self.child.reset()


class Succeeder(BTNode):
    """Decorator that always returns SUCCESS regardless of child result.
    Useful for optional branches that must not fail a Sequence.
    """

    def __init__(self, name: str = "", child: Optional[BTNode] = None) -> None:
        super().__init__(name)
        self.child = child

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        if self.child is not None:
            self.child.tick(context)
        self._status = NodeStatus.SUCCESS
        return self._status

    def reset(self) -> None:
        super().reset()
        if self.child is not None:
            self.child.reset()


class BehaviorTree:
    """Root wrapper for a behavior tree."""

    def __init__(self, name: str, root: BTNode) -> None:
        self.name = name
        self.root = root
        self._last_status: NodeStatus = NodeStatus.FAILURE
        self._tick_count: int = 0

    def tick(self, context: Dict[str, Any]) -> NodeStatus:
        self._tick_count += 1
        self._last_status = self.root.tick(context)
        return self._last_status

    def reset(self) -> None:
        self.root.reset()
        self._last_status = NodeStatus.FAILURE
        self._tick_count = 0

    def snapshot(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "last_status": self._last_status.value,
            "tick_count": self._tick_count,
        }
