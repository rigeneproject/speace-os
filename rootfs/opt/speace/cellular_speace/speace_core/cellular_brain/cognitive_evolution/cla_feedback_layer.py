"""CognitiveLinguisticAlignmentFeedbackLayer — T144: read-only proposal generator.

Pipeline:
Dialogue turn
  → T143 coherence report
  → rileva disallineamento sotto soglia
  → genera proposta cognitiva/linguistica (T132/T133)
  → sandbox skill alternativa
  → fitness evaluation
  → crea proposal pending
  → richiede approvazione umana
  → apply/rollback

Nessuna modifica automatica della risposta.
"""

import copy
import time
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.cognitive_evolution.cognitive_homeostasis import (
    CognitiveHomeostasis,
)
from speace_core.cellular_brain.cognitive_evolution.cognitive_mutation_sandbox import (
    CognitiveMutationSandbox,
)
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
from speace_core.cellular_brain.cognitive_evolution.evolutionary_skill_optimizer import (
    EvolutionarySkillOptimizer,
)
from speace_core.cellular_brain.cognitive_evolution.skill_fitness_evaluator import (
    SkillFitnessEvaluator,
)
from speace_core.cellular_brain.metacognition.cognitive_linguistic_coherence_monitor import (
    CognitiveLinguisticCoherenceReport,
)


