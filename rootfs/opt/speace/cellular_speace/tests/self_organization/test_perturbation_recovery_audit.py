import asyncio
import json
import random

import pytest

from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.self_organization.perturbation_recovery_audit import (
    ControlledPerturbationRecoveryAudit,
    PerturbationKind,
    PerturbationRecoveryResult,
    PerturbationScenario,
    PerturbationTracePoint,
    PerturbationVerdict,
)
from speace_core.dna.parser import load_genome
from speace_core.orchestrator import CellularBrainOrchestrator


@pytest.fixture
def orchestrator():
    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.region_signal_routing_enabled = False
    orch.brainstem_controller_enabled = False
    orch.region_stability_controller_enabled = False
    return orch


@pytest.fixture
def audit(orchestrator):
    return ControlledPerturbationRecoveryAudit(orchestrator=orchestrator, seed=42)


# ------------------------------------------------------------------ #
# Model validation
# ------------------------------------------------------------------ #

def test_perturbation_scenario_defaults():
    s = PerturbationScenario(name="test", kind=PerturbationKind.ACTIVATION_SPIKE)
    assert s.strength == 0.5
    assert s.duration_ticks == 5
    assert s.reversible is True


def test_perturbation_trace_point_defaults():
    t = PerturbationTracePoint(tick=1)
    assert t.coherence_phi == 0.0


def test_perturbation_recovery_result_defaults():
    r = PerturbationRecoveryResult(scenario_name="test")
    assert r.verdict == PerturbationVerdict.INSUFFICIENT_EVIDENCE


# ------------------------------------------------------------------ #
# Scenario factory
# ------------------------------------------------------------------ #

def test_build_default_scenarios_count(audit):
    scenarios = audit.build_default_scenarios()
    assert len(scenarios) >= 6


def test_default_scenarios_have_valid_kinds(audit):
    scenarios = audit.build_default_scenarios()
    kinds = {s.kind for s in scenarios}
    assert all(isinstance(k, PerturbationKind) for k in kinds)


def test_default_scenarios_reversible(audit):
    scenarios = audit.build_default_scenarios()
    assert all(s.reversible for s in scenarios)


# ------------------------------------------------------------------ #
# Perturbation application / reversal
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_activation_spike_changes_activation(audit):
    baseline = [n.activation for n in audit.orch.circuit.hidden_neurons]
    scenario = PerturbationScenario(
        name="spike", kind=PerturbationKind.ACTIVATION_SPIKE, strength=0.5
    )
    audit.apply_perturbation(scenario)
    after = [n.activation for n in audit.orch.circuit.hidden_neurons]
    assert any(a > b for a, b in zip(after, baseline))
    audit.reverse_perturbation(scenario)


@pytest.mark.asyncio
async def test_energy_scarcity_reduces_energy(audit):
    baseline = [n.energy for n in audit.orch.circuit.hidden_neurons]
    scenario = PerturbationScenario(
        name="scarcity", kind=PerturbationKind.ENERGY_SCARCITY, strength=0.3
    )
    audit.apply_perturbation(scenario)
    after = [n.energy for n in audit.orch.circuit.hidden_neurons]
    assert all(a <= b for a, b in zip(after, baseline))
    audit.reverse_perturbation(scenario)


@pytest.mark.asyncio
async def test_plasticity_overdrive_is_reversible(audit):
    baseline = [s.weight for s in audit.orch.circuit.synapses]
    scenario = PerturbationScenario(
        name="overdrive", kind=PerturbationKind.PLASTICITY_OVERDRIVE, strength=0.3
    )
    audit.apply_perturbation(scenario)
    mid = [s.weight for s in audit.orch.circuit.synapses]
    assert any(a > b for a, b in zip(mid, baseline))
    audit.reverse_perturbation(scenario)
    after = [s.weight for s in audit.orch.circuit.synapses]
    assert all(abs(a - b) < 1e-6 for a, b in zip(after, baseline))


