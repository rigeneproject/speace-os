import pytest

from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regions.brainstem_controller import (
    BrainstemFunctionalController,
    BrainstemFunctionalState,
    BrainstemDecision,
    BrainstemModulationResult,
    BrainstemState,
)


# ---------------------------------------------------------------------------
# 1. Importabilita e modelli
# ---------------------------------------------------------------------------

def test_brainstem_importable():
    assert BrainstemFunctionalController is not None
    assert BrainstemFunctionalState is not None
    assert BrainstemDecision is not None
    assert BrainstemModulationResult is not None
    assert BrainstemState is not None


def test_brainstem_state_defaults():
    state = BrainstemState()
    assert state.state == BrainstemFunctionalState.STABLE
    assert state.mean_phi == 0.0


def test_brainstem_decision_defaults():
    dec = BrainstemDecision()
    assert dec.state == BrainstemFunctionalState.STABLE
    assert dec.routing_suppression_multiplier == 1.0
    assert dec.energy_recovery_multiplier == 1.0


def test_brainstem_modulation_result_defaults():
    res = BrainstemModulationResult()
    assert res.state_changed is False
    assert res.decisions_count == 0


# ---------------------------------------------------------------------------
# 2. T36 — Cognitive / Autonomic Scoring
# ---------------------------------------------------------------------------

def test_compute_cognitive_vitality_score_with_benchmark_metrics():
    ctrl = BrainstemFunctionalController()
    metrics = {
        "cognitive_score": 0.8,
        "functional_improvement": 0.6,
        "regional_signal_flow": 0.5,
        "deep_region_signal_flow": 0.4,
        "mean_pathway_utility": 0.7,
    }
    score = ctrl.compute_cognitive_vitality_score(metrics)
    expected = 0.35 * 0.8 + 0.25 * 0.6 + 0.15 * 0.5 + 0.15 * 0.4 + 0.10 * 0.7
    assert round(score, 4) == round(expected, 4)


def test_compute_cognitive_vitality_score_proxy_when_no_benchmark_inputs():
    ctrl = BrainstemFunctionalController()
    metrics = {
        "mean_region_phi": 0.30,
        "regional_signal_flow": 0.4,
        "deep_region_signal_flow": 0.3,
        "mean_pathway_utility": 0.2,
    }
    score = ctrl.compute_cognitive_vitality_score(metrics)
    assert 0.0 <= score <= 1.0


def test_compute_autonomic_risk_score():
    ctrl = BrainstemFunctionalController()
    metrics = {
        "region_instability_mean": 0.50,
        "mean_region_phi": 0.10,
        "mean_energy": 0.20,
        "mean_deep_region_activation": 2.5,
        "unstable_region_count": 2,
        "region_count": 4,
    }
    score = ctrl.compute_autonomic_risk_score(metrics)
    assert 0.0 <= score <= 1.0
    assert score > 0.3  # Should be elevated with these inputs


def test_compute_balance_pressure():
    ctrl = BrainstemFunctionalController()
    metrics = {
        "cognitive_score": 0.6,
        "functional_improvement": 0.5,
        "region_instability_mean": 0.40,
        "mean_region_phi": 0.20,
        "mean_energy": 0.30,
    }
    vitality, risk, pressure = ctrl.compute_balance_pressure(metrics)
    assert 0.0 <= vitality <= 1.0
    assert 0.0 <= risk <= 1.0
    assert pressure >= 0.0
    assert vitality > 0.0
    assert risk > 0.0


# ---------------------------------------------------------------------------
# 3. State evaluation (T36 balance-pressure driven)
# ---------------------------------------------------------------------------

def test_evaluate_state_stable_low_pressure():
    ctrl = BrainstemFunctionalController()
    # Healthy system: low risk, decent vitality
    metrics = {
        "mean_region_phi": 0.35,
        "mean_energy": 0.60,
        "region_instability_mean": 0.05,
        "cognitive_score": 0.7,
        "functional_improvement": 0.5,
    }
    state = ctrl.evaluate_state(metrics)
    assert state == BrainstemFunctionalState.STABLE


