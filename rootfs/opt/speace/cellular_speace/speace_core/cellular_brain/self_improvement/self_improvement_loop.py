import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.memory.morphology_events import (
    MorphologyEvent,
    MorphologyEventType,
)
from speace_core.cellular_brain.self_improvement.architecture_rewriter import (
    ArchitectureRewriteProposal,
    ArchitectureRewriter,
    RewriteSimulationResult,
    SelfImprovementCycleResult,
)
from speace_core.cellular_brain.self_improvement.limitation_detector import (
    LimitationDetector,
    LimitationDiagnosis,
    LimitationSignal,
)
from speace_core.cellular_brain.self_improvement.proposal_store import ProposalStore
from speace_core.cellular_brain.self_improvement.outcome_tracker import (
    OutcomeTracker,
    ProposalOutcome,
)
from speace_core.cellular_brain.self_improvement.proposal_learning_engine import (
    ProposalLearningEngine,
    ProposalLearningRecord,
)
from speace_core.cellular_brain.self_improvement.self_improvement_memory import (
    SelfImprovementMemory,
)
from speace_core.cellular_brain.self_improvement.episodic_policy import (
    EpisodicSelfImprovementPolicy,
    EpisodicPolicyContext,
    EpisodicProposalAdjustment,
)
from speace_core.cellular_brain.self_improvement.counterfactual_sandbox import (
    CounterfactualArchitectureSandbox,
    CounterfactualResult,
    CounterfactualBatchResult,
)
from speace_core.cellular_brain.self_improvement.architecture_patch_executor import (
    ArchitecturePatchExecutor,
    PatchExecutionResult,
)


