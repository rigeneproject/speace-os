import pytest
from unittest.mock import MagicMock, PropertyMock

from speace_core.cellular_brain.self_improvement.counterfactual_sandbox import (
    CounterfactualScenario,
    CounterfactualResult,
    CounterfactualBatchResult,
    CounterfactualArchitectureSandbox,
)
from speace_core.cellular_brain.self_improvement.architecture_rewriter import (
    ArchitectureRewriteProposal,
)
from speace_core.cellular_brain.memory.morphology_events import (
    MorphologyEvent,
    MorphologyEventType,
)


class FakeCircuit:
    def __init__(self):
        self.input_neurons = [MagicMock(), MagicMock()]
        self.hidden_neurons = [MagicMock(), MagicMock(), MagicMock()]
        self.output_neurons = [MagicMock(), MagicMock()]
        self.synapses = [MagicMock(), MagicMock()]


class FakeMetrics:
    def __init__(self):
        self.speace_cognitive_score = 0.5
        self.coherence_phi = 0.6
        self.mean_energy = 0.7
        self.accuracy_score = 0.4


class FakeMemory:
    def __init__(self):
        self.events = []

    def log_event(self, event):
        self.events.append(event)


class FakeOrchestrator:
    def __init__(self):
        self.execution_mode = "global_tick"
        self.stdp_enabled = True
        self.inhibition_enabled = True
        self.energy_control_enabled = True
        self.community_detection_enabled = True
        self.confidence_enabled = True
        self.inter_region_plasticity_enabled = True
        self.region_signal_routing_enabled = True
        self.negative_feedback_count = 2
        self.latest_metrics = FakeMetrics()
        self.circuit = FakeCircuit()
        self.memory = FakeMemory()


class FakeRegressionGuard:
    def __init__(self, verdict="POLICY_SAFE"):
        self._verdict = verdict

    def evaluate(self, delta_metrics):
        result = MagicMock()
        result.verdict = self._verdict
        return result


@pytest.fixture
def proposal():
    return ArchitectureRewriteProposal(
        id="prop-test",
        diagnosis_id="diag-test",
        title="Test Proposal",
        proposal_type="parameter_tuning",
        target_modules=["module_a"],
        rationale="Test rationale",
        expected_benefits={"phi_recovery": 0.3, "energy_efficiency": 0.2},
        expected_risks={"safety": 0.05, "regression": 0.1},
        implementation_plan=["Step 1"],
        rollback_plan=["Revert"],
        safety_constraints=["No core mutation"],
        created_at="2024-01-01T00:00:00Z",
    )


@pytest.fixture
def sandbox():
    orch = FakeOrchestrator()
    mem = FakeMemory()
    return CounterfactualArchitectureSandbox(
        orchestrator=orch,
        memory=mem,
    )


# ------------------------------------------------------------------ #
# Model tests
# ------------------------------------------------------------------ #

class TestCounterfactualScenario:
    def test_model_creation(self):
        s = CounterfactualScenario(
            scenario_id="s1",
            proposal_id="p1",
            limitation_type="phi_regression",
        )
        assert s.scenario_id == "s1"
        assert s.limitation_type == "phi_regression"
        assert s.sandbox_profile == "default"


class TestCounterfactualResult:
    def test_model_defaults(self):
        r = CounterfactualResult(scenario_id="s1", proposal_id="p1")
        assert r.baseline_score == 0.0
        assert r.verdict == "needs_more_evidence"
        assert r.confidence == 0.0
        assert r.regression_flags == []


class TestCounterfactualBatchResult:
    def test_model_defaults(self):
        b = CounterfactualBatchResult(limitation_type="phi_regression")
        assert b.scenarios_tested == 0
        assert b.verdict == "no_scenarios"


# ------------------------------------------------------------------ #
# clone_orchestrator_state
# ------------------------------------------------------------------ #