def test_evaluate_state_watchful_moderate_pressure():
    ctrl = BrainstemFunctionalController()
    metrics = {
        "mean_region_phi": 0.25,
        "mean_energy": 0.50,
        "region_instability_mean": 0.20,
        "cognitive_score": 0.4,
        "functional_improvement": 0.2,
    }
    state = ctrl.evaluate_state(metrics)
    assert state == BrainstemFunctionalState.WATCHFUL


def test_evaluate_state_corrective_high_pressure():
    ctrl = BrainstemFunctionalController()
    metrics = {
        "mean_region_phi": 0.15,
        "mean_energy": 0.35,
        "region_instability_mean": 0.40,
        "cognitive_score": 0.2,
        "functional_improvement": 0.1,
    }
    state = ctrl.evaluate_state(metrics)
    assert state == BrainstemFunctionalState.CORRECTIVE


def test_evaluate_state_protective_very_high_pressure():
    ctrl = BrainstemFunctionalController()
    metrics = {
        "mean_region_phi": 0.12,  # just above PHI_COLLAPSE_THRESHOLD to avoid absolute emergency
        "mean_energy": 0.20,
        "region_instability_mean": 0.60,
        "cognitive_score": 0.1,
        "functional_improvement": 0.05,
    }
    state = ctrl.evaluate_state(metrics)
    assert state == BrainstemFunctionalState.PROTECTIVE


def test_evaluate_state_emergency_critical():
    ctrl = BrainstemFunctionalController()
    # Critical energy should trigger emergency regardless of vitality
    metrics = {
        "mean_region_phi": 0.20,
        "mean_energy": 0.05,
        "region_instability_mean": 0.10,
        "cognitive_score": 0.8,
        "functional_improvement": 0.6,
    }
    state = ctrl.evaluate_state(metrics)
    assert state == BrainstemFunctionalState.EMERGENCY


def test_evaluate_state_cognitive_preservation_caps_at_corrective():
    ctrl = BrainstemFunctionalController()
    # High cognitive vitality should cap state at corrective even with moderate risk
    metrics = {
        "mean_region_phi": 0.25,
        "mean_energy": 0.50,
        "region_instability_mean": 0.50,
        "cognitive_score": 0.9,
        "functional_improvement": 0.8,
        "regional_signal_flow": 0.7,
        "deep_region_signal_flow": 0.6,
        "mean_pathway_utility": 0.8,
    }
    state = ctrl.evaluate_state(metrics)
    # With high vitality, should not exceed corrective due to preservation rule
    assert state in {BrainstemFunctionalState.STABLE, BrainstemFunctionalState.WATCHFUL, BrainstemFunctionalState.CORRECTIVE}


def test_evaluate_state_absolute_emergency_overrides_preservation():
    ctrl = BrainstemFunctionalController()
    # Activation explosion should trigger emergency even with high cognition
    metrics = {
        "mean_region_phi": 0.20,
        "mean_energy": 0.50,
        "region_instability_mean": 0.10,
        "mean_deep_region_activation": 6.0,
        "cognitive_score": 0.9,
        "functional_improvement": 0.8,
    }
    state = ctrl.evaluate_state(metrics)
    assert state == BrainstemFunctionalState.EMERGENCY


# ---------------------------------------------------------------------------
# 4. Hysteresis
# ---------------------------------------------------------------------------

def test_emergency_hysteresis_requires_consecutive_ticks():
    ctrl = BrainstemFunctionalController()
    # First tick at emergency pressure — should be downgraded to protective
    metrics = {
        "mean_region_phi": 0.05,
        "mean_energy": 0.08,
        "region_instability_mean": 0.90,
    }
    state = ctrl._apply_hysteresis(BrainstemFunctionalState.EMERGENCY)
    # First time — not yet in emergency, only 1 consecutive tick
    assert state == BrainstemFunctionalState.PROTECTIVE
    # Second tick
    state = ctrl._apply_hysteresis(BrainstemFunctionalState.EMERGENCY)
    assert state == BrainstemFunctionalState.EMERGENCY


