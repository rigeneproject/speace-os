from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType


class BrainstemFunctionalState(str, Enum):
    STABLE = "stable"
    WATCHFUL = "watchful"
    CORRECTIVE = "corrective"
    PROTECTIVE = "protective"
    EMERGENCY = "emergency"


class BrainstemState(BaseModel):
    state: BrainstemFunctionalState = BrainstemFunctionalState.STABLE
    mean_phi: float = 0.0
    mean_energy: float = 0.0
    instability_mean: float = 0.0
    unstable_region_count: int = 0
    mean_deep_activation: float = 0.0
    regional_signal_flow: float = 0.0
    deep_region_signal_flow: float = 0.0
    stability_actions: int = 0
    routing_blocks: int = 0
    cooldowns: int = 0
    mean_pathway_utility: float = 0.0
    energy_state: float = 0.0


class BrainstemDecision(BaseModel):
    state: BrainstemFunctionalState = BrainstemFunctionalState.STABLE
    reason: str = ""
    energy_recovery_multiplier: float = 1.0
    routing_suppression_multiplier: float = 1.0
    plasticity_suppression_multiplier: float = 1.0
    decay_boost_multiplier: float = 1.0
    cooldown_boost_multiplier: float = 1.0
    neurogenesis_suppression_multiplier: float = 1.0
    apoptosis_boost_multiplier: float = 1.0
    brainstem_priority_boost: float = 1.0


class BrainstemModulationResult(BaseModel):
    decision: BrainstemDecision = Field(default_factory=BrainstemDecision)
    state_changed: bool = False
    decisions_count: int = 0
    emergency_count: int = 0
    recovery_actions: int = 0
    homeostatic_gain: float = 0.0
    phi_recovery_contribution: float = 0.0


class BrainstemCouplingTrace(BaseModel):
    """T39 — Output coupling trace for causal tracking."""

    tick_id: int = 0
    state_before: str = "stable"
    state_after: str = "stable"
    raw_vitality: float = 0.0
    raw_risk: float = 0.0
    adjusted_vitality: float = 0.0
    adjusted_risk: float = 0.0
    raw_balance_pressure: float = 0.0
    adjusted_balance_pressure: float = 0.0
    gain_vector: Dict[str, float] = Field(default_factory=dict)
    raw_modulations: Dict[str, float] = Field(default_factory=dict)
    final_modulations: Dict[str, float] = Field(default_factory=dict)
    coupling_delta: float = 0.0
    protective_escape_applied: bool = False


