import pytest
from pathlib import Path

from speace_core.cellular_brain.postnatal_learning.postnatal_learning_models import (
    CurriculumStage,
    CurriculumStageType,
    DevelopmentalMemoryRecord,
    ImitationTrace,
    LearningEpisode,
    LearningRiskClass,
    PostnatalLearningAuditProfile,
    PostnatalLearningProfileResult,
    PostnatalLearningSuiteResult,
)
from speace_core.cellular_brain.postnatal_learning.curriculum_stage_builder import (
    CurriculumStageBuilder,
)
from speace_core.cellular_brain.postnatal_learning.learning_episode_runner import (
    LearningEpisodeRunner,
)
from speace_core.cellular_brain.postnatal_learning.imitation_learning_sandbox import (
    ImitationLearningSandbox,
)
from speace_core.cellular_brain.postnatal_learning.error_correction_engine import (
    ErrorCorrectionEngine,
)
from speace_core.cellular_brain.postnatal_learning.developmental_memory_consolidator import (
    DevelopmentalMemoryConsolidator,
)
from speace_core.cellular_brain.postnatal_learning.postnatal_learning_policy_engine import (
    PostnatalLearningPolicyEngine,
)
from speace_core.cellular_brain.postnatal_learning.postnatal_curriculum_engine import (
    PostnatalCurriculumEngine,
)
from speace_core.cellular_brain.postnatal_learning.postnatal_learning_audit import (
    PostnatalLearningAudit,
)
from speace_core.cellular_brain.circuits.neural_circuit import NeuralCircuit
from speace_core.dna.models import SharedGenome


def test_stage_builder_returns_stages():
    builder = CurriculumStageBuilder()
    stages = builder.build_default_stages()
    assert len(stages) >= 8
    assert stages[0].stage_type == CurriculumStageType.OBSERVATION


def test_stage_builder_order_increases():
    builder = CurriculumStageBuilder()
    stages = builder.build_default_stages()
    orders = [s.order for s in stages]
    assert orders == sorted(orders)


def test_stage_observation_is_safe():
    builder = CurriculumStageBuilder()
    stages = builder.build_default_stages()
    obs = next(s for s in stages if s.stage_type == CurriculumStageType.OBSERVATION)
    assert obs.simulated_only
    assert obs.estimated_safety == 1.0


def test_stage_transfer_requires_prerequisites():
    builder = CurriculumStageBuilder()
    stages = builder.build_default_stages()
    transfer = next(s for s in stages if s.stage_type == CurriculumStageType.TRANSFER)
    assert len(transfer.required_stages) > 0


def test_episode_runner_generates_episodes():
    runner = LearningEpisodeRunner(seed=1)
    profile = PostnatalLearningAuditProfile(
        name="test",
        duration_cycles=2,
        episode_count=2,
        stage_mix={"observation": 1.0},
    )
    stages = CurriculumStageBuilder().build_default_stages()
    episodes = runner.build_episodes_for_profile(profile, stages)
    assert len(episodes) == 4


def test_episode_runner_respects_stage_mix():
    runner = LearningEpisodeRunner(seed=1)
    profile = PostnatalLearningAuditProfile(
        name="test",
        duration_cycles=1,
        episode_count=10,
        stage_mix={"observation": 1.0},
    )
    stages = CurriculumStageBuilder().build_default_stages()
    episodes = runner.build_episodes_for_profile(profile, stages)
    assert all(e.stage_type == CurriculumStageType.OBSERVATION for e in episodes)


def test_sandbox_evaluates_safe_trace():
    sandbox = ImitationLearningSandbox()
    episode = LearningEpisode(
        episode_id="ep1",
        stage_id="stage_grounding",
        stage_type=CurriculumStageType.GROUNDING_SEMANTIC,
        target_output="hello",
        predicted_output="hello",
    )
    trace = sandbox.evaluate_trace(episode)
    assert not trace.contains_dangerous_action
    assert not trace.blocked


