import json
import pytest
from unittest.mock import MagicMock, PropertyMock

from speace_core.cellular_brain.self_improvement.architecture_patch_executor import (
    ArchitecturePatch,
    ArchitecturePatchExecutor,
    PatchExecutionResult,
)
from speace_core.cellular_brain.self_improvement.architecture_rewriter import (
    ArchitectureRewriteProposal,
)
from speace_core.cellular_brain.memory.morphology_events import (
    MorphologyEvent,
    MorphologyEventType,
)


class FakeMetrics:
    def __init__(self, accuracy=0.5, coherence_phi=0.6, mean_energy=0.7):
        self.accuracy = accuracy
        self.coherence_phi = coherence_phi
        self.mean_energy = mean_energy


class FakeOrchestrator:
    def __init__(self):
        self.semantic_memory_enabled = False
        self.associative_memory_enabled = False
        self.episodic_policy_enabled = False
        self.counterfactual_sandbox_enabled = False
        self.brainstem_controller_enabled = False
        self.region_stability_controller_enabled = False
        self.architecture_patch_execution_enabled = False
        self.learning_rate = 0.01
        self.plasticity_rate = 0.02
        self.decay_rate = 0.001
        self.routing_gain = 1.0
        self.inhibition_decay = 0.5
        self.semantic_similarity_threshold = 0.7
        self.assembly_consolidation_threshold = 0.8
        self.latest_metrics = FakeMetrics()


class FakeMemory:
    def __init__(self):
        self.events = []

    def log_event(self, event):
        self.events.append(event)


class FakeRegressionGuardSafe:
    def evaluate(self, delta_metrics):
        result = MagicMock()
        result.verdict = "POLICY_SAFE"
        return result


class FakeRegressionGuardUnsafe:
    def evaluate(self, delta_metrics):
        result = MagicMock()
        result.verdict = "POLICY_UNSAFE"
        return result


class FakeSnapshotStore:
    def __init__(self):
        self._store = {}

    def save_snapshot(self, snapshot):
        self._store[snapshot.patch_id] = snapshot
        import pathlib
        return pathlib.Path("fake")

    def load_snapshot(self, patch_id):
        return self._store.get(patch_id)


@pytest.fixture
def proposal():
    return ArchitectureRewriteProposal(
        id="prop-test",
        diagnosis_id="diag-test",
        title="Test Proposal",
        proposal_type="parameter_tuning",
        target_modules=["stdp_plasticity_engine"],
        rationale="Test rationale",
        expected_benefits={"phi_recovery": 0.3, "energy_efficiency": 0.2},
        expected_risks={"safety": 0.05, "regression": 0.1},
        implementation_plan=["Step 1"],
        rollback_plan=["Revert"],
        safety_constraints=["No core mutation"],
        created_at="2024-01-01T00:00:00Z",
    )


@pytest.fixture
def executor():
    orch = FakeOrchestrator()
    mem = FakeMemory()
    store = FakeSnapshotStore()
    return ArchitecturePatchExecutor(
        orchestrator=orch,
        benchmark=None,
        regression_guard=FakeRegressionGuardSafe(),
        snapshot_store=store,
        memory=mem,
    )


