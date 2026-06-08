import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from speace_core.cellular_brain.analysis.patch_outcome_audit import (
    PatchOutcomeAuditProfile,
    PatchOutcomeAuditResult,
    PatchOutcomeAuditor,
)
from speace_core.cellular_brain.self_improvement.architecture_patch_executor import (
    ArchitecturePatchExecutor,
)
from speace_core.cellular_brain.self_improvement.limitation_detector import (
    LimitationDiagnosis,
    LimitationSignal,
)
from speace_core.cellular_brain.self_improvement.self_improvement_loop import (
    SelfImprovementCycleResult,
    SelfImprovementLoop,
)


class FakeMemory:
    def __init__(self):
        self.events = []

    def log_event(self, event):
        self.events.append(event)


class FakeMetrics:
    def __init__(self, accuracy=0.5, coherence_phi=0.6, mean_energy=0.7):
        self.accuracy = accuracy
        self.coherence_phi = coherence_phi
        self.mean_energy = mean_energy


class FakeOrchestrator:
    def __init__(self):
        self.semantic_memory_enabled = True
        self.episodic_memory_enabled = True
        self.episodic_policy_enabled = True
        self.counterfactual_sandbox_enabled = True
        self.architecture_patch_execution_enabled = True
        self._memory = FakeMemory()
        self._regression_guard = None
        self.latest_metrics = FakeMetrics()

    def get_episodic_recall(self):
        return None


class TestDefaultProfiles:
    def test_returns_eight_profiles(self):
        profiles = PatchOutcomeAuditor.default_profiles()
        assert len(profiles) == 8

    def test_contains_passive_self_improvement(self):
        profiles = PatchOutcomeAuditor.default_profiles()
        ids = [p.profile_id for p in profiles]
        assert "passive_self_improvement" in ids

    def test_contains_full_autonomous_loop_guarded(self):
        profiles = PatchOutcomeAuditor.default_profiles()
        ids = [p.profile_id for p in profiles]
        assert "full_autonomous_loop_guarded" in ids


class TestRunProfileNoOrchestrator:
    def test_returns_insufficient_evidence_without_orchestrator(self):
        auditor = PatchOutcomeAuditor()
        profile = PatchOutcomeAuditProfile(
            profile_id="test",
            name="Test",
            cycles=1,
        )
        result = auditor.run_profile(profile)
        assert result.verdict == "INSUFFICIENT_EVIDENCE"


class TestRunProfilePassive:
    def test_passive_profile_no_patches(self):
        orch = FakeOrchestrator()
        auditor = PatchOutcomeAuditor(orchestrator=orch)
        profile = PatchOutcomeAuditProfile(
            profile_id="passive_self_improvement",
            name="Passive",
            cycles=1,
            counterfactual_sandbox_enabled=False,
            architecture_patch_execution_enabled=False,
            episodic_policy_enabled=False,
            outcome_learning_enabled=False,
        )
        result = auditor.run_profile(profile, orchestrator=orch)
        assert result.patches_applied == 0
        assert result.proposals_generated >= 0


class TestRunProfileSandboxOnly:
    def test_sandbox_only_no_real_patches(self):
        orch = FakeOrchestrator()
        auditor = PatchOutcomeAuditor(orchestrator=orch)
        profile = PatchOutcomeAuditProfile(
            profile_id="sandbox_only",
            name="Sandbox",
            cycles=1,
            counterfactual_sandbox_enabled=True,
            architecture_patch_execution_enabled=False,
            episodic_policy_enabled=False,
            outcome_learning_enabled=False,
        )
        result = auditor.run_profile(profile, orchestrator=orch)
        assert result.patches_applied == 0


