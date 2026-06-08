import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from speace_core.cellular_brain.analysis.long_horizon_adaptation_audit import (
    LongHorizonAuditResult,
    LongHorizonProfileResult,
)


class FrozenFlags(BaseModel):
    """Canonical boolean switches frozen by T41 policy."""

    deep_regions_enabled: bool = True
    inter_region_plasticity_enabled: bool = True
    region_signal_routing_enabled: bool = True
    region_stability_controller_enabled: bool = True
    brainstem_controller_enabled: bool = True
    brainstem_gain_controller_enabled: bool = True
    deep_region_routing_calibrator_enabled: bool = True


class FrozenGainProfile(BaseModel):
    """Canonical gain profile parameters."""

    profile_name: str = "balanced"
    routing_gain: float = 1.0
    plasticity_gain: float = 1.0
    decay_gain: float = 1.0
    energy_recovery_gain: float = 1.0
    emergency_gain: float = 1.0
    cognitive_preservation_gain: float = 1.0
    global_brainstem_gain: float = 1.0


class FrozenBrainstemThresholds(BaseModel):
    """Canonical brainstem threshold overrides."""

    phi_threshold_stable: float = 0.25
    phi_threshold_watchful: float = 0.20
    phi_threshold_corrective: float = 0.15
    phi_threshold_protective: float = 0.10
    energy_threshold_emergency: float = 0.10
    instability_threshold_watchful: float = 0.15
    instability_threshold_corrective: float = 0.30
    instability_threshold_protective: float = 0.50
    instability_threshold_emergency: float = 0.85


class FrozenEnergyProfile(BaseModel):
    """Canonical energy profile derived from homeostatic calibrator."""

    profile_name: str = "energy_medium"
    ltp_rate: float = 0.05
    ltd_rate: float = 0.03
    energy_cost_per_update: float = 0.001
    energy_modulation_strength: float = 1.0


class RegressionGuardThresholds(BaseModel):
    """Thresholds for T41/T42B regression guard."""

    min_cognitive_score: float = 0.30
    min_phi: float = 0.15
    min_energy_efficiency: float = 0.10
    max_suppression_cost: float = 0.30
    min_long_horizon_recovery_score: float = 0.0
    max_emergency_state_ratio: float = 0.50
    min_state_entropy: float = 0.0
    # T42B — Cellular thresholds
    max_mean_cellular_stress: float = 1.0
    max_mean_damage_score: float = 1.0
    min_cellular_resilience_score: float = 0.0
    min_cellular_self_repair_score: float = 0.0
    min_cellular_defense_score: float = 0.0


class RecoveryPolicy(BaseModel):
    """Frozen canonical operating policy for the full organism."""

    policy_id: str = "recovery_policy_v0_3_25"
    source_audit_id: str = ""
    source_tag: str = "v0.3.24-t40-long-horizon-adaptation-audit"
    selected_profile: str = ""
    selected_profile_id: str = ""
    selected_horizon: int = 250
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Snapshot metrics at freeze time
    cognitive_score: float = 0.0
    coherence_phi: float = 0.0
    energy_efficiency: float = 0.0
    suppression_cost: float = 0.0
    state_entropy: float = 0.0
    long_horizon_recovery_score: float = 0.0
    net_gain_slope: float = 0.0
    cognitive_score_slope: float = 0.0
    phi_slope: float = 0.0
    energy_slope: float = 0.0
    suppression_cost_slope: float = 0.0

    # Frozen configuration
    frozen_flags: FrozenFlags = Field(default_factory=FrozenFlags)
    frozen_gain_profile: FrozenGainProfile = Field(default_factory=FrozenGainProfile)
    frozen_brainstem_thresholds: FrozenBrainstemThresholds = Field(
        default_factory=FrozenBrainstemThresholds
    )
    frozen_energy_profile: FrozenEnergyProfile = Field(default_factory=FrozenEnergyProfile)
    regression_guard_thresholds: RegressionGuardThresholds = Field(
        default_factory=RegressionGuardThresholds
    )

    model_config = ConfigDict(extra="allow")