class BrainstemFunctionalController:
    """Active homeostatic arbiter for the cellular brain.

    T35 transforms brainstem_homeostatic from a passive deep-region target
    into a systemic regulator of energy, routing, plasticity, decay,
    cooldown, and recovery.

    T36 adds Cognitive/Autonomic Balance Tuning:
    - cognitive_vitality_score to prevent over-suppression of useful cognition
    - autonomic_risk_score for holistic threat assessment
    - balance_pressure = risk - vitality  drives state selection
    - soft modulation profiles to reduce cognitive regression
    - emergency hysteresis to avoid chronic panic
    - cognitive preservation rule to cap suppression when cognition is productive

    T39 adds Gain Input Coupling Redesign:
    - gain-coupled vitality/risk scoring
    - dynamic state thresholds adjusted by gain vector
    - protective escape rule after persistent protective state
    - explicit output coupling trace
    """

    # T36 — Balance thresholds (balance_pressure = autonomic_risk - cognitive_vitality)
    BALANCE_PRESSURE_STABLE: float = 0.10
    BALANCE_PRESSURE_WATCHFUL: float = 0.10
    BALANCE_PRESSURE_CORRECTIVE: float = 0.25
    BALANCE_PRESSURE_PROTECTIVE: float = 0.45
    BALANCE_PRESSURE_EMERGENCY: float = 0.70

    # T36 — Emergency hysteresis
    EMERGENCY_CONSECUTIVE_TICKS_REQUIRED: int = 2
    EMERGENCY_EXIT_THRESHOLD: float = 0.55

    # T36 — Cognitive preservation
    COGNITIVE_PRESERVATION_THRESHOLD: float = 0.55
    PHI_COLLAPSE_THRESHOLD: float = 0.10
    ENERGY_CRITICAL_LOW: float = 0.10

    # T39 — Protective escape
    PROTECTIVE_ESCAPE_TICKS: int = 3
    PROTECTIVE_ESCAPE_VITALITY: float = 0.45
    PROTECTIVE_ESCAPE_RISK: float = 0.65
    PROTECTIVE_ESCAPE_ENERGY: float = 0.15

    def __init__(
        self,
        phi_threshold_stable: float = 0.25,
        phi_threshold_watchful: float = 0.20,
        phi_threshold_corrective: float = 0.15,
        phi_threshold_protective: float = 0.10,
        energy_threshold_emergency: float = 0.10,
        instability_threshold_watchful: float = 0.15,
        instability_threshold_corrective: float = 0.30,
        instability_threshold_protective: float = 0.50,
        instability_threshold_emergency: float = 0.85,
    ):
        # Legacy thresholds kept for backward compatibility / absolute overrides
        self.phi_threshold_stable = phi_threshold_stable
        self.phi_threshold_watchful = phi_threshold_watchful
        self.phi_threshold_corrective = phi_threshold_corrective
        self.phi_threshold_protective = phi_threshold_protective
        self.energy_threshold_emergency = energy_threshold_emergency
        self.instability_threshold_watchful = instability_threshold_watchful
        self.instability_threshold_corrective = instability_threshold_corrective
        self.instability_threshold_protective = instability_threshold_protective
        self.instability_threshold_emergency = instability_threshold_emergency

        self._previous_state: Optional[BrainstemFunctionalState] = None
        self._decisions_count: int = 0
        self._emergency_count: int = 0
        self._recovery_actions: int = 0
        self._last_phi: float = 0.0

        # T36 — Hysteresis tracking
        self._consecutive_emergency_ticks: int = 0
        self._in_emergency: bool = False

        # T36 — State distribution counters
        self._state_ticks: Dict[str, int] = {
            "stable": 0,
            "watchful": 0,
            "corrective": 0,
            "protective": 0,
            "emergency": 0,
        }

        # T36 — Latest computed scores (for benchmark extraction)
        self._last_cognitive_vitality: float = 0.0
        self._last_autonomic_risk: float = 0.0
        self._last_balance_pressure: float = 0.0
        self._last_cognitive_preservation_applied: bool = False
        self._last_suppression_cost: float = 0.0
        self._last_useful_activity_preserved: bool = False

        # T39 — Gain input coupling
        self._gain_vector: Dict[str, float] = {}
        self._last_adjusted_vitality: float = 0.0
        self._last_adjusted_risk: float = 0.0
        self._last_adjusted_balance_pressure: float = 0.0
        self._protective_consecutive_ticks: int = 0
        self._protective_escape_count: int = 0
        self._coupling_traces: List[BrainstemCouplingTrace] = []
        self._last_coupling_delta: float = 0.0
        self._last_suppression_cost_after_coupling: float = 0.0
        self._state_transition_count: int = 0

    # ------------------------------------------------------------------ #
    # T39 — Gain-coupled input scoring
    # ------------------------------------------------------------------ #

    def apply_gain_to_input_scores(
        self,
        vitality: float,
        risk: float,
        gain_vector: Optional[Dict[str, float]] = None,
    ) -> tuple[float, float, float]:
        """Adjust vitality and risk by gain vector.

        Returns (adjusted_vitality, adjusted_risk, adjusted_balance_pressure).
        """
        gv = gain_vector or self._gain_vector or {}
        cog_pres = max(1.0, min(1.5, gv.get("cognitive_preservation_gain", 1.0)))
        emg = max(0.4, min(1.2, gv.get("emergency_gain", 1.0)))

        adjusted_vitality = min(1.0, vitality * cog_pres)
        adjusted_risk = min(1.0, risk * emg)
        adjusted_pressure = max(0.0, adjusted_risk - adjusted_vitality)

        self._last_adjusted_vitality = round(adjusted_vitality, 4)
        self._last_adjusted_risk = round(adjusted_risk, 4)
        self._last_adjusted_balance_pressure = round(adjusted_pressure, 4)
        return adjusted_vitality, adjusted_risk, adjusted_pressure

    # ------------------------------------------------------------------ #
    # T39 — Dynamic state thresholds
    # ------------------------------------------------------------------ #

    def compute_adjusted_thresholds(
        self,
        gain_vector: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """Compute state thresholds adjusted by gain vector."""
        gv = gain_vector or self._gain_vector or {}
        cog_pres = max(1.0, min(1.5, gv.get("cognitive_preservation_gain", 1.0)))
        emg = max(0.4, min(1.2, gv.get("emergency_gain", 1.0)))

        # protective_threshold_adjusted = base + 0.10 * (cog_pres - 1.0)
        protective = self.BALANCE_PRESSURE_PROTECTIVE + 0.10 * (cog_pres - 1.0)
        # emergency_threshold_adjusted = base + 0.10 * (1.0 - emg)
        emergency = self.BALANCE_PRESSURE_EMERGENCY + 0.10 * (1.0 - emg)
        # corrective_threshold_adjusted = base + 0.05 * (cog_pres - emg)
        corrective = self.BALANCE_PRESSURE_CORRECTIVE + 0.05 * (cog_pres - emg)

        return {
            "stable": self._clamp(self.BALANCE_PRESSURE_STABLE, 0.0, 1.0),
            "watchful": self._clamp(self.BALANCE_PRESSURE_WATCHFUL, 0.0, 1.0),
            "corrective": self._clamp(corrective, -0.20, 0.40),
            "protective": self._clamp(protective, 0.10, 0.60),
            "emergency": self._clamp(emergency, 0.35, 0.90),
        }

    # ------------------------------------------------------------------ #
    # T39 — Protective escape rule
    # ------------------------------------------------------------------ #

    def protective_escape(
        self,
        raw_state: BrainstemFunctionalState,
        energy: float,
    ) -> tuple[BrainstemFunctionalState, bool]:
        """Escape from protective if conditions allow."""
        if raw_state == BrainstemFunctionalState.PROTECTIVE:
            self._protective_consecutive_ticks += 1
        else:
            self._protective_consecutive_ticks = 0

        if raw_state == BrainstemFunctionalState.PROTECTIVE:
            if (
                self._protective_consecutive_ticks >= self.PROTECTIVE_ESCAPE_TICKS
                and self._last_adjusted_vitality > self.PROTECTIVE_ESCAPE_VITALITY
                and self._last_adjusted_risk < self.PROTECTIVE_ESCAPE_RISK
                and energy >= self.PROTECTIVE_ESCAPE_ENERGY
            ):
                self._protective_escape_count += 1
                return BrainstemFunctionalState.CORRECTIVE, True
        return raw_state, False

    # ------------------------------------------------------------------ #
    # T36 — Cognitive / Autonomic Scoring
    # ------------------------------------------------------------------ #

    def compute_cognitive_vitality_score(self, metrics: Dict[str, Any]) -> float:
        """Score of productive cognitive activity in [0, 1].

        Uses available tick-level proxies; falls back to phi + signal flow
        when benchmark-level metrics are absent.
        """
        # Prefer explicit benchmark-level inputs when available
        cognitive_score = metrics.get("cognitive_score", 0.0)
        functional_improvement = metrics.get("functional_improvement", 0.0)
        regional_signal_flow = metrics.get("regional_signal_flow", 0.0)
        deep_region_signal_flow = metrics.get("deep_region_signal_flow", 0.0)
        mean_pathway_utility = max(0.0, metrics.get("mean_pathway_utility", 0.0))
        mean_region_phi = metrics.get("mean_region_phi", 0.0)

        # If benchmark-level metrics are zero (typical during orchestrator ticks),
        # build a proxy from tick-level signals
        if cognitive_score == 0.0 and functional_improvement == 0.0:
            # Proxy: phi is the strongest single indicator of coherent cognition
            # signal_flow and pathway_utility proxy productive activity
            proxy = (
                0.45 * min(1.0, mean_region_phi)
                + 0.25 * min(1.0, regional_signal_flow)
                + 0.20 * min(1.0, deep_region_signal_flow)
                + 0.10 * min(1.0, mean_pathway_utility)
            )
            return round(min(1.0, max(0.0, proxy)), 4)

        # Full formula when benchmark inputs are available
        score = (
            0.35 * cognitive_score
            + 0.25 * functional_improvement
            + 0.15 * regional_signal_flow
            + 0.15 * deep_region_signal_flow
            + 0.10 * mean_pathway_utility
        )
        return round(min(1.0, max(0.0, score)), 4)

    def compute_autonomic_risk_score(self, metrics: Dict[str, Any]) -> float:
        """Score of systemic autonomic risk in [0, 1]."""
        region_instability_mean = metrics.get("region_instability_mean", 0.0)
        mean_region_phi = metrics.get("mean_region_phi", 0.0)
        mean_energy = metrics.get("mean_energy", 0.0)
        mean_deep_activation = metrics.get("mean_deep_region_activation", 0.0)
        unstable_region_count = metrics.get("unstable_region_count", 0)
        total_regions = max(1, metrics.get("region_count", 4))
        unstable_ratio = unstable_region_count / total_regions

        # Activation overflow: penalize if deep activation is very high (> 3.0)
        activation_overflow = max(0.0, (mean_deep_activation - 1.0) / 4.0)

        score = (
            0.30 * region_instability_mean
            + 0.20 * max(0.0, 1.0 - mean_region_phi)
            + 0.20 * max(0.0, 1.0 - mean_energy)
            + 0.15 * activation_overflow
            + 0.15 * unstable_ratio
        )
        return round(min(1.0, max(0.0, score)), 4)

    def compute_balance_pressure(
        self, metrics: Dict[str, Any]
    ) -> tuple[float, float, float]:
        """Return (cognitive_vitality, autonomic_risk, balance_pressure)."""
        vitality = self.compute_cognitive_vitality_score(metrics)
        risk = self.compute_autonomic_risk_score(metrics)
        pressure = max(0.0, risk - vitality)
        self._last_cognitive_vitality = vitality
        self._last_autonomic_risk = risk
        self._last_balance_pressure = pressure
        return vitality, risk, pressure

    # ------------------------------------------------------------------ #
    # State evaluation
    # ------------------------------------------------------------------ #

    def evaluate_state(
        self,
        metrics: Dict[str, Any],
        gain_vector: Optional[Dict[str, float]] = None,
    ) -> BrainstemFunctionalState:
        vitality, risk, raw_pressure = self.compute_balance_pressure(metrics)

        # T39 — Apply gain-coupled scoring
        self.apply_gain_to_input_scores(vitality, risk, gain_vector)
        adjusted_vitality = self._last_adjusted_vitality
        adjusted_risk = self._last_adjusted_risk
        pressure = self._last_adjusted_balance_pressure

        phi = metrics.get("mean_region_phi", 0.0)
        energy = metrics.get("mean_energy", 0.0)
        instability = metrics.get("region_instability_mean", 0.0)
        unstable_count = metrics.get("unstable_region_count", 0)
        deep_activation = metrics.get("mean_deep_region_activation", 0.0)

        # Absolute emergency overrides (hard biological limits)
        energy_critical = energy < self.ENERGY_CRITICAL_LOW
        activation_explosion = deep_activation > 5.0
        phi_collapsing = phi < self.PHI_COLLAPSE_THRESHOLD
        extreme_instability = instability >= self.instability_threshold_emergency
        many_unstable = unstable_count >= 4

        absolute_emergency = (
            energy_critical
            or activation_explosion
            or (phi_collapsing and instability >= 0.40)
            or (extreme_instability and many_unstable)
        )

        # T39 — Dynamic thresholds
        thresholds = self.compute_adjusted_thresholds(gain_vector)

        # T36 — Cognitive preservation rule
        # If cognition is productive and no hard limit is breached, cap at corrective
        self._last_cognitive_preservation_applied = False
        if adjusted_vitality > self.COGNITIVE_PRESERVATION_THRESHOLD and not absolute_emergency:
            self._last_cognitive_preservation_applied = True
            # Cap state at corrective regardless of pressure
            if pressure < thresholds["stable"]:
                return BrainstemFunctionalState.STABLE
            if pressure < thresholds["watchful"]:
                return BrainstemFunctionalState.WATCHFUL
            return BrainstemFunctionalState.CORRECTIVE

        # Normal T39 balance-pressure driven state selection with adjusted thresholds
        if absolute_emergency:
            return BrainstemFunctionalState.EMERGENCY

        if pressure >= thresholds["emergency"]:
            return BrainstemFunctionalState.EMERGENCY
        if pressure >= thresholds["protective"]:
            return BrainstemFunctionalState.PROTECTIVE
        if pressure >= thresholds["corrective"]:
            return BrainstemFunctionalState.CORRECTIVE
        if pressure >= thresholds["watchful"]:
            return BrainstemFunctionalState.WATCHFUL
        return BrainstemFunctionalState.STABLE

    # ------------------------------------------------------------------ #
    # Hysteresis
    # ------------------------------------------------------------------ #

    def _apply_hysteresis(self, raw_state: BrainstemFunctionalState) -> BrainstemFunctionalState:
        """Require consecutive ticks for emergency entry; smooth exit."""
        if raw_state == BrainstemFunctionalState.EMERGENCY:
            self._consecutive_emergency_ticks += 1
        else:
            self._consecutive_emergency_ticks = 0

        if raw_state == BrainstemFunctionalState.EMERGENCY:
            if self._in_emergency or self._consecutive_emergency_ticks >= self.EMERGENCY_CONSECUTIVE_TICKS_REQUIRED:
                self._in_emergency = True
                return BrainstemFunctionalState.EMERGENCY
            # Not yet qualified for emergency — downgrade to protective
            return BrainstemFunctionalState.PROTECTIVE

        # Exit emergency only when balance pressure drops well below threshold
        if self._in_emergency:
            if self._last_balance_pressure < self.EMERGENCY_EXIT_THRESHOLD:
                self._in_emergency = False
                return raw_state
            return BrainstemFunctionalState.EMERGENCY

        return raw_state

    # ------------------------------------------------------------------ #
    # Decision computation
    # ------------------------------------------------------------------ #

    def decide(
        self,
        metrics: Dict[str, Any],
        memory: Optional[MorphologicalMemory] = None,
        gain_vector: Optional[Dict[str, float]] = None,
    ) -> BrainstemDecision:
        # T39 — Store gain vector for later use (filter out non-numeric fields like 'reason')
        if gain_vector is not None:
            self._gain_vector = {
                k: float(v)
                for k, v in gain_vector.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            }

        raw_state = self.evaluate_state(metrics, gain_vector)
        state = self._apply_hysteresis(raw_state)

        # T39 — Protective escape
        energy = metrics.get("mean_energy", 0.0)
        state, escape_applied = self.protective_escape(state, energy)

        vitality = self._last_adjusted_vitality
        pressure = self._last_adjusted_balance_pressure

        reasons: List[str] = []
        reasons.append(f"vitality={vitality:.2f}")
        reasons.append(f"pressure={pressure:.2f}")
        if self._last_cognitive_preservation_applied:
            reasons.append("cognitive_preservation_applied")
        if escape_applied:
            reasons.append("protective_escape_applied")

        if state == BrainstemFunctionalState.STABLE:
            reasons.append("system_stable")
        if state == BrainstemFunctionalState.WATCHFUL:
            reasons.append("mild_pressure")
        if state == BrainstemFunctionalState.CORRECTIVE:
            reasons.append("moderate_pressure")
        if state == BrainstemFunctionalState.PROTECTIVE:
            reasons.append("strong_pressure")
        if state == BrainstemFunctionalState.EMERGENCY:
            reasons.append("critical_balance_or_hard_limit")

        decision = BrainstemDecision(
            state=state,
            reason="; ".join(reasons),
        )

        # T36 — Soft modulation profiles (less suppressive than T35)
        if state == BrainstemFunctionalState.STABLE:
            return decision

        if state == BrainstemFunctionalState.WATCHFUL:
            decision.routing_suppression_multiplier = 0.95
            decision.plasticity_suppression_multiplier = 0.95
            decision.decay_boost_multiplier = 1.05
            decision.brainstem_priority_boost = 1.02
            return decision

        if state == BrainstemFunctionalState.CORRECTIVE:
            decision.routing_suppression_multiplier = 0.85
            decision.plasticity_suppression_multiplier = 0.90
            decision.decay_boost_multiplier = 1.10
            decision.cooldown_boost_multiplier = 1.05
            decision.brainstem_priority_boost = 1.05
            return decision

        if state == BrainstemFunctionalState.PROTECTIVE:
            decision.routing_suppression_multiplier = 0.70
            decision.plasticity_suppression_multiplier = 0.75
            decision.decay_boost_multiplier = 1.20
            decision.cooldown_boost_multiplier = 1.15
            decision.neurogenesis_suppression_multiplier = 0.50
            decision.apoptosis_boost_multiplier = 1.15
            decision.brainstem_priority_boost = 1.10
            return decision

        if state == BrainstemFunctionalState.EMERGENCY:
            decision.routing_suppression_multiplier = 0.50
            decision.plasticity_suppression_multiplier = 0.50
            decision.decay_boost_multiplier = 1.50
            decision.cooldown_boost_multiplier = 1.30
            decision.neurogenesis_suppression_multiplier = 0.30
            decision.apoptosis_boost_multiplier = 1.30
            decision.energy_recovery_multiplier = 1.30
            decision.brainstem_priority_boost = 1.20
            return decision

        return decision

    # ------------------------------------------------------------------ #
    # Apply modulation
    # ------------------------------------------------------------------ #

    def apply(
        self,
        metrics: Dict[str, Any],
        memory: Optional[MorphologicalMemory] = None,
        gain_vector: Optional[Dict[str, float]] = None,
    ) -> BrainstemModulationResult:
        decision = self.decide(metrics, memory, gain_vector)
        state = decision.state
        state_changed = self._previous_state != state
        if state_changed:
            self._state_transition_count += 1
        self._previous_state = state
        self._decisions_count += 1
        self._state_ticks[state.value] = self._state_ticks.get(state.value, 0) + 1

        if state == BrainstemFunctionalState.EMERGENCY:
            self._emergency_count += 1

        phi = metrics.get("mean_region_phi", 0.0)
        phi_recovery = max(0.0, phi - self._last_phi)
        self._last_phi = phi

        recovery_actions = 0
        if state in {BrainstemFunctionalState.CORRECTIVE, BrainstemFunctionalState.PROTECTIVE, BrainstemFunctionalState.EMERGENCY}:
            recovery_actions = 1
            self._recovery_actions += 1

        # T36 — suppression cost and useful activity preserved
        suppression_cost = 0.0
        if state == BrainstemFunctionalState.WATCHFUL:
            suppression_cost = 0.02
        elif state == BrainstemFunctionalState.CORRECTIVE:
            suppression_cost = 0.05
        elif state == BrainstemFunctionalState.PROTECTIVE:
            suppression_cost = 0.12
        elif state == BrainstemFunctionalState.EMERGENCY:
            suppression_cost = 0.25
        self._last_suppression_cost = suppression_cost

        useful_activity_preserved = (
            self._last_cognitive_vitality > self.COGNITIVE_PRESERVATION_THRESHOLD
            and state not in {BrainstemFunctionalState.PROTECTIVE, BrainstemFunctionalState.EMERGENCY}
        )
        self._last_useful_activity_preserved = useful_activity_preserved

        # Compute homeostatic gain score (T36 adjusted)
        homeostatic_gain = 0.0
        if state == BrainstemFunctionalState.STABLE:
            homeostatic_gain = 0.05
        elif state == BrainstemFunctionalState.WATCHFUL:
            homeostatic_gain = 0.02
        elif state == BrainstemFunctionalState.CORRECTIVE:
            homeostatic_gain = -0.02
        elif state == BrainstemFunctionalState.PROTECTIVE:
            homeostatic_gain = -0.08
        elif state == BrainstemFunctionalState.EMERGENCY:
            homeostatic_gain = -0.15

        # T39 — Output coupling trace
        raw_modulations = {
            "routing_suppression_multiplier": 0.70 if self._last_balance_pressure >= self.BALANCE_PRESSURE_PROTECTIVE else (
                0.85 if self._last_balance_pressure >= self.BALANCE_PRESSURE_CORRECTIVE else 1.0
            ),
            "plasticity_suppression_multiplier": 0.75 if self._last_balance_pressure >= self.BALANCE_PRESSURE_PROTECTIVE else (
                0.90 if self._last_balance_pressure >= self.BALANCE_PRESSURE_CORRECTIVE else 1.0
            ),
            "decay_boost_multiplier": 1.20 if self._last_balance_pressure >= self.BALANCE_PRESSURE_PROTECTIVE else (
                1.10 if self._last_balance_pressure >= self.BALANCE_PRESSURE_CORRECTIVE else 1.0
            ),
            "energy_recovery_multiplier": 1.0,
        }
        final_modulations = {
            "routing_suppression_multiplier": decision.routing_suppression_multiplier,
            "plasticity_suppression_multiplier": decision.plasticity_suppression_multiplier,
            "decay_boost_multiplier": decision.decay_boost_multiplier,
            "energy_recovery_multiplier": decision.energy_recovery_multiplier,
        }
        coupling_delta = sum(
            abs(final_modulations[k] - raw_modulations[k])
            for k in raw_modulations if k in final_modulations
        ) / len(raw_modulations)
        self._last_coupling_delta = round(coupling_delta, 4)

        trace = BrainstemCouplingTrace(
            tick_id=self._decisions_count,
            state_before=self._previous_state.value if self._previous_state and not state_changed else state.value,
            state_after=state.value,
            raw_vitality=round(self._last_cognitive_vitality, 4),
            raw_risk=round(self._last_autonomic_risk, 4),
            adjusted_vitality=round(self._last_adjusted_vitality, 4),
            adjusted_risk=round(self._last_adjusted_risk, 4),
            raw_balance_pressure=round(self._last_balance_pressure, 4),
            adjusted_balance_pressure=round(self._last_adjusted_balance_pressure, 4),
            gain_vector=dict(self._gain_vector),
            raw_modulations=raw_modulations,
            final_modulations=final_modulations,
            coupling_delta=self._last_coupling_delta,
            protective_escape_applied=(
                state == BrainstemFunctionalState.CORRECTIVE
                and self._protective_consecutive_ticks >= self.PROTECTIVE_ESCAPE_TICKS
            ),
        )
        self._coupling_traces.append(trace)
        self._last_suppression_cost_after_coupling = suppression_cost

        result = BrainstemModulationResult(
            decision=decision,
            state_changed=state_changed,
            decisions_count=self._decisions_count,
            emergency_count=self._emergency_count,
            recovery_actions=recovery_actions,
            homeostatic_gain=homeostatic_gain,
            phi_recovery_contribution=phi_recovery,
        )

        if memory is not None:
            if state_changed:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_STATE_CHANGED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "new_state": state.value,
                        "previous_state": self._previous_state.value if self._previous_state else None,
                        "reason": decision.reason,
                        "balance_pressure": round(self._last_balance_pressure, 4),
                        "cognitive_vitality": round(self._last_cognitive_vitality, 4),
                        "autonomic_risk": round(self._last_autonomic_risk, 4),
                    },
                )
            memory.create_event(
                event_type=MorphologyEventType.BRAINSTEM_MODULATION_APPLIED,
                region_id="brainstem_homeostatic",
                metadata={
                    "state": state.value,
                    "routing_suppression_multiplier": decision.routing_suppression_multiplier,
                    "plasticity_suppression_multiplier": decision.plasticity_suppression_multiplier,
                    "energy_recovery_multiplier": decision.energy_recovery_multiplier,
                    "decay_boost_multiplier": decision.decay_boost_multiplier,
                    "brainstem_priority_boost": decision.brainstem_priority_boost,
                    "balance_pressure": round(self._last_balance_pressure, 4),
                },
            )
            if state == BrainstemFunctionalState.EMERGENCY:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_EMERGENCY_TRIGGERED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "reason": decision.reason,
                        "routing_suppression_multiplier": decision.routing_suppression_multiplier,
                        "energy_recovery_multiplier": decision.energy_recovery_multiplier,
                    },
                )
            if recovery_actions > 0:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_RECOVERY_APPLIED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "state": state.value,
                        "phi_recovery_contribution": phi_recovery,
                    },
                )
            if decision.routing_suppression_multiplier < 1.0:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_ROUTING_SUPPRESSED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "routing_suppression_multiplier": decision.routing_suppression_multiplier,
                    },
                )
            if decision.plasticity_suppression_multiplier < 1.0:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_PLASTICITY_SUPPRESSED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "plasticity_suppression_multiplier": decision.plasticity_suppression_multiplier,
                    },
                )
            if decision.energy_recovery_multiplier > 1.0:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_ENERGY_RECOVERY_BOOSTED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "energy_recovery_multiplier": decision.energy_recovery_multiplier,
                    },
                )
            # T36 — New events
            if self._last_cognitive_preservation_applied:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_COGNITIVE_ACTIVITY_PRESERVED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "cognitive_vitality": round(self._last_cognitive_vitality, 4),
                        "capped_state": state.value,
                    },
                )
            if self._in_emergency and state_changed and state == BrainstemFunctionalState.EMERGENCY:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_EMERGENCY_HYSTERESIS_APPLIED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "consecutive_ticks": self._consecutive_emergency_ticks,
                    },
                )
            if state_changed and self._previous_state == BrainstemFunctionalState.EMERGENCY and not self._in_emergency:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_STATE_EXITED_EMERGENCY,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "balance_pressure": round(self._last_balance_pressure, 4),
                    },
                )
            if self._last_useful_activity_preserved:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_SUPPRESSION_SOFTENED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "cognitive_vitality": round(self._last_cognitive_vitality, 4),
                        "balance_pressure": round(self._last_balance_pressure, 4),
                    },
                )
            memory.create_event(
                event_type=MorphologyEventType.BRAINSTEM_BALANCE_EVALUATED,
                region_id="brainstem_homeostatic",
                metadata={
                    "cognitive_vitality": round(self._last_cognitive_vitality, 4),
                    "autonomic_risk": round(self._last_autonomic_risk, 4),
                    "balance_pressure": round(self._last_balance_pressure, 4),
                    "state": state.value,
                },
            )
            # T39 — New events
            if self._gain_vector:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_GAIN_INPUT_COUPLED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "raw_vitality": round(self._last_cognitive_vitality, 4),
                        "adjusted_vitality": round(self._last_adjusted_vitality, 4),
                        "raw_risk": round(self._last_autonomic_risk, 4),
                        "adjusted_risk": round(self._last_adjusted_risk, 4),
                        "gain_vector": dict(self._gain_vector),
                    },
                )
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_STATE_THRESHOLD_ADJUSTED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "thresholds": self.compute_adjusted_thresholds(self._gain_vector),
                    },
                )
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_OUTPUT_COUPLED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "raw_modulations": raw_modulations,
                        "final_modulations": final_modulations,
                        "coupling_delta": self._last_coupling_delta,
                    },
                )
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_COUPLING_TRACE_RECORDED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "trace_id": trace.tick_id,
                        "coupling_delta": trace.coupling_delta,
                    },
                )
            if trace.protective_escape_applied:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_PROTECTIVE_ESCAPE,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "consecutive_protective_ticks": self._protective_consecutive_ticks,
                        "adjusted_vitality": trace.adjusted_vitality,
                        "adjusted_risk": trace.adjusted_risk,
                    },
                )
            if coupling_delta > 0.01:
                memory.create_event(
                    event_type=MorphologyEventType.BRAINSTEM_SUPPRESSION_RELEASED,
                    region_id="brainstem_homeostatic",
                    metadata={
                        "coupling_delta": coupling_delta,
                        "state_before": trace.state_before,
                        "state_after": trace.state_after,
                    },
                )

        return result

    # ------------------------------------------------------------------ #
    # Getters for benchmark / orchestrator integration
    # ------------------------------------------------------------------ #

    def get_modulation_summary(self) -> Dict[str, Any]:
        total_ticks = max(1, sum(self._state_ticks.values()))
        return {
            "previous_state": self._previous_state.value if self._previous_state else None,
            "decisions_count": self._decisions_count,
            "emergency_count": self._emergency_count,
            "recovery_actions": self._recovery_actions,
            "state_ticks": dict(self._state_ticks),
            "cognitive_vitality": self._last_cognitive_vitality,
            "autonomic_risk": self._last_autonomic_risk,
            "balance_pressure": self._last_balance_pressure,
            "cognitive_preservation_applied": self._last_cognitive_preservation_applied,
            "suppression_cost": self._last_suppression_cost,
            "useful_activity_preserved": self._last_useful_activity_preserved,
            "in_emergency": self._in_emergency,
            "consecutive_emergency_ticks": self._consecutive_emergency_ticks,
            # T39
            "adjusted_cognitive_vitality": self._last_adjusted_vitality,
            "adjusted_autonomic_risk": self._last_adjusted_risk,
            "adjusted_balance_pressure": self._last_adjusted_balance_pressure,
            "gain_vector": dict(self._gain_vector),
            "protective_escape_count": self._protective_escape_count,
            "protective_state_ratio": round(self._state_ticks.get("protective", 0) / total_ticks, 4),
            "corrective_state_ratio": round(self._state_ticks.get("corrective", 0) / total_ticks, 4),
            "emergency_state_ratio": round(self._state_ticks.get("emergency", 0) / total_ticks, 4),
            "coupling_delta": self._last_coupling_delta,
            "suppression_cost_after_coupling": self._last_suppression_cost_after_coupling,
            "state_transition_count": self._state_transition_count,
        }

    @staticmethod
    def _clamp(value: float, min_val: float, max_val: float) -> float:
        return max(min_val, min(max_val, value))