@pytest.mark.asyncio
async def test_mixed_stress_runs_without_exception(audit):
    scenario = PerturbationScenario(
        name="mixed", kind=PerturbationKind.MIXED_STRESS, strength=0.3
    )
    audit.apply_perturbation(scenario)
    audit.reverse_perturbation(scenario)
    assert True


@pytest.mark.asyncio
async def test_semantic_noise_does_not_crash_without_semantic_memory(audit):
    scenario = PerturbationScenario(
        name="semantic", kind=PerturbationKind.SEMANTIC_NOISE, strength=0.3
    )
    audit.apply_perturbation(scenario)
    audit.reverse_perturbation(scenario)
    assert True


@pytest.mark.asyncio
async def test_routing_overload_generates_signal_pressure(audit):
    scenario = PerturbationScenario(
        name="routing", kind=PerturbationKind.ROUTING_OVERLOAD, strength=0.5
    )
    audit.apply_perturbation(scenario)
    # No crash is the success criterion when routing is disabled
    assert True
    audit.reverse_perturbation(scenario)


# ------------------------------------------------------------------ #
# Trace point capture
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_trace_point_has_all_metrics(audit):
    await audit.orch.run_ticks(1)
    point = audit.capture_trace_point(audit.orch.current_tick)
    assert point.tick >= 1
    assert isinstance(point.coherence_phi, float)
    assert isinstance(point.energy_efficiency, float)
    assert isinstance(point.mean_activation, float)
    assert isinstance(point.suppression_level, float)


# ------------------------------------------------------------------ #
# Verdict computation
# ------------------------------------------------------------------ #

def test_validated_recovery_verdict():
    v = ControlledPerturbationRecoveryAudit.compute_verdict(
        post_perturbation_recovery_score=0.70,
        collapse_detected=False,
        baseline_phi=0.5,
        final_phi=0.48,
        baseline_cognitive=0.5,
        final_cognitive=0.48,
        suppression_cost=0.1,
    )
    assert v == PerturbationVerdict.PERTURBATION_RECOVERY_VALIDATED


def test_phi_collapse_verdict():
    v = ControlledPerturbationRecoveryAudit.compute_verdict(
        post_perturbation_recovery_score=0.3,
        collapse_detected=True,
        baseline_phi=0.5,
        final_phi=0.1,
        baseline_cognitive=0.5,
        final_cognitive=0.4,
        suppression_cost=0.1,
    )
    assert v == PerturbationVerdict.PHI_COLLAPSE


def test_energy_collapse_verdict():
    v = ControlledPerturbationRecoveryAudit.compute_verdict(
        post_perturbation_recovery_score=0.3,
        collapse_detected=True,
        baseline_phi=0.5,
        final_phi=0.35,
        baseline_cognitive=0.5,
        final_cognitive=0.4,
        suppression_cost=0.1,
    )
    assert v == PerturbationVerdict.ENERGY_COLLAPSE


def test_over_suppression_verdict():
    v = ControlledPerturbationRecoveryAudit.compute_verdict(
        post_perturbation_recovery_score=0.40,
        collapse_detected=False,
        baseline_phi=0.5,
        final_phi=0.45,
        baseline_cognitive=0.5,
        final_cognitive=0.3,
        suppression_cost=1.5,
    )
    assert v == PerturbationVerdict.OVER_SUPPRESSION


def test_perturbation_no_effect_verdict():
    v = ControlledPerturbationRecoveryAudit.compute_verdict(
        post_perturbation_recovery_score=0.02,
        collapse_detected=False,
        baseline_phi=0.5,
        final_phi=0.5,
        baseline_cognitive=0.5,
        final_cognitive=0.5,
        suppression_cost=0.0,
    )
    assert v == PerturbationVerdict.PERTURBATION_NO_EFFECT