class RecoveryPolicySelectionResult(BaseModel):
    """Output of the recovery policy selection process."""

    policy: RecoveryPolicy = Field(default_factory=RecoveryPolicy)
    runner_up_profiles: List[str] = Field(default_factory=list)
    selection_reason: str = ""
    profile_scores: Dict[str, float] = Field(default_factory=dict)


class RecoveryPolicySelector:
    """T41 — Select and freeze the best long-horizon recovery policy."""

    @staticmethod
    def compute_policy_score(result: LongHorizonProfileResult) -> float:
        """Score a profile result for policy selection.

        Combines long-horizon recovery score with additional weight on:
        - positive net_gain_slope
        - lower suppression cost
        - higher state entropy (diversity)
        - lower emergency ratio
        """
        if not result.passed:
            return -999.0

        base = result.long_horizon_recovery_score
        slope_bonus = max(0.0, result.net_gain_slope) * 100.0
        suppression_bonus = max(0.0, -result.suppression_cost_slope) * 100.0
        entropy_bonus = result.state_entropy * 0.02
        emergency_penalty = result.emergency_state_ratio_over_time * 0.3

        return round(
            base + slope_bonus + suppression_bonus + entropy_bonus - emergency_penalty,
            4,
        )

    @classmethod
    def select_best_policy(cls, audit_result: LongHorizonAuditResult) -> RecoveryPolicySelectionResult:
        """Select the best profile from a T40 audit and freeze it into a RecoveryPolicy."""
        valid = [r for r in audit_result.profile_results if r.passed]
        if not valid:
            return RecoveryPolicySelectionResult(
                selection_reason="No valid profile results found in audit."
            )

        # Score every valid profile
        scores: Dict[str, float] = {}
        for r in valid:
            scores[r.profile.profile_id] = cls.compute_policy_score(r)

        # Best profile by score
        best = max(valid, key=lambda r: scores.get(r.profile.profile_id, -999.0))
        best_score = scores[best.profile.profile_id]

        # Runner-ups (other passed profiles within 0.05 of best)
        runner_ups = [
            r.profile.name
            for r in valid
            if r.profile.profile_id != best.profile.profile_id
            and scores.get(r.profile.profile_id, -999.0) >= best_score - 0.05
        ]

        # Extract frozen flags from profile extra fields
        extra = getattr(best.profile, "__pydantic_extra__", {}) or {}
        frozen_flags = FrozenFlags(
            deep_regions_enabled=best.profile.deep_regions_enabled,
            inter_region_plasticity_enabled=best.profile.inter_region_plasticity_enabled,
            region_signal_routing_enabled=best.profile.region_signal_routing_enabled,
            region_stability_controller_enabled=best.profile.region_stability_controller_enabled,
            brainstem_controller_enabled=extra.get("brainstem_controller_enabled", False),
            brainstem_gain_controller_enabled=extra.get("brainstem_gain_controller_enabled", False),
            deep_region_routing_calibrator_enabled=extra.get("deep_region_routing_calibrator_enabled", False),
        )

        # Frozen gain profile
        gain_profile_name = extra.get("brainstem_gain_profile", "balanced")
        from speace_core.cellular_brain.regions.brainstem_gain_controller import (
            GAIN_PROFILE_PRESETS,
        )
        preset = GAIN_PROFILE_PRESETS.get(gain_profile_name, {})
        frozen_gain = FrozenGainProfile(
            profile_name=gain_profile_name,
            routing_gain=preset.get("routing_gain", 1.0),
            plasticity_gain=preset.get("plasticity_gain", 1.0),
            decay_gain=preset.get("decay_gain", 1.0),
            energy_recovery_gain=preset.get("energy_recovery_gain", 1.0),
            emergency_gain=preset.get("emergency_gain", 1.0),
            cognitive_preservation_gain=preset.get("cognitive_preservation_gain", 1.0),
            global_brainstem_gain=preset.get("global_brainstem_gain", 1.0),
        )

        # Frozen energy profile
        frozen_energy = FrozenEnergyProfile(
            profile_name="energy_medium",
            ltp_rate=best.profile.ltp_rate,
            ltd_rate=best.profile.ltd_rate,
            energy_cost_per_update=best.profile.energy_cost_per_update,
            energy_modulation_strength=best.profile.energy_modulation_strength,
        )

        # Regression guard thresholds derived from the best profile's actual values
        # with a safety margin (10% tolerance)
        cognitive_final = best.trajectory_points[-1].cognitive_score if best.trajectory_points else 0.0
        phi_final = best.trajectory_points[-1].phi if best.trajectory_points else 0.0
        energy_final = best.trajectory_points[-1].energy_efficiency if best.trajectory_points else 0.0
        suppression_final = best.trajectory_points[-1].suppression_cost if best.trajectory_points else 0.0

        regression_thresholds = RegressionGuardThresholds(
            min_cognitive_score=round(max(0.0, cognitive_final * 0.90), 4),
            min_phi=round(max(0.0, phi_final * 0.90), 4),
            min_energy_efficiency=round(max(0.0, energy_final * 0.90), 4),
            max_suppression_cost=round(min(1.0, suppression_final * 1.20) if suppression_final > 0 else 0.30, 4),
            min_long_horizon_recovery_score=round(max(0.0, best.long_horizon_recovery_score * 0.80), 4),
            max_emergency_state_ratio=round(min(1.0, best.emergency_state_ratio_over_time * 1.20), 4),
            min_state_entropy=round(best.state_entropy * 0.80, 4),
        )

        policy = RecoveryPolicy(
            policy_id=f"recovery_policy_{audit_result.audit_id}",
            source_audit_id=audit_result.audit_id,
            selected_profile=best.profile.name,
            selected_profile_id=best.profile.profile_id,
            selected_horizon=best.trajectory_points[-1].tick if best.trajectory_points else 250,
            cognitive_score=cognitive_final,
            coherence_phi=phi_final,
            energy_efficiency=energy_final,
            suppression_cost=suppression_final,
            state_entropy=best.state_entropy,
            long_horizon_recovery_score=best.long_horizon_recovery_score,
            net_gain_slope=best.net_gain_slope,
            cognitive_score_slope=best.cognitive_score_slope,
            phi_slope=best.phi_slope,
            energy_slope=best.energy_slope,
            suppression_cost_slope=best.suppression_cost_slope,
            frozen_flags=frozen_flags,
            frozen_gain_profile=frozen_gain,
            frozen_brainstem_thresholds=FrozenBrainstemThresholds(),
            frozen_energy_profile=frozen_energy,
            regression_guard_thresholds=regression_thresholds,
        )

        return RecoveryPolicySelectionResult(
            policy=policy,
            runner_up_profiles=runner_ups,
            selection_reason=(
                f"Selected '{best.profile.name}' ({best.profile.profile_id}) "
                f"with policy score {best_score:.4f} from audit {audit_result.audit_id}. "
                f"Recovery score: {best.long_horizon_recovery_score:.4f}."
            ),
            profile_scores=scores,
        )

    # ------------------------------------------------------------------ #
    # Export helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def export_policy_json(selection_result: RecoveryPolicySelectionResult, path: Path) -> Path:
        """Serialize the selected policy to JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(selection_result.model_dump_json(indent=2), encoding="utf-8")
        return path

    @staticmethod
    def export_policy_yaml(selection_result: RecoveryPolicySelectionResult, path: Path) -> Path:
        """Serialize the selected policy to YAML."""
        import yaml
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.dump(selection_result.model_dump(mode="json"), sort_keys=False), encoding="utf-8")
        return path

    @staticmethod
    def generate_markdown_report(selection_result: RecoveryPolicySelectionResult) -> str:
        """Generate a human-readable Markdown report."""
        p = selection_result.policy
        lines = [
            "# T41 — Recovery Policy Freezing Report",
            "",
            f"**Policy ID:** {p.policy_id}",
            f"**Source Audit:** {p.source_audit_id}",
            f"**Source Tag:** {p.source_tag}",
            f"**Selected Profile:** {p.selected_profile} ({p.selected_profile_id})",
            f"**Selected Horizon:** {p.selected_horizon} ticks",
            f"**Created At:** {p.created_at}",
            "",
            "## Selection Rationale",
            selection_result.selection_reason,
            "",
            "## Profile Scores",
            "",
            "| Profile ID | Score |",
            "|---|---|",
        ]
        for pid, score in sorted(selection_result.profile_scores.items(), key=lambda x: -x[1]):
            lines.append(f"| {pid} | {score:.4f} |")

        if selection_result.runner_up_profiles:
            lines.extend([
                "",
                "## Runner-up Profiles",
                ", ".join(selection_result.runner_up_profiles),
            ])

        lines.extend([
            "",
            "## Frozen Metrics Snapshot",
            f"- Cognitive score: {p.cognitive_score:.4f}",
            f"- Coherence Φ: {p.coherence_phi:.4f}",
            f"- Energy efficiency: {p.energy_efficiency:.4f}",
            f"- Suppression cost: {p.suppression_cost:.4f}",
            f"- State entropy: {p.state_entropy:.4f}",
            f"- Long-horizon recovery score: {p.long_horizon_recovery_score:.4f}",
            "",
            "## Frozen Flags",
            f"- Deep regions: {p.frozen_flags.deep_regions_enabled}",
            f"- Inter-region plasticity: {p.frozen_flags.inter_region_plasticity_enabled}",
            f"- Signal routing: {p.frozen_flags.region_signal_routing_enabled}",
            f"- Stability controller: {p.frozen_flags.region_stability_controller_enabled}",
            f"- Brainstem controller: {p.frozen_flags.brainstem_controller_enabled}",
            f"- Gain controller: {p.frozen_flags.brainstem_gain_controller_enabled}",
            f"- Deep region routing calibrator: {p.frozen_flags.deep_region_routing_calibrator_enabled}",
            "",
            "## Frozen Gain Profile",
            f"- Profile name: {p.frozen_gain_profile.profile_name}",
            f"- Routing gain: {p.frozen_gain_profile.routing_gain:.4f}",
            f"- Plasticity gain: {p.frozen_gain_profile.plasticity_gain:.4f}",
            f"- Decay gain: {p.frozen_gain_profile.decay_gain:.4f}",
            f"- Energy recovery gain: {p.frozen_gain_profile.energy_recovery_gain:.4f}",
            f"- Emergency gain: {p.frozen_gain_profile.emergency_gain:.4f}",
            f"- Cognitive preservation gain: {p.frozen_gain_profile.cognitive_preservation_gain:.4f}",
            f"- Global brainstem gain: {p.frozen_gain_profile.global_brainstem_gain:.4f}",
            "",
            "## Regression Guard Thresholds",
            f"- Min cognitive score: {p.regression_guard_thresholds.min_cognitive_score:.4f}",
            f"- Min Φ: {p.regression_guard_thresholds.min_phi:.4f}",
            f"- Min energy efficiency: {p.regression_guard_thresholds.min_energy_efficiency:.4f}",
            f"- Max suppression cost: {p.regression_guard_thresholds.max_suppression_cost:.4f}",
            f"- Min recovery score: {p.regression_guard_thresholds.min_long_horizon_recovery_score:.4f}",
            f"- Max emergency ratio: {p.regression_guard_thresholds.max_emergency_state_ratio:.4f}",
            f"- Min state entropy: {p.regression_guard_thresholds.min_state_entropy:.4f}",
            "",
            "---",
            "*Generated by T41 Recovery Policy Selector*",
        ])
        return "\n".join(lines)
