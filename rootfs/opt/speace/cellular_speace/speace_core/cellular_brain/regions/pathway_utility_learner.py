from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType


class PathwayUtilityRecord(BaseModel):
    """Historical utility tracking for a single inter-region pathway."""

    source_region_id: str
    target_region_id: str
    pathway_id: str

    utility_score: float = 0.0
    reward_ema: float = 0.0
    cost_ema: float = 0.0
    stability_ema: float = 0.0

    update_count: int = 0
    positive_updates: int = 0
    negative_updates: int = 0

    last_reward: float = 0.0
    last_cost: float = 0.0
    last_delta_phi: float = 0.0
    last_delta_cognitive_score: float = 0.0
    last_delta_energy: float = 0.0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class PathwayRewardSignal(BaseModel):
    """Reward signal computed from before/after metrics."""

    delta_cognitive_score: float = 0.0
    delta_phi: float = 0.0
    delta_energy_efficiency: float = 0.0
    delta_functional_improvement: float = 0.0
    routing_cost: float = 0.0
    plasticity_cost: float = 0.0

    composite_reward: float = 0.0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class PathwayUtilityLearningResult(BaseModel):
    """Result snapshot of a utility learning tick."""

    updated_pathways: int = 0
    rewarded_pathways: int = 0
    penalized_pathways: int = 0
    mean_utility_score: float = 0.0
    best_pathway_id: Optional[str] = None
    worst_pathway_id: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class PathwayUtilityLearner:
    """Learns pathway utility via reward-modulated plasticity.

    T30 transforms plasticity from safety-gated to value-gated:
    pathways that improve cognitive score, coherence, and energy efficiency
    receive positive reward and are strengthened; harmful pathways are weakened.
    """

    def __init__(self, alpha: float = 0.2, cost_penalty: float = 0.5):
        self.alpha = alpha
        self.cost_penalty = cost_penalty
        self._utilities: Dict[str, PathwayUtilityRecord] = {}

    # ------------------------------------------------------------------ #
    # Core reward computation
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_reward_signal(
        before_metrics: Dict[str, float],
        after_metrics: Dict[str, float],
        routing_cost: float = 0.0,
        plasticity_cost: float = 0.0,
    ) -> PathwayRewardSignal:
        """Compute composite reward from metric deltas and costs."""
        delta_cognitive = after_metrics.get("speace_cognitive_score", 0.0) - before_metrics.get("speace_cognitive_score", 0.0)
        delta_phi = after_metrics.get("coherence_phi", 0.0) - before_metrics.get("coherence_phi", 0.0)
        delta_energy = after_metrics.get("energy_efficiency", 0.0) - before_metrics.get("energy_efficiency", 0.0)
        delta_func = after_metrics.get("functional_improvement", 0.0) - before_metrics.get("functional_improvement", 0.0)

        composite = (
            0.35 * delta_cognitive
            + 0.30 * delta_phi
            + 0.15 * delta_func
            + 0.10 * delta_energy
            - 0.10 * routing_cost
            - 0.10 * plasticity_cost
        )
        composite = max(-1.0, min(1.0, composite))

        return PathwayRewardSignal(
            delta_cognitive_score=delta_cognitive,
            delta_phi=delta_phi,
            delta_energy_efficiency=delta_energy,
            delta_functional_improvement=delta_func,
            routing_cost=routing_cost,
            plasticity_cost=plasticity_cost,
            composite_reward=composite,
        )

    # ------------------------------------------------------------------ #
    # Utility update
    # ------------------------------------------------------------------ #

    def update_pathway_utility(
        self,
        pathway_id: str,
        source_region_id: str,
        target_region_id: str,
        reward_signal: PathwayRewardSignal,
        memory: Optional[MorphologicalMemory] = None,
    ) -> PathwayUtilityRecord:
        """Update EMAs and utility score for a pathway."""
        if pathway_id not in self._utilities:
            self._utilities[pathway_id] = PathwayUtilityRecord(
                pathway_id=pathway_id,
                source_region_id=source_region_id,
                target_region_id=target_region_id,
            )

        rec = self._utilities[pathway_id]
        rec.reward_ema = self.alpha * reward_signal.composite_reward + (1.0 - self.alpha) * rec.reward_ema
        rec.cost_ema = self.alpha * (reward_signal.routing_cost + reward_signal.plasticity_cost) + (1.0 - self.alpha) * rec.cost_ema
        rec.utility_score = rec.reward_ema - self.cost_penalty * rec.cost_ema

        rec.update_count += 1
        if reward_signal.composite_reward > 0:
            rec.positive_updates += 1
        else:
            rec.negative_updates += 1

        rec.last_reward = reward_signal.composite_reward
        rec.last_cost = reward_signal.routing_cost + reward_signal.plasticity_cost
        rec.last_delta_phi = reward_signal.delta_phi
        rec.last_delta_cognitive_score = reward_signal.delta_cognitive_score
        rec.last_delta_energy = reward_signal.delta_energy_efficiency

        if memory is not None:
            event_type = (
                MorphologyEventType.PATHWAY_UTILITY_POSITIVE
                if reward_signal.composite_reward > 0
                else MorphologyEventType.PATHWAY_UTILITY_NEGATIVE
            )
            memory.create_event(
                event_type=event_type,
                source_id=source_region_id,
                target_id=target_region_id,
                metadata={
                    "pathway_id": pathway_id,
                    "composite_reward": reward_signal.composite_reward,
                    "utility_score": rec.utility_score,
                    "reward_ema": rec.reward_ema,
                    "cost_ema": rec.cost_ema,
                    "update_count": rec.update_count,
                },
            )
            memory.create_event(
                event_type=MorphologyEventType.PATHWAY_REWARD_COMPUTED,
                source_id=source_region_id,
                target_id=target_region_id,
                metadata={
                    "pathway_id": pathway_id,
                    "delta_cognitive": reward_signal.delta_cognitive_score,
                    "delta_phi": reward_signal.delta_phi,
                    "delta_energy": reward_signal.delta_energy_efficiency,
                    "delta_functional": reward_signal.delta_functional_improvement,
                    "routing_cost": reward_signal.routing_cost,
                    "plasticity_cost": reward_signal.plasticity_cost,
                    "composite_reward": reward_signal.composite_reward,
                },
            )

        return rec

    # ------------------------------------------------------------------ #
    # Batch reward over all connections
    # ------------------------------------------------------------------ #

    def reward_all_pathways(
        self,
        registry,
        before_metrics: Dict[str, float],
        after_metrics: Dict[str, float],
        routing_cost: float = 0.0,
        plasticity_cost: float = 0.0,
        memory: Optional[MorphologicalMemory] = None,
    ) -> PathwayUtilityLearningResult:
        """Compute rewards for all inter-region pathways."""
        result = PathwayUtilityLearningResult()
        if registry is None or registry.connectome is None:
            return result

        reward_signal = self.compute_reward_signal(
            before_metrics, after_metrics, routing_cost, plasticity_cost
        )

        for conn in registry.connectome.connections:
            pathway_id = f"{conn.source_region_id}->{conn.target_region_id}"
            rec = self.update_pathway_utility(
                pathway_id=pathway_id,
                source_region_id=conn.source_region_id,
                target_region_id=conn.target_region_id,
                reward_signal=reward_signal,
                memory=memory,
            )
            result.updated_pathways += 1
            if reward_signal.composite_reward > 0:
                result.rewarded_pathways += 1
            else:
                result.penalized_pathways += 1

        if self._utilities:
            result.mean_utility_score = sum(
                u.utility_score for u in self._utilities.values()
            ) / len(self._utilities)
            best = max(self._utilities.values(), key=lambda u: u.utility_score)
            worst = min(self._utilities.values(), key=lambda u: u.utility_score)
            result.best_pathway_id = best.pathway_id
            result.worst_pathway_id = worst.pathway_id

        return result

    # ------------------------------------------------------------------ #
    # Utility gate for T29 tuner
    # ------------------------------------------------------------------ #

    def apply_utility_gate(
        self,
        pathway_id: str,
        candidate_update_type: str,
    ) -> tuple[bool, str]:
        """Return (should_proceed, reason) based on utility score.

        Rules:
        - utility_score < -0.05: block LTP, allow LTD/skip
        - utility_score > 0.05: allow LTP
        - neutral: proceed with light update
        """
        rec = self._utilities.get(pathway_id)
        if rec is None:
            return True, "no_utility_history"

        if rec.utility_score < -0.05:
            if candidate_update_type == "ltp":
                return False, "utility_negative_blocks_ltp"
            return True, "utility_negative_allows_ltd"

        if rec.utility_score > 0.05:
            return True, "utility_positive_allows_ltp"

        return True, "utility_neutral"

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get_utility_score(self, pathway_id: str) -> float:
        rec = self._utilities.get(pathway_id)
        return rec.utility_score if rec is not None else 0.0

    def summarize_utilities(self) -> Dict[str, Any]:
        if not self._utilities:
            return {"count": 0, "mean_utility": 0.0}
        values = [u.utility_score for u in self._utilities.values()]
        return {
            "count": len(values),
            "mean_utility": sum(values) / len(values),
            "max_utility": max(values),
            "min_utility": min(values),
            "positive_count": sum(1 for v in values if v > 0),
            "negative_count": sum(1 for v in values if v < 0),
        }

    def reset_utilities(self) -> None:
        self._utilities.clear()
