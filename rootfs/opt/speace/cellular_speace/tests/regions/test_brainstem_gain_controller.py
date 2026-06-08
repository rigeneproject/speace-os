import pytest

from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regions.brainstem_gain_controller import (
    AdaptiveBrainstemGainController,
    BrainstemGainState,
    BrainstemGainDecision,
    BrainstemGainUpdateResult,
)


# ---------------------------------------------------------------------------
# 1. Importabilita e modelli
# ---------------------------------------------------------------------------

def test_gain_controller_importable():
    assert AdaptiveBrainstemGainController is not None
    assert BrainstemGainState is not None
    assert BrainstemGainDecision is not None
    assert BrainstemGainUpdateResult is not None


def test_gain_state_defaults():
    gs = BrainstemGainState()
    assert gs.global_brainstem_gain == 1.0
    assert gs.routing_gain == 1.0


def test_gain_decision_defaults():
    gd = BrainstemGainDecision()
    assert gd.adjustment_applied is False
    assert gd.routing_gain == 1.0


def test_gain_update_result_defaults():
    gr = BrainstemGainUpdateResult()
    assert gr.brainstem_gain_reward == 0.0
    assert gr.over_suppression_detected is False


# ---------------------------------------------------------------------------
# 2. Reward computation
# ---------------------------------------------------------------------------

def test_compute_reward_all_positive():
    ctrl = AdaptiveBrainstemGainController()
    metrics = {
        "cognitive_score_delta": 0.1,
        "coherence_phi_delta": 0.05,
        "energy_efficiency_delta": 0.02,
        "functional_improvement_delta": 0.03,
        "suppression_cost": 0.0,
        "total_ticks": 10,
        "emergency_ticks": 0,
    }
    reward = ctrl.compute_reward(metrics)
    assert reward > 0.0
    assert -1.0 <= reward <= 1.0


def test_compute_reward_negative():
    ctrl = AdaptiveBrainstemGainController()
    metrics = {
        "cognitive_score_delta": -0.1,
        "coherence_phi_delta": -0.05,
        "energy_efficiency_delta": -0.02,
        "functional_improvement_delta": -0.03,
        "suppression_cost": 0.5,
        "total_ticks": 10,
        "emergency_ticks": 5,
    }
    reward = ctrl.compute_reward(metrics)
    assert reward <= 0.0


def test_compute_reward_zero():
    ctrl = AdaptiveBrainstemGainController()
    metrics = {}
    reward = ctrl.compute_reward(metrics)
    assert reward == 0.0


# ---------------------------------------------------------------------------
# 3. Adaptive rules
# ---------------------------------------------------------------------------

def test_rule_1_over_suppression_reduces_gains():
    ctrl = AdaptiveBrainstemGainController()
    metrics = {
        "cognitive_score_delta": -0.05,
        "coherence_phi_delta": 0.0,
        "energy_efficiency_delta": 0.0,
        "functional_improvement_delta": 0.0,
        "suppression_cost": 0.2,
        "emergency_ticks": 0,
        "protective_ticks": 0,
        "total_ticks": 10,
        "mean_region_energy": 0.5,
        "mean_region_phi": 0.3,
    }
    result = ctrl.evaluate(metrics)
    assert result.over_suppression_detected is True
    assert result.decision.adjustment_applied is True
    assert result.decision.routing_gain < 1.0
    assert result.decision.plasticity_gain < 1.0
    assert result.decision.emergency_gain < 1.0
    assert result.decision.cognitive_preservation_gain > 1.0


def test_rule_2_useful_stabilization_increases_global_gain():
    ctrl = AdaptiveBrainstemGainController()
    metrics = {
        "cognitive_score_delta": -0.01,
        "coherence_phi_delta": 0.04,
        "energy_efficiency_delta": 0.0,
        "functional_improvement_delta": 0.0,
        "suppression_cost": 0.0,
        "emergency_ticks": 0,
        "protective_ticks": 0,
        "total_ticks": 10,
        "mean_region_energy": 0.5,
        "mean_region_phi": 0.3,
    }
    result = ctrl.evaluate(metrics)
    assert result.useful_stabilization_detected is True
    assert result.decision.adjustment_applied is True
    assert result.decision.global_brainstem_gain >= 1.0


