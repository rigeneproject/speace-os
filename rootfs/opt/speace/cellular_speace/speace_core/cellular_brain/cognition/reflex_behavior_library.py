"""ReflexBehaviorLibrary — predefined behavior trees for SPEACE micro-reflexes (T164).

Provides BTs for:
- explore_local
- avoid_overload
- prioritize_homeostatic_need
- search_grounding_input

Each leaf action adds a BehaviorProposal to context["proposals"] and returns SUCCESS.
No action is executed autonomously.
"""

from typing import Any, Dict, List

from speace_core.cellular_brain.cognition.behavior_tree_core import (
    Action,
    BehaviorTree,
    Condition,
    NodeStatus,
    Selector,
    Sequence,
)


def _make_proposal(
    context: Dict[str, Any],
    proposal_type: str,
    description: str,
    params: Dict[str, Any],
    priority: int = 5,
) -> NodeStatus:
    """Helper: append a proposal to the context and return SUCCESS."""
    proposals: List[Dict[str, Any]] = context.setdefault("proposals", [])
    proposals.append({
        "source_layer": "behavior_tree",
        "proposal_type": proposal_type,
        "description": description,
        "params": params,
        "priority": priority,
        "confidence": 0.7,
        "simulate_only": True,
    })
    return NodeStatus.SUCCESS


# --------------------------------------------------------------------------- #
# Conditions
# --------------------------------------------------------------------------- #

def _stability_ok(ctx: Dict[str, Any]) -> bool:
    health = ctx.get("health_score", 0.0)
    return health >= 0.4


def _curiosity_high(ctx: Dict[str, Any]) -> bool:
    return ctx.get("curiosity_score", 0.0) >= 0.5


def _load_high(ctx: Dict[str, Any]) -> bool:
    return ctx.get("cognitive_load", 0.0) >= 0.75


def _energy_low(ctx: Dict[str, Any]) -> bool:
    return ctx.get("energy", 1.0) <= 0.3


def _uncertainty_high(ctx: Dict[str, Any]) -> bool:
    pred_err = ctx.get("prediction_error", 0.0)
    return pred_err >= 0.6


# --------------------------------------------------------------------------- #
# Leaf actions
# --------------------------------------------------------------------------- #

def _action_scan_sensors(ctx: Dict[str, Any]) -> NodeStatus:
    return _make_proposal(
        ctx,
        "observe_sensor",
        "BT reflex: scan cyber-physical sensors for novel input.",
        {"sensor_types": ["cpu", "memory", "filesystem"]},
        priority=4,
    )


def _action_propose_observe(ctx: Dict[str, Any]) -> NodeStatus:
    return _make_proposal(
        ctx,
        "observe",
        "BT reflex: propose passive observation cycle.",
        {"duration_seconds": 5},
        priority=3,
    )


def _action_reduce_tick(ctx: Dict[str, Any]) -> NodeStatus:
    return _make_proposal(
        ctx,
        "modulate_tick",
        "BT reflex: reduce tick interval to lower cognitive load.",
        {"tick_multiplier": 2.0},
        priority=7,
    )


def _action_pause_nonessential(ctx: Dict[str, Any]) -> NodeStatus:
    return _make_proposal(
        ctx,
        "pause_modules",
        "BT reflex: pause non-essential modules during overload.",
        {"modules": ["curiosity", "concept_formation"]},
        priority=8,
    )


def _action_propose_rest(ctx: Dict[str, Any]) -> NodeStatus:
    return _make_proposal(
        ctx,
        "request_state",
        "BT reflex: propose transition to resting state.",
        {"target_state": "resting"},
        priority=6,
    )


def _action_propose_conservation(ctx: Dict[str, Any]) -> NodeStatus:
    return _make_proposal(
        ctx,
        "energy_conservation",
        "BT reflex: trigger energy conservation mode.",
        {"reduce_sampling": True},
        priority=7,
    )


def _action_propose_dialogue(ctx: Dict[str, Any]) -> NodeStatus:
    return _make_proposal(
        ctx,
        "social_interaction",
        "BT reflex: propose social dialogue to satisfy social drive.",
        {"initiative": "greeting"},
        priority=4,
    )


def _action_query_memory(ctx: Dict[str, Any]) -> NodeStatus:
    return _make_proposal(
        ctx,
        "query_memory",
        "BT reflex: query episodic memory to reduce uncertainty.",
        {"query_type": "recent_episodes"},
        priority=5,
    )


# --------------------------------------------------------------------------- #
# Predefined behavior trees
# --------------------------------------------------------------------------- #

def build_explore_local() -> BehaviorTree:
    """Sequence: if stability OK and curiosity high, scan sensors and propose observe."""
    return BehaviorTree(
        name="explore_local",
        root=Sequence(
            name="explore_local_seq",
            children=[
                Condition(name="stability_ok", predicate=_stability_ok),
                Condition(name="curiosity_high", predicate=_curiosity_high),
                Action(name="scan_sensors", fn=_action_scan_sensors),
                Action(name="propose_observe", fn=_action_propose_observe),
            ],
        ),
    )


def build_avoid_overload() -> BehaviorTree:
    """Sequence: if load high, try reduce tick, pause nonessential, or propose rest."""
    return BehaviorTree(
        name="avoid_overload",
        root=Sequence(
            name="avoid_overload_seq",
            children=[
                Condition(name="load_high", predicate=_load_high),
                Selector(
                    name="overload_mitigation",
                    children=[
                        Action(name="reduce_tick", fn=_action_reduce_tick),
                        Action(name="pause_nonessential", fn=_action_pause_nonessential),
                        Action(name="propose_rest", fn=_action_propose_rest),
                    ],
                ),
            ],
        ),
    )


def build_prioritize_homeostatic_need() -> BehaviorTree:
    """Selector: if energy low propose conservation, else if social low propose dialogue."""
    return BehaviorTree(
        name="prioritize_homeostatic_need",
        root=Selector(
            name="homeostatic_selector",
            children=[
                Sequence(
                    name="energy_low_seq",
                    children=[
                        Condition(name="energy_low", predicate=_energy_low),
                        Action(name="propose_conservation", fn=_action_propose_conservation),
                    ],
                ),
                Sequence(
                    name="social_low_seq",
                    children=[
                        # social drive low inferred when not energy_low and organism_state != exploring
                        Condition(
                            name="not_exploring",
                            predicate=lambda ctx: ctx.get("organism_state") != "exploring",
                        ),
                        Action(name="propose_dialogue", fn=_action_propose_dialogue),
                    ],
                ),
            ],
        ),
    )


def build_search_grounding_input() -> BehaviorTree:
    """Sequence: if uncertainty high, scan sensors and query memory."""
    return BehaviorTree(
        name="search_grounding_input",
        root=Sequence(
            name="search_grounding_seq",
            children=[
                Condition(name="uncertainty_high", predicate=_uncertainty_high),
                Action(name="scan_sensors", fn=_action_scan_sensors),
                Action(name="query_memory", fn=_action_query_memory),
            ],
        ),
    )


DEFAULT_BT_LIBRARY = {
    "explore_local": build_explore_local,
    "avoid_overload": build_avoid_overload,
    "prioritize_homeostatic_need": build_prioritize_homeostatic_need,
    "search_grounding_input": build_search_grounding_input,
}