class TestCloneOrchestratorState:
    def test_returns_empty_when_no_orchestrator(self):
        sb = CounterfactualArchitectureSandbox()
        assert sb.clone_orchestrator_state() == {}

    def test_captures_scalar_fields(self, sandbox):
        state = sandbox.clone_orchestrator_state()
        assert state["execution_mode"] == "global_tick"
        assert state["stdp_enabled"] is True
        assert state["negative_feedback_count"] == 2

    def test_captures_circuit_counts(self, sandbox):
        state = sandbox.clone_orchestrator_state()
        assert state["circuit_neuron_count"] == 7
        assert state["circuit_synapse_count"] == 2

    def test_captures_memory_event_count(self, sandbox):
        sandbox.orchestrator.memory.events.append(MagicMock())
        state = sandbox.clone_orchestrator_state()
        assert state["memory_event_count"] == 1


# ------------------------------------------------------------------ #
# apply_proposal_counterfactually
# ------------------------------------------------------------------ #

class TestApplyProposalCounterfactually:
    def test_parameter_tuning(self, sandbox, proposal):
        state = sandbox.clone_orchestrator_state()
        result = sandbox.apply_proposal_counterfactually(state, proposal)
        assert result["applied_changes"]["proposal_type"] == "parameter_tuning"
        assert result["applied_changes"]["stdp_enabled"] is True

    def test_module_addition(self, sandbox, proposal):
        proposal.proposal_type = "module_addition"
        proposal.title = "New Module"
        state = sandbox.clone_orchestrator_state()
        result = sandbox.apply_proposal_counterfactually(state, proposal)
        assert result["applied_changes"]["new_module_added"] == "New Module"

    def test_genome_mutation(self, sandbox, proposal):
        proposal.proposal_type = "genome_mutation"
        state = sandbox.clone_orchestrator_state()
        result = sandbox.apply_proposal_counterfactually(state, proposal)
        assert result["applied_changes"]["genome_mutated"] is True

    def test_routing_redesign(self, sandbox, proposal):
        proposal.proposal_type = "routing_redesign"
        state = sandbox.clone_orchestrator_state()
        result = sandbox.apply_proposal_counterfactually(state, proposal)
        assert result["applied_changes"]["region_signal_routing_enabled"] is True

    def test_plasticity_redesign(self, sandbox, proposal):
        proposal.proposal_type = "plasticity_redesign"
        state = sandbox.clone_orchestrator_state()
        result = sandbox.apply_proposal_counterfactually(state, proposal)
        assert result["applied_changes"]["inter_region_plasticity_enabled"] is True

    def test_module_refactor(self, sandbox, proposal):
        proposal.proposal_type = "module_refactor"
        state = sandbox.clone_orchestrator_state()
        result = sandbox.apply_proposal_counterfactually(state, proposal)
        assert result["applied_changes"]["refactored_module"] == "module_a"

    def test_generic_fallback(self, sandbox, proposal):
        proposal.proposal_type = "unknown_type"
        state = sandbox.clone_orchestrator_state()
        result = sandbox.apply_proposal_counterfactually(state, proposal)
        assert result["applied_changes"]["generic_change"] == "Test Proposal"


# ------------------------------------------------------------------ #
# run_scenario verdicts
# ------------------------------------------------------------------ #