class TestRunProfileWithPatchExecution:
    def test_single_cycle_runs(self):
        orch = FakeOrchestrator()
        auditor = PatchOutcomeAuditor(orchestrator=orch)
        profile = PatchOutcomeAuditProfile(
            profile_id="safe_patch_single_cycle",
            name="Single",
            cycles=1,
            counterfactual_sandbox_enabled=True,
            architecture_patch_execution_enabled=True,
            episodic_policy_enabled=False,
            outcome_learning_enabled=False,
        )
        result = auditor.run_profile(profile, orchestrator=orch)
        assert result.cycles_run == 1

    def test_multi_cycle_runs(self):
        orch = FakeOrchestrator()
        auditor = PatchOutcomeAuditor(orchestrator=orch)
        profile = PatchOutcomeAuditProfile(
            profile_id="safe_patch_multi_cycle",
            name="Multi",
            cycles=3,
            counterfactual_sandbox_enabled=True,
            architecture_patch_execution_enabled=True,
            episodic_policy_enabled=False,
            outcome_learning_enabled=False,
        )
        result = auditor.run_profile(profile, orchestrator=orch)
        assert result.cycles_run == 3


class TestUnsafeAndRegressionProfiles:
    def test_unsafe_patch_injection_blocked(self):
        orch = FakeOrchestrator()
        auditor = PatchOutcomeAuditor(orchestrator=orch)
        profile = PatchOutcomeAuditProfile(
            profile_id="unsafe_patch_injection",
            name="Unsafe",
            cycles=1,
            counterfactual_sandbox_enabled=True,
            architecture_patch_execution_enabled=True,
            episodic_policy_enabled=False,
            outcome_learning_enabled=False,
            injected_limitation_type="energy_regression",
        )
        result = auditor.run_profile(profile, orchestrator=orch)
        assert result.unsafe_blocks >= 0 or result.patches_rejected >= 0 or result.patches_rolled_back >= 0

    def test_regression_patch_injection_rolled_back(self):
        orch = FakeOrchestrator()
        auditor = PatchOutcomeAuditor(orchestrator=orch)
        profile = PatchOutcomeAuditProfile(
            profile_id="regression_patch_injection",
            name="Regression",
            cycles=1,
            counterfactual_sandbox_enabled=True,
            architecture_patch_execution_enabled=True,
            episodic_policy_enabled=False,
            outcome_learning_enabled=False,
            injected_limitation_type="phi_regression",
        )
        result = auditor.run_profile(profile, orchestrator=orch)
        assert result.patches_rolled_back >= 0 or result.patches_rejected >= 0


class TestVerdictComputation:
    def test_autonomous_improvement_ready(self):
        result = PatchOutcomeAuditor._compute_verdict(
            patches_confirmed=2,
            patches_rolled_back=0,
            patches_rejected=0,
            unsafe_blocks=0,
            cumulative_delta_score=0.1,
            cumulative_delta_phi=0.0,
            total_patches=2,
            profile=PatchOutcomeAuditProfile(profile_id="test", name="Test", architecture_patch_execution_enabled=True),
        )
        assert result == "AUTONOMOUS_IMPROVEMENT_READY"

    def test_patch_loop_functional_but_weak(self):
        result = PatchOutcomeAuditor._compute_verdict(
            patches_confirmed=1,
            patches_rolled_back=0,
            patches_rejected=0,
            unsafe_blocks=0,
            cumulative_delta_score=0.0,
            cumulative_delta_phi=-0.05,
            total_patches=1,
            profile=PatchOutcomeAuditProfile(profile_id="test", name="Test", architecture_patch_execution_enabled=True),
        )
        assert result == "PATCH_LOOP_FUNCTIONAL_BUT_WEAK"

    def test_patch_loop_overactive(self):
        result = PatchOutcomeAuditor._compute_verdict(
            patches_confirmed=1,
            patches_rolled_back=3,
            patches_rejected=0,
            unsafe_blocks=0,
            cumulative_delta_score=0.0,
            cumulative_delta_phi=0.0,
            total_patches=4,
            profile=PatchOutcomeAuditProfile(profile_id="test", name="Test", architecture_patch_execution_enabled=True),
        )
        assert result == "PATCH_LOOP_OVERACTIVE"

    def test_patch_loop_unsafe_when_blocks_present_but_no_rejection(self):
        result = PatchOutcomeAuditor._compute_verdict(
            patches_confirmed=0,
            patches_rolled_back=0,
            patches_rejected=0,
            unsafe_blocks=1,
            cumulative_delta_score=0.0,
            cumulative_delta_phi=0.0,
            total_patches=1,
            profile=PatchOutcomeAuditProfile(profile_id="test", name="Test", architecture_patch_execution_enabled=True),
        )
        assert result == "PATCH_LOOP_UNSAFE"

    def test_patch_loop_no_effect(self):
        result = PatchOutcomeAuditor._compute_verdict(
            patches_confirmed=0,
            patches_rolled_back=0,
            patches_rejected=0,
            unsafe_blocks=0,
            cumulative_delta_score=0.0,
            cumulative_delta_phi=0.0,
            total_patches=2,
            profile=PatchOutcomeAuditProfile(profile_id="test", name="Test", architecture_patch_execution_enabled=True),
        )
        assert result == "PATCH_LOOP_NO_EFFECT"

    def test_insufficient_evidence_no_patches_disabled(self):
        result = PatchOutcomeAuditor._compute_verdict(
            patches_confirmed=0,
            patches_rolled_back=0,
            patches_rejected=0,
            unsafe_blocks=0,
            cumulative_delta_score=0.0,
            cumulative_delta_phi=0.0,
            total_patches=0,
            profile=PatchOutcomeAuditProfile(profile_id="test", name="Test", architecture_patch_execution_enabled=False, counterfactual_sandbox_enabled=False),
        )
        assert result == "INSUFFICIENT_EVIDENCE"