class TestBuildPatchFromProposal:
    def test_builds_patch_from_parameter_tuning(self, executor, proposal):
        patch = executor.build_patch_from_proposal(proposal)
        assert patch.patch_id.startswith("patch-")
        assert patch.proposal_id == "prop-test"
        assert patch.patch_type == "flag"
        assert patch.target_path == "plasticity_rate"
        assert patch.operation == "scale"

    def test_builds_patch_from_module_addition(self, executor, proposal):
        proposal.proposal_type = "module_addition"
        proposal.target_modules = ["routing_profile"]
        patch = executor.build_patch_from_proposal(proposal)
        assert patch.patch_type == "profile_select"
        assert patch.operation == "enable"

    def test_builds_patch_from_routing_redesign(self, executor, proposal):
        proposal.proposal_type = "routing_redesign"
        proposal.target_modules = ["region_signal_router"]
        patch = executor.build_patch_from_proposal(proposal)
        assert patch.patch_type == "profile_select"

    def test_infer_target_path_energy(self, executor, proposal):
        proposal.target_modules = ["energy_control"]
        patch = executor.build_patch_from_proposal(proposal)
        assert patch.target_path == "energy_control_enabled"

    def test_infer_target_path_routing(self, executor, proposal):
        proposal.target_modules = ["region_signal_router"]
        patch = executor.build_patch_from_proposal(proposal)
        assert patch.target_path == "region_signal_routing_enabled"

    def test_infer_target_path_stability(self, executor, proposal):
        proposal.target_modules = ["region_stability_controller"]
        patch = executor.build_patch_from_proposal(proposal)
        assert patch.target_path == "region_stability_controller_enabled"

    def test_infer_target_path_brainstem(self, executor, proposal):
        proposal.target_modules = ["brainstem_controller"]
        patch = executor.build_patch_from_proposal(proposal)
        assert patch.target_path == "brainstem_controller_enabled"

    def test_infer_target_path_plasticity(self, executor, proposal):
        proposal.target_modules = ["stdp_plasticity_engine"]
        proposal.proposal_type = "parameter_tuning"
        patch = executor.build_patch_from_proposal(proposal)
        assert patch.target_path == "plasticity_rate"
        assert patch.operation == "scale"

    def test_infer_new_value_from_benefits(self, executor, proposal):
        patch = executor.build_patch_from_proposal(proposal)
        assert patch.new_value == 0.3

    def test_infer_new_value_defaults_true(self, executor, proposal):
        proposal.expected_benefits = {}
        patch = executor.build_patch_from_proposal(proposal)
        assert patch.new_value is True

    def test_safety_class_low_for_flag(self, executor, proposal):
        patch = executor.build_patch_from_proposal(proposal)
        assert patch.safety_class == "low"

    def test_safety_class_medium_for_profile(self, executor, proposal):
        proposal.proposal_type = "module_addition"
        patch = executor.build_patch_from_proposal(proposal)
        assert patch.safety_class == "medium"


class TestValidatePatchSafety:
    def test_validates_set_on_allowed_flag(self, executor):
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="semantic_memory_enabled",
            operation="set", new_value=True,
        )
        assert executor.validate_patch_safety(patch) is True

    def test_validates_scale_on_allowed_numeric(self, executor):
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="numeric", target_path="learning_rate",
            operation="scale", new_value=1.2,
        )
        assert executor.validate_patch_safety(patch) is True

    def test_validates_enable_on_allowed_flag(self, executor):
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="brainstem_controller_enabled",
            operation="enable", new_value=True,
        )
        assert executor.validate_patch_safety(patch) is True

    def test_validates_disable_on_allowed_flag(self, executor):
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="region_stability_controller_enabled",
            operation="disable", new_value=False,
        )
        assert executor.validate_patch_safety(patch) is True

    def test_validates_profile_select(self, executor):
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="profile", target_path="routing_profile",
            operation="profile_select", new_value="profile_v2",
        )
        assert executor.validate_patch_safety(patch) is True

    def test_rejects_unknown_target(self, executor):
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="unknown_flag",
            operation="set", new_value=True,
        )
        assert executor.validate_patch_safety(patch) is False

    def test_rejects_unsafe_safety_class(self, executor):
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="unknown_target",
            operation="set", new_value=True, safety_class="high",
        )
        assert executor.validate_patch_safety(patch) is False

    def test_rejects_unknown_operation(self, executor):
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="semantic_memory_enabled",
            operation="delete", new_value=True,
        )
        assert executor.validate_patch_safety(patch) is False


class TestCreatePrePatchSnapshot:
    def test_creates_snapshot(self, executor):
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="semantic_memory_enabled",
            operation="set", new_value=True,
        )
        # Set benchmark to orchestrator so baseline is captured
        executor.benchmark = executor.orchestrator
        snapshot = executor.create_pre_patch_snapshot(patch)
        assert snapshot.patch_id == "p1"
        assert "semantic_memory_enabled" in snapshot.orchestrator_flags
        assert snapshot.orchestrator_flags["semantic_memory_enabled"] is False
        assert "accuracy" in snapshot.benchmark_baseline

    def test_snapshot_logs_event(self, executor):
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="semantic_memory_enabled",
            operation="set", new_value=True,
        )
        executor.create_pre_patch_snapshot(patch)
        assert any(
            e.event_type == MorphologyEventType.ARCHITECTURE_PATCH_SNAPSHOT_CREATED
            for e in executor.memory.events
        )

    def test_snapshot_without_orchestrator(self):
        store = FakeSnapshotStore()
        ex = ArchitecturePatchExecutor(snapshot_store=store)
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="semantic_memory_enabled",
            operation="set", new_value=True,
        )
        snapshot = ex.create_pre_patch_snapshot(patch)
        assert snapshot.orchestrator_flags == {}
        assert snapshot.benchmark_baseline == {}