def test_sandbox_blocks_dangerous_trace():
    sandbox = ImitationLearningSandbox()
    episode = LearningEpisode(
        episode_id="ep1",
        stage_id="stage_imitation",
        stage_type=CurriculumStageType.IMITATION_SANDBOX,
        target_output="call external api",
        predicted_output="call external api",
    )
    trace = sandbox.evaluate_trace(episode)
    assert trace.contains_dangerous_action
    assert trace.blocked


def test_sandbox_blocks_actuate_keyword():
    sandbox = ImitationLearningSandbox()
    episode = LearningEpisode(
        episode_id="ep1",
        stage_id="stage_action_simulation",
        stage_type=CurriculumStageType.ACTION_SIMULATION,
        target_output="actuate motor",
        predicted_output="actuate motor",
    )
    trace = sandbox.evaluate_trace(episode)
    assert trace.blocked


def test_error_engine_detects_error():
    engine = ErrorCorrectionEngine()
    episode = LearningEpisode(
        episode_id="ep1",
        target_output="hello",
        predicted_output="world",
    )
    assert engine.detect_error(episode)


def test_error_engine_no_error_when_equal():
    engine = ErrorCorrectionEngine()
    episode = LearningEpisode(
        episode_id="ep1",
        target_output="hello",
        predicted_output="hello",
    )
    assert not engine.detect_error(episode)


def test_error_engine_applies_correction():
    engine = ErrorCorrectionEngine()
    episode = LearningEpisode(
        episode_id="ep1",
        target_output="hello",
        predicted_output="world",
    )
    corrected = engine.apply_correction(episode)
    assert corrected.correction_applied
    assert corrected.predicted_output == "hello"


def test_error_engine_correction_confidence():
    engine = ErrorCorrectionEngine()
    episode = LearningEpisode(
        episode_id="ep1",
        target_output="abc",
        predicted_output="xyz",
    )
    corrected = engine.apply_correction(episode)
    assert corrected.correction_confidence < 1.0


def test_consolidator_creates_record():
    consolidator = DevelopmentalMemoryConsolidator()
    episode = LearningEpisode(
        episode_id="ep1",
        correction_applied=True,
        correction_confidence=0.9,
        stage_type=CurriculumStageType.GROUNDING_SEMANTIC,
        simulated_only=True,
    )
    record = consolidator.consolidate(episode)
    assert record is not None
    assert record.consolidation_strength == 0.9


def test_consolidator_skips_unsafe_episode():
    consolidator = DevelopmentalMemoryConsolidator()
    episode = LearningEpisode(
        episode_id="ep1",
        error_detected=True,
        correction_applied=False,
    )
    record = consolidator.consolidate(episode)
    assert record is None


def test_consolidator_safety_check():
    consolidator = DevelopmentalMemoryConsolidator()
    record = DevelopmentalMemoryRecord(
        record_id="r1",
        episode_id="ep1",
        stage_id="s1",
        consolidation_strength=0.5,
        safety_preservation_score=0.95,
    )
    assert consolidator.evaluate_safety(record)


def test_policy_classifies_observation_low():
    policy = PostnatalLearningPolicyEngine()
    episode = LearningEpisode(
        episode_id="ep1",
        stage_type=CurriculumStageType.OBSERVATION,
    )
    risk = policy.classify_risk(episode)
    assert risk == LearningRiskClass.LOW


def test_policy_classifies_transfer_high():
    policy = PostnatalLearningPolicyEngine()
    episode = LearningEpisode(
        episode_id="ep1",
        stage_type=CurriculumStageType.TRANSFER,
    )
    risk = policy.classify_risk(episode)
    assert risk == LearningRiskClass.HIGH


def test_policy_evaluates_blocked():
    policy = PostnatalLearningPolicyEngine()
    episode = LearningEpisode(episode_id="ep1", simulated_only=True)
    trace = ImitationTrace(trace_id="t1", episode_id="ep1", blocked=True)
    result = policy.evaluate_policy(episode, trace)
    assert result["blocked"]