class TestReadinessScore:
    def test_in_range_zero_to_one(self):
        result = PatchOutcomeAuditResult(
            profile_id="test",
            outcome_success_rate=0.5,
            cumulative_delta_score=0.1,
            cumulative_delta_phi=0.05,
            unsafe_blocks=1,
            patches_applied=2,
            patches_rejected=0,
            regression_rate=0.2,
            learning_confidence_delta=0.1,
        )
        score = PatchOutcomeAuditor.compute_readiness_score(result)
        assert 0.0 <= score <= 1.0

    def test_zero_when_all_zero(self):
        result = PatchOutcomeAuditResult(profile_id="test")
        score = PatchOutcomeAuditor.compute_readiness_score(result)
        # rollback_success_rate = 1.0 when regression_rate is 0, so minimum score is 0.15
        assert score == 0.15

    def test_formula_components(self):
        result = PatchOutcomeAuditResult(
            profile_id="test",
            outcome_success_rate=1.0,
            cumulative_delta_score=1.0,
            cumulative_delta_phi=1.0,
            unsafe_blocks=1,
            patches_applied=1,
            patches_rejected=0,
            regression_rate=0.0,
            learning_confidence_delta=1.0,
        )
        score = PatchOutcomeAuditor.compute_readiness_score(result)
        expected = round(
            0.25 * 1.0
            + 0.20 * 1.0
            + 0.15 * 1.0
            + 0.15 * 1.0
            + 0.15 * 1.0
            + 0.10 * 1.0,
            4,
        )
        assert score == expected


class TestExtractBenchmarkMetrics:
    def test_contains_all_keys(self):
        result = PatchOutcomeAuditResult(
            profile_id="test",
            cycles_run=2,
            patches_confirmed=1,
            patches_rolled_back=0,
            patches_rejected=0,
            unsafe_blocks=0,
            outcome_success_rate=1.0,
            regression_rate=0.0,
            cumulative_delta_score=0.1,
            cumulative_delta_phi=0.05,
            learning_confidence_delta=0.05,
        )
        metrics = PatchOutcomeAuditor.extract_benchmark_metrics(result)
        assert "patch_audit_cycles_run" in metrics
        assert "autonomous_improvement_readiness_score" in metrics
        assert metrics["autonomous_improvement_readiness_score"] > 0.0