class TestApplyPatch:
    def test_apply_set(self, executor):
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="semantic_memory_enabled",
            operation="set", new_value=True,
        )
        assert executor.apply_patch(patch) is True
        assert executor.orchestrator.semantic_memory_enabled is True

    def test_apply_scale(self, executor):
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="numeric", target_path="learning_rate",
            operation="scale", new_value=2.0,
        )
        assert executor.apply_patch(patch) is True
        assert executor.orchestrator.learning_rate == 0.02

    def test_apply_enable(self, executor):
        executor.orchestrator.semantic_memory_enabled = False
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="semantic_memory_enabled",
            operation="enable", new_value=True,
        )
        assert executor.apply_patch(patch) is True
        assert executor.orchestrator.semantic_memory_enabled is True

    def test_apply_disable(self, executor):
        executor.orchestrator.semantic_memory_enabled = True
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="semantic_memory_enabled",
            operation="disable", new_value=False,
        )
        assert executor.apply_patch(patch) is True
        assert executor.orchestrator.semantic_memory_enabled is False

    def test_apply_profile_select(self, executor):
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="profile", target_path="routing_profile",
            operation="profile_select", new_value="v2",
        )
        assert executor.apply_patch(patch) is True
        assert executor.orchestrator.routing_profile == "v2"

    def test_apply_fails_without_orchestrator(self):
        ex = ArchitecturePatchExecutor()
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="semantic_memory_enabled",
            operation="set", new_value=True,
        )
        assert ex.apply_patch(patch) is False

    def test_apply_fails_invalid_target(self, executor):
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="nonexistent_target",
            operation="set", new_value=True,
        )
        assert executor.apply_patch(patch) is False

    def test_apply_scale_fails_on_non_numeric(self, executor):
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="numeric", target_path="semantic_memory_enabled",
            operation="scale", new_value=2.0,
        )
        assert executor.apply_patch(patch) is False

    def test_apply_enable_fails_on_non_bool(self, executor):
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="learning_rate",
            operation="enable", new_value=True,
        )
        assert executor.apply_patch(patch) is False


class TestPostPatchValidation:
    def test_confirmed_on_improvement(self, executor):
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="semantic_memory_enabled",
            operation="set", new_value=True,
        )
        snapshot = executor.create_pre_patch_snapshot(patch)
        executor.orchestrator.latest_metrics = FakeMetrics(
            accuracy=0.6, coherence_phi=0.7, mean_energy=0.8
        )
        result = executor.run_post_patch_validation(patch)
        assert result.verdict == "PATCH_CONFIRMED"
        assert result.confirmed is True
        assert result.rolled_back is False

    def test_rolled_back_on_score_regression(self, executor):
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="semantic_memory_enabled",
            operation="set", new_value=True,
        )
        executor.benchmark = executor.orchestrator
        # Baseline metrics
        executor.orchestrator.latest_metrics = FakeMetrics(
            accuracy=0.5, coherence_phi=0.6, mean_energy=0.7
        )
        snapshot = executor.create_pre_patch_snapshot(patch)
        # Post-patch metrics regressed
        executor.orchestrator.latest_metrics = FakeMetrics(
            accuracy=0.3, coherence_phi=0.6, mean_energy=0.7
        )
        result = executor.run_post_patch_validation(patch)
        assert result.verdict == "PATCH_ROLLED_BACK"
        assert "SCORE_REGRESSION" in result.regression_flags

    def test_rolled_back_on_phi_regression(self, executor):
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="semantic_memory_enabled",
            operation="set", new_value=True,
        )
        executor.benchmark = executor.orchestrator
        executor.orchestrator.latest_metrics = FakeMetrics(
            accuracy=0.5, coherence_phi=0.6, mean_energy=0.7
        )
        snapshot = executor.create_pre_patch_snapshot(patch)
        executor.orchestrator.latest_metrics = FakeMetrics(
            accuracy=0.5, coherence_phi=0.4, mean_energy=0.7
        )
        result = executor.run_post_patch_validation(patch)
        assert result.verdict == "PATCH_ROLLED_BACK"
        assert "PHI_REGRESSION" in result.regression_flags

    def test_rolled_back_on_policy_unsafe(self, executor):
        executor.regression_guard = FakeRegressionGuardUnsafe()
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="semantic_memory_enabled",
            operation="set", new_value=True,
        )
        executor.benchmark = executor.orchestrator
        executor.orchestrator.latest_metrics = FakeMetrics(
            accuracy=0.5, coherence_phi=0.6, mean_energy=0.7
        )
        snapshot = executor.create_pre_patch_snapshot(patch)
        executor.orchestrator.latest_metrics = FakeMetrics(
            accuracy=0.5, coherence_phi=0.6, mean_energy=0.7
        )
        result = executor.run_post_patch_validation(patch)
        assert result.verdict == "PATCH_ROLLED_BACK"
        assert "POLICY_UNSAFE" in result.regression_flags

    def test_needs_more_evidence_on_small_deltas(self, executor):
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="semantic_memory_enabled",
            operation="set", new_value=True,
        )
        executor.benchmark = executor.orchestrator
        executor.orchestrator.latest_metrics = FakeMetrics(
            accuracy=0.5, coherence_phi=0.6, mean_energy=0.7
        )
        snapshot = executor.create_pre_patch_snapshot(patch)
        executor.orchestrator.latest_metrics = FakeMetrics(
            accuracy=0.5, coherence_phi=0.6, mean_energy=0.7
        )
        result = executor.run_post_patch_validation(patch)
        assert result.verdict == "PATCH_NEEDS_MORE_EVIDENCE"

    def test_post_patch_without_orchestrator(self):
        store = FakeSnapshotStore()
        ex = ArchitecturePatchExecutor(snapshot_store=store)
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="semantic_memory_enabled",
            operation="set", new_value=True,
        )
        snapshot = MagicMock()
        snapshot.benchmark_baseline = {"accuracy": 0.5, "coherence_phi": 0.6, "mean_energy": 0.7}
        store.save_snapshot(snapshot)
        # Need to link patch_id
        snapshot.patch_id = "p1"
        store._store["p1"] = snapshot
        result = ex.run_post_patch_validation(patch)
        assert result.pre_score == 0.5
        assert result.post_score == 0.0