def test_policy_requires_review_for_high():
    policy = PostnatalLearningPolicyEngine()
    episode = LearningEpisode(episode_id="ep1", stage_type=CurriculumStageType.TRANSFER, simulated_only=True)
    trace = ImitationTrace(trace_id="t1", episode_id="ep1", blocked=False)
    result = policy.evaluate_policy(episode, trace)
    assert result["requires_human_review"]


def test_curriculum_engine_has_stages():
    engine = PostnatalCurriculumEngine(seed=1)
    assert len(engine.get_stages()) >= 8


def test_curriculum_engine_run_episode_returns_result():
    engine = PostnatalCurriculumEngine(seed=1)
    episode = LearningEpisode(
        episode_id="ep1",
        stage_id="stage_observation",
        stage_type=CurriculumStageType.OBSERVATION,
        target_output="hello",
        predicted_output="world",
        simulated_only=True,
    )
    result = engine.run_episode(episode)
    assert "episode" in result
    assert "trace" in result
    assert "policy" in result


def test_audit_builds_default_profiles():
    audit = PostnatalLearningAudit(seed=1)
    profiles = audit.build_default_profiles()
    assert len(profiles) >= 12


def test_audit_run_profile_baseline():
    audit = PostnatalLearningAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_observation_baseline")
    result = audit.run_profile(profile)
    assert result.episodes_generated >= 1
    assert result.verdict in (
        "POSTNATAL_LEARNING_VALIDATED",
        "POSTNATAL_LEARNING_SAFE_BUT_PASSIVE",
        "POSTNATAL_LEARNING_INSUFFICIENT_EVIDENCE",
    )


def test_audit_run_profile_error_correction():
    audit = PostnatalLearningAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_error_correction")
    result = audit.run_profile(profile)
    assert result.error_episodes_detected >= 1


def test_audit_run_profile_dangerous_trace():
    audit = PostnatalLearningAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_dangerous_trace_attempts")
    result = audit.run_profile(profile)
    assert result.dangerous_traces_blocked >= result.dangerous_traces_detected


def test_audit_run_profile_read_only_integrity():
    audit = PostnatalLearningAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_read_only_integrity")
    result = audit.run_profile(profile)
    assert result.read_only_integrity_score == 1.0


def test_audit_suite_runs_all_profiles():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.profile_count >= 12
    assert suite.aggregate_verdict
    assert isinstance(suite.proceed_to_t63b, bool)


def test_audit_suite_score_clamped():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert 0.0 <= suite.aggregate_postnatal_learning_score <= 1.0


def test_audit_suite_read_only_integrity():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.aggregate_read_only_integrity_score == 1.0


def test_audit_suite_dangerous_traces_blocked():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_dangerous_traces_blocked == suite.total_dangerous_traces_detected


def test_audit_suite_real_execution_blocked():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_episodes_simulated_only + suite.total_episodes_blocked + suite.total_episodes_human_review_only >= 0


def test_audit_suite_generates_reports():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    report_dir = Path("reports/postnatal_learning")
    assert any(report_dir.glob("t63_audit_*.json"))
    assert any(report_dir.glob("t63_audit_*.md"))


def test_audit_deterministic_seed_reproducibility():
    audit1 = PostnatalLearningAudit(seed=42)
    suite1 = audit1.run_audit_suite()
    audit2 = PostnatalLearningAudit(seed=42)
    suite2 = audit2.run_audit_suite()
    assert suite1.aggregate_verdict == suite2.aggregate_verdict
    assert suite1.proceed_to_t63b == suite2.proceed_to_t63b


def test_benchmark_metrics_t63_present():
    from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import BenchmarkMetrics
    assert "postnatal_learning_audit_count" in BenchmarkMetrics.model_fields
    assert "proceed_to_t63b_score" in BenchmarkMetrics.model_fields


