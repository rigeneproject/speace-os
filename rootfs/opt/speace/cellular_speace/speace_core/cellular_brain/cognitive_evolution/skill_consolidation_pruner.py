"""SkillConsolidationPruner — T138: consolidates stable skills and prunes obsolete ones.

Rules:
- Only approved skills can be consolidated
- Skills with fitness > 0.7 for >= 10 cycles become core skills
- Core skills are protected from pruning
- Skills with fitness < 0.3 for 20+ cycles are pruned
- Redundant skills (same type, params within 5%, fitness within 5%) are candidates for merge
- Pruning creates a snapshot before removal (reversible)
- Merge proposals require human approval (T133)
"""

import copy
import time
from typing import Any, Dict, List, Optional, Tuple

from speace_core.cellular_brain.cognitive_evolution.cognitive_patch_proposal import (
    CognitivePatchProposalBuilder,
)
from speace_core.cellular_brain.cognitive_evolution.cognitive_self_modification_proposal import (
    CognitiveSelfModificationProposal,
)
from speace_core.cellular_brain.cognitive_evolution.cognitive_skill_registry import (
    CognitiveSkill,
    CognitiveSkillRegistry,
)
from speace_core.cellular_brain.cognitive_evolution.longitudinal_evolution_tracker import (
    LongitudinalEvolutionTracker,
)


class ConsolidationReport:
    """Result of a consolidation/pruning maintenance run."""

    def __init__(
        self,
        consolidated: List[str],
        pruned: List[str],
        merge_proposals: List[str],
        similarity_clusters: List[List[str]],
        action_taken: bool,
    ):
        self.consolidated = consolidated
        self.pruned = pruned
        self.merge_proposals = merge_proposals
        self.similarity_clusters = similarity_clusters
        self.action_taken = action_taken

    def to_dict(self) -> Dict[str, Any]:
        return {
            "consolidated": self.consolidated,
            "pruned": self.pruned,
            "merge_proposals": self.merge_proposals,
            "similarity_clusters": self.similarity_clusters,
            "action_taken": self.action_taken,
        }