class TestRunScenarioVerdicts:
    def test_accepts_high_benefit_proposal(self, sandbox, proposal):
        proposal.expected_benefits = {"phi_recovery": 0.5, "energy_efficiency": 0.5}
        proposal.expected_risks = {"safety": 0.01, "regression": 0.01}
        result = sandbox.run_scenario(proposal, "phi_regression")
        assert result.verdict == "accept"
        assert result.delta_score > 0.02

    def test_rejects_zero_benefit(self, sandbox, proposal):
        proposal.expected_benefits = {}
        proposal.expected_risks = {}
        result = sandbox.run_scenario(proposal, "phi_regression")
        assert result.verdict == "reject"

    def test_rejects_negative_delta(self, sandbox, proposal):
        proposal.expected_benefits = {"phi_recovery": 0.01}
        proposal.expected_risks = {"safety": 0.5, "regression": 0.5}
        result = sandbox.run_scenario(proposal, "phi_regression")
        assert result.verdict == "reject"

    def test_needs_more_evidence_on_small_positive(self, sandbox, proposal):
        # Baseline score is 0.5 from FakeMetrics; need counterfactual score just above it
        proposal.expected_benefits = {"phi_recovery": 0.5}
        proposal.expected_risks = {"safety": 0.5}
        result = sandbox.run_scenario(proposal, "phi_regression")
        assert result.verdict == "needs_more_evidence"

    def test_unsafe_on_neuron_count_below_threshold(self, sandbox, proposal):
        sandbox.orchestrator.circuit.hidden_neurons = []
        sandbox.orchestrator.circuit.input_neurons = []
        sandbox.orchestrator.circuit.output_neurons = [MagicMock()]
        result = sandbox.run_scenario(proposal, "phi_regression")
        assert result.verdict == "unsafe"
        assert "NEURON_COUNT_BELOW_THRESHOLD" in result.regression_flags

    def test_unsafe_on_energy_collapse(self, sandbox, proposal):
        proposal.expected_benefits = {}
        proposal.expected_risks = {"energy": 0.9}
        result = sandbox.run_scenario(proposal, "phi_regression")
        assert result.verdict == "unsafe"
        assert "ENERGY_COLLAPSE" in result.regression_flags

    def test_unsafe_on_policy_unsafe(self, sandbox, proposal):
        sandbox.regression_guard = FakeRegressionGuard(verdict="POLICY_UNSAFE")
        result = sandbox.run_scenario(proposal, "phi_regression")
        assert result.verdict == "unsafe"
        assert "POLICY_UNSAFE" in result.regression_flags

    def test_runtime_error_returns_unsafe(self, sandbox, proposal):
        def _raise():
            raise RuntimeError("simulated failure")
        sandbox.clone_orchestrator_state = _raise
        result = sandbox.run_scenario(proposal, "phi_regression")
        assert result.verdict == "unsafe"
        assert "RUNTIME_ERROR" in result.regression_flags


# ------------------------------------------------------------------ #
# Proposal type modifiers
# ------------------------------------------------------------------ #

class TestProposalTypeModifiers:
    def test_module_addition_modifier(self, sandbox, proposal):
        proposal.proposal_type = "module_addition"
        proposal.expected_benefits = {"phi_recovery": 0.5, "energy_efficiency": 0.5}
        proposal.expected_risks = {"safety": 0.01, "regression": 0.01}
        result = sandbox.run_scenario(proposal, "phi_regression")
        assert result.counterfactual_score < 1.0

    def test_genome_mutation_modifier(self, sandbox, proposal):
        proposal.proposal_type = "genome_mutation"
        proposal.expected_benefits = {"phi_recovery": 0.5, "energy_efficiency": 0.5}
        proposal.expected_risks = {"safety": 0.01, "regression": 0.01}
        result = sandbox.run_scenario(proposal, "phi_regression")
        assert result.counterfactual_score < 1.0

    def test_parameter_tuning_modifier(self, sandbox, proposal):
        proposal.proposal_type = "parameter_tuning"
        proposal.expected_benefits = {"phi_recovery": 0.5, "energy_efficiency": 0.5}
        proposal.expected_risks = {"safety": 0.01, "regression": 0.01}
        result = sandbox.run_scenario(proposal, "phi_regression")
        assert result.counterfactual_score > 0.0


# ------------------------------------------------------------------ #
# run_batch
# ------------------------------------------------------------------ #