class SelfImprovementLoop:
    """T45 — Autonomous Limitation Detection & Architecture Rewriting Loop."""

    def __init__(
        self,
        orchestrator=None,
        detector=None,
        rewriter=None,
        proposal_store=None,
        regression_guard=None,
        benchmark=None,
        memory=None,
        outcome_tracker=None,
        proposal_learning_engine=None,
        self_improvement_memory=None,
        episodic_policy_enabled: bool = False,
        episodic_policy=None,
        counterfactual_sandbox_enabled: bool = False,
        counterfactual_sandbox=None,
        architecture_patch_execution_enabled: bool = False,
        architecture_patch_executor=None,
        mmapr_router=None,
    ):
        self.orchestrator = orchestrator
        self.detector = detector or LimitationDetector()
        self.rewriter = rewriter or ArchitectureRewriter(safety_level="conservative")
        self.proposal_store = proposal_store or ProposalStore()
        self.regression_guard = regression_guard
        self.benchmark = benchmark
        self.memory = memory
        self.outcome_tracker = outcome_tracker or OutcomeTracker(memory=memory)
        self.proposal_learning_engine = proposal_learning_engine or ProposalLearningEngine(memory=memory)
        self.self_improvement_memory = self_improvement_memory or SelfImprovementMemory(memory=memory)
        self.episodic_policy_enabled = episodic_policy_enabled
        self.episodic_policy = episodic_policy
        self.counterfactual_sandbox_enabled = counterfactual_sandbox_enabled
        self.counterfactual_sandbox = counterfactual_sandbox
        self.architecture_patch_execution_enabled = architecture_patch_execution_enabled
        self.architecture_patch_executor = architecture_patch_executor
        # T-Phase 8C — MM-APR Hard Veto Router (opt-in)
        self.mmapr_router = mmapr_router

    # ------------------------------------------------------------------ #
    # Detection cycle
    # ------------------------------------------------------------------ #

    def run_detection_cycle(
        self, metrics: Dict[str, Any]
    ) -> SelfImprovementCycleResult:
        now = datetime.now(timezone.utc).isoformat()
        cycle_id = f"cycle-{uuid.uuid4().hex[:8]}"

        # 1. Detect limitations
        signals = self.detector.detect_from_metrics(metrics)
        self._log_event(MorphologyEventType.LIMITATION_DETECTED, {
            "cycle_id": cycle_id,
            "signals_count": len(signals),
        })

        # 2. Aggregate into diagnoses
        diagnoses = self.detector.aggregate_signals(signals)
        for diag in diagnoses:
            self._log_event(MorphologyEventType.LIMITATION_DIAGNOSED, {
                "cycle_id": cycle_id,
                "diagnosis_id": diag.id,
                "category": diag.primary_category,
                "urgency_score": diag.urgency_score,
            })

        # 3. Generate proposals
        proposals: List[ArchitectureRewriteProposal] = []
        for diag in diagnoses:
            proposal = self.rewriter.generate_proposal(diag)
            proposals.append(proposal)
            self._log_event(MorphologyEventType.ARCHITECTURE_PROPOSAL_CREATED, {
                "cycle_id": cycle_id,
                "proposal_id": proposal.id,
                "diagnosis_id": diag.id,
                "title": proposal.title,
            })
            self.proposal_store.save_proposal(proposal)

        # T48 — Apply episodic policy to adjust proposal ranking
        episodic_context = None
        episodic_adjustments = []
        if self.episodic_policy_enabled and self.episodic_policy is not None and proposals:
            limitation_type = diagnoses[0].primary_category if diagnoses else "unknown"
            episodic_context = self.episodic_policy.build_context(limitation_type, metrics)
            episodic_adjustments = self.episodic_policy.adjust_proposals(proposals, episodic_context)
            adj_map = {a.proposal_id: a.adjusted_confidence for a in episodic_adjustments}
            proposals.sort(key=lambda p: adj_map.get(p.id, 0.0), reverse=True)

        # T49 — Counterfactual sandbox evaluation
        counterfactual_results: List[CounterfactualResult] = []
        counterfactual_best = None
        counterfactual_verdict = ""
        if self.counterfactual_sandbox_enabled and self.counterfactual_sandbox is not None and proposals:
            limitation_type = diagnoses[0].primary_category if diagnoses else "unknown"
            for proposal in proposals:
                cf_result = self.counterfactual_sandbox.run_scenario(proposal, limitation_type)
                counterfactual_results.append(cf_result)
            best = self.counterfactual_sandbox.select_best_safe_result(counterfactual_results)
            counterfactual_best = best
            if best is not None:
                counterfactual_verdict = best.verdict

        # T50 — Safe Architecture Patch Execution
        patch_execution_result: Optional[PatchExecutionResult] = None
        patch_verdict = ""
        if (
            self.architecture_patch_execution_enabled
            and self.architecture_patch_executor is not None
            and counterfactual_best is not None
        ):
            # counterfactual_best may be a Pydantic model (CounterfactualResult)
            # or a plain dict (depending on caller). Use a defensive getter.
            best_proposal_id = getattr(
                counterfactual_best, "proposal_id",
                counterfactual_best.get("proposal_id") if isinstance(counterfactual_best, dict) else None,
            )
            target_proposal = None
            for p in proposals:
                if p.id == best_proposal_id:
                    target_proposal = p
                    break
            if target_proposal is not None:
                patch_execution_result = self.architecture_patch_executor.execute_patch(target_proposal)
                patch_verdict = patch_execution_result.verdict

        # 4. Simulate proposals
        simulations: List[RewriteSimulationResult] = []
        accepted: List[str] = []
        rejected: List[str] = []
        for proposal in proposals:
            sim = self.simulate_proposal(proposal)
            simulations.append(sim)
            self._log_event(MorphologyEventType.ARCHITECTURE_PROPOSAL_SIMULATED, {
                "cycle_id": cycle_id,
                "proposal_id": proposal.id,
                "acceptance_score": sim.acceptance_score,
                "safety_passed": sim.safety_passed,
            })

            verdict = self.accept_or_reject(sim)
            if verdict == "accept":
                accepted.append(proposal.id)
                proposal.status = "accepted"
                self._log_event(MorphologyEventType.ARCHITECTURE_PROPOSAL_ACCEPTED, {
                    "cycle_id": cycle_id,
                    "proposal_id": proposal.id,
                    "acceptance_score": sim.acceptance_score,
                })
            elif verdict == "reject":
                rejected.append(proposal.id)
                proposal.status = "rejected"
                self._log_event(MorphologyEventType.ARCHITECTURE_PROPOSAL_REJECTED, {
                    "cycle_id": cycle_id,
                    "proposal_id": proposal.id,
                    "acceptance_score": sim.acceptance_score,
                })
            else:
                proposal.status = "simulated"

        # 5. Determine final verdict
        if not signals:
            final_verdict = "NO_LIMITATION_DETECTED"
        elif not proposals:
            final_verdict = "LIMITATION_DETECTED_NO_SAFE_PATCH"
        elif accepted:
            final_verdict = "PROPOSAL_ACCEPTED_FOR_NEXT_TASK"
        elif rejected and not accepted:
            final_verdict = "REGRESSION_BLOCKED"
        else:
            final_verdict = "SAFE_PROPOSAL_GENERATED"

        # 5b. T-Phase 8C — MM-APR Hard Veto Router hook point
        mmapr_veto_dict: Optional[Dict[str, Any]] = None
        mmapr_audit_path: Optional[str] = None
        if self.mmapr_router is not None and proposals:
            try:
                mmapr_veto_dict, mmapr_audit_path = self._apply_mmapr_veto(
                    proposals=proposals,
                    simulations=simulations,
                    counterfactual_best=counterfactual_best,
                    patch_execution_result=patch_execution_result,
                    cycle_id=cycle_id,
                    final_verdict=final_verdict,
                )
                if mmapr_veto_dict is not None:
                    self._log_event(
                        MorphologyEventType.MMAPR_VETO_GATE_TRIGGERED,
                        {
                            "cycle_id": cycle_id,
                            "final_status": mmapr_veto_dict.get("final_status"),
                            "hard_blocked_by": mmapr_veto_dict.get("hard_blocked_by", []),
                            "soft_flagged_by": mmapr_veto_dict.get("soft_flagged_by", []),
                        },
                    )
                    if mmapr_veto_dict.get("final_status") == "hard_blocked":
                        # Hard veto: downgrade to LIMITATION_DETECTED_NO_SAFE_PATCH
                        # and move all accepted to rejected. This is the
                        # conservative, non-breaking path agreed in the
                        # MM-APR Phase 8C plan (no new verdict value).
                        final_verdict = "LIMITATION_DETECTED_NO_SAFE_PATCH"
                        rejected.extend(accepted)
                        accepted.clear()
                        self._log_event(
                            MorphologyEventType.MMAPR_VETO_HARD_BLOCKED,
                            {
                                "cycle_id": cycle_id,
                                "hard_blocked_by": mmapr_veto_dict.get("hard_blocked_by", []),
                            },
                        )
                    elif mmapr_veto_dict.get("final_status") == "soft_flagged":
                        self._log_event(
                            MorphologyEventType.MMAPR_VETO_SOFT_FLAGGED,
                            {
                                "cycle_id": cycle_id,
                                "flaggers": mmapr_veto_dict.get("soft_flagged_by", []),
                            },
                        )
            except Exception as exc:  # pragma: no cover - defensive
                logging.getLogger(__name__).warning(
                    "MMAPR veto step failed: %s", exc, exc_info=True
                )
                mmapr_veto_dict = None
                mmapr_audit_path = None

        result = SelfImprovementCycleResult(
            cycle_id=cycle_id,
            detected_limitations=signals,
            diagnoses=diagnoses,
            proposals=proposals,
            simulations=simulations,
            accepted_proposals=accepted,
            rejected_proposals=rejected,
            final_verdict=final_verdict,
            episodic_context=episodic_context.model_dump() if episodic_context is not None else None,
            episodic_adjustments=[a.model_dump() for a in episodic_adjustments],
            counterfactual_results=[r.model_dump() for r in counterfactual_results],
            counterfactual_best_result=counterfactual_best.model_dump() if counterfactual_best is not None else None,
            counterfactual_verdict=counterfactual_verdict,
            patch_execution_result=patch_execution_result.model_dump() if patch_execution_result is not None else None,
            patch_verdict=patch_verdict if patch_verdict else None,
            mmapr_veto_verdict=mmapr_veto_dict,
            mmapr_audit_trail_path=mmapr_audit_path,
        )

        self.proposal_store.save_cycle_result(result)
        self._log_event(MorphologyEventType.SELF_IMPROVEMENT_CYCLE_COMPLETED, {
            "cycle_id": cycle_id,
            "final_verdict": final_verdict,
            "proposals_count": len(proposals),
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
        })
        return result

    def run_from_audit_report(
        self, report: Dict[str, Any]
    ) -> SelfImprovementCycleResult:
        now = datetime.now(timezone.utc).isoformat()
        cycle_id = f"cycle-{uuid.uuid4().hex[:8]}"

        signals = self.detector.detect_from_audit_report(report)
        self._log_event(MorphologyEventType.LIMITATION_DETECTED, {
            "cycle_id": cycle_id,
            "source": "audit_report",
            "signals_count": len(signals),
        })

        diagnoses = self.detector.aggregate_signals(signals)
        proposals = []
        simulations = []
        accepted = []
        rejected = []

        for diag in diagnoses:
            proposal = self.rewriter.generate_proposal(diag)
            proposals.append(proposal)
            self.proposal_store.save_proposal(proposal)

        # T48 — Apply episodic policy to adjust proposal ranking
        episodic_context = None
        episodic_adjustments = []
        if self.episodic_policy_enabled and self.episodic_policy is not None and proposals:
            limitation_type = diagnoses[0].primary_category if diagnoses else "unknown"
            episodic_context = self.episodic_policy.build_context(limitation_type, report)
            episodic_adjustments = self.episodic_policy.adjust_proposals(proposals, episodic_context)
            adj_map = {a.proposal_id: a.adjusted_confidence for a in episodic_adjustments}
            proposals.sort(key=lambda p: adj_map.get(p.id, 0.0), reverse=True)

        # T49 — Counterfactual sandbox evaluation
        counterfactual_results: List[CounterfactualResult] = []
        counterfactual_best = None
        counterfactual_verdict = ""
        if self.counterfactual_sandbox_enabled and self.counterfactual_sandbox is not None and proposals:
            limitation_type = diagnoses[0].primary_category if diagnoses else "unknown"
            for proposal in proposals:
                cf_result = self.counterfactual_sandbox.run_scenario(proposal, limitation_type)
                counterfactual_results.append(cf_result)
            best = self.counterfactual_sandbox.select_best_safe_result(counterfactual_results)
            counterfactual_best = best
            if best is not None:
                counterfactual_verdict = best.verdict

        # T50 — Safe Architecture Patch Execution
        patch_execution_result: Optional[PatchExecutionResult] = None
        patch_verdict = ""
        if (
            self.architecture_patch_execution_enabled
            and self.architecture_patch_executor is not None
            and counterfactual_best is not None
        ):
            # counterfactual_best may be a Pydantic model (CounterfactualResult)
            # or a plain dict (depending on caller). Use a defensive getter.
            best_proposal_id = getattr(
                counterfactual_best, "proposal_id",
                counterfactual_best.get("proposal_id") if isinstance(counterfactual_best, dict) else None,
            )
            target_proposal = None
            for p in proposals:
                if p.id == best_proposal_id:
                    target_proposal = p
                    break
            if target_proposal is not None:
                patch_execution_result = self.architecture_patch_executor.execute_patch(target_proposal)
                patch_verdict = patch_execution_result.verdict

        for proposal in proposals:
            sim = self.simulate_proposal(proposal)
            simulations.append(sim)

            verdict = self.accept_or_reject(sim)
            if verdict == "accept":
                accepted.append(proposal.id)
                proposal.status = "accepted"
            elif verdict == "reject":
                rejected.append(proposal.id)
                proposal.status = "rejected"
            else:
                proposal.status = "simulated"

        if not signals:
            final_verdict = "NO_LIMITATION_DETECTED"
        elif not proposals:
            final_verdict = "LIMITATION_DETECTED_NO_SAFE_PATCH"
        elif accepted:
            final_verdict = "PROPOSAL_ACCEPTED_FOR_NEXT_TASK"
        elif rejected and not accepted:
            final_verdict = "REGRESSION_BLOCKED"
        else:
            final_verdict = "SAFE_PROPOSAL_GENERATED"

        # 5b. T-Phase 8C — MM-APR Hard Veto Router hook point
        mmapr_veto_dict: Optional[Dict[str, Any]] = None
        mmapr_audit_path: Optional[str] = None
        if self.mmapr_router is not None and proposals:
            try:
                mmapr_veto_dict, mmapr_audit_path = self._apply_mmapr_veto(
                    proposals=proposals,
                    simulations=simulations,
                    counterfactual_best=counterfactual_best,
                    patch_execution_result=patch_execution_result,
                    cycle_id=cycle_id,
                    final_verdict=final_verdict,
                )
                if mmapr_veto_dict is not None:
                    self._log_event(
                        MorphologyEventType.MMAPR_VETO_GATE_TRIGGERED,
                        {
                            "cycle_id": cycle_id,
                            "final_status": mmapr_veto_dict.get("final_status"),
                            "hard_blocked_by": mmapr_veto_dict.get("hard_blocked_by", []),
                            "soft_flagged_by": mmapr_veto_dict.get("soft_flagged_by", []),
                        },
                    )
                    if mmapr_veto_dict.get("final_status") == "hard_blocked":
                        final_verdict = "LIMITATION_DETECTED_NO_SAFE_PATCH"
                        rejected.extend(accepted)
                        accepted.clear()
                        self._log_event(
                            MorphologyEventType.MMAPR_VETO_HARD_BLOCKED,
                            {
                                "cycle_id": cycle_id,
                                "hard_blocked_by": mmapr_veto_dict.get("hard_blocked_by", []),
                            },
                        )
                    elif mmapr_veto_dict.get("final_status") == "soft_flagged":
                        self._log_event(
                            MorphologyEventType.MMAPR_VETO_SOFT_FLAGGED,
                            {
                                "cycle_id": cycle_id,
                                "flaggers": mmapr_veto_dict.get("soft_flagged_by", []),
                            },
                        )
            except Exception as exc:  # pragma: no cover - defensive
                logging.getLogger(__name__).warning(
                    "MMAPR veto step failed: %s", exc, exc_info=True
                )
                mmapr_veto_dict = None
                mmapr_audit_path = None

        result = SelfImprovementCycleResult(
            cycle_id=cycle_id,
            detected_limitations=signals,
            diagnoses=diagnoses,
            proposals=proposals,
            simulations=simulations,
            accepted_proposals=accepted,
            rejected_proposals=rejected,
            final_verdict=final_verdict,
            episodic_context=episodic_context.model_dump() if episodic_context is not None else None,
            episodic_adjustments=[a.model_dump() for a in episodic_adjustments],
            counterfactual_results=[r.model_dump() for r in counterfactual_results],
            counterfactual_best_result=counterfactual_best.model_dump() if counterfactual_best is not None else None,
            counterfactual_verdict=counterfactual_verdict,
            patch_execution_result=patch_execution_result.model_dump() if patch_execution_result is not None else None,
            patch_verdict=patch_verdict if patch_verdict else None,
            mmapr_veto_verdict=mmapr_veto_dict,
            mmapr_audit_trail_path=mmapr_audit_path,
        )
        self.proposal_store.save_cycle_result(result)
        return result

    # ------------------------------------------------------------------ #
    # Simulation
    # ------------------------------------------------------------------ #

    def simulate_proposal(
        self, proposal: ArchitectureRewriteProposal
    ) -> RewriteSimulationResult:
        risks = self.rewriter.estimate_risk(proposal)
        benefits = self.rewriter.estimate_benefit(proposal)
        safety_passed = self.rewriter.validate_safety_constraints(proposal)

        # Compute acceptance score from risk/benefit balance
        benefit_sum = sum(benefits.values()) if benefits else 0.0
        risk_sum = sum(risks.values()) if risks else 0.0
        if benefit_sum + risk_sum > 0:
            raw_score = benefit_sum / (benefit_sum + risk_sum + 0.01)
        else:
            raw_score = 0.0

        # Modifiers
        if proposal.proposal_type == "module_addition":
            raw_score *= 0.95
        elif proposal.proposal_type == "genome_mutation":
            raw_score *= 0.85
        elif proposal.proposal_type == "parameter_tuning":
            raw_score *= 1.05

        acceptance_score = max(0.0, min(1.0, raw_score))

        # Delta metrics = estimated benefits minus estimated risks
        delta = {}
        for k, v in benefits.items():
            delta[k] = v - risks.get(k, 0.0)
        for k, v in risks.items():
            if k not in delta:
                delta[k] = -v

        # Regression guard check
        rg_verdict = "POLICY_SAFE"
        if self.regression_guard is not None and hasattr(self.regression_guard, "evaluate"):
            try:
                rg_result = self.regression_guard.evaluate(delta)
                rg_verdict = getattr(rg_result, "verdict", "POLICY_SAFE")
            except Exception:
                rg_verdict = "POLICY_SAFE"

        if rg_verdict == "POLICY_UNSAFE":
            safety_passed = False
            acceptance_score = 0.0

        recommendation = self.accept_or_reject(
            RewriteSimulationResult(
                proposal_id=proposal.id,
                safety_passed=safety_passed,
                acceptance_score=acceptance_score,
                regression_guard_verdict=rg_verdict,
            )
        )

        return RewriteSimulationResult(
            proposal_id=proposal.id,
            baseline_metrics={},
            simulated_metrics=benefits,
            delta_metrics=delta,
            regression_guard_verdict=rg_verdict,
            safety_passed=safety_passed,
            acceptance_score=acceptance_score,
            recommendation=recommendation,
        )

    def accept_or_reject(self, simulation: RewriteSimulationResult) -> str:
        if not simulation.safety_passed:
            return "reject"
        if simulation.regression_guard_verdict == "POLICY_UNSAFE":
            return "reject"
        if simulation.acceptance_score < 0.35:
            return "reject"
        if (
            simulation.safety_passed
            and simulation.acceptance_score >= 0.55
        ):
            risks_safe = True
            # Additional risk checks if we had access to the proposal object;
            # here we rely on acceptance_score and safety_passed.
            if risks_safe:
                return "accept"
        return "needs_more_evidence"

    # ------------------------------------------------------------------ #
    # Reporting
    # ------------------------------------------------------------------ #

    def generate_markdown_report(
        self, result: SelfImprovementCycleResult
    ) -> str:
        lines = [
            "# T45 Autonomous Limitation Detection & Architecture Rewriting Loop",
            "",
            "## Detected Limitations",
        ]
        if result.detected_limitations:
            for sig in result.detected_limitations:
                lines.append(f"- **{sig.category}** (severity={sig.severity:.2f}, confidence={sig.confidence:.2f}): {sig.description}")
        else:
            lines.append("No limitations detected.")

        lines.extend(["", "## Diagnoses"])
        if result.diagnoses:
            for diag in result.diagnoses:
                lines.append(f"- **{diag.primary_category}** | urgency={diag.urgency_score:.2f} | recurrence={diag.recurrence_score:.2f} | confidence={diag.confidence:.2f}")
                lines.append(f"  - Hypothesis: {diag.root_cause_hypothesis}")
                lines.append(f"  - Affected modules: {', '.join(diag.affected_modules)}")
                lines.append(f"  - Recommended action: {diag.recommended_action_type}")
        else:
            lines.append("No diagnoses generated.")

        lines.extend(["", "## Architecture Rewrite Proposals"])
        if result.proposals:
            for prop in result.proposals:
                lines.append(f"- **{prop.title}** (type={prop.proposal_type}, status={prop.status})")
                lines.append(f"  - Rationale: {prop.rationale}")
                lines.append(f"  - Target modules: {', '.join(prop.target_modules)}")
        else:
            lines.append("No proposals generated.")

        lines.extend(["", "## Simulation Results"])
        if result.simulations:
            for sim in result.simulations:
                lines.append(f"- Proposal {sim.proposal_id}: acceptance_score={sim.acceptance_score:.2f}, safety_passed={sim.safety_passed}, recommendation={sim.recommendation}")
        else:
            lines.append("No simulations run.")

        lines.extend(["", "## Accepted / Rejected Proposals"])
        lines.append(f"- Accepted: {len(result.accepted_proposals)}")
        for pid in result.accepted_proposals:
            lines.append(f"  - {pid}")
        lines.append(f"- Rejected: {len(result.rejected_proposals)}")
        for pid in result.rejected_proposals:
            lines.append(f"  - {pid}")

        # T48 — Episodic Policy Context
        if result.episodic_context:
            ctx = result.episodic_context
            lines.extend(["", "## Episodic Policy Context"])
            lines.append(f"- Limitation type: {ctx.get('limitation_type', 'unknown')}")
            lines.append(f"- Similar episodes: {ctx.get('similar_episode_count', 0)}")
            lines.append(f"- Recovery episodes: {ctx.get('recovery_episode_count', 0)}")
            lines.append(f"- Regression episodes: {ctx.get('regression_episode_count', 0)}")
            lines.append(f"- Recovery patterns: {', '.join(ctx.get('recovery_patterns', []))}")
            lines.append(f"- Regression precursors: {', '.join(ctx.get('regression_precursors', []))}")
            lines.append(f"- Confidence modifier: {ctx.get('confidence_modifier', 0.0):.4f}")
            lines.append(f"- Risk modifier: {ctx.get('risk_modifier', 0.0):.4f}")
        if result.episodic_adjustments:
            lines.extend(["", "## Episodic Proposal Adjustments"])
            for adj in result.episodic_adjustments:
                lines.append(
                    f"- {adj.get('proposal_id', 'unknown')}: "
                    f"original={adj.get('original_confidence', 0.0):.4f}, "
                    f"adjusted={adj.get('adjusted_confidence', 0.0):.4f}, "
                    f"bonus={adj.get('episodic_bonus', 0.0):.4f}, "
                    f"penalty={adj.get('episodic_penalty', 0.0):.4f}"
                )
                reasons = adj.get('reasons', [])
                if reasons:
                    lines.append(f"  - reasons: {', '.join(reasons)}")

        # T49 — Counterfactual Sandbox Results
        if result.counterfactual_results:
            lines.extend(["", "## Counterfactual Sandbox Results"])
            for cf in result.counterfactual_results:
                lines.append(
                    f"- Scenario {cf.get('scenario_id', 'unknown')} | "
                    f"Proposal {cf.get('proposal_id', 'unknown')}: "
                    f"verdict={cf.get('verdict', 'unknown')}, "
                    f"delta_score={cf.get('delta_score', 0.0):.4f}, "
                    f"confidence={cf.get('confidence', 0.0):.4f}"
                )
                flags = cf.get('regression_flags', [])
                if flags:
                    lines.append(f"  - flags: {', '.join(flags)}")
        if result.counterfactual_best_result:
            best = result.counterfactual_best_result
            lines.extend(["", "## Best Counterfactual Result"])
            lines.append(f"- Scenario: {best.get('scenario_id', 'unknown')}")
            lines.append(f"- Proposal: {best.get('proposal_id', 'unknown')}")
            lines.append(f"- Verdict: {best.get('verdict', 'unknown')}")
            lines.append(f"- Delta score: {best.get('delta_score', 0.0):.4f}")
            lines.append(f"- Confidence: {best.get('confidence', 0.0):.4f}")

        # T50 — Safe Architecture Patch Execution
        if result.patch_execution_result:
            per = result.patch_execution_result
            lines.extend(["", "## Safe Architecture Patch Execution (T50)"])
            lines.append(f"- Patch ID: {per.get('patch_id', 'unknown')}")
            lines.append(f"- Proposal ID: {per.get('proposal_id', 'unknown')}")
            lines.append(f"- Applied: {per.get('applied', False)}")
            lines.append(f"- Confirmed: {per.get('confirmed', False)}")
            lines.append(f"- Rolled back: {per.get('rolled_back', False)}")
            lines.append(f"- Verdict: {per.get('verdict', 'unknown')}")
            lines.append(f"- Pre-score: {per.get('pre_score', 0.0):.4f}")
            lines.append(f"- Post-score: {per.get('post_score', 0.0):.4f}")
            lines.append(f"- Delta score: {per.get('delta_score', 0.0):.4f}")
            lines.append(f"- Delta Φ: {per.get('delta_phi', 0.0):.4f}")
            lines.append(f"- Delta energy: {per.get('delta_energy', 0.0):.4f}")
            flags = per.get('regression_flags', [])
            if flags:
                lines.append(f"- Regression flags: {', '.join(flags)}")
            else:
                lines.append("- Regression flags: none")
            report_path = per.get('report_path')
            if report_path:
                lines.append(f"- Report: {report_path}")

        lines.extend(["", "## Final Verdict"])
        lines.append(f"**{result.final_verdict}**")

        lines.extend(["", "## Recommended Next Task"])
        if result.accepted_proposals:
            # Find the accepted proposal title
            title = "Unknown"
            for p in result.proposals:
                if p.id in result.accepted_proposals:
                    title = p.title
                    break
            lines.append(f"Recommended Next Task: {title}")
        else:
            lines.append("No task recommended (no accepted proposals).")

        return "\n".join(lines) + "\n"

    def generate_json_report(
        self, result: SelfImprovementCycleResult
    ) -> str:
        return json.dumps(result.model_dump(), indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------ #
    # T46 — Outcome Learning Integration
    # ------------------------------------------------------------------ #

    def record_proposal_outcome(
        self,
        proposal_id: str,
        limitation_type: str,
        task_id: str,
        audit_verdict: str,
        metrics: Dict[str, Any],
    ) -> ProposalOutcome:
        """Record the outcome of an implemented proposal after audit."""
        outcome = self.outcome_tracker.record_outcome(
            proposal_id=proposal_id,
            limitation_type=limitation_type,
            task_id=task_id,
            audit_verdict=audit_verdict,
            metrics=metrics,
        )
        self.self_improvement_memory.record_audit_outcome(
            outcome_id=outcome.id,
            proposal_id=proposal_id,
            verdict=audit_verdict,
            net_gain=outcome.net_gain,
        )
        return outcome

    def learn_from_outcome(self, outcome: ProposalOutcome) -> ProposalLearningRecord:
        """Update learning records from an outcome."""
        record = self.proposal_learning_engine.update_from_outcome(outcome)
        self.self_improvement_memory.record_learning_update(
            limitation_type=outcome.originating_limitation_type,
            task_id=outcome.implemented_task_id,
            confidence=record.confidence,
            mean_net_gain=record.mean_net_gain,
        )
        return record

    def get_best_known_proposal_for_limitation(
        self,
        limitation_type: str,
        candidates: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return the highest-confidence known proposal for a limitation."""
        if candidates is None:
            candidates = []
            # Build candidates from accepted proposals in store
            for prop in self.proposal_store.list_proposals(status="accepted"):
                candidates.append({
                    "task_id": prop.title,
                    "proposal_id": prop.id,
                    "title": prop.title,
                })
        if not candidates:
            return None
        ranked = self.proposal_learning_engine.rank_candidate_proposals(
            limitation_type=limitation_type,
            candidates=candidates,
        )
        return ranked[0] if ranked else None

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _apply_mmapr_veto(
        self,
        proposals: List[ArchitectureRewriteProposal],
        simulations: List[RewriteSimulationResult],
        counterfactual_best: Optional[CounterfactualResult],
        patch_execution_result: Optional[PatchExecutionResult],
        cycle_id: str,
        final_verdict: str,
    ) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        """T-Phase 8C — Run the MM-APR Hard Veto Router on all proposals.

        Routes every proposal through the four epistemic classes (A/B/C/D)
        and returns a serialisable summary plus the audit path. The hook
        point in ``run_detection_cycle``/``run_from_audit_report`` uses
        ``final_status == "hard_blocked"`` to downgrade the cycle's
        ``final_verdict`` to ``LIMITATION_DETECTED_NO_SAFE_PATCH``.

        The router is invoked once per *cycle* with the best
        counterfactual scenario and the patch execution result (when
        available). The router currently treats the *worst* verdict
        across the proposals as the cycle-level verdict, so even a
        single hard_block downgrades the whole cycle.
        """
        from speace_core.cellular_brain.self_improvement.mmapr_veto_router import (
            VetoVerdict,
        )

        # Pick the worst per-proposal verdict for the cycle-level view.
        worst: Optional[VetoVerdict] = None
        # Build proposal -> simulation lookup for the router signature
        sim_by_id: Dict[str, RewriteSimulationResult] = {
            s.proposal_id: s for s in (simulations or [])
        }
        for proposal in proposals:
            sim = sim_by_id.get(proposal.id)
            verdict = self.mmapr_router.route(  # type: ignore[union-attr]
                proposal=proposal,
                simulation=sim,
                counterfactual=counterfactual_best,
                patch_result=patch_execution_result,
                cycle_id=cycle_id,
            )
            if worst is None:
                worst = verdict
            else:
                # Promote "hard_blocked" above "soft_flagged" above "admit"
                rank = {"hard_blocked": 2, "soft_flagged": 1, "bypassed": 1, "admit": 0}
                if rank.get(verdict.final_status, 0) > rank.get(worst.final_status, 0):
                    worst = verdict

        if worst is None:
            return None, None

        # Build the serialisable summary
        verdict_dict = worst.model_dump()
        audit_path: Optional[str] = None
        try:
            path = self.mmapr_router.audit_path_for(worst.verdict_id)  # type: ignore[union-attr]
            if path is not None:
                # Phase 8D: persist the full envelope (proposal +
                # verdict + checkpoints) to disk for audit / replay.
                from speace_core.cellular_brain.self_improvement.mmapr_proposal_envelope import (
                    MMAPRAuditTrail,
                    build_envelope,
                )
                # Find the proposal for the worst verdict
                worst_proposal = None
                for p in proposals:
                    if p.id == worst.proposal_id:
                        worst_proposal = p
                        break
                env = build_envelope(
                    proposal=worst_proposal,
                    simulation=sim_by_id.get(worst.proposal_id) if worst_proposal else None,
                    counterfactual=counterfactual_best,
                    patch_result=patch_execution_result,
                    veto_verdict=worst,
                    cycle_id=cycle_id,
                )
                trail = MMAPRAuditTrail(path)
                trail.append(env)
                audit_path = str(path)
        except Exception as exc:  # pragma: no cover - defensive
            _logger = logging.getLogger(__name__)
            _logger.debug("MMAPR audit persistence failed: %s", exc)
            audit_path = None
        return verdict_dict, audit_path

    def _log_event(
        self,
        event_type: MorphologyEventType,
        metadata: Dict[str, Any],
    ) -> None:
        if self.memory is None or not hasattr(self.memory, "log_event"):
            return
        try:
            event = MorphologyEvent(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=event_type,
                timestamp=datetime.now(timezone.utc).timestamp(),
                metadata=metadata,
            )
            self.memory.log_event(event)
        except Exception:
            logging.getLogger(__name__).warning("Self-improvement loop step failed", exc_info=True)