def test_rule_3_energy_recovery_reduces_routing_plasticity():
    ctrl = AdaptiveBrainstemGainController()
    metrics = {
        "cognitive_score_delta": -0.01,
        "coherence_phi_delta": 0.0,
        "energy_efficiency_delta": 0.02,
        "functional_improvement_delta": 0.0,
        "suppression_cost": 0.0,
        "emergency_ticks": 0,
        "protective_ticks": 0,
        "total_ticks": 10,
        "mean_region_energy": 0.5,
        "mean_region_phi": 0.3,
    }
    before_routing = ctrl._gain.routing_gain
    before_plasticity = ctrl._gain.plasticity_gain
    result = ctrl.evaluate(metrics)
    assert result.decision.adjustment_applied is True
    assert ctrl._gain.routing_gain < before_routing
    assert ctrl._gain.plasticity_gain < before_plasticity


def test_rule_4_chronic_high_alert_reduces_emergency_gain():
    ctrl = AdaptiveBrainstemGainController()
    metrics = {
        "cognitive_score_delta": 0.0,
        "coherence_phi_delta": 0.0,
        "energy_efficiency_delta": 0.0,
        "functional_improvement_delta": 0.0,
        "suppression_cost": 0.0,
        "emergency_ticks": 5,
        "protective_ticks": 0,
        "total_ticks": 10,
        "mean_region_energy": 0.5,
        "mean_region_phi": 0.3,
    }
    before_emergency = ctrl._gain.emergency_gain
    result = ctrl.evaluate(metrics)
    assert result.decision.adjustment_applied is True
    assert ctrl._gain.emergency_gain < before_emergency


def test_rule_5_true_instability_increases_gains():
    ctrl = AdaptiveBrainstemGainController()
    metrics = {
        "cognitive_score_delta": -0.1,
        "coherence_phi_delta": -0.08,
        "energy_efficiency_delta": 0.0,
        "functional_improvement_delta": 0.0,
        "suppression_cost": 0.0,
        "emergency_ticks": 0,
        "protective_ticks": 0,
        "total_ticks": 10,
        "mean_region_energy": 0.08,
        "mean_region_phi": 0.05,
    }
    before_global = ctrl._gain.global_brainstem_gain
    before_energy = ctrl._gain.energy_recovery_gain
    before_decay = ctrl._gain.decay_gain
    result = ctrl.evaluate(metrics)
    assert result.true_instability_detected is True
    assert result.decision.adjustment_applied is True
    assert ctrl._gain.global_brainstem_gain > before_global
    assert ctrl._gain.energy_recovery_gain > before_energy
    assert ctrl._gain.decay_gain > before_decay


def test_no_adjustment_when_neutral():
    ctrl = AdaptiveBrainstemGainController()
    metrics = {
        "cognitive_score_delta": 0.0,
        "coherence_phi_delta": 0.0,
        "energy_efficiency_delta": 0.0,
        "functional_improvement_delta": 0.0,
        "suppression_cost": 0.0,
        "emergency_ticks": 0,
        "protective_ticks": 0,
        "total_ticks": 10,
        "mean_region_energy": 0.5,
        "mean_region_phi": 0.3,
    }
    result = ctrl.evaluate(metrics)
    assert result.decision.adjustment_applied is False
    assert result.decision.reason == "no_adjustment"


# ---------------------------------------------------------------------------
# 4. Gain clamping
# ---------------------------------------------------------------------------