class CLAFeedbackLayer:
    """T144: read-only feedback layer from coherence misalignment to proposals.

    Configurable thresholds:
    - overall_coherence_score < 0.4  → critical
    - overall_coherence_score < 0.6  → warning
    """

    def __init__(
        self,
        registry: Optional[CognitiveSkillRegistry] = None,
        proposal_builder: Optional[CognitivePatchProposalBuilder] = None,
        self_modification: Optional[CognitiveSelfModificationProposal] = None,
        optimizer: Optional[EvolutionarySkillOptimizer] = None,
        warning_threshold: float = 0.6,
        critical_threshold: float = 0.4,
    ) -> None:
        self._registry = registry or CognitiveSkillRegistry()
        self._proposals = proposal_builder or CognitivePatchProposalBuilder()
        self._self_mod = self_modification or CognitiveSelfModificationProposal(
            registry=self._registry,
            proposal_builder=self._proposals,
        )
        self._optimizer = optimizer or EvolutionarySkillOptimizer(
            registry=self._registry,
            sandbox=CognitiveMutationSandbox(),
            fitness_evaluator=SkillFitnessEvaluator(),
            proposal_builder=self._proposals,
        )
        self._warning_threshold = warning_threshold
        self._critical_threshold = critical_threshold

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def process_coherence_report(
        self,
        report: CognitiveLinguisticCoherenceReport,
        current_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Process a T143 coherence report and generate proposals if needed.

        Returns a dict with:
        - status: 'ok' | 'warning' | 'critical'
        - proposals: list of generated proposals (if any)
        - diagnostics: what metrics triggered the proposal
        """
        overall = report.overall_coherence_score

        if overall >= self._warning_threshold:
            return {
                "status": "ok",
                "overall_coherence_score": overall,
                "proposals": [],
                "diagnostics": [],
            }

        status = "critical" if overall < self._critical_threshold else "warning"
        diagnostics = self._diagnose(report)

        proposals: List[Dict[str, Any]] = []
        for diag in diagnostics:
            proposal = self._generate_proposal(diag, report, current_state)
            if proposal:
                proposals.append(proposal)

        return {
            "status": status,
            "overall_coherence_score": overall,
            "proposals": proposals,
            "diagnostics": [d["type"] for d in diagnostics],
        }

    def get_pending_proposals(self) -> List[Dict[str, Any]]:
        """List all pending cognitive-linguistic alignment proposals."""
        return self._self_mod.list_pending()

    def approve_proposal(
        self,
        proposal_id: str,
        reviewer: str,
        current_health: float = 0.0,
    ) -> Dict[str, Any]:
        """Approve and apply a CLA proposal."""
        return self._self_mod.approve_and_apply(proposal_id, reviewer=reviewer, current_health=current_health)

    def reject_proposal(self, proposal_id: str, reviewer: str) -> Dict[str, Any]:
        """Reject a pending CLA proposal."""
        return self._self_mod.reject(proposal_id, reviewer=reviewer)

    def rollback_proposal(self, proposal_id: str, reviewer: str) -> Dict[str, Any]:
        """Rollback an applied CLA proposal."""
        return self._self_mod.rollback(proposal_id, reviewer=reviewer)

    def get_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """Get a single proposal by ID."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            return None
        return proposal.model_dump(mode="json")

    def list_all_proposals(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all CLA proposals, optionally filtered by status."""
        if status == "pending":
            return self._self_mod.list_pending()
        if status == "applied":
            return self._self_mod.list_applied()
        return [p.model_dump(mode="json") for p in self._proposals.list_proposals()]

    def audit_log(
        self,
        hours: float = 24.0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return recent audit events for CLA proposals."""
        if self._self_mod._tracker is not None:
            return self._self_mod._tracker.recent_events(
                hours=hours,
                event_types=[
                    "proposal_applied",
                    "proposal_rejected",
                    "proposal_rolled_back",
                    "fitness_evaluated",
                ],
                limit=limit,
            )
        return []

    def summary(self) -> Dict[str, Any]:
        """Summary of the feedback layer state."""
        return {
            "warning_threshold": self._warning_threshold,
            "critical_threshold": self._critical_threshold,
            "pending_proposals": len(self.get_pending_proposals()),
            "self_mod_summary": self._self_mod.summary(),
        }

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #

    @staticmethod
    def _diagnose(report: CognitiveLinguisticCoherenceReport) -> List[Dict[str, Any]]:
        """Identify which metrics are misaligned and what skill to evolve."""
        issues: List[Dict[str, Any]] = []

        # 1. Confidence-language mismatch
        if report.confidence_language_alignment < 0.4:
            issues.append({
                "type": "confidence_language_mismatch",
                "metric": "confidence_language_alignment",
                "value": report.confidence_language_alignment,
                "target_skill_type": "language",
                "description": "Epistemic confidence and linguistic certainty are misaligned",
            })

        # 2. Memory not referenced
        if report.memory_reference_consistency < 0.3:
            issues.append({
                "type": "memory_not_referenced",
                "metric": "memory_reference_consistency",
                "value": report.memory_reference_consistency,
                "target_skill_type": "language",
                "description": "Relational memory is not being referenced in dialogue",
            })

        # 3. Self-model absent
        if report.self_model_consistency < 0.4:
            issues.append({
                "type": "self_model_absent",
                "metric": "self_model_consistency",
                "value": report.self_model_consistency,
                "target_skill_type": "language",
                "description": "Self-model identity references are missing",
            })

        # 4. Grounding not expressed
        if report.grounding_consistency < 0.3:
            issues.append({
                "type": "grounding_not_expressed",
                "metric": "grounding_consistency",
                "value": report.grounding_consistency,
                "target_skill_type": "language",
                "description": "Grounded concepts are present internally but not in output",
            })

        # 5. Repetitive loop
        if report.repetitive_loop_density > 0.5:
            issues.append({
                "type": "repetitive_loop",
                "metric": "repetitive_loop_density",
                "value": report.repetitive_loop_density,
                "target_skill_type": "metacognitive",
                "description": "Dialogue is caught in a repetitive loop",
            })

        # 6. Contradictions
        if report.contradiction_rate > 0.3:
            issues.append({
                "type": "contradiction",
                "metric": "contradiction_rate",
                "value": report.contradiction_rate,
                "target_skill_type": "metacognitive",
                "description": "Contradictory statements detected in dialogue history",
            })

        # 7. Narrative incoherence
        if report.narrative_coherence < 0.3:
            issues.append({
                "type": "narrative_incoherence",
                "metric": "narrative_coherence",
                "value": report.narrative_coherence,
                "target_skill_type": "metacognitive",
                "description": "Dialogue topic is incoherent with narrative state",
            })

        return issues

    # ------------------------------------------------------------------ #
    # Proposal generation
    # ------------------------------------------------------------------ #

    def _generate_proposal(
        self,
        diag: Dict[str, Any],
        report: CognitiveLinguisticCoherenceReport,
        current_state: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Generate a single proposal for a diagnosed issue."""
        skill_type = diag["target_skill_type"]
        approved_skills = self._registry.list_skills(skill_type=skill_type, approved_only=True)
        if not approved_skills:
            return None

        # Pick the lowest-fitness approved skill as parent
        parent = min(approved_skills, key=lambda s: s.fitness_score)

        # Build a targeted mutation based on the diagnostic type
        mutation = self._build_mutation(diag)

        # Run sandbox evolution
        input_state = current_state or {
            "overall_coherence": report.overall_coherence_score,
            "metric_value": diag["value"],
        }
        result = self._optimizer.evolve_skill(
            parent_skill_id=parent.skill_id,
            input_state=input_state,
            mutation_rate=0.2,
            requested_by=f"T144_{diag['type']}",
            current_tick=0,
        )

        if result is None:
            return None

        # Submit to self-modification layer (pending approval)
        proposal_id = result.get("proposal_id")
        if proposal_id:
            self._self_mod.submit_proposal(proposal_id)

        return {
            "issue_type": diag["type"],
            "proposal_id": proposal_id,
            "parent_skill_id": parent.skill_id,
            "fitness": result.get("fitness"),
            "status": result.get("status"),
        }

    @staticmethod
    def _build_mutation(diag: Dict[str, Any]) -> Dict[str, Any]:
        """Build a targeted parameter mutation for the diagnosed issue."""
        issue_type = diag["type"]
        base_mutation: Dict[str, Any] = {"params": {}}

        if issue_type == "confidence_language_mismatch":
            base_mutation["params"] = {
                "language_fluency": 0.9,
                "context_depth": 5,
                "formality_level": 0.6,
                "success_bias": 0.85,
                "stability_boost": 0.1,
                "coherence_boost": 0.15,
                "confidence_boost": 0.1,
            }
        elif issue_type == "memory_not_referenced":
            base_mutation["params"] = {
                "turn_memory": 15,
                "prosody_adaptation": 0.4,
                "pause_threshold_ms": 200.0,
                "success_bias": 0.85,
                "stability_boost": 0.0,
                "coherence_boost": 0.2,
                "confidence_boost": 0.05,
            }
        elif issue_type == "self_model_absent":
            base_mutation["params"] = {
                "language_fluency": 0.8,
                "context_depth": 4,
                "formality_level": 0.5,
                "success_bias": 0.9,
                "stability_boost": 0.0,
                "coherence_boost": 0.1,
                "confidence_boost": 0.1,
            }
            base_mutation["template"] = (
                "Generate Italian responses with {language_fluency} fluency. "
                "Maintain context depth of {context_depth} turns. "
                "Adapt formality to interlocutor. "
                "Always include self-identification as SPEACE."
            )
        elif issue_type == "grounding_not_expressed":
            base_mutation["params"] = {
                "language_fluency": 0.85,
                "context_depth": 4,
                "formality_level": 0.5,
                "success_bias": 0.85,
                "stability_boost": 0.05,
                "coherence_boost": 0.2,
                "confidence_boost": 0.05,
            }
            base_mutation["template"] = (
                "Generate Italian responses with {language_fluency} fluency. "
                "Maintain context depth of {context_depth} turns. "
                "Adapt formality to interlocutor. "
                "Explicitly reference grounded concepts in every response."
            )
        elif issue_type == "repetitive_loop":
            base_mutation["params"] = {
                "meta_effectiveness": 0.8,
                "self_observation_rate": 0.7,
                "error_sensitivity": 0.8,
                "strategy_evaluation_window": 5,
                "success_bias": 0.8,
                "stability_boost": 0.15,
                "coherence_boost": 0.1,
                "confidence_boost": 0.1,
            }
            base_mutation["template"] = (
                "Observe workspace stability and narrative coherence. "
                "Detect repetitive loops, contradictions, and overfocus. "
                "Evaluate recent strategies over {strategy_evaluation_window} cycles. "
                "Flag repetitive dialogue patterns for variant exploration."
            )
        elif issue_type == "contradiction":
            base_mutation["params"] = {
                "meta_effectiveness": 0.9,
                "self_observation_rate": 0.8,
                "error_sensitivity": 0.9,
                "strategy_evaluation_window": 3,
                "success_bias": 0.8,
                "stability_boost": 0.2,
                "coherence_boost": 0.15,
                "confidence_boost": 0.15,
            }
            base_mutation["template"] = (
                "Observe workspace stability and narrative coherence. "
                "Detect repetitive loops, contradictions, and overfocus. "
                "Evaluate recent strategies over {strategy_evaluation_window} cycles. "
                "Prioritize contradiction detection and resolution."
            )
        elif issue_type == "narrative_incoherence":
            base_mutation["params"] = {
                "narrative_compression_ratio": 0.2,
                "temporal_span_hours": 48.0,
                "importance_threshold": 4,
                "success_bias": 0.8,
                "stability_boost": 0.05,
                "coherence_boost": 0.25,
                "confidence_boost": 0.05,
            }
            base_mutation["template"] = (
                "Synthesize events from the last {temporal_span_hours} hours. "
                "Compress by {narrative_compression_ratio} while preserving events "
                "with importance >= {importance_threshold}. "
                "Maintain causal and temporal coherence with dialogue topics."
            )

        return base_mutation