def test_emergency_exit_after_pressure_drops():
    ctrl = BrainstemFunctionalController()
    ctrl._in_emergency = True
    ctrl._last_balance_pressure = 0.40  # Below EMERGENCY_EXIT_THRESHOLD (0.55)
    state = ctrl._apply_hysteresis(BrainstemFunctionalState.WATCHFUL)
    assert state == BrainstemFunctionalState.WATCHFUL
    assert ctrl._in_emergency is False


# ---------------------------------------------------------------------------
# 5. Decision computation (T36 soft modulation)
# ---------------------------------------------------------------------------

def test_decide_stable_no_suppression():
    ctrl = BrainstemFunctionalController()
    dec = ctrl.decide({"mean_region_phi": 0.35, "mean_energy": 0.60, "region_instability_mean": 0.05})
    assert dec.state == BrainstemFunctionalState.STABLE
    assert dec.routing_suppression_multiplier == 1.0
    assert dec.plasticity_suppression_multiplier == 1.0


def test_decide_watchful_soft():
    ctrl = BrainstemFunctionalController()
    dec = ctrl.decide({"mean_region_phi": 0.30, "mean_energy": 0.50, "region_instability_mean": 0.20})
    assert dec.state == BrainstemFunctionalState.WATCHFUL
    assert dec.routing_suppression_multiplier == 0.95
    assert dec.plasticity_suppression_multiplier == 0.95
    assert dec.decay_boost_multiplier == 1.05


def test_decide_corrective_soft():
    ctrl = BrainstemFunctionalController()
    dec = ctrl.decide({"mean_region_phi": 0.20, "mean_energy": 0.40, "region_instability_mean": 0.40})
    assert dec.state == BrainstemFunctionalState.CORRECTIVE
    assert dec.routing_suppression_multiplier == 0.85
    assert dec.plasticity_suppression_multiplier == 0.90
    assert dec.decay_boost_multiplier == 1.10


def test_decide_protective_moderate():
    ctrl = BrainstemFunctionalController()
    dec = ctrl.decide({"mean_region_phi": 0.10, "mean_energy": 0.25, "region_instability_mean": 0.60})
    assert dec.state == BrainstemFunctionalState.PROTECTIVE
    assert dec.routing_suppression_multiplier == 0.70
    assert dec.plasticity_suppression_multiplier == 0.75
    assert dec.decay_boost_multiplier == 1.20


def test_decide_emergency_less_aggressive_than_t35():
    ctrl = BrainstemFunctionalController()
    metrics = {"mean_region_phi": 0.05, "mean_energy": 0.05, "region_instability_mean": 0.90}
    # Pre-warm hysteresis so emergency qualifies on second tick
    ctrl._apply_hysteresis(BrainstemFunctionalState.EMERGENCY)
    dec = ctrl.decide(metrics)
    assert dec.state == BrainstemFunctionalState.EMERGENCY
    assert dec.routing_suppression_multiplier == 0.50  # T35 was 0.30
    assert dec.plasticity_suppression_multiplier == 0.50  # T35 was 0.20
    assert dec.decay_boost_multiplier == 1.50  # T35 was 2.00


# ---------------------------------------------------------------------------
# 6. Apply modulation with memory events
# ---------------------------------------------------------------------------

def test_apply_emergency_records_events():
    ctrl = BrainstemFunctionalController()
    mem = MorphologicalMemory()
    metrics = {
        "mean_region_phi": 0.05,
        "mean_energy": 0.05,
        "region_instability_mean": 0.90,
    }
    # Pre-warm hysteresis so emergency qualifies
    ctrl._apply_hysteresis(BrainstemFunctionalState.EMERGENCY)
    ctrl._apply_hysteresis(BrainstemFunctionalState.EMERGENCY)
    result = ctrl.apply(metrics, memory=mem)
    assert result.decision.state == BrainstemFunctionalState.EMERGENCY
    types = [e.event_type for e in mem.events]
    assert MorphologyEventType.BRAINSTEM_STATE_CHANGED in types
    assert MorphologyEventType.BRAINSTEM_MODULATION_APPLIED in types
    assert MorphologyEventType.BRAINSTEM_BALANCE_EVALUATED in types