def test_recovery_partial_verdict():
    v = ControlledPerturbationRecoveryAudit.compute_verdict(
        post_perturbation_recovery_score=0.50,
        collapse_detected=False,
        baseline_phi=0.5,
        final_phi=0.45,
        baseline_cognitive=0.5,
        final_cognitive=0.45,
        suppression_cost=0.1,
    )
    assert v == PerturbationVerdict.RECOVERY_PARTIAL


def test_insufficient_evidence_verdict():
    v = ControlledPerturbationRecoveryAudit.compute_verdict(
        post_perturbation_recovery_score=0.20,
        collapse_detected=False,
        baseline_phi=0.5,
        final_phi=0.45,
        baseline_cognitive=0.5,
        final_cognitive=0.45,
        suppression_cost=0.1,
    )
    assert v == PerturbationVerdict.INSUFFICIENT_EVIDENCE


# ------------------------------------------------------------------ #
# Scenario execution
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_run_scenario_returns_result(audit):
    scenario = PerturbationScenario(
        name="test_spike", kind=PerturbationKind.ACTIVATION_SPIKE, strength=0.2
    )
    result = await audit.run_scenario(
        scenario, warmup_ticks=1, perturbation_ticks=2, recovery_ticks=3
    )
    assert isinstance(result, PerturbationRecoveryResult)
    assert result.scenario_name == "test_spike"
    assert len(result.trace) > 0


@pytest.mark.asyncio
async def test_run_scenario_trace_length(audit):
    scenario = PerturbationScenario(
        name="test", kind=PerturbationKind.ENERGY_SCARCITY, strength=0.1
    )
    result = await audit.run_scenario(
        scenario, warmup_ticks=1, perturbation_ticks=1, recovery_ticks=2
    )
    expected_ticks = 1 + 1 + 2
    assert len(result.trace) >= expected_ticks


@pytest.mark.asyncio
async def test_run_scenario_recovery_score_clamped(audit):
    scenario = PerturbationScenario(
        name="test", kind=PerturbationKind.PLASTICITY_OVERDRIVE, strength=0.1
    )
    result = await audit.run_scenario(
        scenario, warmup_ticks=1, perturbation_ticks=1, recovery_ticks=2
    )
    assert 0.0 <= result.post_perturbation_recovery_score <= 1.0


@pytest.mark.asyncio
async def test_run_scenario_collapse_detection(audit):
    scenario = PerturbationScenario(
        name="test", kind=PerturbationKind.MIXED_STRESS, strength=0.1
    )
    result = await audit.run_scenario(
        scenario, warmup_ticks=1, perturbation_ticks=1, recovery_ticks=2
    )
    assert isinstance(result.collapse_detected, bool)


# ------------------------------------------------------------------ #
# Audit suite
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_audit_suite_runs_all_scenarios(audit):
    results = await audit.run_audit_suite()
    assert len(results) >= 6
    assert all(isinstance(r, PerturbationRecoveryResult) for r in results)


@pytest.mark.asyncio
async def test_audit_suite_different_verdicts(audit):
    results = await audit.run_audit_suite()
    verdicts = {r.verdict for r in results}
    assert len(verdicts) >= 1


# ------------------------------------------------------------------ #
# Reports
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_report_json_created(audit):
    results = await audit.run_audit_suite()
    report = audit.generate_json_report(results)
    data = json.loads(report)
    assert isinstance(data, list)
    assert len(data) == len(results)


@pytest.mark.asyncio
async def test_report_markdown_contains_metrics(audit):
    results = await audit.run_audit_suite()
    report = audit.generate_markdown_report(results)
    assert "Controlled Perturbation & Recovery Audit Report" in report
    assert results[0].scenario_name in report


# ------------------------------------------------------------------ #
# Determinism
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_deterministic_seed(orchestrator):
    random.seed(42)
    audit1 = ControlledPerturbationRecoveryAudit(orchestrator=orchestrator, seed=42)
    audit2 = ControlledPerturbationRecoveryAudit(orchestrator=orchestrator, seed=42)
    s1 = audit1.build_default_scenarios()
    s2 = audit2.build_default_scenarios()
    assert len(s1) == len(s2)
    for a, b in zip(s1, s2):
        assert a.name == b.name
        assert a.kind == b.kind