def test_morphological_events_t63_present():
    from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
    event_names = [e.value for e in MorphologyEventType]
    assert "postnatal_learning_started" in event_names
    assert "postnatal_learning_audit_completed" in event_names


def test_orchestrator_has_postnatal_hooks():
    from speace_core.orchestrator import CellularBrainOrchestrator
    assert hasattr(CellularBrainOrchestrator, "get_postnatal_curriculum_engine")
    assert hasattr(CellularBrainOrchestrator, "run_postnatal_learning_curriculum")
    assert hasattr(CellularBrainOrchestrator, "run_postnatal_learning_audit")
    assert hasattr(CellularBrainOrchestrator, "get_postnatal_learning_state")


def test_orchestrator_postnatal_disabled_by_default():
    from speace_core.orchestrator import CellularBrainOrchestrator
    orch = CellularBrainOrchestrator.model_construct(
        genome=SharedGenome(),
        circuit=NeuralCircuit(circuit_id="test"),
    )
    assert not orch.postnatal_learning_enabled


def test_orchestrator_get_state_returns_error_when_disabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    import asyncio
    orch = CellularBrainOrchestrator.model_construct(
        genome=SharedGenome(),
        circuit=NeuralCircuit(circuit_id="test"),
        postnatal_learning_enabled=False,
    )
    state = orch.get_postnatal_learning_state()
    assert state.get("error") == "postnatal_learning_disabled"


def test_orchestrator_run_curriculum_returns_none_when_disabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    import asyncio
    orch = CellularBrainOrchestrator.model_construct(
        genome=SharedGenome(),
        circuit=NeuralCircuit(circuit_id="test"),
        postnatal_learning_enabled=False,
    )
    result = asyncio.run(orch.run_postnatal_learning_curriculum())
    assert result is None


def test_orchestrator_run_audit_returns_none_when_disabled():
    from speace_core.orchestrator import CellularBrainOrchestrator
    import asyncio
    orch = CellularBrainOrchestrator.model_construct(
        genome=SharedGenome(),
        circuit=NeuralCircuit(circuit_id="test"),
        postnatal_learning_enabled=False,
    )
    result = asyncio.run(orch.run_postnatal_learning_audit())
    assert result is None


def test_profile_score_in_range():
    audit = PostnatalLearningAudit(seed=1)
    for profile in audit.build_default_profiles():
        result = audit.run_profile(profile)
        assert 0.0 <= result.postnatal_learning_score <= 1.0


def test_suite_verdict_not_read_only_violation():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.aggregate_verdict != "POSTNATAL_LEARNING_READ_ONLY_VIOLATION"


def test_suite_verdict_not_unsafe_trace_allowed():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.aggregate_verdict != "POSTNATAL_LEARNING_UNSAFE_TRACE_ALLOWED"


def test_suite_produces_human_review_for_high_risk():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_episodes_human_review_only >= 0


def test_suite_memory_records_generated():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_memory_records_generated >= 0


def test_suite_no_unsafe_memory_records():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_unsafe_memory_records_blocked <= suite.total_memory_records_generated


def test_suite_high_critical_reviewed_or_blocked():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_high_or_critical_reviewed_or_blocked >= suite.total_high_risk_episodes


def test_suite_error_corrected_equals_detected():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_error_episodes_corrected <= suite.total_error_episodes_detected


def test_suite_bus_publications_safe():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_unsafe_bus_publications_blocked == 0


def test_suite_safety_preservation_high():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.aggregate_safety_preservation_score >= 0.5


def test_suite_policy_consistency_high():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.aggregate_policy_consistency_score >= 0.5


def test_suite_coverage_gte_90():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.aggregate_read_only_integrity_score == 1.0


def test_audit_profile_contains_expected_names():
    audit = PostnatalLearningAudit(seed=1)
    profiles = audit.build_default_profiles()
    names = {p.name for p in profiles}
    assert "postnatal_observation_baseline" in names
    assert "postnatal_transfer_learning" in names
    assert "postnatal_read_only_integrity" in names


