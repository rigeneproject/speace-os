"""Dopaminergic Drive Circuit — biologically-inspired reward prediction error.

Provides:
- RewardPredictionErrorSignal (RPE = actual_reward − predicted_reward)
- DopaminergicModulator: VTA burst/dip, dopamine_level, vta_firing_rate
- Integration with PathwayUtilityLearner (consumes PathwayRewardSignal)
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from speace_core.cellular_brain.memory.morphological_memory import MorphologicalMemory
from speace_core.cellular_brain.memory.morphology_events import MorphologyEventType
from speace_core.cellular_brain.regions.pathway_utility_learner import PathwayRewardSignal


class RewardPredictionErrorSignal(BaseModel):
    """RPE and dopaminergic response for a single reward event."""

    predicted_reward: float = 0.0
    actual_reward: float = 0.0
    rpe: float = 0.0
    dopamine_burst: float = 0.0
    dopamine_dip: float = 0.0
    vta_firing_rate: float = 0.0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class DopaminergicState(BaseModel):
    """Observable state of the dopaminergic subsystem."""

    dopamine_level: float = 0.5
    vta_firing_rate: float = 0.0
    predicted_reward_ema: float = 0.0
    last_rpe: float = 0.0
    burst_count: int = 0
    dip_count: int = 0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class DopaminergicModulator:
    """Biologically-inspired dopaminergic modulator.

    The VTA (ventral tegmental area) fires in bursts when reward exceeds
    prediction (positive RPE) and dips when reward falls short
    (negative RPE).  Dopamine level modulates downstream plasticity gates.
    """

    def __init__(
        self,
        alpha: float = 0.2,
        baseline_dopamine: float = 0.5,
        burst_gain: float = 1.0,
        dip_gain: float = 1.0,
    ) -> None:
        self.alpha = alpha
        self.baseline_dopamine = baseline_dopamine
        self.burst_gain = burst_gain
        self.dip_gain = dip_gain

        self.state = DopaminergicState(
            dopamine_level=baseline_dopamine,
        )

    def tick(
        self,
        reward_signal: PathwayRewardSignal,
        memory: Optional[MorphologicalMemory] = None,
        source_id: str = "dopaminergic_modulator",
        target_id: str = "pathway_utility",
    ) -> RewardPredictionErrorSignal:
        """Process a reward signal and emit dopaminergic response."""
        actual = float(reward_signal.composite_reward)
        predicted = self.state.predicted_reward_ema
        rpe = actual - predicted

        # Update reward prediction EMA (basal ganglia / striatum learning)
        self.state.predicted_reward_ema = (
            self.alpha * actual + (1.0 - self.alpha) * self.state.predicted_reward_ema
        )

        burst = max(0.0, rpe) * self.burst_gain
        dip = min(0.0, rpe) * self.dip_gain

        # VTA firing rate tracks positive RPE (burst)
        self.state.vta_firing_rate = burst

        # Dopamine level = baseline + net modulatory signal, clamped [0, 1]
        self.state.dopamine_level = max(
            0.0,
            min(1.0, self.baseline_dopamine + burst + dip),
        )
        self.state.last_rpe = rpe

        if burst > 0:
            self.state.burst_count += 1
        elif dip < 0:
            self.state.dip_count += 1

        signal = RewardPredictionErrorSignal(
            predicted_reward=round(predicted, 6),
            actual_reward=round(actual, 6),
            rpe=round(rpe, 6),
            dopamine_burst=round(burst, 6),
            dopamine_dip=round(dip, 6),
            vta_firing_rate=round(self.state.vta_firing_rate, 6),
        )

        if memory is not None:
            if burst > 0:
                memory.create_event(
                    event_type=MorphologyEventType.DOPAMINE_BURST,
                    source_id=source_id,
                    target_id=target_id,
                    metadata={
                        "rpe": signal.rpe,
                        "dopamine_level": self.state.dopamine_level,
                        "vta_firing_rate": self.state.vta_firing_rate,
                        "actual_reward": signal.actual_reward,
                        "predicted_reward": signal.predicted_reward,
                    },
                )
            elif dip < 0:
                memory.create_event(
                    event_type=MorphologyEventType.DOPAMINE_DIP,
                    source_id=source_id,
                    target_id=target_id,
                    metadata={
                        "rpe": signal.rpe,
                        "dopamine_level": self.state.dopamine_level,
                        "vta_firing_rate": self.state.vta_firing_rate,
                        "actual_reward": signal.actual_reward,
                        "predicted_reward": signal.predicted_reward,
                    },
                )

        return signal

    def plasticity_gate(self, pathway_utility_score: float) -> tuple[bool, str]:
        """Return (should_strengthen, reason) based on dopamine level.

        High dopamine (> 0.65) facilitates LTP-like strengthening;
        low dopamine (< 0.35) suppresses it.
        """
        if self.state.dopamine_level > 0.65:
            return True, "high_dopamine_facilitates_ltp"
        if self.state.dopamine_level < 0.35:
            return False, "low_dopamine_suppresses_ltp"
        return pathway_utility_score > 0.0, "dopamine_neutral_utility_gated"

    def get_state(self) -> DopaminergicState:
        return self.state

    def reset(self) -> None:
        self.state = DopaminergicState(dopamine_level=self.baseline_dopamine)