class TestRunBatch:
    def test_batch_counts(self, sandbox, proposal):
        p1 = proposal.model_copy()
        p2 = proposal.model_copy()
        p3 = proposal.model_copy()
        p1.id = "p1"
        p2.id = "p2"
        p3.id = "p3"
        p1.expected_benefits = {"phi_recovery": 0.5, "energy_efficiency": 0.5}
        p1.expected_risks = {"safety": 0.01, "regression": 0.01}
        p2.expected_benefits = {}
        p2.expected_risks = {}
        p3.expected_benefits = {}
        p3.expected_risks = {"energy": 0.9}
        batch = sandbox.run_batch([p1, p2, p3], "phi_regression")
        assert batch.scenarios_tested == 3
        assert batch.accepted_count == 1
        assert batch.rejected_count == 1
        assert batch.unsafe_count == 1
        assert batch.verdict == "has_unsafe"

    def test_empty_batch(self, sandbox):
        batch = sandbox.run_batch([], "phi_regression")
        assert batch.scenarios_tested == 0
        assert batch.verdict == "no_scenarios"


# ------------------------------------------------------------------ #
# select_best_safe_result
# ------------------------------------------------------------------ #

class TestSelectBestSafeResult:
    def test_selects_highest_delta(self):
        r1 = CounterfactualResult(
            scenario_id="s1", proposal_id="p1", verdict="accept", delta_score=0.1
        )
        r2 = CounterfactualResult(
            scenario_id="s2", proposal_id="p2", verdict="accept", delta_score=0.3
        )
        best = CounterfactualArchitectureSandbox.select_best_safe_result([r1, r2])
        assert best.scenario_id == "s2"

    def test_returns_none_when_no_safe(self):
        r1 = CounterfactualResult(
            scenario_id="s1", proposal_id="p1", verdict="unsafe", delta_score=0.1
        )
        best = CounterfactualArchitectureSandbox.select_best_safe_result([r1])
        assert best is None

    def test_includes_needs_more_evidence(self):
        r1 = CounterfactualResult(
            scenario_id="s1", proposal_id="p1", verdict="needs_more_evidence", delta_score=0.01
        )
        best = CounterfactualArchitectureSandbox.select_best_safe_result([r1])
        assert best.scenario_id == "s1"


# ------------------------------------------------------------------ #
# _compute_verdict
# ------------------------------------------------------------------ #

class TestComputeVerdict:
    def test_runtime_error_unsafe(self):
        assert (
            CounterfactualArchitectureSandbox._compute_verdict(0.5, 0.0, 0.0, ["RUNTIME_ERROR"])
            == "unsafe"
        )

    def test_energy_collapse_unsafe(self):
        assert (
            CounterfactualArchitectureSandbox._compute_verdict(0.5, 0.0, 0.0, ["ENERGY_COLLAPSE"])
            == "unsafe"
        )

    def test_neuron_threshold_unsafe(self):
        assert (
            CounterfactualArchitectureSandbox._compute_verdict(
                0.5, 0.0, 0.0, ["NEURON_COUNT_BELOW_THRESHOLD"]
            )
            == "unsafe"
        )

    def test_policy_unsafe_unsafe(self):
        assert (
            CounterfactualArchitectureSandbox._compute_verdict(
                0.5, 0.0, 0.0, ["POLICY_UNSAFE"]
            )
            == "unsafe"
        )

    def test_zero_delta_reject(self):
        assert (
            CounterfactualArchitectureSandbox._compute_verdict(0.0, 0.0, 0.0, [])
            == "reject"
        )

    def test_negative_delta_reject(self):
        assert (
            CounterfactualArchitectureSandbox._compute_verdict(-0.1, 0.0, 0.0, [])
            == "reject"
        )

    def test_accept(self):
        assert (
            CounterfactualArchitectureSandbox._compute_verdict(0.1, 0.0, 0.0, [])
            == "accept"
        )

    def test_needs_more_evidence(self):
        assert (
            CounterfactualArchitectureSandbox._compute_verdict(0.01, 0.0, 0.0, [])
            == "needs_more_evidence"
        )

    def test_accept_boundary(self):
        assert (
            CounterfactualArchitectureSandbox._compute_verdict(0.03, -0.01, -0.03, [])
            == "accept"
        )

    def test_reject_low_phi(self):
        assert (
            CounterfactualArchitectureSandbox._compute_verdict(0.1, -0.05, 0.0, [])
            == "reject"
        )

    def test_reject_low_energy(self):
        assert (
            CounterfactualArchitectureSandbox._compute_verdict(0.1, 0.0, -0.1, [])
            == "reject"
        )


