import pytest

from speace_core.cellular_brain.dynamics.dopaminergic_drive_circuit import (
    DopaminergicModulator,
    RewardPredictionErrorSignal,
)
from speace_core.cellular_brain.regions.pathway_utility_learner import PathwayRewardSignal


class TestDopaminergicDriveCircuit:
    def test_rpe_computation(self):
        mod = DopaminergicModulator(alpha=0.5, baseline_dopamine=0.5)
        reward = PathwayRewardSignal(composite_reward=0.8)
        signal = mod.tick(reward)
        assert signal.actual_reward == 0.8
        assert signal.predicted_reward == 0.0
        assert signal.rpe > 0
        assert signal.dopamine_burst > 0
        assert signal.dopamine_dip == 0.0

    def test_dip_on_negative_reward(self):
        mod = DopaminergicModulator(alpha=0.5, baseline_dopamine=0.5)
        # first tick positive to set prediction
        mod.tick(PathwayRewardSignal(composite_reward=0.8))
        # second tick negative
        signal = mod.tick(PathwayRewardSignal(composite_reward=-0.2))
        assert signal.rpe < 0
        assert signal.dopamine_dip < 0
        assert signal.dopamine_burst == 0.0

    def test_plasticity_gate_high_dopamine(self):
        mod = DopaminergicModulator(alpha=1.0, baseline_dopamine=0.5)
        mod.tick(PathwayRewardSignal(composite_reward=1.0))
        # After full update, dopamine should be high
        gate, reason = mod.plasticity_gate(0.0)
        assert gate is True
        assert "high_dopamine" in reason

    def test_plasticity_gate_low_dopamine(self):
        mod = DopaminergicModulator(alpha=1.0, baseline_dopamine=0.5)
        mod.tick(PathwayRewardSignal(composite_reward=-1.0))
        gate, reason = mod.plasticity_gate(0.0)
        assert gate is False
        assert "low_dopamine" in reason

    def test_state_reset(self):
        mod = DopaminergicModulator()
        mod.tick(PathwayRewardSignal(composite_reward=0.5))
        mod.reset()
        assert mod.state.dopamine_level == 0.5
        assert mod.state.vta_firing_rate == 0.0