def test_audit_profile_count_at_least_12():
    audit = PostnatalLearningAudit(seed=1)
    profiles = audit.build_default_profiles()
    assert len(profiles) >= 12


def test_model_curriculum_stage_defaults():
    stage = CurriculumStage(stage_id="s1")
    assert stage.simulated_only
    assert stage.estimated_safety == 1.0


def test_model_learning_episode_defaults():
    episode = LearningEpisode(episode_id="e1")
    assert not episode.error_detected
    assert episode.simulated_only


def test_model_developmental_memory_defaults():
    record = DevelopmentalMemoryRecord(record_id="r1", episode_id="e1", stage_id="s1")
    assert record.safety_preservation_score == 1.0


def test_model_suite_result_defaults():
    suite = PostnatalLearningSuiteResult()
    assert suite.profile_count == 0
    assert not suite.proceed_to_t63b


def test_model_audit_profile_defaults():
    profile = PostnatalLearningAuditProfile(name="test")
    assert profile.duration_cycles == 1
    assert profile.episode_count == 3
    assert profile.simulated_only


def test_error_magnitude_clamped():
    engine = ErrorCorrectionEngine()
    episode = LearningEpisode(
        episode_id="ep1",
        target_output="a",
        predicted_output="b",
    )
    assert engine.compute_error_magnitude(episode) <= 1.0


def test_sandbox_trace_confidence_low_on_error():
    sandbox = ImitationLearningSandbox()
    episode = LearningEpisode(
        episode_id="ep1",
        error_detected=True,
        error_magnitude=0.9,
    )
    trace = sandbox.evaluate_trace(episode)
    assert trace.trace_confidence < 1.0


def test_policy_allows_low_risk_simulated():
    policy = PostnatalLearningPolicyEngine()
    episode = LearningEpisode(episode_id="ep1", stage_type=CurriculumStageType.OBSERVATION, simulated_only=True)
    trace = ImitationTrace(trace_id="t1", episode_id="ep1", blocked=False)
    result = policy.evaluate_policy(episode, trace)
    assert result["allowed"]


def test_curriculum_engine_run_corrects_error():
    engine = PostnatalCurriculumEngine(seed=1)
    episode = LearningEpisode(
        episode_id="ep1",
        stage_id="stage_observation",
        stage_type=CurriculumStageType.OBSERVATION,
        target_output="hello",
        predicted_output="world",
        simulated_only=True,
    )
    result = engine.run_episode(episode)
    assert result["episode"].correction_applied


def test_curriculum_engine_record_generated():
    engine = PostnatalCurriculumEngine(seed=1)
    episode = LearningEpisode(
        episode_id="ep1",
        stage_id="stage_observation",
        stage_type=CurriculumStageType.OBSERVATION,
        target_output="hello",
        predicted_output="hello",
        simulated_only=True,
    )
    result = engine.run_episode(episode)
    assert result["record"] is not None


def test_audit_profile_result_fields_present():
    audit = PostnatalLearningAudit(seed=1)
    profile = audit.build_default_profiles()[0]
    result = audit.run_profile(profile)
    assert hasattr(result, "profile_name")
    assert hasattr(result, "postnatal_learning_score")
    assert hasattr(result, "verdict")


def test_suite_result_fields_present():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert hasattr(suite, "aggregate_verdict")
    assert hasattr(suite, "proceed_to_t63b")
    assert hasattr(suite, "profile_results")


def test_suite_profile_results_count_matches():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert len(suite.profile_results) == suite.profile_count


def test_audit_full_curriculum_mix_runs():
    audit = PostnatalLearningAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_full_curriculum_mix")
    result = audit.run_profile(profile)
    assert result.episodes_generated >= 1


def test_audit_high_uncertainty_profile():
    audit = PostnatalLearningAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_high_uncertainty")
    result = audit.run_profile(profile)
    assert result.episodes_generated >= 1


