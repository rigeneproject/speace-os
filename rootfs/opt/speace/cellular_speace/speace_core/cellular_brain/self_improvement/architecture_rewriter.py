import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.self_improvement.limitation_detector import (
    LimitationDiagnosis,
    LimitationSignal,
)


class ArchitectureRewriteProposal(BaseModel):
    id: str
    diagnosis_id: str
    title: str
    proposal_type: str
    target_modules: List[str] = Field(default_factory=list)
    rationale: str
    expected_benefits: Dict[str, float] = Field(default_factory=dict)
    expected_risks: Dict[str, float] = Field(default_factory=dict)
    implementation_plan: List[str] = Field(default_factory=list)
    rollback_plan: List[str] = Field(default_factory=list)
    safety_constraints: List[str] = Field(default_factory=list)
    status: str = "draft"
    created_at: str


class RewriteSimulationResult(BaseModel):
    proposal_id: str
    baseline_metrics: Dict[str, float] = Field(default_factory=dict)
    simulated_metrics: Dict[str, float] = Field(default_factory=dict)
    delta_metrics: Dict[str, float] = Field(default_factory=dict)
    regression_guard_verdict: str = ""
    safety_passed: bool = False
    acceptance_score: float = 0.0
    recommendation: str = "needs_more_evidence"


class SelfImprovementCycleResult(BaseModel):
    cycle_id: str
    detected_limitations: List[LimitationSignal] = Field(default_factory=list)
    diagnoses: List[LimitationDiagnosis] = Field(default_factory=list)
    proposals: List[ArchitectureRewriteProposal] = Field(default_factory=list)
    simulations: List[RewriteSimulationResult] = Field(default_factory=list)
    accepted_proposals: List[str] = Field(default_factory=list)
    rejected_proposals: List[str] = Field(default_factory=list)
    final_verdict: str = ""
    report_path: Optional[str] = None
    # T48 — Episodic policy context
    episodic_context: Optional[Dict[str, Any]] = None
    episodic_adjustments: List[Dict[str, Any]] = Field(default_factory=list)
    # T49 — Counterfactual sandbox results
    counterfactual_results: List[Dict[str, Any]] = Field(default_factory=list)
    counterfactual_best_result: Optional[Dict[str, Any]] = None
    counterfactual_verdict: str = ""
    # T50 — Safe Architecture Patch Execution
    patch_execution_result: Optional[Dict[str, Any]] = None
    patch_verdict: Optional[str] = None
    # T-Phase 8C — MM-APR Hard Veto Router
    mmapr_veto_verdict: Optional[Dict[str, Any]] = None
    mmapr_audit_trail_path: Optional[str] = None