# ------------------------------------------------------------------ #
# Event logging
# ------------------------------------------------------------------ #

class TestEventLogging:
    def test_scenario_started_event(self, sandbox, proposal):
        sandbox.run_scenario(proposal, "phi_regression")
        started = [
            e for e in sandbox.memory.events
            if e.event_type == MorphologyEventType.COUNTERFACTUAL_SCENARIO_STARTED
        ]
        assert len(started) == 1
        assert started[0].metadata["proposal_id"] == proposal.id

    def test_scenario_completed_event(self, sandbox, proposal):
        result = sandbox.run_scenario(proposal, "phi_regression")
        completed = [
            e for e in sandbox.memory.events
            if e.event_type == MorphologyEventType.COUNTERFACTUAL_SCENARIO_COMPLETED
        ]
        assert len(completed) == 1
        assert completed[0].metadata["verdict"] == result.verdict

    def test_batch_completed_event(self, sandbox, proposal):
        sandbox.run_batch([proposal], "phi_regression")
        batches = [
            e for e in sandbox.memory.events
            if e.event_type == MorphologyEventType.COUNTERFACTUAL_BATCH_COMPLETED
        ]
        assert len(batches) == 1
        assert batches[0].metadata["scenarios_tested"] == 1

    def test_accepted_event(self, sandbox, proposal):
        proposal.expected_benefits = {"phi_recovery": 0.5, "energy_efficiency": 0.5}
        proposal.expected_risks = {"safety": 0.01, "regression": 0.01}
        sandbox.run_scenario(proposal, "phi_regression")
        accepted = [
            e for e in sandbox.memory.events
            if e.event_type == MorphologyEventType.COUNTERFACTUAL_PROPOSAL_ACCEPTED
        ]
        assert len(accepted) == 1

    def test_rejected_event(self, sandbox, proposal):
        proposal.expected_benefits = {}
        proposal.expected_risks = {}
        sandbox.run_scenario(proposal, "phi_regression")
        rejected = [
            e for e in sandbox.memory.events
            if e.event_type == MorphologyEventType.COUNTERFACTUAL_PROPOSAL_REJECTED
        ]
        assert len(rejected) == 1

    def test_unsafe_event(self, sandbox, proposal):
        sandbox.orchestrator.circuit.hidden_neurons = []
        sandbox.orchestrator.circuit.input_neurons = []
        sandbox.orchestrator.circuit.output_neurons = [MagicMock()]
        sandbox.run_scenario(proposal, "phi_regression")
        unsafe = [
            e for e in sandbox.memory.events
            if e.event_type == MorphologyEventType.COUNTERFACTUAL_PROPOSAL_UNSAFE
        ]
        assert len(unsafe) == 1
        assert "NEURON_COUNT_BELOW_THRESHOLD" in unsafe[0].metadata["flags"]


# ------------------------------------------------------------------ #
# Score bounds
# ------------------------------------------------------------------ #