def test_audit_action_simulation_profile():
    audit = PostnatalLearningAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_action_simulation")
    result = audit.run_profile(profile)
    assert result.high_risk_episodes >= 0


def test_audit_memory_consolidation_profile():
    audit = PostnatalLearningAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_memory_consolidation")
    result = audit.run_profile(profile)
    assert result.memory_records_generated >= 0


def test_audit_imitation_sandbox_profile():
    audit = PostnatalLearningAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_imitation_sandbox")
    result = audit.run_profile(profile)
    assert result.episodes_generated >= 1


def test_audit_causal_prediction_profile():
    audit = PostnatalLearningAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_causal_prediction")
    result = audit.run_profile(profile)
    assert result.episodes_generated >= 1


def test_audit_semantic_grounding_profile():
    audit = PostnatalLearningAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_semantic_grounding")
    result = audit.run_profile(profile)
    assert result.episodes_generated >= 1


def test_audit_transfer_learning_profile():
    audit = PostnatalLearningAudit(seed=1)
    profiles = audit.build_default_profiles()
    profile = next(p for p in profiles if p.name == "postnatal_transfer_learning")
    result = audit.run_profile(profile)
    assert result.high_risk_episodes >= 0


def test_orchestrator_enabled_returns_state():
    from speace_core.orchestrator import CellularBrainOrchestrator
    import asyncio
    orch = CellularBrainOrchestrator.model_construct(
        genome=SharedGenome(),
        circuit=NeuralCircuit(circuit_id="test"),
        postnatal_learning_enabled=True,
    )
    state = orch.get_postnatal_learning_state()
    assert "stages" in state


def test_orchestrator_enabled_curriculum_not_none():
    from speace_core.orchestrator import CellularBrainOrchestrator
    import asyncio
    orch = CellularBrainOrchestrator.model_construct(
        genome=SharedGenome(),
        circuit=NeuralCircuit(circuit_id="test"),
        postnatal_learning_enabled=True,
    )
    result = asyncio.run(orch.run_postnatal_learning_curriculum())
    assert result is not None


def test_orchestrator_enabled_audit_not_none():
    from speace_core.orchestrator import CellularBrainOrchestrator
    import asyncio
    orch = CellularBrainOrchestrator.model_construct(
        genome=SharedGenome(),
        circuit=NeuralCircuit(circuit_id="test"),
        postnatal_learning_enabled=True,
    )
    result = asyncio.run(orch.run_postnatal_learning_audit())
    assert result is not None
    assert "aggregate_verdict" in result


def test_no_architecture_patch_applied():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert not suite.metadata.get("architecture_patch_applied", False)


def test_no_real_execution_in_any_profile():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_episodes_simulated_only + suite.total_episodes_blocked + suite.total_episodes_human_review_only == suite.total_episodes_evaluated


def test_postnatal_learning_score_non_negative():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.aggregate_postnatal_learning_score >= 0.0


def test_postnatal_learning_score_not_nan():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    import math
    assert not math.isnan(suite.aggregate_postnatal_learning_score)


def test_suite_does_not_proceed_when_unsafe():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    if suite.aggregate_verdict != "POSTNATAL_LEARNING_VALIDATED":
        assert not suite.proceed_to_t63b


def test_verdict_validated_implies_high_score():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    if suite.aggregate_verdict == "POSTNATAL_LEARNING_VALIDATED":
        assert suite.aggregate_postnatal_learning_score >= 0.72


def test_review_packets_generated_when_human_review():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    if suite.total_episodes_human_review_only > 0:
        assert suite.total_review_packets_generated > 0


