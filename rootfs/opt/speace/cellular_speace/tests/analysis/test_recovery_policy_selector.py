import json
from pathlib import Path

import pytest

from speace_core.cellular_brain.analysis.long_horizon_adaptation_audit import (
    LongHorizonAuditResult,
    LongHorizonProfileResult,
    LongHorizonTrajectoryPoint,
)
from speace_core.cellular_brain.analysis.recovery_policy_selector import (
    FrozenBrainstemThresholds,
    FrozenEnergyProfile,
    FrozenFlags,
    FrozenGainProfile,
    RecoveryPolicy,
    RecoveryPolicySelectionResult,
    RecoveryPolicySelector,
    RegressionGuardThresholds,
)

from speace_core.cellular_brain.analysis.deep_region_audit import DeepRegionAuditProfile


# ------------------------------------------------------------------ #
# Import & construction
# ------------------------------------------------------------------ #

def test_selector_importable():
    assert RecoveryPolicySelector is not None


def test_policy_model_defaults():
    p = RecoveryPolicy()
    assert p.policy_id == "recovery_policy_v0_3_25"
    assert p.frozen_flags.deep_regions_enabled is True
    assert p.frozen_gain_profile.routing_gain == 1.0


# ------------------------------------------------------------------ #
# compute_policy_score
# ------------------------------------------------------------------ #

def test_score_passed_profile():
    result = LongHorizonProfileResult(
        profile=DeepRegionAuditProfile(profile_id="lh5", name="t39"),
        long_horizon_recovery_score=0.2344,
        net_gain_slope=0.0001,
        suppression_cost_slope=-0.0001,
        state_entropy=1.5,
        emergency_state_ratio_over_time=0.0,
        passed=True,
    )
    score = RecoveryPolicySelector.compute_policy_score(result)
    assert score > 0.0


def test_score_failed_profile_is_penalized():
    result = LongHorizonProfileResult(
        profile=DeepRegionAuditProfile(profile_id="bad", name="bad"),
        passed=False,
    )
    score = RecoveryPolicySelector.compute_policy_score(result)
    assert score == -999.0


def test_score_negative_slope_reduces_score():
    result = LongHorizonProfileResult(
        profile=DeepRegionAuditProfile(profile_id="neg", name="neg"),
        long_horizon_recovery_score=0.1,
        net_gain_slope=-0.001,
        suppression_cost_slope=0.0,
        state_entropy=0.5,
        emergency_state_ratio_over_time=0.0,
        passed=True,
    )
    score = RecoveryPolicySelector.compute_policy_score(result)
    assert score < 0.2  # no slope bonus applied


# ------------------------------------------------------------------ #
# select_best_policy
# ------------------------------------------------------------------ #

def test_select_best_policy_picks_highest_score():
    audit = LongHorizonAuditResult(
        audit_id="test_audit",
        created_at="2026-01-01T00:00:00Z",
        profile_results=[
            LongHorizonProfileResult(
                profile=DeepRegionAuditProfile(profile_id="lh0", name="baseline"),
                long_horizon_recovery_score=0.0,
                passed=False,
            ),
            LongHorizonProfileResult(
                profile=DeepRegionAuditProfile(profile_id="lh5", name="t39"),
                long_horizon_recovery_score=0.2344,
                net_gain_slope=0.0001,
                suppression_cost_slope=-0.0001,
                state_entropy=1.5,
                emergency_state_ratio_over_time=0.0,
                passed=True,
                trajectory_points=[
                    LongHorizonTrajectoryPoint(tick=250, cognitive_score=0.38, phi=0.28, energy_efficiency=0.21, suppression_cost=0.12),
                ],
            ),
            LongHorizonProfileResult(
                profile=DeepRegionAuditProfile(profile_id="lh3", name="nogain"),
                long_horizon_recovery_score=0.2774,
                net_gain_slope=0.0001,
                suppression_cost_slope=0.0,
                state_entropy=1.8,
                emergency_state_ratio_over_time=0.0,
                passed=True,
                trajectory_points=[
                    LongHorizonTrajectoryPoint(tick=250, cognitive_score=0.38, phi=0.28, energy_efficiency=0.21, suppression_cost=0.12),
                ],
            ),
        ],
    )
    sel = RecoveryPolicySelector.select_best_policy(audit)
    assert sel.policy.selected_profile_id == "lh3"
    assert sel.policy.long_horizon_recovery_score == 0.2774
    assert sel.selection_reason != ""


def test_select_best_policy_empty_audit():
    audit = LongHorizonAuditResult(audit_id="empty", created_at="2026-01-01T00:00:00Z")
    sel = RecoveryPolicySelector.select_best_policy(audit)
    assert sel.policy.selected_profile == ""
    assert "No valid profile" in sel.selection_reason