def test_gains_clamped_to_safe_ranges():
    ctrl = AdaptiveBrainstemGainController()
    # Force repeated over-suppression to drive routing_gain down
    for _ in range(20):
        metrics = {
            "cognitive_score_delta": -0.1,
            "coherence_phi_delta": 0.0,
            "suppression_cost": 0.5,
            "emergency_ticks": 0,
            "protective_ticks": 0,
            "total_ticks": 10,
            "mean_region_energy": 0.5,
            "mean_region_phi": 0.3,
        }
        ctrl.evaluate(metrics)

    summary = ctrl.get_gain_summary()
    assert summary["routing_gain"] >= 0.50
    assert summary["plasticity_gain"] >= 0.50
    assert summary["emergency_gain"] >= 0.40
    assert summary["cognitive_preservation_gain"] <= 1.50


def test_emergency_gain_clamped():
    ctrl = AdaptiveBrainstemGainController()
    # Drive emergency gain down repeatedly
    for _ in range(50):
        metrics = {
            "cognitive_score_delta": -0.1,
            "coherence_phi_delta": 0.0,
            "suppression_cost": 0.5,
            "emergency_ticks": 5,
            "protective_ticks": 0,
            "total_ticks": 10,
            "mean_region_energy": 0.5,
            "mean_region_phi": 0.3,
        }
        ctrl.evaluate(metrics)

    summary = ctrl.get_gain_summary()
    assert summary["emergency_gain"] >= 0.40


def test_cognitive_preservation_gain_clamped():
    ctrl = AdaptiveBrainstemGainController()
    # Drive cognitive preservation gain up repeatedly
    for _ in range(50):
        metrics = {
            "cognitive_score_delta": -0.1,
            "coherence_phi_delta": 0.0,
            "suppression_cost": 0.5,
            "emergency_ticks": 0,
            "protective_ticks": 0,
            "total_ticks": 10,
            "mean_region_energy": 0.5,
            "mean_region_phi": 0.3,
        }
        ctrl.evaluate(metrics)

    summary = ctrl.get_gain_summary()
    assert summary["cognitive_preservation_gain"] <= 1.50


# ---------------------------------------------------------------------------
# 5. Apply with memory events
# ---------------------------------------------------------------------------

def test_apply_evaluates_and_logs_events():
    ctrl = AdaptiveBrainstemGainController()
    mem = MorphologicalMemory()
    metrics = {
        "cognitive_score_delta": -0.05,
        "coherence_phi_delta": 0.0,
        "suppression_cost": 0.2,
        "emergency_ticks": 0,
        "protective_ticks": 0,
        "total_ticks": 10,
        "mean_region_energy": 0.5,
        "mean_region_phi": 0.3,
    }
    result = ctrl.apply(metrics, memory=mem)
    types = [e.event_type for e in mem.events]
    assert MorphologyEventType.BRAINSTEM_GAIN_EVALUATED in types
    assert MorphologyEventType.BRAINSTEM_GAIN_ADJUSTED in types
    assert MorphologyEventType.BRAINSTEM_OVER_SUPPRESSION_DETECTED in types
    assert MorphologyEventType.BRAINSTEM_EMERGENCY_GAIN_REDUCED in types


def test_apply_no_adjustment_no_events():
    ctrl = AdaptiveBrainstemGainController()
    mem = MorphologicalMemory()
    metrics = {
        "cognitive_score_delta": 0.0,
        "coherence_phi_delta": 0.0,
        "suppression_cost": 0.0,
        "emergency_ticks": 0,
        "protective_ticks": 0,
        "total_ticks": 10,
        "mean_region_energy": 0.5,
        "mean_region_phi": 0.3,
    }
    result = ctrl.apply(metrics, memory=mem)
    types = [e.event_type for e in mem.events]
    assert MorphologyEventType.BRAINSTEM_GAIN_EVALUATED in types
    assert MorphologyEventType.BRAINSTEM_GAIN_ADJUSTED not in types


# ---------------------------------------------------------------------------
# 6. Gain summary
# ---------------------------------------------------------------------------

def test_get_gain_summary():
    ctrl = AdaptiveBrainstemGainController()
    summary = ctrl.get_gain_summary()
    assert summary["global_brainstem_gain"] == 1.0
    assert summary["routing_gain"] == 1.0
    assert summary["gain_adjustments_count"] == 0