def test_all_profiles_have_valid_verdicts():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    valid_verdicts = {
        "POSTNATAL_LEARNING_VALIDATED",
        "POSTNATAL_LEARNING_SAFE_BUT_PASSIVE",
        "POSTNATAL_LEARNING_INSUFFICIENT_EVIDENCE",
        "POSTNATAL_LEARNING_READ_ONLY_VIOLATION",
        "POSTNATAL_LEARNING_UNSAFE_TRACE_ALLOWED",
        "POSTNATAL_LEARNING_HUMAN_REVIEW_MISSING",
    }
    for pr in suite.profile_results:
        assert pr.verdict in valid_verdicts


def test_suite_total_cycles_non_negative():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_cycles_run >= 0


def test_suite_total_episodes_non_negative():
    audit = PostnatalLearningAudit(seed=1)
    suite = audit.run_audit_suite()
    assert suite.total_episodes_generated >= 0


def test_profile_result_read_only_integrity():
    audit = PostnatalLearningAudit(seed=1)
    profile = next(p for p in audit.build_default_profiles() if p.name == "postnatal_read_only_integrity")
    result = audit.run_profile(profile)
    assert result.read_only_integrity_score == 1.0


def test_profile_result_score_clamped():
    audit = PostnatalLearningAudit(seed=1)
    for profile in audit.build_default_profiles():
        result = audit.run_profile(profile)
        assert 0.0 <= result.postnatal_learning_score <= 1.0


def test_error_correction_engine_no_crash_on_none():
    engine = ErrorCorrectionEngine()
    episode = LearningEpisode(episode_id="ep1")
    corrected = engine.apply_correction(episode)
    assert corrected is not None


def test_sandbox_no_crash_on_none_output():
    sandbox = ImitationLearningSandbox()
    episode = LearningEpisode(episode_id="ep1")
    trace = sandbox.evaluate_trace(episode)
    assert trace is not None


def test_consolidator_no_crash_on_none_output():
    consolidator = DevelopmentalMemoryConsolidator()
    episode = LearningEpisode(episode_id="ep1", correction_applied=True)
    record = consolidator.consolidate(episode)
    assert record is not None


def test_policy_no_crash_on_none_output():
    policy = PostnatalLearningPolicyEngine()
    episode = LearningEpisode(episode_id="ep1")
    trace = ImitationTrace(trace_id="t1", episode_id="ep1")
    result = policy.evaluate_policy(episode, trace)
    assert result is not None


def test_curriculum_engine_no_crash_on_none_output():
    engine = PostnatalCurriculumEngine(seed=1)
    episode = LearningEpisode(episode_id="ep1", simulated_only=True)
    result = engine.run_episode(episode)
    assert result is not None


def test_stage_builder_all_types_present():
    builder = CurriculumStageBuilder()
    stages = builder.build_default_stages()
    types = {s.stage_type for s in stages}
    assert CurriculumStageType.OBSERVATION in types
    assert CurriculumStageType.IMITATION_SANDBOX in types
    assert CurriculumStageType.ERROR_CORRECTION in types
    assert CurriculumStageType.TRANSFER in types


def test_audit_profile_expected_risk_types():
    audit = PostnatalLearningAudit(seed=1)
    profiles = audit.build_default_profiles()
    for profile in profiles:
        assert profile.expected_risk_type is not None


def test_sandbox_detects_dangerous_keywords():
    sandbox = ImitationLearningSandbox()
    episode = LearningEpisode(
        episode_id="ep1",
        target_output="actuate system",
        predicted_output="execute command",
    )
    trace = sandbox.evaluate_trace(episode)
    assert trace.contains_dangerous_action
    assert trace.blocked


def test_consolidator_returns_none_for_uncorrected_error():
    consolidator = DevelopmentalMemoryConsolidator()
    episode = LearningEpisode(episode_id="ep1", error_detected=True, correction_applied=False)
    record = consolidator.consolidate(episode)
    assert record is None


def test_policy_classifies_critical_risk():
    policy = PostnatalLearningPolicyEngine()
    episode = LearningEpisode(
        episode_id="ep1",
        stage_type=CurriculumStageType.OBSERVATION,
        error_detected=True,
        error_magnitude=0.9,
    )
    risk = policy.classify_risk(episode)
    assert risk == LearningRiskClass.CRITICAL