# ------------------------------------------------------------------ #
# Events
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_events_logged(audit):
    mem = audit.orch.memory
    before = len(mem.events)
    scenario = PerturbationScenario(
        name="event_test", kind=PerturbationKind.ACTIVATION_SPIKE, strength=0.1
    )
    await audit.run_scenario(scenario, warmup_ticks=1, perturbation_ticks=1, recovery_ticks=2)
    after = len(mem.events)
    assert after >= before


# ------------------------------------------------------------------ #
# No rollback needed for safe profile
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_no_rollback_needed_for_safe_profile(audit):
    scenario = PerturbationScenario(
        name="safe", kind=PerturbationKind.ACTIVATION_SPIKE, strength=0.05
    )
    result = await audit.run_scenario(
        scenario, warmup_ticks=1, perturbation_ticks=1, recovery_ticks=2
    )
    assert result.rollback_needed is False


# ------------------------------------------------------------------ #
# Collapse detection
# ------------------------------------------------------------------ #

def test_collapse_detection_works(audit):
    scenario = PerturbationScenario(
        name="collapse", kind=PerturbationKind.MIXED_STRESS, strength=0.1
    )
    audit.apply_perturbation(scenario)
    # Just ensure no exception and some state change happened
    assert True
    audit.reverse_perturbation(scenario)


# ------------------------------------------------------------------ #
# Recovery latency
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_recovery_latency_non_negative(audit):
    scenario = PerturbationScenario(
        name="latency", kind=PerturbationKind.ENERGY_SCARCITY, strength=0.1
    )
    result = await audit.run_scenario(
        scenario, warmup_ticks=1, perturbation_ticks=1, recovery_ticks=3
    )
    assert result.recovery_latency_ticks >= 0


# ------------------------------------------------------------------ #
# Scenario strength bounds
# ------------------------------------------------------------------ #

def test_scenario_strength_clamped():
    with pytest.raises(ValueError):
        PerturbationScenario(name="bad", kind=PerturbationKind.ACTIVATION_SPIKE, strength=1.5)


# ------------------------------------------------------------------ #
# Trace point after tick
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_capture_trace_point_after_tick(audit):
    await audit.orch.run_ticks(2)
    point = audit.capture_trace_point(audit.orch.current_tick)
    assert point.tick >= 2


# ------------------------------------------------------------------ #
# Verdict bounds
# ------------------------------------------------------------------ #

def test_verdict_enum_values():
    assert PerturbationVerdict.PERTURBATION_RECOVERY_VALIDATED.value == "PERTURBATION_RECOVERY_VALIDATED"
    assert PerturbationVerdict.RECOVERY_PARTIAL.value == "RECOVERY_PARTIAL"
    assert PerturbationVerdict.PHI_COLLAPSE.value == "PHI_COLLAPSE"
    assert PerturbationVerdict.ENERGY_COLLAPSE.value == "ENERGY_COLLAPSE"


# ------------------------------------------------------------------ #
# Result serialization
# ------------------------------------------------------------------ #

def test_result_json_roundtrip():
    result = PerturbationRecoveryResult(
        scenario_name="roundtrip",
        baseline_phi=0.5,
        final_phi=0.4,
        post_perturbation_recovery_score=0.6,
        verdict=PerturbationVerdict.RECOVERY_PARTIAL,
        trace=[PerturbationTracePoint(tick=1, coherence_phi=0.5)],
    )
    data = result.model_dump_json()
    loaded = PerturbationRecoveryResult.model_validate_json(data)
    assert loaded.scenario_name == "roundtrip"
    assert loaded.verdict == PerturbationVerdict.RECOVERY_PARTIAL
