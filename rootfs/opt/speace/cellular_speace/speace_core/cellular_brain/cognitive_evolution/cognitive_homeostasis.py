"""CognitiveHomeostasis — T137: enforces cognitive stability limits.

Prevents over-evolution by constraining:
- number of active skills
- mutation rate per cycle
- pending proposals
- node divergence
- narrative density
- cooldown between mutations

Governance principle: limits are rigid, not modifiable at runtime by the orchestrator.
"""

import time
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.cognitive_evolution.cognitive_patch_proposal import (
    CognitivePatchProposalBuilder,
)
from speace_core.cellular_brain.cognitive_evolution.cognitive_skill_registry import (
    CognitiveSkillRegistry,
)
from speace_core.cellular_brain.cognitive_evolution.longitudinal_evolution_tracker import (
    LongitudinalEvolutionTracker,
)


class HomeostasisReport:
    """Result of a homeostasis check."""

    def __init__(
        self,
        overall_pressure: float,
        pressure_by_limit: Dict[str, float],
        can_mutate: bool,
        can_create_proposal: bool,
        should_consolidate: bool,
        should_prune: bool,
        recommended_action: str,
    ):
        self.overall_pressure = overall_pressure
        self.pressure_by_limit = pressure_by_limit
        self.can_mutate = can_mutate
        self.can_create_proposal = can_create_proposal
        self.should_consolidate = should_consolidate
        self.should_prune = should_prune
        self.recommended_action = recommended_action

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_pressure": round(self.overall_pressure, 4),
            "pressure_by_limit": self.pressure_by_limit,
            "can_mutate": self.can_mutate,
            "can_create_proposal": self.can_create_proposal,
            "should_consolidate": self.should_consolidate,
            "should_prune": self.should_prune,
            "recommended_action": self.recommended_action,
        }


class CognitiveHomeostasis:
    """T137: cognitive homeostasis regulator."""

    def __init__(
        self,
        max_active_skills: int = 20,
        max_mutation_rate_per_cycle: float = 0.1,
        max_pending_proposals: int = 5,
        max_node_divergence: float = 0.3,
        max_narrative_density: float = 0.8,
        min_cycles_between_mutations: int = 10,
    ) -> None:
        self._limits = {
            "max_active_skills": max_active_skills,
            "max_mutation_rate_per_cycle": max_mutation_rate_per_cycle,
            "max_pending_proposals": max_pending_proposals,
            "max_node_divergence": max_node_divergence,
            "max_narrative_density": max_narrative_density,
            "min_cycles_between_mutations": min_cycles_between_mutations,
        }
        self._last_mutation_tick: Optional[int] = None

    # ------------------------------------------------------------------ #
    # Core check
    # ------------------------------------------------------------------ #

    def check(
        self,
        registry: CognitiveSkillRegistry,
        proposals: CognitivePatchProposalBuilder,
        current_tick: int,
        current_mutation_rate: float = 0.0,
        narrative_density: float = 0.0,
        node_divergence: float = 0.0,
    ) -> HomeostasisReport:
        """Run all homeostatic checks and return a report."""
        pressure: Dict[str, float] = {}

        # 1. Active skills pressure
        total_skills = len(registry.list_skills(approved_only=False))
        active_pressure = min(1.0, total_skills / self._limits["max_active_skills"])
        pressure["active_skills"] = active_pressure

        # 2. Mutation rate pressure
        mutation_pressure = (
            current_mutation_rate / self._limits["max_mutation_rate_per_cycle"]
            if self._limits["max_mutation_rate_per_cycle"] > 0
            else 0.0
        )
        pressure["mutation_rate"] = min(1.0, mutation_pressure)

        # 3. Pending proposals pressure
        pending_count = len(proposals.list_proposals(status="pending"))
        proposal_pressure = min(
            1.0,
            pending_count / self._limits["max_pending_proposals"],
        ) if self._limits["max_pending_proposals"] > 0 else 0.0
        pressure["pending_proposals"] = proposal_pressure

        # 4. Node divergence pressure
        divergence_pressure = min(
            1.0,
            node_divergence / self._limits["max_node_divergence"],
        ) if self._limits["max_node_divergence"] > 0 else 0.0
        pressure["node_divergence"] = divergence_pressure

        # 5. Narrative density pressure
        narrative_pressure = min(
            1.0,
            narrative_density / self._limits["max_narrative_density"],
        ) if self._limits["max_narrative_density"] > 0 else 0.0
        pressure["narrative_density"] = narrative_pressure

        # 6. Cooldown pressure
        cooldown_ok = self._cooldown_ok(current_tick)
        pressure["cooldown"] = 0.0 if cooldown_ok else 1.0

        # Overall pressure = max of all pressures
        overall_pressure = max(pressure.values()) if pressure else 0.0

        # Decision logic (use raw counts, not clamped pressure)
        can_mutate = (
            total_skills < self._limits["max_active_skills"]
            and current_mutation_rate <= self._limits["max_mutation_rate_per_cycle"]
            and pending_count < self._limits["max_pending_proposals"]
            and cooldown_ok
        )
        can_create_proposal = (
            total_skills < self._limits["max_active_skills"]
            and pending_count < self._limits["max_pending_proposals"]
            and cooldown_ok
        )
        should_consolidate = active_pressure >= 0.8 or overall_pressure >= 0.7
        should_prune = active_pressure >= 0.9 or overall_pressure >= 0.8

        # Recommended action
        if not can_mutate:
            recommended_action = "halt_mutations"
        elif should_prune:
            recommended_action = "prune"
        elif should_consolidate:
            recommended_action = "consolidate"
        elif overall_pressure >= 0.5:
            recommended_action = "reduce_plasticity"
        else:
            recommended_action = "maintain"

        return HomeostasisReport(
            overall_pressure=overall_pressure,
            pressure_by_limit=pressure,
            can_mutate=can_mutate,
            can_create_proposal=can_create_proposal,
            should_consolidate=should_consolidate,
            should_prune=should_prune,
            recommended_action=recommended_action,
        )

    # ------------------------------------------------------------------ #
    # Mutation tracking
    # ------------------------------------------------------------------ #

    def register_mutation(self, tick: int) -> None:
        """Record that a mutation occurred at the given tick."""
        self._last_mutation_tick = tick

    def _cooldown_ok(self, current_tick: int) -> bool:
        if self._last_mutation_tick is None:
            return True
        elapsed = current_tick - self._last_mutation_tick
        return elapsed >= self._limits["min_cycles_between_mutations"]

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def get_pressure_report(self) -> Dict[str, Any]:
        """Return current limit configuration and last known pressures."""
        return {
            "limits": self._limits,
            "last_mutation_tick": self._last_mutation_tick,
        }

    def apply_pressure_relief(
        self,
        registry: CognitiveSkillRegistry,
        proposals: CognitivePatchProposalBuilder,
    ) -> Dict[str, Any]:
        """If pressure is too high, suggest or enforce relief actions.

        This is a read-only diagnostic; actual relief is delegated to T138.
        """
        pending = proposals.list_proposals(status="pending")
        total_skills = len(registry.list_skills(approved_only=False))

        actions: List[str] = []
        if total_skills > self._limits["max_active_skills"] * 0.9:
            actions.append("consider_pruning_low_fitness_skills")
        if len(pending) > self._limits["max_pending_proposals"] * 0.9:
            actions.append("review_pending_proposals")

        return {
            "actions": actions,
            "total_skills": total_skills,
            "pending_proposals": len(pending),
            "limits": self._limits,
        }
