from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType


class BrainstemGainState(BaseModel):
    global_brainstem_gain: float = 1.0
    routing_gain: float = 1.0
    plasticity_gain: float = 1.0
    decay_gain: float = 1.0
    energy_recovery_gain: float = 1.0
    cooldown_gain: float = 1.0
    emergency_gain: float = 1.0
    cognitive_preservation_gain: float = 1.0


class BrainstemGainDecision(BaseModel):
    global_brainstem_gain: float = 1.0
    routing_gain: float = 1.0
    plasticity_gain: float = 1.0
    decay_gain: float = 1.0
    energy_recovery_gain: float = 1.0
    cooldown_gain: float = 1.0
    emergency_gain: float = 1.0
    cognitive_preservation_gain: float = 1.0
    adjustment_applied: bool = False
    reason: str = ""


class BrainstemGainUpdateResult(BaseModel):
    decision: BrainstemGainDecision = Field(default_factory=BrainstemGainDecision)
    brainstem_gain_reward: float = 0.0
    brainstem_gain_reward_v2: float = 0.0
    adaptive_gain_learning_rate: float = 0.05
    gain_profile_divergence: float = 0.0
    gain_convergence_detected: bool = False
    diversity_pressure_applied: bool = False
    suppression_cost_reduction: float = 0.0
    cognitive_recovery_margin: float = 0.0
    phi_preservation_margin: float = 0.0
    over_suppression_detected: bool = False
    useful_stabilization_detected: bool = False
    true_instability_detected: bool = False
    gain_adjustments_count: int = 0
    gain_stability_score: float = 0.0


GAIN_PROFILE_PRESETS: Dict[str, Dict[str, float]] = {
    "conservative": {
        "routing_gain": 0.90,
        "plasticity_gain": 0.90,
        "decay_gain": 0.90,
        "energy_recovery_gain": 1.10,
        "cooldown_gain": 1.10,
        "emergency_gain": 0.70,
        "cognitive_preservation_gain": 1.20,
        "global_brainstem_gain": 0.95,
    },
    "balanced": {
        "routing_gain": 1.0,
        "plasticity_gain": 1.0,
        "decay_gain": 1.0,
        "energy_recovery_gain": 1.0,
        "cooldown_gain": 1.0,
        "emergency_gain": 1.0,
        "cognitive_preservation_gain": 1.0,
        "global_brainstem_gain": 1.0,
    },
    "cognitive_preserving": {
        "routing_gain": 1.10,
        "plasticity_gain": 1.10,
        "decay_gain": 0.75,
        "energy_recovery_gain": 1.0,
        "cooldown_gain": 1.0,
        "emergency_gain": 0.55,
        "cognitive_preservation_gain": 1.45,
        "global_brainstem_gain": 1.05,
    },
    "phi_preserving": {
        "routing_gain": 0.90,
        "plasticity_gain": 0.95,
        "decay_gain": 1.05,
        "energy_recovery_gain": 1.0,
        "cooldown_gain": 1.0,
        "emergency_gain": 0.80,
        "cognitive_preservation_gain": 1.20,
        "global_brainstem_gain": 1.0,
    },
    "energy_preserving": {
        "routing_gain": 0.85,
        "plasticity_gain": 0.85,
        "decay_gain": 1.10,
        "energy_recovery_gain": 1.20,
        "cooldown_gain": 1.10,
        "emergency_gain": 0.75,
        "cognitive_preservation_gain": 1.10,
        "global_brainstem_gain": 0.95,
    },
    "exploratory": {
        "routing_gain": 1.20,
        "plasticity_gain": 1.20,
        "decay_gain": 0.80,
        "energy_recovery_gain": 1.0,
        "cooldown_gain": 0.90,
        "emergency_gain": 0.60,
        "cognitive_preservation_gain": 1.30,
        "global_brainstem_gain": 1.10,
    },
    "low_suppression": {
        "routing_gain": 1.20,
        "plasticity_gain": 1.15,
        "decay_gain": 0.70,
        "energy_recovery_gain": 1.0,
        "cooldown_gain": 1.0,
        "emergency_gain": 0.45,
        "cognitive_preservation_gain": 1.50,
        "global_brainstem_gain": 1.15,
    },
    "emergency_minimal": {
        "routing_gain": 1.0,
        "plasticity_gain": 1.0,
        "decay_gain": 1.0,
        "energy_recovery_gain": 1.0,
        "cooldown_gain": 1.0,
        "emergency_gain": 0.40,
        "cognitive_preservation_gain": 1.35,
        "global_brainstem_gain": 1.0,
    },
}