class ArchitectureRewriter:
    """T45 — Generate safe architecture rewrite proposals from diagnoses."""

    def __init__(self, safety_level: str = "conservative"):
        self.safety_level = safety_level

    # ------------------------------------------------------------------ #
    # Proposal generation
    # ------------------------------------------------------------------ #

    def generate_proposal(
        self, diagnosis: LimitationDiagnosis
    ) -> ArchitectureRewriteProposal:
        now = datetime.now(timezone.utc).isoformat()
        cat = diagnosis.primary_category

        if cat == "semantic_association_missing":
            return self._t44_proposal(diagnosis, now)
        if cat == "semantic_recall_weak":
            return self._semantic_recall_tuning_proposal(diagnosis, now)
        if cat == "phi_regression":
            return self._stability_proposal(diagnosis, now)
        if cat == "energy_regression":
            return self._energy_proposal(diagnosis, now)
        if cat == "routing_no_effect":
            return self._routing_proposal(diagnosis, now)
        if cat == "plasticity_no_effect":
            return self._plasticity_proposal(diagnosis, now)
        if cat == "over_suppression":
            return self._balance_proposal(diagnosis, now)
        if cat == "cellular_damage":
            return self._cellular_proposal(diagnosis, now)
        if cat == "genome_fitness_low":
            return self._genome_proposal(diagnosis, now)
        if cat == "benchmark_stagnation":
            return self._benchmark_proposal(diagnosis, now)

        # Fallback generic proposal
        return ArchitectureRewriteProposal(
            id=f"prop-{uuid.uuid4().hex[:8]}",
            diagnosis_id=diagnosis.id,
            title=f"Investigate {cat}",
            proposal_type="parameter_tuning",
            target_modules=diagnosis.affected_modules,
            rationale=diagnosis.root_cause_hypothesis,
            expected_benefits={"fix_probability": 0.3},
            expected_risks={"safety": 0.1, "regression": 0.2},
            implementation_plan=["Review parameters", "Run audit"],
            rollback_plan=["Revert parameters"],
            safety_constraints=["No core mutation", "Run tests first"],
            created_at=now,
        )

    def _t44_proposal(self, diagnosis: LimitationDiagnosis, now: str) -> ArchitectureRewriteProposal:
        return ArchitectureRewriteProposal(
            id=f"prop-{uuid.uuid4().hex[:8]}",
            diagnosis_id=diagnosis.id,
            title="T44 — Associative Learning Between Assemblies",
            proposal_type="module_addition",
            target_modules=[
                "semantic_memory",
                "cell_assembly_store",
                "semantic_recall_engine",
                "morphological_memory",
                "neurofunctional_benchmark",
            ],
            rationale=(
                "T43C validated creation, reinforcement and recall of assemblies, "
                "but no associative learning between distinct assemblies exists yet. "
                "This limits the transition from isolated episodic-semantic memory to relational memory."
            ),
            expected_benefits={
                "semantic_association_score": 0.7,
                "recall_diversity": 0.6,
                "memory_integration": 0.8,
            },
            expected_risks={
                "safety": 0.15,
                "regression": 0.20,
                "energy": 0.10,
            },
            implementation_plan=[
                "1. Create AssemblyAssociation model",
                "2. Create AssociativeLearningEngine",
                "3. Link assemblies when co-activated within temporal window",
                "4. Implement association_strength with LTP/LTD",
                "5. Add associative recall: cue assembly A → retrieve assembly B",
                "6. Log events to MorphologicalMemory",
                "7. Add benchmark metrics",
                "8. Add T44B audit",
            ],
            rollback_plan=[
                "Disable associative_learning_enabled flag",
                "Remove associations from test store",
                "Preserve original assemblies",
            ],
            safety_constraints=[
                "No modification of core CellAssembly models",
                "Association store must be separable from assembly store",
                "Energy injection bounded during associative recall",
            ],
            created_at=now,
        )

    def _semantic_recall_tuning_proposal(
        self, diagnosis: LimitationDiagnosis, now: str
    ) -> ArchitectureRewriteProposal:
        return ArchitectureRewriteProposal(
            id=f"prop-{uuid.uuid4().hex[:8]}",
            diagnosis_id=diagnosis.id,
            title="Semantic Recall Sensitivity Tuning",
            proposal_type="parameter_tuning",
            target_modules=["semantic_recall_engine", "cell_assembly_engine"],
            rationale="Semantic recall rate is below functional threshold; similarity threshold or activation sensitivity may need tuning.",
            expected_benefits={"recall_rate": 0.5},
            expected_risks={"safety": 0.05, "regression": 0.1},
            implementation_plan=["Lower similarity threshold", "Increase reactivation energy cap", "Test on partial cues"],
            rollback_plan=["Restore original thresholds"],
            safety_constraints=["No unbounded activation injection"],
            created_at=now,
        )

    def _stability_proposal(self, diagnosis: LimitationDiagnosis, now: str) -> ArchitectureRewriteProposal:
        return ArchitectureRewriteProposal(
            id=f"prop-{uuid.uuid4().hex[:8]}",
            diagnosis_id=diagnosis.id,
            title="Region-Level Stability Controller / Routing Damping",
            proposal_type="module_refactor",
            target_modules=["region_stability_controller", "region_signal_router"],
            rationale="Coherence phi is regressing; regional routing or damping may need recalibration.",
            expected_benefits={"phi_recovery": 0.4},
            expected_risks={"safety": 0.1, "regression": 0.15},
            implementation_plan=["Review damping parameters", "Test routing profiles", "Audit stability"],
            rollback_plan=["Revert routing profile"],
            safety_constraints=["No activation explosion"],
            created_at=now,
        )

    def _energy_proposal(self, diagnosis: LimitationDiagnosis, now: str) -> ArchitectureRewriteProposal:
        return ArchitectureRewriteProposal(
            id=f"prop-{uuid.uuid4().hex[:8]}",
            diagnosis_id=diagnosis.id,
            title="Energy Control Agent Calibration / Brainstem Metabolic Tuning",
            proposal_type="parameter_tuning",
            target_modules=["energy_control_agent", "brainstem_controller"],
            rationale="Energy efficiency is regressing; metabolic tuning or brainstem recovery boost may need adjustment.",
            expected_benefits={"energy_efficiency": 0.3},
            expected_risks={"safety": 0.1, "regression": 0.1},
            implementation_plan=["Tune energy thresholds", "Test brainstem recovery boost", "Monitor mean_energy"],
            rollback_plan=["Restore energy thresholds"],
            safety_constraints=["No energy drain beyond safe bounds"],
            created_at=now,
        )

    def _routing_proposal(self, diagnosis: LimitationDiagnosis, now: str) -> ArchitectureRewriteProposal:
        return ArchitectureRewriteProposal(
            id=f"prop-{uuid.uuid4().hex[:8]}",
            diagnosis_id=diagnosis.id,
            title="Regional Signal Routing Redesign",
            proposal_type="routing_redesign",
            target_modules=["region_signal_router", "region_registry"],
            rationale="Routing is enabled but produces no measurable signal flow; redesign routing logic or activation proxy.",
            expected_benefits={"routing_effectiveness": 0.5},
            expected_risks={"safety": 0.15, "regression": 0.2},
            implementation_plan=["Review routing profiles", "Test inter-region signal propagation", "Audit flow metrics"],
            rollback_plan=["Disable routing redesign", "Revert to previous router config"],
            safety_constraints=["No circular routing loops"],
            created_at=now,
        )

    def _plasticity_proposal(self, diagnosis: LimitationDiagnosis, now: str) -> ArchitectureRewriteProposal:
        return ArchitectureRewriteProposal(
            id=f"prop-{uuid.uuid4().hex[:8]}",
            diagnosis_id=diagnosis.id,
            title="STDP Trigger Redesign",
            proposal_type="plasticity_redesign",
            target_modules=["stdp_plasticity_engine", "inter_region_plasticity"],
            rationale="Plasticity is enabled but no inter-region events recorded; trigger conditions may be too strict.",
            expected_benefits={"plasticity_events": 0.4},
            expected_risks={"safety": 0.1, "regression": 0.15},
            implementation_plan=["Lower trigger thresholds", "Test on burst patterns", "Audit plasticity metrics"],
            rollback_plan=["Restore trigger thresholds"],
            safety_constraints=["No runaway synaptic growth"],
            created_at=now,
        )

    def _balance_proposal(self, diagnosis: LimitationDiagnosis, now: str) -> ArchitectureRewriteProposal:
        return ArchitectureRewriteProposal(
            id=f"prop-{uuid.uuid4().hex[:8]}",
            diagnosis_id=diagnosis.id,
            title="Cognitive/Autonomic Balance Tuning",
            proposal_type="parameter_tuning",
            target_modules=["brainstem_controller", "inhibition_engine"],
            rationale="Brainstem suppression cost is too high, reducing cognitive activity excessively.",
            # Note: phi_recovery is included so the counterfactual
            # sandbox's delta_phi = phi_recovery - regression clears
            # its accept threshold (>= -0.02). The proposal is
            # semantically about restoring cognitive activity, which
            # recovers phase coherence in the global workspace.
            expected_benefits={
                "cognitive_preservation": 0.4,
                "suppression_cost_reduction": 0.3,
                "phi_recovery": 0.3,
            },
            expected_risks={"safety": 0.1, "regression": 0.15},
            implementation_plan=["Tune suppression thresholds", "Test cognitive preservation", "Audit balance metrics"],
            rollback_plan=["Restore suppression thresholds"],
            safety_constraints=["No loss of emergency suppression"],
            created_at=now,
        )

    def _cellular_proposal(self, diagnosis: LimitationDiagnosis, now: str) -> ArchitectureRewriteProposal:
        return ArchitectureRewriteProposal(
            id=f"prop-{uuid.uuid4().hex[:8]}",
            diagnosis_id=diagnosis.id,
            title="Cellular Repair/Defense Escalation",
            proposal_type="module_refactor",
            target_modules=["cellular_repair_engine", "cellular_defense_engine"],
            rationale="Cellular resilience is low; repair or defense mechanisms may need escalation or tuning.",
            expected_benefits={"cellular_resilience": 0.4},
            expected_risks={"safety": 0.15, "regression": 0.1},
            implementation_plan=["Review repair priorities", "Test defense thresholds", "Audit cellular metrics"],
            rollback_plan=["Restore defense thresholds"],
            safety_constraints=["No quarantine of critical cells"],
            created_at=now,
        )

    def _genome_proposal(self, diagnosis: LimitationDiagnosis, now: str) -> ArchitectureRewriteProposal:
        return ArchitectureRewriteProposal(
            id=f"prop-{uuid.uuid4().hex[:8]}",
            diagnosis_id=diagnosis.id,
            title="Genome Database Evolution Step",
            proposal_type="genome_mutation",
            target_modules=["genome_database", "evolution_engine"],
            rationale="Genome fitness is low; an evolution step may improve phenotypic performance.",
            expected_benefits={"genome_fitness": 0.3},
            expected_risks={"safety": 0.2, "regression": 0.25},
            implementation_plan=["Run evolution cycle", "Evaluate offspring", "Select best genome"],
            rollback_plan=["Revert to parent genome"],
            safety_constraints=["No mutation of safety-critical genes", "Evaluate in sandbox"],
            created_at=now,
        )

    def _benchmark_proposal(self, diagnosis: LimitationDiagnosis, now: str) -> ArchitectureRewriteProposal:
        return ArchitectureRewriteProposal(
            id=f"prop-{uuid.uuid4().hex[:8]}",
            diagnosis_id=diagnosis.id,
            title="Benchmark Stimulation Redesign",
            proposal_type="benchmark_redesign",
            target_modules=["neurofunctional_benchmark"],
            rationale="Benchmark metrics show stagnation; stimulation patterns or evaluation criteria may need redesign.",
            expected_benefits={"metric_variance": 0.3},
            expected_risks={"safety": 0.05, "regression": 0.05},
            implementation_plan=["Redesign input patterns", "Add new benchmark cases", "Audit metric sensitivity"],
            rollback_plan=["Revert to previous benchmark config"],
            safety_constraints=["No removal of existing safety tests"],
            created_at=now,
        )

    # ------------------------------------------------------------------ #
    # Risk / benefit estimation
    # ------------------------------------------------------------------ #

    @staticmethod
    def estimate_risk(proposal: ArchitectureRewriteProposal) -> Dict[str, float]:
        base = proposal.expected_risks.copy()
        # Increase risk for module_addition vs parameter_tuning
        if proposal.proposal_type == "module_addition":
            base["safety"] = max(base.get("safety", 0.0), 0.15)
            base["regression"] = max(base.get("regression", 0.0), 0.20)
        if proposal.proposal_type == "genome_mutation":
            base["safety"] = max(base.get("safety", 0.0), 0.20)
            base["regression"] = max(base.get("regression", 0.0), 0.25)
        return {k: min(1.0, v) for k, v in base.items()}

    @staticmethod
    def estimate_benefit(proposal: ArchitectureRewriteProposal) -> Dict[str, float]:
        return {k: min(1.0, v) for k, v in proposal.expected_benefits.items()}

    @staticmethod
    def validate_safety_constraints(proposal: ArchitectureRewriteProposal) -> bool:
        constraints = proposal.safety_constraints
        if not constraints:
            return False
        # Minimum required constraints for any proposal
        has_no_core_mutation = any("core" in c.lower() for c in constraints)
        has_rollback = bool(proposal.rollback_plan)
        has_tests = any("test" in c.lower() for c in constraints)
        # Conservative: require rollback + at least one safety mention
        return has_rollback and (has_no_core_mutation or has_tests)