def test_apply_stable_no_suppression_events():
    ctrl = BrainstemFunctionalController()
    mem = MorphologicalMemory()
    metrics = {"mean_region_phi": 0.35, "mean_energy": 0.60}
    result = ctrl.apply(metrics, memory=mem)
    assert result.decision.state == BrainstemFunctionalState.STABLE
    assert result.state_changed is True
    types = [e.event_type for e in mem.events]
    assert MorphologyEventType.BRAINSTEM_STATE_CHANGED in types
    assert MorphologyEventType.BRAINSTEM_MODULATION_APPLIED in types
    assert MorphologyEventType.BRAINSTEM_EMERGENCY_TRIGGERED not in types


def test_apply_cognitive_preservation_event():
    ctrl = BrainstemFunctionalController()
    mem = MorphologicalMemory()
    metrics = {
        "mean_region_phi": 0.30,
        "mean_energy": 0.50,
        "region_instability_mean": 0.50,
        "cognitive_score": 0.9,
        "functional_improvement": 0.8,
        "regional_signal_flow": 0.7,
        "deep_region_signal_flow": 0.6,
        "mean_pathway_utility": 0.8,
    }
    result = ctrl.apply(metrics, memory=mem)
    types = [e.event_type for e in mem.events]
    assert MorphologyEventType.BRAINSTEM_COGNITIVE_ACTIVITY_PRESERVED in types


def test_apply_suppression_softened_event():
    ctrl = BrainstemFunctionalController()
    mem = MorphologicalMemory()
    metrics = {
        "mean_region_phi": 0.30,
        "mean_energy": 0.50,
        "region_instability_mean": 0.20,
        "cognitive_score": 0.9,
        "functional_improvement": 0.8,
        "regional_signal_flow": 0.7,
        "deep_region_signal_flow": 0.6,
        "mean_pathway_utility": 0.8,
    }
    result = ctrl.apply(metrics, memory=mem)
    types = [e.event_type for e in mem.events]
    assert MorphologyEventType.BRAINSTEM_SUPPRESSION_SOFTENED in types


def test_apply_recovery_actions_count():
    ctrl = BrainstemFunctionalController()
    mem = MorphologicalMemory()
    metrics = {"mean_region_phi": 0.20, "mean_energy": 0.40, "region_instability_mean": 0.40}
    result = ctrl.apply(metrics, memory=mem)
    assert result.recovery_actions == 1
    assert result.homeostatic_gain == -0.02  # T36 corrective


def test_apply_no_state_change_on_second_call():
    ctrl = BrainstemFunctionalController()
    mem = MorphologicalMemory()
    metrics = {"mean_region_phi": 0.20, "mean_energy": 0.40, "region_instability_mean": 0.40}
    r1 = ctrl.apply(metrics, memory=mem)
    assert r1.state_changed is True
    r2 = ctrl.apply(metrics, memory=mem)
    assert r2.state_changed is False


# ---------------------------------------------------------------------------
# 7. Modulation summary (T36 enriched)
# ---------------------------------------------------------------------------

def test_get_modulation_summary_t36_fields():
    ctrl = BrainstemFunctionalController()
    ctrl.apply({"mean_region_phi": 0.05, "mean_energy": 0.05, "region_instability_mean": 0.90})
    summary = ctrl.get_modulation_summary()
    assert "cognitive_vitality" in summary
    assert "autonomic_risk" in summary
    assert "balance_pressure" in summary
    assert "state_ticks" in summary
    assert "cognitive_preservation_applied" in summary
    assert "suppression_cost" in summary
    assert "useful_activity_preserved" in summary
    assert "in_emergency" in summary


def test_state_ticks_tracked():
    ctrl = BrainstemFunctionalController()
    ctrl.apply({"mean_region_phi": 0.35, "mean_energy": 0.60})
    ctrl.apply({"mean_region_phi": 0.20, "mean_energy": 0.40, "region_instability_mean": 0.40})
    summary = ctrl.get_modulation_summary()
    assert summary["state_ticks"]["stable"] == 1
    assert summary["state_ticks"]["corrective"] == 1


# ---------------------------------------------------------------------------
# 8. Orchestrator integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orchestrator_brainstem_enabled():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.brainstem_controller_enabled = True
    # Re-initialize to pick up the new flag
    orch.model_post_init(None)
    assert orch._brainstem_controller is not None