class TestRollbackPatch:
    def test_rollback_restores_flags(self, executor):
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="semantic_memory_enabled",
            operation="set", new_value=True,
        )
        snapshot = executor.create_pre_patch_snapshot(patch)
        executor.orchestrator.semantic_memory_enabled = True
        assert executor.rollback_patch(patch, snapshot) is True
        assert executor.orchestrator.semantic_memory_enabled is False

    def test_rollback_without_orchestrator(self):
        ex = ArchitecturePatchExecutor()
        patch = ArchitecturePatch(
            patch_id="p1", proposal_id="pr1", limitation_type="test",
            patch_type="flag", target_path="semantic_memory_enabled",
            operation="set", new_value=True,
        )
        snapshot = MagicMock()
        snapshot.orchestrator_flags = {"semantic_memory_enabled": False}
        assert ex.rollback_patch(patch, snapshot) is False


class TestExecutePatch:
    def test_full_pipeline_confirms(self, executor, proposal):
        executor.orchestrator.latest_metrics = FakeMetrics(
            accuracy=0.6, coherence_phi=0.7, mean_energy=0.8
        )
        result = executor.execute_patch(proposal)
        assert result.applied is True
        assert result.confirmed is True
        assert result.verdict == "PATCH_CONFIRMED"
        assert result.report_path is not None

    def test_full_pipeline_rejects_unsafe(self, executor, proposal):
        proposal.target_modules = ["unknown_module"]
        result = executor.execute_patch(proposal)
        assert result.applied is False
        assert result.verdict == "PATCH_REJECTED_UNSAFE"

    def test_full_pipeline_rolls_back(self, executor, proposal):
        # Pre-seed snapshot with baseline metrics
        from speace_core.cellular_brain.self_improvement.patch_snapshot_store import PatchSnapshot
        baseline_snapshot = PatchSnapshot(
            snapshot_id="snap-baseline",
            patch_id="will-be-overwritten",
            timestamp="2024-01-01T00:00:00Z",
            benchmark_baseline={"accuracy": 0.8, "coherence_phi": 0.7, "mean_energy": 0.9},
        )
        original_create = executor.create_pre_patch_snapshot
        def _mocked_create(patch):
            baseline_snapshot.patch_id = patch.patch_id
            executor.snapshot_store.save_snapshot(baseline_snapshot)
            return baseline_snapshot
        executor.create_pre_patch_snapshot = _mocked_create
        executor.orchestrator.latest_metrics = FakeMetrics(
            accuracy=0.3, coherence_phi=0.4, mean_energy=0.2
        )
        result = executor.execute_patch(proposal)
        assert result.applied is True
        assert result.rolled_back is True
        assert result.verdict == "PATCH_ROLLED_BACK"

    def test_execute_logs_events(self, executor, proposal):
        executor.execute_patch(proposal)
        event_types = {e.event_type for e in executor.memory.events}
        assert MorphologyEventType.ARCHITECTURE_PATCH_PROPOSED in event_types
        assert MorphologyEventType.ARCHITECTURE_PATCH_VALIDATED in event_types
        assert MorphologyEventType.ARCHITECTURE_PATCH_APPLIED in event_types

    def test_execute_logs_confirmed_event(self, executor, proposal):
        executor.orchestrator.latest_metrics = FakeMetrics(
            accuracy=0.6, coherence_phi=0.7, mean_energy=0.8
        )
        executor.execute_patch(proposal)
        event_types = {e.event_type for e in executor.memory.events}
        assert MorphologyEventType.ARCHITECTURE_PATCH_CONFIRMED in event_types

    def test_execute_logs_rollback_event(self, executor, proposal):
        from speace_core.cellular_brain.self_improvement.patch_snapshot_store import PatchSnapshot
        baseline_snapshot = PatchSnapshot(
            snapshot_id="snap-baseline",
            patch_id="will-be-overwritten",
            timestamp="2024-01-01T00:00:00Z",
            benchmark_baseline={"accuracy": 0.8, "coherence_phi": 0.7, "mean_energy": 0.9},
        )
        original_create = executor.create_pre_patch_snapshot
        def _mocked_create(patch):
            baseline_snapshot.patch_id = patch.patch_id
            executor.snapshot_store.save_snapshot(baseline_snapshot)
            return baseline_snapshot
        executor.create_pre_patch_snapshot = _mocked_create
        executor.orchestrator.latest_metrics = FakeMetrics(
            accuracy=0.3, coherence_phi=0.4, mean_energy=0.2
        )
        executor.execute_patch(proposal)
        event_types = {e.event_type for e in executor.memory.events}
        assert MorphologyEventType.ARCHITECTURE_PATCH_ROLLED_BACK in event_types

    def test_compute_verdict_confirmed(self):
        assert ArchitecturePatchExecutor._compute_verdict(0.01, 0.0, 0.0, []) == "PATCH_CONFIRMED"
        assert ArchitecturePatchExecutor._compute_verdict(0.0, 0.01, 0.0, []) == "PATCH_CONFIRMED"
        assert ArchitecturePatchExecutor._compute_verdict(0.0, 0.0, 0.01, []) == "PATCH_CONFIRMED"

    def test_compute_verdict_rolled_back(self):
        assert ArchitecturePatchExecutor._compute_verdict(0.01, 0.01, 0.01, ["POLICY_UNSAFE"]) == "PATCH_ROLLED_BACK"
        assert ArchitecturePatchExecutor._compute_verdict(-0.1, 0.0, 0.0, []) == "PATCH_ROLLED_BACK"
        assert ArchitecturePatchExecutor._compute_verdict(0.0, -0.1, 0.0, []) == "PATCH_ROLLED_BACK"
        assert ArchitecturePatchExecutor._compute_verdict(0.0, 0.0, -0.2, []) == "PATCH_ROLLED_BACK"

    def test_compute_verdict_needs_evidence(self):
        assert ArchitecturePatchExecutor._compute_verdict(0.0, 0.0, 0.0, []) == "PATCH_NEEDS_MORE_EVIDENCE"
        assert ArchitecturePatchExecutor._compute_verdict(0.005, -0.01, -0.02, []) == "PATCH_NEEDS_MORE_EVIDENCE"

    def test_compute_verdict_rolled_back_on_negative(self):
        assert ArchitecturePatchExecutor._compute_verdict(-0.01, -0.01, -0.01, []) == "PATCH_ROLLED_BACK"


class TestSaveReport:
    def test_saves_report(self, executor, tmp_path, proposal):
        import speace_core.cellular_brain.self_improvement.architecture_patch_executor as ape_mod
        original_dir = ape_mod.Path
        # Patch reports_dir for test
        report = PatchExecutionResult(
            patch_id="p1", proposal_id="pr1",
            applied=True, confirmed=True, rolled_back=False,
            verdict="PATCH_CONFIRMED", pre_score=0.5, post_score=0.6,
            delta_score=0.1, delta_phi=0.05, delta_energy=0.02,
        )
        path = executor._save_report(
            ArchitecturePatch(patch_id="p1", proposal_id="pr1", limitation_type="test",
                              patch_type="flag", target_path="a", operation="set"),
            report,
        )
        assert path is not None
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["verdict"] == "PATCH_CONFIRMED"
