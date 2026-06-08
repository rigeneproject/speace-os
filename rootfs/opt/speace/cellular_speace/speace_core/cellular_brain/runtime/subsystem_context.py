from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class TickState:
    current_tick: int = 0
    latest_metrics: Any = None
    last_community_result: Any = None
    last_confidence_state: Any = None
    last_routing_result: Any = None
    negative_feedback_count: int = 0


@dataclass
class SubsystemContext:
    """Mutable context passed to every plugin on each tick."""

    orchestrator_ref: Callable[[], Any]
    genome: Any = None
    tick_state: TickState = field(default_factory=TickState)