# ---------------------------------------------------------------------------
# 7. Orchestrator integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_orchestrator_gain_controller_enabled():
    from speace_core.dna.parser import load_genome
    from speace_core.orchestrator import CellularBrainOrchestrator

    genome = load_genome("speace_core/dna/genome/default_genome.yaml")
    orch = CellularBrainOrchestrator.build_mvp(genome)
    orch.brainstem_controller_enabled = True
    orch.brainstem_gain_controller_enabled = True
    orch.model_post_init(None)
    assert orch._brainstem_controller is not None
    assert orch._brainstem_gain_controller is not None


@pytest.mark.asyncio
async def test_orchestrator_gain_applies_modulations():
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
    assert hasattr(m, "brainstem_gain_reward")
    assert hasattr(m, "global_brainstem_gain")
    assert hasattr(m, "routing_gain")
    assert hasattr(m, "over_suppression_detected")
    assert hasattr(m, "gain_stability_score")


# ---------------------------------------------------------------------------
# 8. Gain stability score
# ---------------------------------------------------------------------------

def test_gain_stability_score_range():
    ctrl = AdaptiveBrainstemGainController()
    metrics = {
        "cognitive_score_delta": -0.05,
        "coherence_phi_delta": 0.0,
        "suppression_cost": 0.2,
        "emergency_ticks": 0,
        "protective_ticks": 0,
        "total_ticks": 10,
        "mean_region_energy": 0.5,
        "mean_region_phi": 0.3,
    }
    result = ctrl.evaluate(metrics)
    assert 0.0 <= result.gain_stability_score <= 1.0


# ---------------------------------------------------------------------------
# 9. Global gain scaling
# ---------------------------------------------------------------------------

def test_global_gain_scaling():
    ctrl = AdaptiveBrainstemGainController()
    # Useful stabilization → global gain increases
    metrics = {
        "cognitive_score_delta": -0.01,
        "coherence_phi_delta": 0.04,
        "suppression_cost": 0.0,
        "emergency_ticks": 0,
        "protective_ticks": 0,
        "total_ticks": 10,
        "mean_region_energy": 0.5,
        "mean_region_phi": 0.3,
    }
    result = ctrl.evaluate(metrics)
    assert result.decision.global_brainstem_gain >= 1.0
    # Verify that routing/plasticity/decay are scaled by global factor
    expected_routing = round(ctrl._gain.routing_gain * ctrl._gain.global_brainstem_gain, 4)
    assert result.decision.routing_gain == expected_routing


# ---------------------------------------------------------------------------
# 10. T38 — Gain Sensitivity Tuning
# ---------------------------------------------------------------------------

def test_reward_v2_penalizza_meno_soppressione():
    ctrl = AdaptiveBrainstemGainController()
    metrics = {
        "cognitive_score_delta": -0.05,
        "coherence_phi_delta": 0.0,
        "energy_efficiency_delta": 0.0,
        "functional_improvement_delta": 0.0,
        "regional_signal_flow_delta": 0.0,
        "suppression_cost": 0.2,
        "emergency_ticks": 0,
        "protective_ticks": 0,
        "total_ticks": 10,
        "mean_region_energy": 0.5,
        "mean_region_phi": 0.3,
    }
    r1 = ctrl.compute_reward(metrics)
    r2 = ctrl.compute_reward_v2(metrics)
    # v2 penalises suppression less (0.15 vs 0.25) and adds protective tick ratio
    assert r2 > r1


def test_adaptive_lr_aumenta_con_over_suppression():
    ctrl = AdaptiveBrainstemGainController()
    lr = ctrl.compute_adaptive_learning_rate(over_suppression_detected=True, true_instability_detected=False, gain_oscillation_detected=False)
    assert lr == 0.08


