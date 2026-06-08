"""BTRuntimeIntegration — adapter that runs behavior trees inside the runtime tick (T164).

Feeds BTs with runtime context (sensors, homeostasis, organism state) and collects
BehaviorProposals. Proposals are forwarded to the existing governance pipeline;
no autonomous execution occurs.
"""

import time
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.cognition.behavior_tree_core import BehaviorTree, NodeStatus
from speace_core.cellular_brain.cognition.reflex_behavior_library import DEFAULT_BT_LIBRARY
from speace_core.cellular_brain.experience.temporal_narrative_engine import TemporalNarrativeEngine


class BTRuntimeIntegration:
    """Runs the behavior tree library each tick and surfaces proposals."""

    def __init__(
        self,
        library: Optional[Dict[str, Any]] = None,
        narrative_engine: Optional[TemporalNarrativeEngine] = None,
        max_tick_ms: float = 10.0,
    ) -> None:
        self._library = library or DEFAULT_BT_LIBRARY
        self._narrative_engine = narrative_engine
        self._max_tick_ms = max_tick_ms

        # Instantiate trees
        self._trees: Dict[str, BehaviorTree] = {}
        for name, builder in self._library.items():
            try:
                self._trees[name] = builder()
            except Exception:
                pass

        self._proposals: List[Dict[str, Any]] = []
        self._last_tick_latencies_ms: Dict[str, float] = {}
        self._tick_count: int = 0

    # ------------------------------------------------------------------ #
    # Tick
    # ------------------------------------------------------------------ #

    def tick(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Run all behavior trees against the provided context.

        Returns the list of BehaviorProposals collected during this tick.
        """
        self._tick_count += 1
        self._proposals.clear()
        context["proposals"] = self._proposals

        for name, tree in self._trees.items():
            start = time.time()
            try:
                status = tree.tick(context)
            except Exception:
                status = NodeStatus.FAILURE
            elapsed_ms = (time.time() - start) * 1000.0
            self._last_tick_latencies_ms[name] = elapsed_ms

            # Timeout guard: if a single tree exceeds budget, skip remaining trees this tick
            if elapsed_ms > self._max_tick_ms:
                if self._narrative_engine is not None:
                    try:
                        self._narrative_engine.record(
                            event_type="bt_timeout",
                            description=f"Behavior tree {name} exceeded {self._max_tick_ms} ms budget.",
                            importance=4,
                            metadata={"tree": name, "latency_ms": round(elapsed_ms, 3)},
                        )
                    except Exception:
                        pass
                break

        # Log proposals to narrative
        if self._proposals and self._narrative_engine is not None:
            try:
                self._narrative_engine.record(
                    event_type="bt_proposals_generated",
                    description=f"Behavior trees generated {len(self._proposals)} proposals.",
                    importance=3,
                    metadata={
                        "proposal_types": [p["proposal_type"] for p in self._proposals],
                        "count": len(self._proposals),
                    },
                )
            except Exception:
                pass

        return list(self._proposals)

    # ------------------------------------------------------------------ #
    # Context builder
    # ------------------------------------------------------------------ #

    def build_context(
        self,
        *,
        health_score: float = 0.0,
        cognitive_load: float = 0.0,
        prediction_error: float = 0.0,
        energy: float = 1.0,
        curiosity_score: float = 0.0,
        organism_state: str = "awake",
        sensor_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Assemble the context dict consumed by behavior trees."""
        return {
            "health_score": health_score,
            "cognitive_load": cognitive_load,
            "prediction_error": prediction_error,
            "energy": energy,
            "curiosity_score": curiosity_score,
            "organism_state": organism_state,
            "sensor_snapshot": sensor_snapshot or {},
            "tick_count": self._tick_count,
            "proposals": [],
        }

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def snapshot(self) -> Dict[str, Any]:
        return {
            "trees": {name: tree.snapshot() for name, tree in self._trees.items()},
            "last_tick_latencies_ms": dict(self._last_tick_latencies_ms),
            "tick_count": self._tick_count,
            "active_tree_count": len(self._trees),
        }