class TestScoreBounds:
    def test_counterfactual_score_between_zero_and_one(self, sandbox, proposal):
        proposal.expected_benefits = {"phi_recovery": 10.0}
        proposal.expected_risks = {"safety": 0.01}
        result = sandbox.run_scenario(proposal, "phi_regression")
        assert 0.0 <= result.counterfactual_score <= 1.0

    def test_delta_phi_computed(self, sandbox, proposal):
        proposal.expected_benefits = {"phi_recovery": 0.3}
        proposal.expected_risks = {"regression": 0.1}
        result = sandbox.run_scenario(proposal, "phi_regression")
        assert result.delta_phi == pytest.approx(0.2, abs=1e-4)

    def test_delta_energy_computed(self, sandbox, proposal):
        proposal.expected_benefits = {"energy_efficiency": 0.4}
        proposal.expected_risks = {"energy": 0.1}
        result = sandbox.run_scenario(proposal, "phi_regression")
        assert result.delta_energy == pytest.approx(0.3, abs=1e-4)

    def test_delta_cognitive_computed(self, sandbox, proposal):
        proposal.expected_benefits = {"cognitive_preservation": 0.5}
        proposal.expected_risks = {"safety": 0.2}
        result = sandbox.run_scenario(proposal, "phi_regression")
        assert result.delta_cognitive == pytest.approx(0.3, abs=1e-4)

    def test_confidence_bounded(self, sandbox, proposal):
        proposal.expected_benefits = {"phi_recovery": 0.5}
        proposal.expected_risks = {"safety": 0.5}
        result = sandbox.run_scenario(proposal, "phi_regression")
        assert 0.0 <= result.confidence <= 1.0

    def test_select_best_safe_result_with_needs_more_evidence(self):
        r1 = CounterfactualResult(
            scenario_id="s1", proposal_id="p1", verdict="needs_more_evidence", delta_score=0.005
        )
        r2 = CounterfactualResult(
            scenario_id="s2", proposal_id="p2", verdict="accept", delta_score=0.05
        )
        best = CounterfactualArchitectureSandbox.select_best_safe_result([r1, r2])
        assert best.scenario_id == "s2"

    def test_batch_verdict_has_accepted(self, sandbox, proposal):
        p1 = proposal.model_copy()
        p2 = proposal.model_copy()
        p1.id = "p1"
        p2.id = "p2"
        p1.expected_benefits = {"phi_recovery": 0.5, "energy_efficiency": 0.5}
        p1.expected_risks = {"safety": 0.01, "regression": 0.01}
        p2.expected_benefits = {}
        p2.expected_risks = {}
        batch = sandbox.run_batch([p1, p2], "phi_regression")
        assert batch.verdict == "has_accepted"
        assert batch.best_proposal_id is not None

    def test_batch_verdict_all_rejected(self, sandbox, proposal):
        p1 = proposal.model_copy()
        p2 = proposal.model_copy()
        p1.id = "p1"
        p2.id = "p2"
        p1.expected_benefits = {}
        p1.expected_risks = {}
        p2.expected_benefits = {}
        p2.expected_risks = {}
        batch = sandbox.run_batch([p1, p2], "phi_regression")
        assert batch.verdict == "all_rejected"

    def test_clone_state_with_none_circuit(self):
        orch = FakeOrchestrator()
        orch.circuit = None
        sb = CounterfactualArchitectureSandbox(orchestrator=orch)
        state = sb.clone_orchestrator_state()
        assert "circuit_neuron_count" not in state

    def test_clone_state_with_none_memory(self):
        orch = FakeOrchestrator()
        orch.memory = None
        sb = CounterfactualArchitectureSandbox(orchestrator=orch)
        state = sb.clone_orchestrator_state()
        assert "memory_event_count" not in state

    def test_run_scenario_with_none_regression_guard(self, sandbox, proposal):
        sandbox.regression_guard = None
        result = sandbox.run_scenario(proposal, "phi_regression")
        assert result.verdict in {"accept", "reject", "needs_more_evidence", "unsafe"}

    def test_apply_proposal_does_not_mutate_original(self, sandbox, proposal):
        state = sandbox.clone_orchestrator_state()
        result = sandbox.apply_proposal_counterfactually(state, proposal)
        assert "applied_changes" in result
        assert "applied_changes" not in state
