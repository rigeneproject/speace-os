"""EvolutionarySkillOptimizer — T132: evolves cognitive skills via mutation + selection.

Pipeline:
1. Select parent skill (approved)
2. Mutate in sandbox
3. Run trials
4. Evaluate fitness
5. If fitness > baseline, create proposal (T133)
"""

import time
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.cognitive_evolution.cognitive_mutation_sandbox import (
    CognitiveMutationSandbox,
)
from speace_core.cellular_brain.cognitive_evolution.cognitive_homeostasis import (
    CognitiveHomeostasis,
)
from speace_core.cellular_brain.cognitive_evolution.cognitive_patch_proposal import (
    CognitivePatchProposalBuilder,
)
from speace_core.cellular_brain.cognitive_evolution.cognitive_skill_registry import (
    CognitiveSkillRegistry,
)
from speace_core.cellular_brain.cognitive_evolution.longitudinal_evolution_tracker import (
    LongitudinalEvolutionTracker,
)
from speace_core.cellular_brain.cognitive_evolution.skill_fitness_evaluator import (
    SkillFitnessEvaluator,
)


class EvolutionarySkillOptimizer:
    """Orchestrates the evolutionary loop for cognitive skills."""

    def __init__(
        self,
        registry: Optional[CognitiveSkillRegistry] = None,
        sandbox: Optional[CognitiveMutationSandbox] = None,
        fitness_evaluator: Optional[SkillFitnessEvaluator] = None,
        proposal_builder: Optional[CognitivePatchProposalBuilder] = None,
        tracker: Optional[LongitudinalEvolutionTracker] = None,
        homeostasis: Optional[CognitiveHomeostasis] = None,
    ) -> None:
        self._registry = registry or CognitiveSkillRegistry()
        self._sandbox = sandbox or CognitiveMutationSandbox()
        self._fitness = fitness_evaluator or SkillFitnessEvaluator()
        self._proposals = proposal_builder or CognitivePatchProposalBuilder()
        self._tracker = tracker or LongitudinalEvolutionTracker()
        self._homeostasis = homeostasis

    def evolve_skill(
        self,
        parent_skill_id: str,
        input_state: Dict[str, Any],
        mutation_rate: float = 0.2,
        requested_by: str = "",
        current_tick: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """Run one evolutionary cycle for a skill.

        Returns proposal info if a promising variant is found, else None.
        """
        # T137: homeostasis gate
        if self._homeostasis is not None:
            report = self._homeostasis.check(
                registry=self._registry,
                proposals=self._proposals,
                current_tick=current_tick,
                current_mutation_rate=mutation_rate,
            )
            if not report.can_mutate:
                return None

        parent = self._registry.get(parent_skill_id)
        if parent is None or not parent.approved:
            return None

        if self._homeostasis is not None:
            self._homeostasis.register_mutation(current_tick)

        # 1. Mutate
        mutated_params = self._sandbox.mutate_params(parent.params, mutation_rate=mutation_rate)
        mutated_template = self._sandbox.mutate_template(parent.template)

        variant = {
            "skill_id": parent.skill_id,
            "skill_type": parent.skill_type,
            "params": mutated_params,
            "template": mutated_template,
        }

        # 2. Validate
        if not self._sandbox.validate_mutation(variant):
            return None

        # 3. Run trials
        trials: List[Dict[str, Any]] = []
        for _ in range(self._fitness._trials):
            trial = self._sandbox.run_sandbox(variant, input_state)
            trials.append(trial)

        # 4. Evaluate fitness
        baseline = {"fitness": parent.fitness_score}
        fitness_result = self._fitness.evaluate(variant, trials, baseline=baseline)

        if not fitness_result.get("passed", False):
            return None

        # 5. Create proposal (T133)
        proposal = self._proposals.create(
            skill_id=parent.skill_id,
            skill_type=parent.skill_type,
            fitness=fitness_result,
            pre_snapshot=input_state,
            variant_params=mutated_params,
            variant_template=mutated_template,
            requested_by=requested_by,
            description=f"Evolved variant of {parent.name} with fitness {fitness_result['fitness']:.4f}",
        )

        if self._tracker is not None:
            self._tracker.record_event(
                parent.skill_id,
                "skill_mutated",
                {
                    "proposal_id": proposal.proposal_id,
                    "fitness": fitness_result.get("fitness"),
                    "mutation_rate": mutation_rate,
                },
            )
            self._tracker.record_event(
                parent.skill_id,
                "proposal_created",
                {"proposal_id": proposal.proposal_id, "requested_by": requested_by},
            )

        return {
            "proposal_id": proposal.proposal_id,
            "fitness": fitness_result,
            "parent_id": parent_skill_id,
            "status": "pending_approval",
        }

    def list_pending_proposals(self) -> List[Dict[str, Any]]:
        """List all pending cognitive patch proposals."""
        return [p.model_dump(mode="json") for p in self._proposals.list_proposals(status="pending")]