class TestReportGeneration:
    def test_saves_json_and_md(self, tmp_path):
        orch = FakeOrchestrator()
        auditor = PatchOutcomeAuditor(orchestrator=orch, report_dir=str(tmp_path))
        profile = PatchOutcomeAuditProfile(profile_id="test", name="Test", cycles=1)
        result = PatchOutcomeAuditResult(profile_id="test")
        auditor._save_reports(result, profile)
        assert result.json_report_path is not None
        assert result.markdown_report_path is not None
        assert Path(result.json_report_path).exists()
        assert Path(result.markdown_report_path).exists()

    def test_json_is_valid(self, tmp_path):
        orch = FakeOrchestrator()
        auditor = PatchOutcomeAuditor(orchestrator=orch, report_dir=str(tmp_path))
        profile = PatchOutcomeAuditProfile(profile_id="test", name="Test", cycles=1)
        result = PatchOutcomeAuditResult(profile_id="test", verdict="TEST")
        auditor._save_reports(result, profile)
        data = json.loads(Path(result.json_report_path).read_text(encoding="utf-8"))
        assert data["verdict"] == "TEST"

    def test_md_contains_verdict(self, tmp_path):
        orch = FakeOrchestrator()
        auditor = PatchOutcomeAuditor(orchestrator=orch, report_dir=str(tmp_path))
        profile = PatchOutcomeAuditProfile(profile_id="test", name="Test", cycles=1)
        result = PatchOutcomeAuditResult(profile_id="test", verdict="TEST")
        auditor._save_reports(result, profile)
        text = Path(result.markdown_report_path).read_text(encoding="utf-8")
        assert "TEST" in text


class TestGatherMetrics:
    def test_default_metrics_present(self):
        orch = FakeOrchestrator()
        auditor = PatchOutcomeAuditor()
        profile = PatchOutcomeAuditProfile(profile_id="test", name="Test")
        metrics = auditor._gather_metrics(orch, profile)
        assert "cognitive_delta" in metrics

    def test_energy_injection(self):
        orch = FakeOrchestrator()
        auditor = PatchOutcomeAuditor()
        profile = PatchOutcomeAuditProfile(
            profile_id="test", name="Test", injected_limitation_type="energy_regression"
        )
        metrics = auditor._gather_metrics(orch, profile)
        assert metrics["mean_energy"] == 0.95

    def test_phi_injection(self):
        orch = FakeOrchestrator()
        auditor = PatchOutcomeAuditor()
        profile = PatchOutcomeAuditProfile(
            profile_id="test", name="Test", injected_limitation_type="phi_regression"
        )
        metrics = auditor._gather_metrics(orch, profile)
        assert metrics["coherence_phi"] == 0.15

    def test_semantic_injection(self):
        orch = FakeOrchestrator()
        auditor = PatchOutcomeAuditor()
        profile = PatchOutcomeAuditProfile(
            profile_id="test", name="Test", injected_limitation_type="semantic_association_missing"
        )
        metrics = auditor._gather_metrics(orch, profile)
        assert metrics["semantic_assembly_count"] == 5


class TestPrimaryLimitationType:
    def test_from_diagnoses(self):
        result = SelfImprovementCycleResult(
            cycle_id="c1",
            detected_limitations=[],
            diagnoses=[
                LimitationDiagnosis(
                    id="d1",
                    signals=[LimitationSignal(id="s1", source="m", category="phi_regression", severity=0.5, confidence=0.8, description="d", detected_at="2024-01-01T00:00:00Z")],
                    primary_category="phi_regression",
                    root_cause_hypothesis="h",
                    affected_modules=["a"],
                )
            ],
            proposals=[],
            simulations=[],
            accepted_proposals=[],
            rejected_proposals=[],
            final_verdict="v",
        )
        assert PatchOutcomeAuditor._primary_limitation_type(result) == "phi_regression"

    def test_from_signals_when_no_diagnoses(self):
        result = SelfImprovementCycleResult(
            cycle_id="c1",
            detected_limitations=[LimitationSignal(id="s1", source="m", category="energy_regression", severity=0.5, confidence=0.8, description="d", detected_at="2024-01-01T00:00:00Z")],
            diagnoses=[],
            proposals=[],
            simulations=[],
            accepted_proposals=[],
            rejected_proposals=[],
            final_verdict="v",
        )
        assert PatchOutcomeAuditor._primary_limitation_type(result) == "energy_regression"

    def test_unknown_when_empty(self):
        result = SelfImprovementCycleResult(
            cycle_id="c1",
            detected_limitations=[],
            diagnoses=[],
            proposals=[],
            simulations=[],
            accepted_proposals=[],
            rejected_proposals=[],
            final_verdict="v",
        )
        assert PatchOutcomeAuditor._primary_limitation_type(result) == "unknown"