class AdaptiveBrainstemGainController:
    """T37/T38 — Adaptive gain layer atop BrainstemFunctionalController.

    Dynamically modulates the intensity of brainstem modulations based on
    observed cognitive, energetic, and stability outcomes.

    T38 additions:
    - reward_v2 with reduced suppression penalty weight
    - adaptive_learning_rate that responds to conditions
    - gain profile presets for differentiated trajectories
    - anti-convergence / diversity pressure
    """

    # Safe ranges
    MIN_GENERAL_GAIN: float = 0.50
    MAX_GENERAL_GAIN: float = 1.50
    MIN_EMERGENCY_GAIN: float = 0.40
    MAX_EMERGENCY_GAIN: float = 1.20
    MIN_COGNITIVE_PRESERVATION_GAIN: float = 1.00
    MAX_COGNITIVE_PRESERVATION_GAIN: float = 1.50

    # Learning rate bounds
    MIN_LEARNING_RATE: float = 0.02
    MAX_LEARNING_RATE: float = 0.15
    BASE_LEARNING_RATE: float = 0.05

    def __init__(self, profile_type: str = "balanced") -> None:
        self._gain = BrainstemGainState()
        self._gain_adjustments_count: int = 0
        self._last_reward: float = 0.0
        self._last_reward_v2: float = 0.0
        self._last_over_suppression: bool = False
        self._last_useful_stabilization: bool = False
        self._last_true_instability: bool = False
        self._profile_type: str = profile_type
        self._adaptive_lr: float = self.BASE_LEARNING_RATE
        self._reward_history: List[float] = []
        self._gain_history: List[Dict[str, float]] = []
        self._last_suppression_cost: float = 0.0
        self._diversity_pressure_applied: bool = False
        self._gain_convergence_detected: bool = False
        self._suppression_cost_reduction: float = 0.0
        self._cognitive_recovery_margin: float = 0.0
        self._phi_preservation_margin: float = 0.0
        self.apply_preset(profile_type)

    # ------------------------------------------------------------------ #
    # Presets
    # ------------------------------------------------------------------ #

    def apply_preset(self, profile_type: str) -> None:
        preset = GAIN_PROFILE_PRESETS.get(profile_type, GAIN_PROFILE_PRESETS["balanced"])
        self._gain.global_brainstem_gain = preset.get("global_brainstem_gain", 1.0)
        self._gain.routing_gain = preset.get("routing_gain", 1.0)
        self._gain.plasticity_gain = preset.get("plasticity_gain", 1.0)
        self._gain.decay_gain = preset.get("decay_gain", 1.0)
        self._gain.energy_recovery_gain = preset.get("energy_recovery_gain", 1.0)
        self._gain.cooldown_gain = preset.get("cooldown_gain", 1.0)
        self._gain.emergency_gain = preset.get("emergency_gain", 1.0)
        self._gain.cognitive_preservation_gain = preset.get("cognitive_preservation_gain", 1.0)
        self._profile_type = profile_type

    # ------------------------------------------------------------------ #
    # Reward computation (v1 and v2)
    # ------------------------------------------------------------------ #

    def compute_reward(self, metrics: Dict[str, Any]) -> float:
        """Compute scalar reward in [-1, 1] from observed deltas (T37)."""
        cog_delta = metrics.get("cognitive_score_delta", 0.0)
        phi_delta = metrics.get("coherence_phi_delta", 0.0)
        energy_delta = metrics.get("energy_efficiency_delta", 0.0)
        func_delta = metrics.get("functional_improvement_delta", 0.0)
        suppression_cost = metrics.get("suppression_cost", 0.0)
        total_ticks = max(1, metrics.get("total_ticks", 5))
        emergency_ticks = metrics.get("emergency_ticks", 0)
        emergency_tick_ratio = emergency_ticks / total_ticks

        reward = (
            0.35 * max(0.0, cog_delta)
            + 0.25 * max(0.0, phi_delta)
            + 0.20 * max(0.0, energy_delta)
            + 0.10 * max(0.0, func_delta)
            - 0.25 * suppression_cost
            - 0.15 * emergency_tick_ratio
        )
        return round(max(-1.0, min(1.0, reward)), 4)

    def compute_reward_v2(self, metrics: Dict[str, Any]) -> float:
        """T38 reward with reduced suppression penalty and preservation focus."""
        cog_delta = metrics.get("cognitive_score_delta", 0.0)
        phi_delta = metrics.get("coherence_phi_delta", 0.0)
        energy_delta = metrics.get("energy_efficiency_delta", 0.0)
        func_delta = metrics.get("functional_improvement_delta", 0.0)
        flow_delta = metrics.get("regional_signal_flow_delta", 0.0)
        suppression_cost = metrics.get("suppression_cost", 0.0)
        total_ticks = max(1, metrics.get("total_ticks", 5))
        emergency_ticks = metrics.get("emergency_ticks", 0)
        protective_ticks = metrics.get("protective_ticks", 0)
        emergency_tick_ratio = emergency_ticks / total_ticks
        protective_tick_ratio = protective_ticks / total_ticks

        # cognitive_preservation_delta: how much cognitive preservation helped
        cognitive_preservation_delta = metrics.get("cognitive_preservation_delta", cog_delta)

        reward = (
            0.30 * cognitive_preservation_delta
            + 0.25 * max(0.0, phi_delta)
            + 0.20 * max(0.0, energy_delta)
            + 0.15 * max(0.0, func_delta)
            + 0.10 * max(0.0, flow_delta)
            - 0.15 * suppression_cost
            - 0.10 * emergency_tick_ratio
            - 0.05 * protective_tick_ratio
        )
        return round(max(-1.0, min(1.0, reward)), 4)

    # ------------------------------------------------------------------ #
    # Adaptive learning rate
    # ------------------------------------------------------------------ #

    def compute_adaptive_learning_rate(
        self,
        over_suppression_detected: bool,
        true_instability_detected: bool,
        gain_oscillation_detected: bool,
    ) -> float:
        """T38 adaptive LR: respond to conditions with bounded steps."""
        lr = self.BASE_LEARNING_RATE
        if over_suppression_detected:
            lr = 0.08
        if true_instability_detected:
            lr = 0.10
        # If reward has been negative for 3 consecutive evaluations, boost LR
        if len(self._reward_history) >= 3 and all(r < 0 for r in self._reward_history[-3:]):
            lr = 0.12
        if gain_oscillation_detected:
            lr = 0.03
        return self._clamp(lr, self.MIN_LEARNING_RATE, self.MAX_LEARNING_RATE)

    def _detect_gain_oscillation(self) -> bool:
        """Detect if any gain has oscillated across last 4 evaluations."""
        if len(self._gain_history) < 4:
            return False
        keys = ["routing_gain", "plasticity_gain", "decay_gain", "emergency_gain"]
        for k in keys:
            values = [h.get(k, 1.0) for h in self._gain_history[-4:]]
            # Oscillation = direction changes at least twice
            directions = [1 if values[i + 1] > values[i] else (-1 if values[i + 1] < values[i] else 0) for i in range(len(values) - 1)]
            non_zero = [d for d in directions if d != 0]
            if len(non_zero) >= 2 and any(non_zero[i] != non_zero[i + 1] for i in range(len(non_zero) - 1)):
                return True
        return False

    # ------------------------------------------------------------------ #
    # Diversity and anti-convergence
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_gain_profile_divergence(gain_vectors: List[Dict[str, float]]) -> float:
        """Mean absolute difference between all pairs of gain vectors."""
        if len(gain_vectors) < 2:
            return 0.0
        keys = ["routing_gain", "plasticity_gain", "decay_gain", "emergency_gain", "cognitive_preservation_gain", "global_brainstem_gain"]
        diffs: List[float] = []
        for i in range(len(gain_vectors)):
            for j in range(i + 1, len(gain_vectors)):
                d = sum(abs(gain_vectors[i].get(k, 1.0) - gain_vectors[j].get(k, 1.0)) for k in keys) / len(keys)
                diffs.append(d)
        return round(sum(diffs) / len(diffs), 4) if diffs else 0.0

    def apply_diversity_pressure(self) -> None:
        """T38: if convergence detected, push profile toward its designated pole."""
        pt = self._profile_type
        lr = self._adaptive_lr
        if pt == "cognitive_preserving":
            self._gain.cognitive_preservation_gain = self._clamp(
                self._gain.cognitive_preservation_gain + lr, self.MIN_COGNITIVE_PRESERVATION_GAIN, self.MAX_COGNITIVE_PRESERVATION_GAIN
            )
            self._gain.emergency_gain = self._clamp(self._gain.emergency_gain - lr * 0.5, self.MIN_EMERGENCY_GAIN, self.MAX_EMERGENCY_GAIN)
        elif pt == "phi_preserving":
            self._gain.decay_gain = self._clamp(self._gain.decay_gain + lr * 0.5, self.MIN_GENERAL_GAIN, self.MAX_GENERAL_GAIN)
            self._gain.routing_gain = self._clamp(self._gain.routing_gain - lr * 0.5, self.MIN_GENERAL_GAIN, self.MAX_GENERAL_GAIN)
        elif pt == "low_suppression":
            self._gain.routing_gain = self._clamp(self._gain.routing_gain + lr, self.MIN_GENERAL_GAIN, self.MAX_GENERAL_GAIN)
            self._gain.plasticity_gain = self._clamp(self._gain.plasticity_gain + lr, self.MIN_GENERAL_GAIN, self.MAX_GENERAL_GAIN)
            self._gain.emergency_gain = self._clamp(self._gain.emergency_gain - lr, self.MIN_EMERGENCY_GAIN, self.MAX_EMERGENCY_GAIN)
        elif pt == "exploratory":
            self._gain.routing_gain = self._clamp(self._gain.routing_gain + lr, self.MIN_GENERAL_GAIN, self.MAX_GENERAL_GAIN)
            self._gain.plasticity_gain = self._clamp(self._gain.plasticity_gain + lr, self.MIN_GENERAL_GAIN, self.MAX_GENERAL_GAIN)
        elif pt == "energy_preserving":
            self._gain.energy_recovery_gain = self._clamp(
                self._gain.energy_recovery_gain + lr, self.MIN_GENERAL_GAIN, self.MAX_GENERAL_GAIN
            )
        elif pt == "emergency_minimal":
            self._gain.emergency_gain = self._clamp(self._gain.emergency_gain - lr, self.MIN_EMERGENCY_GAIN, self.MAX_EMERGENCY_GAIN)
            self._gain.cognitive_preservation_gain = self._clamp(
                self._gain.cognitive_preservation_gain + lr, self.MIN_COGNITIVE_PRESERVATION_GAIN, self.MAX_COGNITIVE_PRESERVATION_GAIN
            )
        elif pt == "conservative":
            self._gain.global_brainstem_gain = self._clamp(
                self._gain.global_brainstem_gain - lr * 0.5, self.MIN_GENERAL_GAIN, self.MAX_GENERAL_GAIN
            )
        self._diversity_pressure_applied = True

    # ------------------------------------------------------------------ #
    # Adaptive rules
    # ------------------------------------------------------------------ #

    def evaluate(
        self,
        metrics: Dict[str, Any],
    ) -> BrainstemGainUpdateResult:
        cog_delta = metrics.get("cognitive_score_delta", 0.0)
        phi_delta = metrics.get("coherence_phi_delta", 0.0)
        energy_delta = metrics.get("energy_efficiency_delta", 0.0)
        func_delta = metrics.get("functional_improvement_delta", 0.0)
        suppression_cost = metrics.get("suppression_cost", 0.0)
        emergency_ticks = metrics.get("emergency_ticks", 0)
        protective_ticks = metrics.get("protective_ticks", 0)
        total_ticks = max(1, metrics.get("total_ticks", 5))
        mean_region_energy = metrics.get("mean_region_energy", metrics.get("mean_energy", 0.0))
        mean_region_phi = metrics.get("mean_region_phi", 0.0)

        decision = BrainstemGainDecision()
        decision.global_brainstem_gain = self._gain.global_brainstem_gain
        decision.routing_gain = self._gain.routing_gain
        decision.plasticity_gain = self._gain.plasticity_gain
        decision.decay_gain = self._gain.decay_gain
        decision.energy_recovery_gain = self._gain.energy_recovery_gain
        decision.cooldown_gain = self._gain.cooldown_gain
        decision.emergency_gain = self._gain.emergency_gain
        decision.cognitive_preservation_gain = self._gain.cognitive_preservation_gain

        reward = self.compute_reward(metrics)
        reward_v2 = self.compute_reward_v2(metrics)
        self._last_reward = reward
        self._last_reward_v2 = reward_v2
        self._reward_history.append(reward_v2)

        reasons: list[str] = []
        adjustment = False

        self._last_over_suppression = False
        self._last_useful_stabilization = False
        self._last_true_instability = False
        self._diversity_pressure_applied = False
        self._gain_convergence_detected = False

        # Track suppression cost for reduction metric
        old_suppression_cost = self._last_suppression_cost
        self._last_suppression_cost = suppression_cost
        self._suppression_cost_reduction = max(0.0, old_suppression_cost - suppression_cost)
        self._cognitive_recovery_margin = max(0.0, cog_delta)
        self._phi_preservation_margin = max(0.0, phi_delta)

        # Adaptive LR
        gain_oscillation = self._detect_gain_oscillation()
        lr = self.compute_adaptive_learning_rate(False, False, gain_oscillation)

        # Rule 1: Over-suppression detection
        if cog_delta < -0.02 and phi_delta >= -0.02:
            self._last_over_suppression = True
            adjustment = True
            reasons.append("over_suppression")
            lr = self.compute_adaptive_learning_rate(True, False, gain_oscillation)
            self._gain.routing_gain = self._clamp(
                self._gain.routing_gain - lr, self.MIN_GENERAL_GAIN, self.MAX_GENERAL_GAIN
            )
            self._gain.plasticity_gain = self._clamp(
                self._gain.plasticity_gain - lr, self.MIN_GENERAL_GAIN, self.MAX_GENERAL_GAIN
            )
            self._gain.emergency_gain = self._clamp(
                self._gain.emergency_gain - lr, self.MIN_EMERGENCY_GAIN, self.MAX_EMERGENCY_GAIN
            )
            self._gain.cognitive_preservation_gain = self._clamp(
                self._gain.cognitive_preservation_gain + lr,
                self.MIN_COGNITIVE_PRESERVATION_GAIN,
                self.MAX_COGNITIVE_PRESERVATION_GAIN,
            )

        # Rule 2: Useful stabilization
        if phi_delta > 0.02 and cog_delta >= -0.03:
            self._last_useful_stabilization = True
            adjustment = True
            reasons.append("useful_stabilization")
            self._gain.global_brainstem_gain = self._clamp(
                self._gain.global_brainstem_gain + lr * 0.5,
                self.MIN_GENERAL_GAIN,
                self.MAX_GENERAL_GAIN,
            )

        # Rule 3: Energy recovery without cognitive damage
        if energy_delta > 0.01 and cog_delta >= -0.03:
            adjustment = True
            reasons.append("energy_recovery_safe")
            self._gain.routing_gain = self._clamp(
                self._gain.routing_gain - lr * 0.5, self.MIN_GENERAL_GAIN, self.MAX_GENERAL_GAIN
            )
            self._gain.plasticity_gain = self._clamp(
                self._gain.plasticity_gain - lr * 0.5, self.MIN_GENERAL_GAIN, self.MAX_GENERAL_GAIN
            )

        # Rule 4: Chronic emergency/protective without Φ collapse
        if (emergency_ticks > 3 or protective_ticks > 6) and phi_delta >= -0.03:
            adjustment = True
            reasons.append("chronic_high_alert")
            self._gain.emergency_gain = self._clamp(
                self._gain.emergency_gain - lr, self.MIN_EMERGENCY_GAIN, self.MAX_EMERGENCY_GAIN
            )
            self._gain.decay_gain = self._clamp(
                self._gain.decay_gain - lr * 0.5, self.MIN_GENERAL_GAIN, self.MAX_GENERAL_GAIN
            )
            self._gain.cognitive_preservation_gain = self._clamp(
                self._gain.cognitive_preservation_gain + lr,
                self.MIN_COGNITIVE_PRESERVATION_GAIN,
                self.MAX_COGNITIVE_PRESERVATION_GAIN,
            )

        # Rule 5: True instability escalation
        if phi_delta < -0.05 or mean_region_energy < 0.12 or mean_region_phi < 0.10:
            self._last_true_instability = True
            adjustment = True
            reasons.append("true_instability")
            lr = self.compute_adaptive_learning_rate(False, True, gain_oscillation)
            self._gain.global_brainstem_gain = self._clamp(
                self._gain.global_brainstem_gain + lr, self.MIN_GENERAL_GAIN, self.MAX_GENERAL_GAIN
            )
            self._gain.energy_recovery_gain = self._clamp(
                self._gain.energy_recovery_gain + lr, self.MIN_GENERAL_GAIN, self.MAX_GENERAL_GAIN
            )
            self._gain.decay_gain = self._clamp(
                self._gain.decay_gain + lr, self.MIN_GENERAL_GAIN, self.MAX_GENERAL_GAIN
            )

        if adjustment:
            self._gain_adjustments_count += 1

        # Record gain history for oscillation detection
        self._gain_history.append({
            "routing_gain": self._gain.routing_gain,
            "plasticity_gain": self._gain.plasticity_gain,
            "decay_gain": self._gain.decay_gain,
            "emergency_gain": self._gain.emergency_gain,
            "cognitive_preservation_gain": self._gain.cognitive_preservation_gain,
            "global_brainstem_gain": self._gain.global_brainstem_gain,
        })
        # Keep only last 10 entries
        if len(self._gain_history) > 10:
            self._gain_history = self._gain_history[-10:]

        # T38 Anti-convergence / diversity pressure
        # Use a self-divergence proxy: compare current gain to preset baseline
        preset = GAIN_PROFILE_PRESETS.get(self._profile_type, GAIN_PROFILE_PRESETS["balanced"])
        current_vector = {
            "routing_gain": self._gain.routing_gain,
            "plasticity_gain": self._gain.plasticity_gain,
            "decay_gain": self._gain.decay_gain,
            "emergency_gain": self._gain.emergency_gain,
            "cognitive_preservation_gain": self._gain.cognitive_preservation_gain,
            "global_brainstem_gain": self._gain.global_brainstem_gain,
        }
        preset_vector = {
            "routing_gain": preset.get("routing_gain", 1.0),
            "plasticity_gain": preset.get("plasticity_gain", 1.0),
            "decay_gain": preset.get("decay_gain", 1.0),
            "emergency_gain": preset.get("emergency_gain", 1.0),
            "cognitive_preservation_gain": preset.get("cognitive_preservation_gain", 1.0),
            "global_brainstem_gain": preset.get("global_brainstem_gain", 1.0),
        }
        divergence = AdaptiveBrainstemGainController.compute_gain_profile_divergence([current_vector, preset_vector])
        if divergence < 0.03 and self._gain_adjustments_count > 0:
            self._gain_convergence_detected = True
            self.apply_diversity_pressure()
            adjustment = True
            reasons.append("diversity_pressure")

        # Apply global gain scaling (soft)
        if adjustment:
            global_factor = self._gain.global_brainstem_gain
            decision.routing_gain = round(self._gain.routing_gain * global_factor, 4)
            decision.plasticity_gain = round(self._gain.plasticity_gain * global_factor, 4)
            decision.decay_gain = round(self._gain.decay_gain * global_factor, 4)
            decision.energy_recovery_gain = round(self._gain.energy_recovery_gain * global_factor, 4)
            decision.cooldown_gain = round(self._gain.cooldown_gain * global_factor, 4)
            decision.emergency_gain = round(self._gain.emergency_gain * global_factor, 4)
            decision.cognitive_preservation_gain = round(self._gain.cognitive_preservation_gain, 4)
            decision.adjustment_applied = True
        else:
            decision.routing_gain = round(self._gain.routing_gain, 4)
            decision.plasticity_gain = round(self._gain.plasticity_gain, 4)
            decision.decay_gain = round(self._gain.decay_gain, 4)
            decision.energy_recovery_gain = round(self._gain.energy_recovery_gain, 4)
            decision.cooldown_gain = round(self._gain.cooldown_gain, 4)
            decision.emergency_gain = round(self._gain.emergency_gain, 4)
            decision.cognitive_preservation_gain = round(self._gain.cognitive_preservation_gain, 4)

        decision.reason = "; ".join(reasons) if reasons else "no_adjustment"

        # Gain stability score: how close gains are to 1.0 (neutral)
        all_gains = [
            decision.routing_gain,
            decision.plasticity_gain,
            decision.decay_gain,
            decision.energy_recovery_gain,
            decision.emergency_gain,
            decision.cognitive_preservation_gain,
        ]
        gain_stability = 1.0 - sum(abs(g - 1.0) for g in all_gains) / len(all_gains)
        gain_stability = max(0.0, min(1.0, gain_stability))

        self._adaptive_lr = lr

        return BrainstemGainUpdateResult(
            decision=decision,
            brainstem_gain_reward=reward,
            brainstem_gain_reward_v2=reward_v2,
            adaptive_gain_learning_rate=round(lr, 4),
            gain_profile_divergence=divergence,
            gain_convergence_detected=self._gain_convergence_detected,
            diversity_pressure_applied=self._diversity_pressure_applied,
            suppression_cost_reduction=round(self._suppression_cost_reduction, 4),
            cognitive_recovery_margin=round(self._cognitive_recovery_margin, 4),
            phi_preservation_margin=round(self._phi_preservation_margin, 4),
            over_suppression_detected=self._last_over_suppression,
            useful_stabilization_detected=self._last_useful_stabilization,
            true_instability_detected=self._last_true_instability,
            gain_adjustments_count=self._gain_adjustments_count,
            gain_stability_score=round(gain_stability, 4),
        )

    def apply(
        self,
        metrics: Dict[str, Any],
        memory: Optional[MorphologicalMemory] = None,
    ) -> BrainstemGainUpdateResult:
        result = self.evaluate(metrics)

        if memory is not None:
            memory.create_event(
                event_type=MorphologyEventType.BRAINSTEM_GAIN_EVALUATED,
                region_id="brainstem_homeostatic",
                metadata={
                    "reward": result.brainstem_gain_reward,
                    "reward_v2": result.brainstem_gain_reward_v2,
                    "adaptive_lr": result.adaptive_gain_learning_rate,
                    "gain_stability_score": result.gain_stability_score,
                    "gain_adjustments_count": result.gain_adjustments_count,
                    "profile_type": self._profile_type,
                },
            )
            if result.decision.adjustment_applied:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_GAIN_ADJUSTED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "reason": result.decision.reason,
                        "routing_gain": result.decision.routing_gain,
                        "plasticity_gain": result.decision.plasticity_gain,
                        "decay_gain": result.decision.decay_gain,
                        "energy_recovery_gain": result.decision.energy_recovery_gain,
                        "emergency_gain": result.decision.emergency_gain,
                        "cognitive_preservation_gain": result.decision.cognitive_preservation_gain,
                        "adaptive_lr": result.adaptive_gain_learning_rate,
                    },
                )
            if result.over_suppression_detected:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_OVER_SUPPRESSION_DETECTED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "cognitive_score_delta": metrics.get("cognitive_score_delta", 0.0),
                        "coherence_phi_delta": metrics.get("coherence_phi_delta", 0.0),
                    },
                )
            if result.useful_stabilization_detected:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_USEFUL_STABILIZATION_DETECTED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "coherence_phi_delta": metrics.get("coherence_phi_delta", 0.0),
                        "cognitive_score_delta": metrics.get("cognitive_score_delta", 0.0),
                    },
                )
            if result.true_instability_detected:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_TRUE_INSTABILITY_DETECTED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "mean_region_energy": metrics.get("mean_region_energy", metrics.get("mean_energy", 0.0)),
                        "coherence_phi_delta": metrics.get("coherence_phi_delta", 0.0),
                    },
                )
            if result.decision.adjustment_applied and "over_suppression" in result.decision.reason:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_EMERGENCY_GAIN_REDUCED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "emergency_gain": result.decision.emergency_gain,
                        "adaptive_lr": result.adaptive_gain_learning_rate,
                    },
                )
            if result.decision.adjustment_applied and "useful_stabilization" in result.decision.reason:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_COGNITIVE_GAIN_BOOSTED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "cognitive_preservation_gain": result.decision.cognitive_preservation_gain,
                    },
                )
            # T38 new events
            memory.create_event(
                event_type=MorphologyEventType.BRAINSTEM_GAIN_REWARD_V2_COMPUTED,
                region_id="brainstem_homeostatic",
                metadata={
                    "reward_v2": result.brainstem_gain_reward_v2,
                },
            )
            memory.create_event(
                event_type=MorphologyEventType.BRAINSTEM_GAIN_LR_ADAPTED,
                region_id="brainstem_homeostatic",
                metadata={
                    "adaptive_lr": result.adaptive_gain_learning_rate,
                    "base_lr": self.BASE_LEARNING_RATE,
                },
            )
            if result.diversity_pressure_applied:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_GAIN_DIVERSITY_PRESSURE_APPLIED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "profile_type": self._profile_type,
                        "divergence": result.gain_profile_divergence,
                    },
                )
            if result.gain_convergence_detected:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_GAIN_CONVERGENCE_DETECTED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "divergence": result.gain_profile_divergence,
                    },
                )
            if result.suppression_cost_reduction > 0:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_SUPPRESSION_COST_REDUCED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "suppression_cost_reduction": result.suppression_cost_reduction,
                    },
                )
            if result.cognitive_recovery_margin > 0:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_COGNITIVE_RECOVERY_IMPROVED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "cognitive_recovery_margin": result.cognitive_recovery_margin,
                    },
                )

        return result

    def get_gain_summary(self) -> Dict[str, Any]:
        return {
            "global_brainstem_gain": self._gain.global_brainstem_gain,
            "routing_gain": self._gain.routing_gain,
            "plasticity_gain": self._gain.plasticity_gain,
            "decay_gain": self._gain.decay_gain,
            "energy_recovery_gain": self._gain.energy_recovery_gain,
            "cooldown_gain": self._gain.cooldown_gain,
            "emergency_gain": self._gain.emergency_gain,
            "cognitive_preservation_gain": self._gain.cognitive_preservation_gain,
            "gain_adjustments_count": self._gain_adjustments_count,
            "last_reward": self._last_reward,
            "last_reward_v2": self._last_reward_v2,
            "last_over_suppression": self._last_over_suppression,
            "last_useful_stabilization": self._last_useful_stabilization,
            "last_true_instability": self._last_true_instability,
            "adaptive_lr": self._adaptive_lr,
            "profile_type": self._profile_type,
            "gain_convergence_detected": self._gain_convergence_detected,
            "diversity_pressure_applied": self._diversity_pressure_applied,
            "suppression_cost_reduction": self._suppression_cost_reduction,
            "cognitive_recovery_margin": self._cognitive_recovery_margin,
            "phi_preservation_margin": self._phi_preservation_margin,
        }

    @staticmethod
    def _clamp(value: float, min_val: float, max_val: float) -> float:
        return max(min_val, min(max_val, value))