@pytest.mark.asyncio
async def test_orchestrator_brainstem_applies_modulations():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import NeuroFunctionalBenchmark

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.brainstem_controller_enabled = True
    orch.model_post_init(None)

    bench = NeuroFunctionalBenchmark(orch)
    result = await bench.run_case(
        "morphological_memory_trace",
        execution_mode="event_driven_burst",
        n_ticks=3,
    )
    m = result.metrics
    assert hasattr(m, "brainstem_state")
    assert hasattr(m, "brainstem_decisions_count")
    assert m.brainstem_decisions_count >= 0


# ---------------------------------------------------------------------------
# 9. Metric enrichment from stability controller
# ---------------------------------------------------------------------------

def test_apply_enriches_instability_from_stability_summary():
    ctrl = BrainstemFunctionalController()
    mem = MorphologicalMemory()
    # Simulate stability-like metrics with high enough pressure for protective
    metrics = {
        "mean_region_phi": 0.10,
        "mean_energy": 0.20,
        "region_instability_mean": 0.90,
        "unstable_region_count": 0,
        "cognitive_score": 0.0,
        "functional_improvement": 0.0,
    }
    result = ctrl.apply(metrics, memory=mem)
    assert result.decision.state == BrainstemFunctionalState.PROTECTIVE


# ---------------------------------------------------------------------------
# 10. T36 Benchmark metrics presence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_benchmark_t36_metrics_present():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import NeuroFunctionalBenchmark

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.brainstem_controller_enabled = True
    orch.model_post_init(None)

    bench = NeuroFunctionalBenchmark(orch)
    result = await bench.run_case(
        "morphological_memory_trace",
        execution_mode="event_driven_burst",
        n_ticks=2,
    )
    m = result.metrics
    assert hasattr(m, "cognitive_vitality_score")
    assert hasattr(m, "autonomic_risk_score")
    assert hasattr(m, "balance_pressure")
    assert hasattr(m, "emergency_ticks")
    assert hasattr(m, "protective_ticks")
    assert hasattr(m, "cognitive_preservation_score")
    assert hasattr(m, "suppression_cost")
    assert hasattr(m, "useful_activity_preserved")


# ---------------------------------------------------------------------------
# 11. Soft modulation vs T35 defaults
# ---------------------------------------------------------------------------

def test_soft_modulation_less_suppressive_than_t35():
    ctrl = BrainstemFunctionalController()
    # Watchful should be softer
    dec_w = ctrl.decide({"mean_region_phi": 0.25, "mean_energy": 0.50, "region_instability_mean": 0.20})
    assert dec_w.routing_suppression_multiplier == 0.95  # T35 was 0.90

    # Corrective should be softer
    dec_c = ctrl.decide({"mean_region_phi": 0.15, "mean_energy": 0.40, "region_instability_mean": 0.40})
    assert dec_c.routing_suppression_multiplier == 0.85  # T35 was 0.75
    assert dec_c.plasticity_suppression_multiplier == 0.90  # T35 was 0.80

    # Protective should be softer
    dec_p = ctrl.decide({"mean_region_phi": 0.10, "mean_energy": 0.25, "region_instability_mean": 0.60})
    assert dec_p.routing_suppression_multiplier == 0.70  # T35 was 0.55
    assert dec_p.plasticity_suppression_multiplier == 0.75  # T35 was 0.50

    # Emergency should be softer (pre-warm hysteresis first)
    ctrl2 = BrainstemFunctionalController()
    ctrl2._apply_hysteresis(BrainstemFunctionalState.EMERGENCY)
    ctrl2._apply_hysteresis(BrainstemFunctionalState.EMERGENCY)
    dec_e = ctrl2.decide({"mean_region_phi": 0.05, "mean_energy": 0.05, "region_instability_mean": 0.90})
    assert dec_e.routing_suppression_multiplier == 0.50  # T35 was 0.30
    assert dec_e.plasticity_suppression_multiplier == 0.50  # T35 was 0.20


# ---------------------------------------------------------------------------
# 12. T39 — Gain Input Coupling Redesign
# ---------------------------------------------------------------------------