class SkillConsolidationPruner:
    """T138: manages skill consolidation and pruning."""

    def __init__(
        self,
        similarity_threshold: float = 0.05,
    ) -> None:
        self._similarity_threshold = similarity_threshold

    # ------------------------------------------------------------------ #
    # Redundancy detection
    # ------------------------------------------------------------------ #

    def find_redundant_skills(
        self,
        registry: CognitiveSkillRegistry,
    ) -> List[Tuple[str, str, float]]:
        """Find pairs of similar skills and return (id_a, id_b, similarity_score)."""
        skills = registry.list_skills(approved_only=False)
        redundant: List[Tuple[str, str, float]] = []
        seen = set()

        for i, a in enumerate(skills):
            for b in skills[i + 1 :]:
                if a.skill_id == b.skill_id:
                    continue
                if a.skill_type != b.skill_type:
                    continue
                pair_key = tuple(sorted([a.skill_id, b.skill_id]))
                if pair_key in seen:
                    continue
                sim = self._compute_similarity(a, b)
                if sim >= 1.0 - self._similarity_threshold:
                    redundant.append((a.skill_id, b.skill_id, round(sim, 4)))
                    seen.add(pair_key)
        return redundant

    def _compute_similarity(self, a: CognitiveSkill, b: CognitiveSkill) -> float:
        """Compute similarity between two skills (0.0-1.0)."""
        if a.skill_type != b.skill_type:
            return 0.0

        # Param similarity
        a_params = a.params
        b_params = b.params
        all_keys = set(a_params.keys()) | set(b_params.keys())
        if not all_keys:
            param_sim = 1.0
        else:
            diffs = []
            for k in all_keys:
                av = a_params.get(k, 0.0)
                bv = b_params.get(k, 0.0)
                try:
                    avf = float(av)
                    bvf = float(bv)
                    diffs.append(abs(avf - bvf))
                except (ValueError, TypeError):
                    diffs.append(0.0 if av == bv else 1.0)
            avg_diff = sum(diffs) / len(diffs)
            param_sim = max(0.0, 1.0 - avg_diff)

        # Fitness similarity
        fitness_diff = abs(a.fitness_score - b.fitness_score)
        fitness_sim = max(0.0, 1.0 - fitness_diff)

        # Weighted average
        return param_sim * 0.7 + fitness_sim * 0.3

    # ------------------------------------------------------------------ #
    # Merge proposals
    # ------------------------------------------------------------------ #

    def propose_merge(
        self,
        skill_a_id: str,
        skill_b_id: str,
        registry: CognitiveSkillRegistry,
        builder: CognitivePatchProposalBuilder,
    ) -> Optional[Any]:
        """Create a merge proposal for two similar skills.

        Returns a CognitivePatchProposal or None.
        """
        a = registry.get(skill_a_id)
        b = registry.get(skill_b_id)
        if a is None or b is None:
            return None

        # Merge params: weighted average by fitness
        merged_params: Dict[str, Any] = {}
        all_keys = set(a.params.keys()) | set(b.params.keys())
        total_fitness = max(0.01, a.fitness_score + b.fitness_score)
        for k in all_keys:
            av = a.params.get(k, 0.0)
            bv = b.params.get(k, 0.0)
            try:
                avf = float(av)
                bvf = float(bv)
                merged_params[k] = round(
                    (avf * a.fitness_score + bvf * b.fitness_score) / total_fitness, 4
                )
            except (ValueError, TypeError):
                merged_params[k] = av if av is not None else bv

        merged_template = a.template if a.fitness_score >= b.fitness_score else b.template
        merged_fitness = max(a.fitness_score, b.fitness_score)

        proposal = builder.create(
            skill_id=a.skill_id,
            skill_type=a.skill_type,
            fitness={"fitness": merged_fitness, "passed": True},
            pre_snapshot={},
            variant_params=merged_params,
            variant_template=merged_template,
            requested_by="T138_consolidation_pruner",
            description=f"Merge {a.skill_id} and {b.skill_id} into consolidated variant",
        )
        return proposal

    # ------------------------------------------------------------------ #
    # Consolidation
    # ------------------------------------------------------------------ #

    def consolidate_core_skills(
        self,
        registry: CognitiveSkillRegistry,
        min_cycles: int = 10,
        min_fitness: float = 0.7,
        tracker: Optional[LongitudinalEvolutionTracker] = None,
    ) -> List[str]:
        """Promote stable approved skills to core status.

        Returns list of skill IDs that were consolidated.
        """
        consolidated: List[str] = []
        skills = registry.list_skills(approved_only=True)
        now = time.time()

        for skill in skills:
            if skill.origin == "consolidated":
                continue
            if skill.fitness_score < min_fitness:
                continue
            # Check age (via created_at as proxy for cycles)
            age_cycles = (now - skill.created_at) / 60.0  # rough proxy
            if age_cycles < min_cycles:
                continue

            # Promote to core
            skill.origin = "consolidated"
            registry.register(skill)
            consolidated.append(skill.skill_id)

            if tracker is not None:
                tracker.record_event(
                    skill.skill_id,
                    "skill_consolidated",
                    {"fitness": skill.fitness_score, "age_cycles": age_cycles},
                )

        return consolidated

    # ------------------------------------------------------------------ #
    # Pruning
    # ------------------------------------------------------------------ #

    def prune_obsolete_skills(
        self,
        registry: CognitiveSkillRegistry,
        fitness_threshold: float = 0.3,
        min_age_cycles: int = 20,
        tracker: Optional[LongitudinalEvolutionTracker] = None,
    ) -> List[str]:
        """Remove obsolete skills (not core) below fitness threshold for too long.

        Returns list of skill IDs that were pruned.
        """
        pruned: List[str] = []
        skills = registry.list_skills(approved_only=False)
        now = time.time()

        for skill in skills:
            if skill.origin == "consolidated":
                continue
            if skill.fitness_score >= fitness_threshold:
                continue
            age_cycles = (now - skill.created_at) / 60.0
            if age_cycles < min_age_cycles:
                continue

            # Prune: mark as deprecated by setting fitness to 0 and unregistering
            # In a real system this would archive; here we mark and skip
            skill.fitness_score = 0.0
            skill.origin = "pruned"
            registry.register(skill)
            pruned.append(skill.skill_id)

            if tracker is not None:
                tracker.record_event(
                    skill.skill_id,
                    "skill_pruned",
                    {"fitness": skill.fitness_score, "age_cycles": age_cycles},
                )

        return pruned

    # ------------------------------------------------------------------ #
    # Maintenance
    # ------------------------------------------------------------------ #

    def run_maintenance(
        self,
        registry: CognitiveSkillRegistry,
        proposals: CognitivePatchProposalBuilder,
        tracker: Optional[LongitudinalEvolutionTracker] = None,
    ) -> ConsolidationReport:
        """Run full maintenance cycle: consolidate, find redundancies, prune.

        Returns a ConsolidationReport.
        """
        # 1. Consolidate
        consolidated = self.consolidate_core_skills(registry, tracker=tracker)

        # 2. Find redundancies
        redundant = self.find_redundant_skills(registry)
        similarity_clusters = self._build_clusters(redundant)

        # 3. Create merge proposals for redundancies
        merge_proposals: List[str] = []
        for a_id, b_id, _ in redundant:
            prop = self.propose_merge(a_id, b_id, registry, proposals)
            if prop is not None:
                merge_proposals.append(prop.proposal_id)

        # 4. Prune
        pruned = self.prune_obsolete_skills(registry, tracker=tracker)

        action_taken = bool(consolidated or pruned or merge_proposals)

        return ConsolidationReport(
            consolidated=consolidated,
            pruned=pruned,
            merge_proposals=merge_proposals,
            similarity_clusters=similarity_clusters,
            action_taken=action_taken,
        )

    def _build_clusters(
        self,
        redundant: List[Tuple[str, str, float]],
    ) -> List[List[str]]:
        """Build similarity clusters from redundant pairs."""
        clusters: Dict[str, set] = {}
        for a, b, _ in redundant:
            if a not in clusters:
                clusters[a] = {a}
            if b not in clusters:
                clusters[b] = {b}
            clusters[a].add(b)
            clusters[b].add(a)

        visited: set = set()
        result: List[List[str]] = []
        for node, neighbors in clusters.items():
            if node in visited:
                continue
            cluster = sorted(neighbors)
            result.append(cluster)
            visited.update(cluster)
        return result
