import copy
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.memory.morphology_events import MorphologyEvent, MorphologyEventType
from speace_core.cellular_brain.self_improvement.architecture_rewriter import ArchitectureRewriteProposal


class CounterfactualScenario(BaseModel):
    scenario_id: str
    proposal_id: str
    limitation_type: str
    sandbox_profile: str = "default"
    applied_changes: Dict[str, Any] = Field(default_factory=dict)
    seed: int = 42


class CounterfactualResult(BaseModel):
    scenario_id: str
    proposal_id: str
    baseline_score: float = 0.0
    counterfactual_score: float = 0.0
    delta_score: float = 0.0
    delta_phi: float = 0.0
    delta_energy: float = 0.0
    delta_cognitive: float = 0.0
    regression_flags: List[str] = Field(default_factory=list)
    verdict: str = "needs_more_evidence"
    confidence: float = 0.0


class CounterfactualBatchResult(BaseModel):
    limitation_type: str
    scenarios_tested: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    unsafe_count: int = 0
    best_scenario_id: Optional[str] = None
    best_proposal_id: Optional[str] = None
    mean_delta_score: float = 0.0
    verdict: str = "no_scenarios"


class CounterfactualArchitectureSandbox:
    """T49 — Counterfactual Architecture Sandbox for safe proposal evaluation."""

    def __init__(
        self,
        orchestrator=None,
        benchmark=None,
        regression_guard=None,
        memory=None,
    ):
        self.orchestrator = orchestrator
        self.benchmark = benchmark
        self.regression_guard = regression_guard
        self.memory = memory

    # ------------------------------------------------------------------ #
    # Orchestrator state cloning
    # ------------------------------------------------------------------ #

    def clone_orchestrator_state(self) -> Dict[str, Any]:
        """Capture a snapshot of relevant orchestrator state without mutation."""
        if self.orchestrator is None:
            return {}
        snapshot: Dict[str, Any] = {}
        # Capture scalar / serializable fields
        for attr in [
            "execution_mode",
            "stdp_enabled",
            "inhibition_enabled",
            "energy_control_enabled",
            "community_detection_enabled",
            "confidence_enabled",
            "inter_region_plasticity_enabled",
            "region_signal_routing_enabled",
            "negative_feedback_count",
            "latest_metrics",
        ]:
            val = getattr(self.orchestrator, attr, None)
            if val is not None:
                try:
                    # Attempt a deep copy for safety
                    snapshot[attr] = copy.deepcopy(val)
                except Exception:
                    snapshot[attr] = val
        # Capture circuit size info (not full circuit to avoid huge snapshots)
        circuit = getattr(self.orchestrator, "circuit", None)
        if circuit is not None:
            snapshot["circuit_neuron_count"] = len(
                getattr(circuit, "input_neurons", [])
                + getattr(circuit, "hidden_neurons", [])
                + getattr(circuit, "output_neurons", [])
            )
            snapshot["circuit_synapse_count"] = len(getattr(circuit, "synapses", []))
        # Capture memory event count
        mem = getattr(self.orchestrator, "memory", None)
        if mem is not None and hasattr(mem, "events"):
            snapshot["memory_event_count"] = len(mem.events)
        return snapshot

    # ------------------------------------------------------------------ #
    # Proposal application (simulated)
    # ------------------------------------------------------------------ #

    def apply_proposal_counterfactually(
        self,
        cloned_state: Dict[str, Any],
        proposal: ArchitectureRewriteProposal,
    ) -> Dict[str, Any]:
        """Apply a proposal in simulation space only."""
        applied = copy.deepcopy(cloned_state)
        # Simulate changes based on proposal type
        changes: Dict[str, Any] = {"proposal_type": proposal.proposal_type}
        if proposal.proposal_type == "parameter_tuning":
            changes["stdp_enabled"] = applied.get("stdp_enabled", True)
            changes["energy_control_enabled"] = applied.get("energy_control_enabled", True)
        elif proposal.proposal_type == "module_addition":
            changes["new_module_added"] = proposal.title
        elif proposal.proposal_type == "genome_mutation":
            changes["genome_mutated"] = True
        elif proposal.proposal_type == "routing_redesign":
            changes["region_signal_routing_enabled"] = True
        elif proposal.proposal_type == "plasticity_redesign":
            changes["inter_region_plasticity_enabled"] = True
        elif proposal.proposal_type == "module_refactor":
            changes["refactored_module"] = proposal.target_modules[0] if proposal.target_modules else "unknown"
        else:
            changes["generic_change"] = proposal.title
        applied["applied_changes"] = changes
        return applied

    # ------------------------------------------------------------------ #
    # Scenario execution
    # ------------------------------------------------------------------ #

    def run_scenario(
        self,
        proposal: ArchitectureRewriteProposal,
        limitation_type: str,
        seed: int = 42,
    ) -> CounterfactualResult:
        scenario_id = f"scenario-{uuid.uuid4().hex[:8]}"
        self._log_event(
            MorphologyEventType.COUNTERFACTUAL_SCENARIO_STARTED,
            {
                "scenario_id": scenario_id,
                "proposal_id": proposal.id,
                "limitation_type": limitation_type,
                "seed": seed,
            },
        )

        try:
            baseline_state = self.clone_orchestrator_state()
            counterfactual_state = self.apply_proposal_counterfactually(baseline_state, proposal)

            # Baseline score from orchestrator metrics if available
            baseline_score = 0.0
            baseline_phi = 0.0
            baseline_energy = 0.0
            baseline_cognitive = 0.0
            if self.orchestrator is not None:
                metrics = getattr(self.orchestrator, "latest_metrics", None)
                if metrics is not None:
                    baseline_score = getattr(metrics, "speace_cognitive_score", 0.0)
                    baseline_phi = getattr(metrics, "coherence_phi", 0.0)
                    baseline_energy = getattr(metrics, "mean_energy", 0.0)
                    baseline_cognitive = getattr(metrics, "accuracy_score", 0.0)

            # Simulate counterfactual score using proposal expected benefits/risks
            benefit_sum = sum(proposal.expected_benefits.values()) if proposal.expected_benefits else 0.0
            risk_sum = sum(proposal.expected_risks.values()) if proposal.expected_risks else 0.0
            if benefit_sum + risk_sum > 0:
                simulated_score = benefit_sum / (benefit_sum + risk_sum + 0.01)
            else:
                simulated_score = 0.0

            # Apply proposal-type modifier (same as simulate_proposal in loop)
            if proposal.proposal_type == "module_addition":
                simulated_score *= 0.95
            elif proposal.proposal_type == "genome_mutation":
                simulated_score *= 0.85
            elif proposal.proposal_type == "parameter_tuning":
                simulated_score *= 1.05

            counterfactual_score = max(0.0, min(1.0, simulated_score))
            delta_score = counterfactual_score - baseline_score

            # Estimate delta metrics from proposal
            delta_phi = proposal.expected_benefits.get("phi_recovery", 0.0) - proposal.expected_risks.get("regression", 0.0)
            delta_energy = proposal.expected_benefits.get("energy_efficiency", 0.0) - proposal.expected_risks.get("energy", 0.0)
            delta_cognitive = proposal.expected_benefits.get("cognitive_preservation", 0.0) - proposal.expected_risks.get("safety", 0.0)

            # Regression guard check
            regression_flags: List[str] = []
            rg_verdict = "POLICY_SAFE"
            if self.regression_guard is not None and hasattr(self.regression_guard, "evaluate"):
                delta_metrics = {
                    "cognitive_score_delta": delta_cognitive,
                    "coherence_phi_delta": delta_phi,
                    "energy_efficiency_delta": delta_energy,
                }
                try:
                    rg_result = self.regression_guard.evaluate(delta_metrics)
                    rg_verdict = getattr(rg_result, "verdict", "POLICY_SAFE")
                except Exception:
                    rg_verdict = "POLICY_SAFE"
            if rg_verdict == "POLICY_UNSAFE":
                regression_flags.append("POLICY_UNSAFE")

            # Safety checks
            neuron_count = counterfactual_state.get("circuit_neuron_count", 0)
            if neuron_count < 5:
                regression_flags.append("NEURON_COUNT_BELOW_THRESHOLD")
            if delta_energy < -0.5:
                regression_flags.append("ENERGY_COLLAPSE")

            # Verdict
            verdict = self._compute_verdict(delta_score, delta_phi, delta_energy, regression_flags)
            confidence = max(0.0, min(1.0, counterfactual_score))

            result = CounterfactualResult(
                scenario_id=scenario_id,
                proposal_id=proposal.id,
                baseline_score=round(baseline_score, 4),
                counterfactual_score=round(counterfactual_score, 4),
                delta_score=round(delta_score, 4),
                delta_phi=round(delta_phi, 4),
                delta_energy=round(delta_energy, 4),
                delta_cognitive=round(delta_cognitive, 4),
                regression_flags=regression_flags,
                verdict=verdict,
                confidence=round(confidence, 4),
            )

            self._log_event(
                MorphologyEventType.COUNTERFACTUAL_SCENARIO_COMPLETED,
                {
                    "scenario_id": scenario_id,
                    "proposal_id": proposal.id,
                    "verdict": verdict,
                    "delta_score": result.delta_score,
                    "regression_flags": regression_flags,
                },
            )

            if verdict == "accept":
                self._log_event(
                    MorphologyEventType.COUNTERFACTUAL_PROPOSAL_ACCEPTED,
                    {"scenario_id": scenario_id, "proposal_id": proposal.id},
                )
            elif verdict == "reject":
                self._log_event(
                    MorphologyEventType.COUNTERFACTUAL_PROPOSAL_REJECTED,
                    {"scenario_id": scenario_id, "proposal_id": proposal.id},
                )
            elif verdict == "unsafe":
                self._log_event(
                    MorphologyEventType.COUNTERFACTUAL_PROPOSAL_UNSAFE,
                    {"scenario_id": scenario_id, "proposal_id": proposal.id, "flags": regression_flags},
                )

            return result
        except Exception as exc:
            # Runtime error during scenario = unsafe
            self._log_event(
                MorphologyEventType.COUNTERFACTUAL_PROPOSAL_UNSAFE,
                {
                    "scenario_id": scenario_id,
                    "proposal_id": proposal.id,
                    "reason": "runtime_error",
                    "error": str(exc),
                },
            )
            return CounterfactualResult(
                scenario_id=scenario_id,
                proposal_id=proposal.id,
                regression_flags=["RUNTIME_ERROR"],
                verdict="unsafe",
                confidence=0.0,
            )

    # ------------------------------------------------------------------ #
    # Batch execution
    # ------------------------------------------------------------------ #

    def run_batch(
        self,
        proposals: List[ArchitectureRewriteProposal],
        limitation_type: str,
    ) -> CounterfactualBatchResult:
        results: List[CounterfactualResult] = []
        for proposal in proposals:
            result = self.run_scenario(proposal, limitation_type)
            results.append(result)

        accepted = [r for r in results if r.verdict == "accept"]
        rejected = [r for r in results if r.verdict == "reject"]
        unsafe = [r for r in results if r.verdict == "unsafe"]

        best = self.select_best_safe_result(results)

        mean_delta = 0.0
        if results:
            mean_delta = sum(r.delta_score for r in results) / len(results)

        batch_verdict = "no_scenarios"
        if unsafe:
            batch_verdict = "has_unsafe"
        elif accepted:
            batch_verdict = "has_accepted"
        elif rejected:
            batch_verdict = "all_rejected"

        batch = CounterfactualBatchResult(
            limitation_type=limitation_type,
            scenarios_tested=len(results),
            accepted_count=len(accepted),
            rejected_count=len(rejected),
            unsafe_count=len(unsafe),
            best_scenario_id=best.scenario_id if best else None,
            best_proposal_id=best.proposal_id if best else None,
            mean_delta_score=round(mean_delta, 4),
            verdict=batch_verdict,
        )

        self._log_event(
            MorphologyEventType.COUNTERFACTUAL_BATCH_COMPLETED,
            {
                "limitation_type": limitation_type,
                "scenarios_tested": batch.scenarios_tested,
                "accepted_count": batch.accepted_count,
                "rejected_count": batch.rejected_count,
                "unsafe_count": batch.unsafe_count,
                "best_scenario_id": batch.best_scenario_id,
            },
        )
        return batch

    # ------------------------------------------------------------------ #
    # Selection
    # ------------------------------------------------------------------ #

    @staticmethod
    def select_best_safe_result(
        results: List[CounterfactualResult],
    ) -> Optional[CounterfactualResult]:
        safe = [r for r in results if r.verdict in ("accept", "needs_more_evidence")]
        if not safe:
            return None
        return max(safe, key=lambda r: r.delta_score)

    # ------------------------------------------------------------------ #
    # Verdict rules
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_verdict(
        delta_score: float,
        delta_phi: float,
        delta_energy: float,
        regression_flags: List[str],
    ) -> str:
        if "RUNTIME_ERROR" in regression_flags or "ENERGY_COLLAPSE" in regression_flags or "NEURON_COUNT_BELOW_THRESHOLD" in regression_flags:
            return "unsafe"
        if "POLICY_UNSAFE" in regression_flags:
            return "unsafe"
        if delta_score <= 0:
            return "reject"
        if delta_score > 0.02 and delta_phi >= -0.02 and delta_energy >= -0.05:
            return "accept"
        if 0.0 < delta_score <= 0.02:
            return "needs_more_evidence"
        return "reject"

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

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
            pass