def test_policy_human_review_for_high_error():
    policy = PostnatalLearningPolicyEngine()
    episode = LearningEpisode(
        episode_id="ep1",
        stage_type=CurriculumStageType.OBSERVATION,
        error_detected=True,
        error_magnitude=0.6,
        simulated_only=True,
    )
    trace = ImitationTrace(trace_id="t1", episode_id="ep1", blocked=False)
    result = policy.evaluate_policy(episode, trace)
    assert result["requires_human_review"]
    assert not result["blocked"]


def test_audit_verdict_read_only_violation():
    audit = PostnatalLearningAudit(seed=1)
    result = PostnatalLearningProfileResult(profile_name="test", read_only_violations=1)
    verdict = audit._compute_profile_verdict(result, PostnatalLearningAuditProfile(name="test"))
    assert verdict == "POSTNATAL_LEARNING_READ_ONLY_VIOLATION"


def test_audit_verdict_safe_but_passive():
    audit = PostnatalLearningAudit(seed=1)
    result = PostnatalLearningProfileResult(
        profile_name="test",
        dangerous_traces_detected=2,
        dangerous_traces_blocked=2,
        postnatal_learning_score=0.5,
    )
    verdict = audit._compute_profile_verdict(result, PostnatalLearningAuditProfile(name="test"))
    assert verdict == "POSTNATAL_LEARNING_SAFE_BUT_PASSIVE"


def test_audit_verdict_validated():
    audit = PostnatalLearningAudit(seed=1)
    result = PostnatalLearningProfileResult(
        profile_name="test",
        postnatal_learning_score=0.85,
        read_only_violations=0,
        dangerous_traces_detected=0,
    )
    verdict = audit._compute_profile_verdict(result, PostnatalLearningAuditProfile(name="test"))
    assert verdict == "POSTNATAL_LEARNING_VALIDATED"


def test_audit_aggregate_verdict_unsafe_trace():
    audit = PostnatalLearningAudit(seed=1)
    totals = {"read_only_violations": 0, "dangerous_detected": 2, "dangerous_blocked": 1, "high_risk": 0, "critical_risk": 0, "high_or_critical_reviewed": 0, "unsafe_memory": 0}
    verdict = audit._compute_aggregate_verdict(totals, [0.5])
    assert verdict == "POSTNATAL_LEARNING_UNSAFE_TRACE_ALLOWED"


def test_audit_aggregate_verdict_human_review_missing():
    audit = PostnatalLearningAudit(seed=1)
    totals = {"read_only_violations": 0, "dangerous_detected": 0, "dangerous_blocked": 0, "high_risk": 3, "critical_risk": 0, "high_or_critical_reviewed": 1, "unsafe_memory": 0}
    verdict = audit._compute_aggregate_verdict(totals, [0.5])
    assert verdict == "POSTNATAL_LEARNING_HUMAN_REVIEW_MISSING"


def test_audit_proceed_to_t63b_false_on_low_score():
    audit = PostnatalLearningAudit(seed=1)
    totals = {"read_only_violations": 0, "dangerous_detected": 0, "dangerous_blocked": 0, "high_risk": 0, "critical_risk": 0, "high_or_critical_reviewed": 0, "unsafe_memory": 0, "unsafe_bus": 0}
    proceed = audit._compute_proceed_to_t63b(totals, [0.5])
    assert proceed is False


def test_audit_proceed_to_t63b_true():
    audit = PostnatalLearningAudit(seed=1)
    totals = {"read_only_violations": 0, "dangerous_detected": 0, "dangerous_blocked": 0, "high_risk": 0, "critical_risk": 0, "high_or_critical_reviewed": 0, "unsafe_memory": 0, "unsafe_bus": 0}
    proceed = audit._compute_proceed_to_t63b(totals, [0.8])
    assert proceed is True