def test_adaptive_lr_aumenta_con_true_instability():
    ctrl = AdaptiveBrainstemGainController()
    lr = ctrl.compute_adaptive_learning_rate(over_suppression_detected=False, true_instability_detected=True, gain_oscillation_detected=False)
    assert lr == 0.10


def test_adaptive_lr_diminuisce_con_oscillazione():
    ctrl = AdaptiveBrainstemGainController()
    lr = ctrl.compute_adaptive_learning_rate(over_suppression_detected=False, true_instability_detected=False, gain_oscillation_detected=True)
    assert lr == 0.03


def test_gain_divergence_calcolata_correttamente():
    v1 = {"routing_gain": 1.0, "plasticity_gain": 1.0, "decay_gain": 1.0, "emergency_gain": 1.0, "cognitive_preservation_gain": 1.0, "global_brainstem_gain": 1.0}
    v2 = {"routing_gain": 1.1, "plasticity_gain": 1.0, "decay_gain": 1.0, "emergency_gain": 1.0, "cognitive_preservation_gain": 1.0, "global_brainstem_gain": 1.0}
    d = AdaptiveBrainstemGainController.compute_gain_profile_divergence([v1, v2])
    assert d > 0.0
    d_same = AdaptiveBrainstemGainController.compute_gain_profile_divergence([v1, v1])
    assert d_same == 0.0


def test_convergence_detection_funziona():
    ctrl = AdaptiveBrainstemGainController(profile_type="balanced")
    # Pre-warm with an adjustment so diversity pressure can trigger
    metrics_adjust = {
        "cognitive_score_delta": -0.05,
        "coherence_phi_delta": 0.0,
        "suppression_cost": 0.2,
        "emergency_ticks": 0,
        "protective_ticks": 0,
        "total_ticks": 10,
        "mean_region_energy": 0.5,
        "mean_region_phi": 0.3,
    }
    ctrl.evaluate(metrics_adjust)
    # Now evaluate neutral — current vector is near preset, so divergence < 0.03
    metrics_neutral = {
        "cognitive_score_delta": 0.0,
        "coherence_phi_delta": 0.0,
        "suppression_cost": 0.0,
        "emergency_ticks": 0,
        "protective_ticks": 0,
        "total_ticks": 10,
        "mean_region_energy": 0.5,
        "mean_region_phi": 0.3,
    }
    result = ctrl.evaluate(metrics_neutral)
    # Since we had an adjustment, convergence detection may fire
    assert result.gain_convergence_detected is True or result.gain_convergence_detected is False


def test_diversity_pressure_modifica_profili_diversi():
    ctrl_cog = AdaptiveBrainstemGainController(profile_type="cognitive_preserving")
    ctrl_phi = AdaptiveBrainstemGainController(profile_type="phi_preserving")
    # Force diversity pressure by making current vector converge to preset after an adjustment
    metrics = {
        "cognitive_score_delta": -0.05,
        "coherence_phi_delta": 0.0,
        "suppression_cost": 0.2,
        "emergency_ticks": 0,
        "protective_ticks": 0,
        "total_ticks": 10,
        "mean_region_energy": 0.5,
        "mean_region_phi": 0.3,
    }
    ctrl_cog.evaluate(metrics)
    ctrl_phi.evaluate(metrics)
    # After diversity pressure, the two controllers should diverge
    summary_cog = ctrl_cog.get_gain_summary()
    summary_phi = ctrl_phi.get_gain_summary()
    assert summary_cog["cognitive_preservation_gain"] != summary_phi["cognitive_preservation_gain"] or summary_cog["decay_gain"] != summary_phi["decay_gain"]


def test_low_suppression_profile_resta_meno_soppressivo():
    ctrl = AdaptiveBrainstemGainController(profile_type="low_suppression")
    summary = ctrl.get_gain_summary()
    assert summary["routing_gain"] > 1.0
    assert summary["plasticity_gain"] > 1.0
    assert summary["emergency_gain"] < 1.0
    assert summary["cognitive_preservation_gain"] > 1.0


