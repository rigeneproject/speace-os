from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict


class StageEvaluation(BaseModel):
    current_stage: str
    next_stage: str
    transition_ready: bool
    blockers: List[str] = []

    model_config = ConfigDict(arbitrary_types_allowed=True)


class OntogeneticStageTracker:
    """Tracks ontogenetic developmental stages 0–7."""

    STAGES = [
        "stage_0",
        "stage_1",
        "stage_2",
        "stage_3",
        "stage_4",
        "stage_5",
        "stage_6",
        "stage_7",
    ]

    STAGE_NAMES = {
        "stage_0": "local_embryo",
        "stage_1": "stable_local_organism",
        "stage_2": "sandboxed_software_body",
        "stage_3": "first_safe_clone",
        "stage_4": "federated_cognitive_swarm",
        "stage_5": "authorized_cyber_physical_embodiment",
        "stage_6": "socio_technical_organism",
        "stage_7": "regulated_planetary_scale_organism",
    }

    TRANSITION_REQUIREMENTS: Dict[str, Dict[str, Any]] = {
        "stage_0": {
            "min_stability_score": 0.5,
            "min_ticks": 50,
            "capabilities": [],
        },
        "stage_1": {
            "min_stability_score": 0.7,
            "min_ticks": 100,
            "capabilities": ["semantic_memory"],
        },
        "stage_2": {
            "min_stability_score": 0.75,
            "min_ticks": 200,
            "capabilities": ["self_improvement"],
        },
        "stage_3": {
            "min_stability_score": 0.8,
            "min_ticks": 300,
            "capabilities": ["clone_safety"],
        },
        "stage_4": {
            "min_stability_score": 0.82,
            "min_ticks": 500,
            "capabilities": ["federated_communication"],
        },
        "stage_5": {
            "min_stability_score": 0.85,
            "min_ticks": 700,
            "capabilities": ["cyber_physical_interface"],
        },
        "stage_6": {
            "min_stability_score": 0.88,
            "min_ticks": 1000,
            "capabilities": ["social_integration"],
        },
    }

    def __init__(self, current_stage: str = "stage_0"):
        self.current_stage = current_stage

    def evaluate_stage_transition(
        self,
        metrics: Any,
        capabilities: List[str],
        clone_count: int,
    ) -> StageEvaluation:
        idx = self.STAGES.index(self.current_stage)
        if idx >= len(self.STAGES) - 1:
            return StageEvaluation(
                current_stage=self.current_stage,
                next_stage=self.current_stage,
                transition_ready=False,
                blockers=["max_stage_reached"],
            )

        next_stage = self.STAGES[idx + 1]
        reqs = self.TRANSITION_REQUIREMENTS.get(self.current_stage, {})
        blockers = []

        stability = getattr(metrics, "coherence_phi", 0.0) if hasattr(metrics, "coherence_phi") else metrics.get("coherence_phi", 0.0)
        ticks = getattr(metrics, "tick", 0) if hasattr(metrics, "tick") else metrics.get("tick", 0)

        if stability < reqs.get("min_stability_score", 0.0):
            blockers.append(f"stability_too_low: {stability:.3f} < {reqs['min_stability_score']}")
        if ticks < reqs.get("min_ticks", 0):
            blockers.append(f"insufficient_ticks: {ticks} < {reqs['min_ticks']}")
        for cap in reqs.get("capabilities", []):
            if cap not in capabilities:
                blockers.append(f"missing_capability: {cap}")

        if self.current_stage == "stage_3" and clone_count < 2:
            blockers.append("insufficient_clones")

        return StageEvaluation(
            current_stage=self.current_stage,
            next_stage=next_stage,
            transition_ready=len(blockers) == 0,
            blockers=blockers,
        )

    def advance_stage(self) -> None:
        idx = self.STAGES.index(self.current_stage)
        if idx < len(self.STAGES) - 1:
            self.current_stage = self.STAGES[idx + 1]