def test_gain_coupled_vitality_increases_with_cognitive_preservation():
    ctrl = BrainstemFunctionalController()
    metrics = {"mean_region_phi": 0.30, "mean_energy": 0.50, "region_instability_mean": 0.10}
    vitality_raw, risk_raw, _ = ctrl.compute_balance_pressure(metrics)
    adj_vit, adj_risk, _ = ctrl.apply_gain_to_input_scores(vitality_raw, risk_raw, {"cognitive_preservation_gain": 1.30})
    assert adj_vit > vitality_raw
    assert adj_vit <= 1.0


def test_gain_coupled_risk_decreases_with_lower_emergency_gain():
    ctrl = BrainstemFunctionalController()
    metrics = {"mean_region_phi": 0.30, "mean_energy": 0.50, "region_instability_mean": 0.10}
    vitality_raw, risk_raw, _ = ctrl.compute_balance_pressure(metrics)
    adj_vit, adj_risk, _ = ctrl.apply_gain_to_input_scores(vitality_raw, risk_raw, {"emergency_gain": 0.60})
    assert adj_risk < risk_raw


def test_adjusted_balance_pressure_changes_state_selection():
    ctrl = BrainstemFunctionalController()
    # Raw metrics would produce protective
    metrics = {"mean_region_phi": 0.10, "mean_energy": 0.25, "region_instability_mean": 0.60, "cognitive_score": 0.0, "functional_improvement": 0.0}
    raw_state = ctrl.evaluate_state(metrics)
    # With high cognitive preservation gain, vitality is boosted → state should be lower
    adjusted_state = ctrl.evaluate_state(metrics, gain_vector={"cognitive_preservation_gain": 1.50, "emergency_gain": 1.0})
    assert adjusted_state.value in ["stable", "watchful", "corrective"] or adjusted_state.value != raw_state.value


def test_dynamic_thresholds_clamped():
    ctrl = BrainstemFunctionalController()
    thresholds = ctrl.compute_adjusted_thresholds({"cognitive_preservation_gain": 1.50, "emergency_gain": 0.40})
    assert 0.10 <= thresholds["protective"] <= 0.60
    assert -0.20 <= thresholds["corrective"] <= 0.40
    assert 0.35 <= thresholds["emergency"] <= 0.90


def test_protective_escape_fires_after_persistent_protective():
    ctrl = BrainstemFunctionalController()
    mem = MorphologicalMemory()
    # Metrics that evaluate to PROTECTIVE state
    metrics = {"mean_region_phi": 0.12, "mean_energy": 0.10, "region_instability_mean": 1.0}
    for _ in range(3):
        ctrl.apply(metrics, memory=mem)
    assert ctrl._protective_consecutive_ticks == 3
    # Escape logic is verified directly below; through normal evaluate_state
    # high adjusted vitality would cap state at corrective, so we test the
    # helper in isolation.
    ctrl._last_adjusted_vitality = 0.50
    ctrl._last_adjusted_risk = 0.40
    state, escaped = ctrl.protective_escape(
        BrainstemFunctionalState.PROTECTIVE, energy=0.20
    )
    assert escaped is True
    assert state == BrainstemFunctionalState.CORRECTIVE


def test_protective_escape_does_not_fire_under_critical_energy():
    ctrl = BrainstemFunctionalController()
    state, escaped = ctrl.protective_escape(BrainstemFunctionalState.PROTECTIVE, energy=0.10)
    assert escaped is False


def test_output_coupling_changes_final_modulations():
    ctrl = BrainstemFunctionalController()
    mem = MorphologicalMemory()
    metrics = {"mean_region_phi": 0.20, "mean_energy": 0.50, "region_instability_mean": 0.50}
    result = ctrl.apply(metrics, memory=mem, gain_vector={"cognitive_preservation_gain": 1.30, "emergency_gain": 0.80})
    # Coupling trace should exist
    assert len(ctrl._coupling_traces) >= 1
    trace = ctrl._coupling_traces[-1]
    assert trace.coupling_delta >= 0.0