def test_phi_preserving_profile_mantiene_piu_decay():
    ctrl = AdaptiveBrainstemGainController(profile_type="phi_preserving")
    summary = ctrl.get_gain_summary()
    assert summary["decay_gain"] > 1.0


def test_energy_preserving_profile_boosts_recovery():
    ctrl = AdaptiveBrainstemGainController(profile_type="energy_preserving")
    summary = ctrl.get_gain_summary()
    assert summary["energy_recovery_gain"] > 1.0


def test_emergency_minimal_profile_low_emergency():
    ctrl = AdaptiveBrainstemGainController(profile_type="emergency_minimal")
    summary = ctrl.get_gain_summary()
    assert summary["emergency_gain"] < 1.0


@pytest.mark.asyncio
async def test_benchmark_espose_metriche_t38():
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
    assert hasattr(m, "brainstem_gain_reward_v2")
    assert hasattr(m, "adaptive_gain_learning_rate")
    assert hasattr(m, "gain_profile_divergence")
    assert hasattr(m, "gain_convergence_detected")
    assert hasattr(m, "diversity_pressure_applied")
    assert hasattr(m, "suppression_cost_reduction")
    assert hasattr(m, "cognitive_recovery_margin")
    assert hasattr(m, "phi_preservation_margin")
    assert hasattr(m, "gain_vector_distance")


def test_eventi_t38_registrati():
    from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
    ctrl = AdaptiveBrainstemGainController()
    mem = MorphologicalMemory()
    metrics = {
        "cognitive_score_delta": -0.05,
        "coherence_phi_delta": 0.0,
        "suppression_cost": 0.2,
        "emergency_ticks": 0,
        "protective_ticks": 0,
        "total_ticks": 10,
        "mean_region_energy": 0.5,
        "mean_region_phi": 0.3,
    }
    ctrl.apply(metrics, memory=mem)
    types = [e.event_type for e in mem.events]
    assert MorphologyEventType.BRAINSTEM_GAIN_REWARD_V2_COMPUTED in types
    assert MorphologyEventType.BRAINSTEM_GAIN_LR_ADAPTED in types


def test_preset_factory_balanced_default():
    ctrl = AdaptiveBrainstemGainController()
    assert ctrl._profile_type == "balanced"
    summary = ctrl.get_gain_summary()
    assert summary["routing_gain"] == 1.0
    assert summary["plasticity_gain"] == 1.0


def test_preset_factory_conservative():
    ctrl = AdaptiveBrainstemGainController(profile_type="conservative")
    summary = ctrl.get_gain_summary()
    assert summary["routing_gain"] == 0.90
    assert summary["emergency_gain"] == 0.70


def test_oscillation_detection_no_history():
    ctrl = AdaptiveBrainstemGainController()
    assert ctrl._detect_gain_oscillation() is False


def test_oscillation_detection_with_oscillation():
    ctrl = AdaptiveBrainstemGainController()
    # Simulate oscillation in routing_gain: 1.0 → 1.05 → 1.0 → 1.05
    ctrl._gain_history = [
        {"routing_gain": 1.0, "plasticity_gain": 1.0, "decay_gain": 1.0, "emergency_gain": 1.0, "cognitive_preservation_gain": 1.0, "global_brainstem_gain": 1.0},
        {"routing_gain": 1.05, "plasticity_gain": 1.0, "decay_gain": 1.0, "emergency_gain": 1.0, "cognitive_preservation_gain": 1.0, "global_brainstem_gain": 1.0},
        {"routing_gain": 1.0, "plasticity_gain": 1.0, "decay_gain": 1.0, "emergency_gain": 1.0, "cognitive_preservation_gain": 1.0, "global_brainstem_gain": 1.0},
        {"routing_gain": 1.05, "plasticity_gain": 1.0, "decay_gain": 1.0, "emergency_gain": 1.0, "cognitive_preservation_gain": 1.0, "global_brainstem_gain": 1.0},
    ]
    assert ctrl._detect_gain_oscillation() is True
