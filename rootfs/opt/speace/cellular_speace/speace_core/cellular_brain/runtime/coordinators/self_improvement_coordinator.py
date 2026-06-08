"""SelfImprovementCoordinator — T132/T133: continuous self-improvement scheduler.

Runs in the background (subsystem tick) and orchestrates:
- Periodic skill evolution via sandbox + fitness evaluation
- Structural audit and consolidation (pruning stale sandbox variants)
- Critical bug detection and emergency patch proposals

All mutations are sandboxed; only human-approved proposals are applied.
"""

import time
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.runtime.subsystem_plugin import SubsystemPlugin
from speace_core.cellular_brain.cognitive_evolution.cognitive_patch_proposal import (
    CognitivePatchProposalBuilder,
)
from speace_core.cellular_brain.cognitive_evolution.cognitive_skill_registry import (
    CognitiveSkillRegistry,
)
from speace_core.cellular_brain.cognitive_evolution.cognitive_mutation_sandbox import (
    CognitiveMutationSandbox,
)
from speace_core.cellular_brain.cognitive_evolution.evolutionary_skill_optimizer import (
    EvolutionarySkillOptimizer,
)
from speace_core.cellular_brain.cognitive_evolution.skill_fitness_evaluator import (
    SkillFitnessEvaluator,
)


class SelfImprovementCoordinator(SubsystemPlugin):
    """Coordinates continuous self-improvement engines."""

    @property
    def name(self) -> str:
        return "self_improvement"

    def __init__(self) -> None:
        self._registry = CognitiveSkillRegistry()
        self._sandbox = CognitiveMutationSandbox()
        self._fitness = SkillFitnessEvaluator()
        self._proposals = CognitivePatchProposalBuilder()
        self._optimizer = EvolutionarySkillOptimizer(
            registry=self._registry,
            sandbox=self._sandbox,
            fitness_evaluator=self._fitness,
            proposal_builder=self._proposals,
        )
        self._tick_counter = 0
        self._evolve_interval = 50
        self._audit_interval = 200
        self._bug_scan_interval = 100
        self._max_evolutions_per_cycle = 2
        self._sandbox_ttl_seconds = 3600  # 1 hour

    def on_tick(self, context: Any) -> Optional[Dict[str, Any]]:
        """Run self-improvement phases on configured intervals."""
        self._tick_counter += 1
        report: Dict[str, Any] = {}

        if self._tick_counter % self._evolve_interval == 0:
            report["evolution"] = self._evolve_skills_cycle(context)

        if self._tick_counter % self._audit_interval == 0:
            report["audit"] = self._structural_audit_cycle(context)

        if self._tick_counter % self._bug_scan_interval == 0:
            report["bug_scan"] = self._critical_bug_scan(context)

        return report if report else None

    # ------------------------------------------------------------------ #
    # Evolution cycle
    # ------------------------------------------------------------------ #

    def _evolve_skills_cycle(self, context: Any) -> Dict[str, Any]:
        orch = context.orchestrator_ref()
        current_tick = getattr(orch, "current_tick", 0)

        approved = self._registry.list_skills(approved_only=True)
        # Prioritize lower-fitness skills
        candidates = sorted(approved, key=lambda s: s.fitness_score)[: self._max_evolutions_per_cycle]

        results: List[Dict[str, Any]] = []
        for skill in candidates:
            input_state = self._capture_orchestrator_state(orch)
            result = self._optimizer.evolve_skill(
                parent_skill_id=skill.skill_id,
                input_state=input_state,
                mutation_rate=0.2,
                requested_by="SelfImprovementCoordinator",
                current_tick=current_tick,
            )
            if result:
                results.append(result)

        return {
            "candidates": len(candidates),
            "proposals_created": len(results),
            "proposals": results,
        }

    # ------------------------------------------------------------------ #
    # Structural audit & consolidation
    # ------------------------------------------------------------------ #

    def _structural_audit_cycle(self, context: Any) -> Dict[str, Any]:
        validated = 0
        errors = 0
        for skill in self._registry.list_skills():
            if skill.graph is not None:
                report = self._registry.validate_skill(skill.skill_id)
                validated += 1
                if not report.valid:
                    errors += 1

        # Prune stale sandbox variants
        now = time.time()
        pruned = 0
        stale_ids = []
        for skill in self._registry.list_skills():
            if (
                not skill.approved
                and skill.parent_id
                and (now - skill.created_at) > self._sandbox_ttl_seconds
            ):
                stale_ids.append(skill.skill_id)

        for sid in stale_ids:
            if sid in self._registry._skills:
                del self._registry._skills[sid]
                pruned += 1
        if pruned:
            self._registry._persist()

        return {
            "validated_skills": validated,
            "validation_errors": errors,
            "pruned_sandbox_skills": pruned,
        }

    # ------------------------------------------------------------------ #
    # Critical bug scan
    # ------------------------------------------------------------------ #

    def _critical_bug_scan(self, context: Any) -> Dict[str, Any]:
        orch = context.orchestrator_ref()
        critical = False
        details: List[str] = []

        # Check recent exceptions
        recent_exceptions = getattr(orch, "recent_exceptions", [])
        if recent_exceptions:
            critical = True
            details.append(f"Recent exceptions: {len(recent_exceptions)}")

        # Check health score
        health = getattr(orch, "_health_tracker", None)
        health_score = getattr(health, "health_score", 1.0) if health is not None else 1.0
        if health_score < 0.5:
            critical = True
            details.append(f"Low health score: {health_score:.2f}")

        proposal_id = None
        if critical:
            emergency_skills = self._registry.list_skills(
                skill_type="metacognitive", approved_only=True
            )
            if emergency_skills:
                parent = emergency_skills[0]
                input_state = self._capture_orchestrator_state(orch)
                result = self._optimizer.evolve_skill(
                    parent_skill_id=parent.skill_id,
                    input_state=input_state,
                    mutation_rate=0.1,
                    requested_by="SelfImprovementCoordinator_bug_scan",
                    current_tick=getattr(orch, "current_tick", 0),
                )
                if result:
                    proposal_id = result.get("proposal_id")

        return {
            "critical": critical,
            "details": details,
            "emergency_proposal_id": proposal_id,
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _capture_orchestrator_state(orch: Any) -> Dict[str, Any]:
        """Extract a safe snapshot of orchestrator state for sandbox trials."""
        state: Dict[str, Any] = {
            "tick": getattr(orch, "current_tick", 0),
            "timestamp": time.time(),
        }
        health = getattr(orch, "_health_tracker", None)
        if health is not None:
            state["health_score"] = getattr(health, "health_score", 0.0)
            state["total_exceptions"] = getattr(health, "total_exceptions", 0)
        if hasattr(orch, "coherence_phi"):
            state["coherence_phi"] = orch.coherence_phi
        if hasattr(orch, "chaos_index"):
            state["chaos_index"] = orch.chaos_index
        return state