def test_select_best_policy_regression_thresholds_computed():
    audit = LongHorizonAuditResult(
        audit_id="test",
        created_at="2026-01-01T00:00:00Z",
        profile_results=[
            LongHorizonProfileResult(
                profile=DeepRegionAuditProfile(
                    profile_id="lh5", name="t39",
                    deep_regions_enabled=True,
                    inter_region_plasticity_enabled=True,
                    region_signal_routing_enabled=True,
                    region_stability_controller_enabled=True,
                    ltp_rate=0.04,
                    ltd_rate=0.02,
                    energy_cost_per_update=0.0008,
                    energy_modulation_strength=1.2,
                ),
                long_horizon_recovery_score=0.2344,
                net_gain_slope=0.0001,
                suppression_cost_slope=-0.0001,
                state_entropy=1.5,
                emergency_state_ratio_over_time=0.0,
                passed=True,
                trajectory_points=[
                    LongHorizonTrajectoryPoint(
                        tick=250,
                        cognitive_score=0.38,
                        phi=0.28,
                        energy_efficiency=0.21,
                        suppression_cost=0.12,
                    ),
                ],
            ),
        ],
    )
    sel = RecoveryPolicySelector.select_best_policy(audit)
    thr = sel.policy.regression_guard_thresholds
    assert thr.min_cognitive_score <= 0.38
    assert thr.min_phi <= 0.28
    assert thr.max_suppression_cost >= 0.12
    assert thr.min_long_horizon_recovery_score <= 0.2344


# ------------------------------------------------------------------ #
# Export
# ------------------------------------------------------------------ #

def test_export_policy_json(tmp_path):
    sel = RecoveryPolicySelectionResult(
        policy=RecoveryPolicy(policy_id="test_p", selected_profile="t39"),
        selection_reason="test",
    )
    path = tmp_path / "policy.json"
    RecoveryPolicySelector.export_policy_json(sel, path)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["policy"]["policy_id"] == "test_p"


def test_export_policy_yaml(tmp_path):
    sel = RecoveryPolicySelectionResult(
        policy=RecoveryPolicy(policy_id="test_p2", selected_profile="t39"),
        selection_reason="test",
    )
    path = tmp_path / "policy.yaml"
    RecoveryPolicySelector.export_policy_yaml(sel, path)
    assert path.exists()
    assert "test_p2" in path.read_text(encoding="utf-8")


# ------------------------------------------------------------------ #
# Markdown report
# ------------------------------------------------------------------ #

def test_generate_markdown_report_contains_key_sections():
    sel = RecoveryPolicySelectionResult(
        policy=RecoveryPolicy(
            policy_id="test_p3",
            selected_profile="t39",
            selected_profile_id="lh5",
            cognitive_score=0.38,
            coherence_phi=0.28,
            energy_efficiency=0.21,
            suppression_cost=0.12,
            state_entropy=1.5,
            long_horizon_recovery_score=0.2344,
            frozen_flags=FrozenFlags(deep_regions_enabled=True, brainstem_controller_enabled=True),
            frozen_gain_profile=FrozenGainProfile(profile_name="cognitive_preserving", routing_gain=1.1),
            frozen_energy_profile=FrozenEnergyProfile(profile_name="energy_medium", ltp_rate=0.04),
            regression_guard_thresholds=RegressionGuardThresholds(min_cognitive_score=0.34),
        ),
        runner_up_profiles=["baseline"],
        selection_reason="Best recovery score.",
        profile_scores={"lh5": 0.2344, "lh0": 0.0},
    )
    md = RecoveryPolicySelector.generate_markdown_report(sel)
    assert "T41" in md
    assert "test_p3" in md
    assert "t39" in md
    assert "cognitive_preserving" in md
    assert "Best recovery score" in md
    assert "0.2344" in md


# ------------------------------------------------------------------ #
# Frozen submodels
# ------------------------------------------------------------------ #

def test_frozen_flags_model():
    flags = FrozenFlags(brainstem_controller_enabled=True, brainstem_gain_controller_enabled=True)
    assert flags.brainstem_controller_enabled is True


def test_frozen_gain_profile_model():
    gain = FrozenGainProfile(profile_name="cognitive_preserving", cognitive_preservation_gain=1.45)
    assert gain.cognitive_preservation_gain == 1.45


def test_frozen_brainstem_thresholds_model():
    bt = FrozenBrainstemThresholds(phi_threshold_protective=0.12)
    assert bt.phi_threshold_protective == 0.12


def test_frozen_energy_profile_model():
    ep = FrozenEnergyProfile(ltp_rate=0.04, energy_modulation_strength=1.5)
    assert ep.ltp_rate == 0.04


# ------------------------------------------------------------------ #
# Determinism
# ------------------------------------------------------------------ #

def test_selection_is_deterministic_given_same_input():
    audit = LongHorizonAuditResult(
        audit_id="det",
        created_at="2026-01-01T00:00:00Z",
        profile_results=[
            LongHorizonProfileResult(
                profile=DeepRegionAuditProfile(profile_id="a", name="a"),
                long_horizon_recovery_score=0.2,
                net_gain_slope=0.0,
                suppression_cost_slope=0.0,
                state_entropy=0.5,
                emergency_state_ratio_over_time=0.0,
                passed=True,
                trajectory_points=[LongHorizonTrajectoryPoint(tick=250, cognitive_score=0.3, phi=0.2, energy_efficiency=0.1, suppression_cost=0.1)],
            ),
            LongHorizonProfileResult(
                profile=DeepRegionAuditProfile(profile_id="b", name="b"),
                long_horizon_recovery_score=0.3,
                net_gain_slope=0.0,
                suppression_cost_slope=0.0,
                state_entropy=0.5,
                emergency_state_ratio_over_time=0.0,
                passed=True,
                trajectory_points=[LongHorizonTrajectoryPoint(tick=250, cognitive_score=0.3, phi=0.2, energy_efficiency=0.1, suppression_cost=0.1)],
            ),
        ],
    )
    sel1 = RecoveryPolicySelector.select_best_policy(audit)
    sel2 = RecoveryPolicySelector.select_best_policy(audit)
    assert sel1.policy.selected_profile_id == sel2.policy.selected_profile_id