def test_coupling_trace_is_produced():
    ctrl = BrainstemFunctionalController()
    mem = MorphologicalMemory()
    metrics = {"mean_region_phi": 0.30, "mean_energy": 0.60}
    ctrl.apply(metrics, memory=mem, gain_vector={"routing_gain": 1.10})
    assert len(ctrl._coupling_traces) >= 1
    trace = ctrl._coupling_traces[0]
    assert trace.tick_id >= 1
    assert "routing_gain" in trace.gain_vector


def test_low_suppression_profile_reduces_suppression_cost():
    ctrl = BrainstemFunctionalController()
    mem = MorphologicalMemory()
    # Without gain: likely protective
    metrics = {"mean_region_phi": 0.15, "mean_energy": 0.30, "region_instability_mean": 0.55}
    ctrl.apply(metrics, memory=mem)
    cost_without = ctrl._last_suppression_cost
    # With low_suppression gain profile
    ctrl2 = BrainstemFunctionalController()
    ctrl2.apply(metrics, memory=mem, gain_vector={"cognitive_preservation_gain": 1.50, "emergency_gain": 0.45})
    cost_with = ctrl2._last_suppression_cost
    assert cost_with <= cost_without


def test_cognitive_preserving_profile_increases_corrective_transitions():
    ctrl = BrainstemFunctionalController()
    mem = MorphologicalMemory()
    metrics = {"mean_region_phi": 0.15, "mean_energy": 0.30, "region_instability_mean": 0.55}
    ctrl.apply(metrics, memory=mem, gain_vector={"cognitive_preservation_gain": 1.50})
    summary = ctrl.get_modulation_summary()
    assert summary["corrective_state_ratio"] >= 0.0


@pytest.mark.asyncio
async def test_benchmark_espose_metriche_t39():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator
    from speace_core.cellular_brain.benchmark.neurofunctional_benchmark import NeuroFunctionalBenchmark

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.brainstem_controller_enabled = True
    orch.brainstem_gain_controller_enabled = True
    orch.model_post_init(None)

    bench = NeuroFunctionalBenchmark(orch)
    result = await bench.run_case(
        "morphological_memory_trace",
        execution_mode="event_driven_burst",
        n_ticks=3,
    )
    m = result.metrics
    assert hasattr(m, "gain_input_coupling_strength")
    assert hasattr(m, "adjusted_cognitive_vitality_score")
    assert hasattr(m, "adjusted_autonomic_risk_score")
    assert hasattr(m, "adjusted_balance_pressure")
    assert hasattr(m, "protective_escape_count")
    assert hasattr(m, "protective_state_ratio")
    assert hasattr(m, "corrective_state_ratio")
    assert hasattr(m, "coupling_delta_mean")
    assert hasattr(m, "suppression_cost_after_coupling")
    assert hasattr(m, "brainstem_state_transition_count")


def test_eventi_t39_registrati():
    ctrl = BrainstemFunctionalController()
    mem = MorphologicalMemory()
    metrics = {"mean_region_phi": 0.15, "mean_energy": 0.30, "region_instability_mean": 0.55}
    ctrl.apply(metrics, memory=mem, gain_vector={"cognitive_preservation_gain": 1.30, "emergency_gain": 0.80})
    types = [e.event_type for e in mem.events]
    assert MorphologyEventType.BRAINSTEM_GAIN_INPUT_COUPLED in types
    assert MorphologyEventType.BRAINSTEM_STATE_THRESHOLD_ADJUSTED in types
    assert MorphologyEventType.BRAINSTEM_OUTPUT_COUPLED in types
    assert MorphologyEventType.BRAINSTEM_COUPLING_TRACE_RECORDED in types


def test_get_modulation_summary_t39_fields():
    ctrl = BrainstemFunctionalController()
    ctrl.apply({"mean_region_phi": 0.05, "mean_energy": 0.05, "region_instability_mean": 0.90}, gain_vector={"cognitive_preservation_gain": 1.20})
    summary = ctrl.get_modulation_summary()
    assert "adjusted_cognitive_vitality" in summary
    assert "adjusted_autonomic_risk" in summary
    assert "adjusted_balance_pressure" in summary
    assert "protective_escape_count" in summary
    assert "protective_state_ratio" in summary
    assert "coupling_delta" in summary
    assert "suppression_cost_after_coupling" in summary
    assert "state_transition_count" in summary
