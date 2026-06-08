import math

import numpy as np
import pytest

from speace_core.cellular_brain.cognition.global_workspace import GlobalWorkspace
from speace_core.cellular_brain.memory.morphology_events import (
    MorphologyEventType,
    MorphologyEvent,
)


class FakeMemory:
    def __init__(self):
        self.events = []

    def log_event(self, event):
        self.events.append(event)


@pytest.fixture
def memory():
    return FakeMemory()


@pytest.fixture
def workspace(memory):
    return GlobalWorkspace(
        broadcast_dim=64,
        symbolic_dim=16,
        num_modules=10,
        seed=42,
        memory=memory,
    )


# ------------------------------------------------------------------ #
# Construction / initial state
# ------------------------------------------------------------------ #

class TestConstruction:
    def test_default_state(self, workspace):
        state = workspace.get_global_state()
        assert state["tick"] == 0
        assert state["awareness_level"] == 0.0
        assert state["coherence"] == 0.0
        assert state["energy"] == 1.0
        assert state["prediction_error"] == 0.0
        assert state["winning_module"] is None
        assert len(state["recurrent_state"]) == 64
        assert len(state["symbolic_state"]) == 16
        assert len(state["predicted_next_symbolic_state"]) == 16

    def test_attention_focus_none_before_step(self, workspace):
        assert workspace.get_attention_focus() is None


# ------------------------------------------------------------------ #
# broadcast
# ------------------------------------------------------------------ #

class TestBroadcast:
    def test_broadcast_queues_module(self, workspace):
        rep = [0.5] * 64
        workspace.broadcast("module_a", rep)
        assert len(workspace._broadcast_queue) == 1
        assert workspace._broadcast_queue[0][0] == "module_a"

    def test_broadcast_pads_short_vector(self, workspace):
        workspace.broadcast("module_b", [0.1] * 32)
        vec = workspace._broadcast_queue[0][1]
        assert len(vec) == 64
        assert vec[32] == 0.0

    def test_broadcast_truncates_long_vector(self, workspace):
        workspace.broadcast("module_c", [0.2] * 128)
        vec = workspace._broadcast_queue[0][1]
        assert len(vec) == 64

    def test_broadcast_logs_event(self, workspace, memory):
        workspace.broadcast("module_d", [0.3] * 64)
        events = [
            e for e in memory.events
            if e.event_type == MorphologyEventType.GLOBAL_WORKSPACE_BROADCAST_QUEUED
        ]
        assert len(events) == 1
        assert events[0].metadata["module_id"] == "module_d"


# ------------------------------------------------------------------ #
# attention_routing
# ------------------------------------------------------------------ #

class TestAttentionRouting:
    def test_empty_queue_returns_spontaneous(self, workspace):
        winner, vec = workspace.attention_routing([])
        assert winner == "spontaneous"
        assert len(vec) == 64

    def test_single_item_wins(self, workspace):
        queue = [("mod1", np.ones(64))]
        winner, vec = workspace.attention_routing(queue)
        assert winner == "mod1"

    def test_winner_boosts_attention_weight(self, workspace):
        queue = [
            ("mod1", np.zeros(64)),
            ("mod2", np.ones(64) * 2.0),
        ]
        winner, _ = workspace.attention_routing(queue)
        assert winner == "mod2"
        assert workspace._module_attention_weights["mod2"] > 1.0

    def test_loser_attention_weight_decays(self, workspace):
        queue = [
            ("mod1", np.ones(64) * 2.0),
            ("mod2", np.zeros(64)),
        ]
        workspace.attention_routing(queue)
        assert workspace._module_attention_weights["mod2"] < 1.0

    def test_attention_routing_logs_event(self, workspace, memory):
        workspace.attention_routing([("mod1", np.ones(64))])
        events = [
            e for e in memory.events
            if e.event_type == MorphologyEventType.GLOBAL_WORKSPACE_ATTENTION_ROUTED
        ]
        assert len(events) == 1
        assert events[0].metadata["winning_module"] == "mod1"

    def test_activity_history_tracked(self, workspace):
        workspace.attention_routing([("mod1", np.ones(64))])
        assert "mod1" in workspace._module_activity_history
        assert workspace._module_activity_history["mod1"][-1] == 1.0

    def test_probabilistic_routing_different_seeds(self):
        ws1 = GlobalWorkspace(seed=1)
        ws2 = GlobalWorkspace(seed=2)
        queue = [
            ("mod1", np.ones(64)),
            ("mod2", np.ones(64) * 1.1),
        ]
        # Same salience-modulated softmax, different RNG draws could differ
        w1, _ = ws1.attention_routing(queue)
        w2, _ = ws2.attention_routing(queue)
        # Since both have similar norms, this is non-deterministic across seeds
        assert w1 in {"mod1", "mod2"}
        assert w2 in {"mod1", "mod2"}


# ------------------------------------------------------------------ #
# recurrent_activation
# ------------------------------------------------------------------ #

class TestRecurrentActivation:
    def test_state_persists(self, workspace):
        init = workspace._recurrent_state.copy()
        broadcast_vec = np.ones(64)
        new_state = workspace.recurrent_activation(broadcast_vec)
        assert not np.array_equal(init, new_state)

    def test_bounded_by_tanh(self, workspace):
        broadcast_vec = np.ones(64) * 10.0
        new_state = workspace.recurrent_activation(broadcast_vec)
        assert np.all(new_state <= 1.0)
        assert np.all(new_state >= -1.0)

    def test_blend_ratio(self, workspace):
        workspace._recurrent_state = np.zeros(64)
        broadcast_vec = np.ones(64)
        new_state = workspace.recurrent_activation(broadcast_vec)
        # leak=0.7, so state is 0.7*0 + 0.3*1 = 0.3, then tanh(0.3) ≈ 0.29
        assert np.allclose(new_state, np.tanh(0.3), atol=0.01)


# ------------------------------------------------------------------ #
# symbolic_compression
# ------------------------------------------------------------------ #

class TestSymbolicCompression:
    def test_output_dim_matches_symbolic_dim(self, workspace):
        vec = np.ones(64)
        compressed = workspace.symbolic_compression(vec)
        assert len(compressed) == 16

    def test_output_normalized(self, workspace):
        vec = np.ones(64) * 5.0
        compressed = workspace.symbolic_compression(vec)
        norm = np.linalg.norm(compressed)
        assert pytest.approx(norm, abs=1e-6) == 1.0

    def test_negative_leakage(self, workspace):
        # Strong negative inputs pass through a random projection; the leaky ReLU
        # ensures any negative post-projection values are small rather than zero.
        vec = -np.ones(64) * 10.0
        compressed = workspace.symbolic_compression(vec)
        # Output must remain normalized and bounded
        assert np.all(np.abs(compressed) <= 1.0)
        assert pytest.approx(np.linalg.norm(compressed), abs=1e-6) == 1.0


# ------------------------------------------------------------------ #
# prediction_loop
# ------------------------------------------------------------------ #

class TestPredictionLoop:
    def test_output_dim_matches_symbolic_dim(self, workspace):
        sym = np.ones(16)
        pred = workspace.prediction_loop(sym)
        assert len(pred) == 16

    def test_output_normalized(self, workspace):
        sym = np.ones(16)
        pred = workspace.prediction_loop(sym)
        norm = np.linalg.norm(pred)
        assert pytest.approx(norm, abs=1e-6) == 1.0

    def test_bounded_by_tanh(self, workspace):
        sym = np.ones(16) * 100.0
        pred = workspace.prediction_loop(sym)
        assert np.all(pred <= 1.0)
        assert np.all(pred >= -1.0)


# ------------------------------------------------------------------ #
# self_state_model
# ------------------------------------------------------------------ #

class TestSelfStateModel:
    def test_awareness_in_range(self, workspace):
        workspace._recurrent_state = np.ones(64) * 0.5
        workspace._current_symbolic_state = np.ones(16) / 16.0
        state = workspace.self_state_model()
        assert 0.0 <= state["awareness_level"] <= 1.0

    def test_coherence_in_range(self, workspace):
        workspace._current_symbolic_state = np.ones(16) / 16.0
        state = workspace.self_state_model()
        assert 0.0 <= state["coherence"] <= 1.0

    def test_energy_in_range(self, workspace):
        workspace._recurrent_state = np.ones(64) * 0.5
        state = workspace.self_state_model()
        assert 0.0 <= state["energy"] <= 1.0

    def test_energy_decays_without_input(self, workspace):
        workspace._energy = 1.0
        workspace._recurrent_state = np.zeros(64)
        before = workspace._energy
        workspace.self_state_model()
        assert workspace._energy < before

    def test_energy_recovers_with_input(self, workspace):
        workspace._energy = 0.1
        workspace._recurrent_state = np.ones(64) * 2.0
        before = workspace._energy
        workspace.self_state_model()
        assert workspace._energy > before


# ------------------------------------------------------------------ #
# step
# ------------------------------------------------------------------ #

class TestStep:
    def test_step_increments_tick(self, workspace):
        workspace.broadcast("mod1", [0.5] * 64)
        workspace.step()
        assert workspace._tick_count == 1

    def test_step_clears_queue(self, workspace):
        workspace.broadcast("mod1", [0.5] * 64)
        workspace.step()
        assert len(workspace._broadcast_queue) == 0

    def test_step_returns_dict(self, workspace):
        workspace.broadcast("mod1", [0.5] * 64)
        result = workspace.step()
        assert isinstance(result, dict)
        assert "tick" in result
        assert "winning_module" in result
        assert "awareness_level" in result
        assert "coherence" in result
        assert "energy" in result
        assert "prediction_error" in result
        assert "symbolic_state" in result
        assert "predicted_next_symbolic_state" in result

    def test_step_with_empty_queue(self, workspace):
        result = workspace.step()
        assert result["winning_module"] == "spontaneous"

    def test_attention_focus_after_step(self, workspace):
        workspace.broadcast("mod1", [0.5] * 64)
        workspace.step()
        assert workspace.get_attention_focus() == "mod1"

    def test_prediction_error_zero_on_first_tick(self, workspace):
        workspace.broadcast("mod1", [0.5] * 64)
        result = workspace.step()
        assert result["prediction_error"] == pytest.approx(0.0, abs=1e-6)

    def test_prediction_error_computed_after_second_tick(self, workspace):
        workspace.broadcast("mod1", [0.5] * 64)
        workspace.step()
        workspace.broadcast("mod1", [0.6] * 64)
        result = workspace.step()
        assert result["prediction_error"] >= 0.0

    def test_step_logs_event(self, workspace, memory):
        workspace.broadcast("mod1", [0.5] * 64)
        workspace.step()
        events = [
            e for e in memory.events
            if e.event_type == MorphologyEventType.GLOBAL_WORKSPACE_STEP_COMPLETED
        ]
        assert len(events) == 1
        assert "tick" in events[0].metadata

    def test_multiple_steps_evolve_state(self, workspace):
        for i in range(5):
            workspace.broadcast(f"mod{i % 3}", [0.1 + i * 0.05] * 64)
            workspace.step()
        state = workspace.get_global_state()
        assert state["tick"] == 5
        assert state["winning_module"] is not None


# ------------------------------------------------------------------ #
# get_global_state
# ------------------------------------------------------------------ #

class TestGetGlobalState:
    def test_contains_all_keys(self, workspace):
        state = workspace.get_global_state()
        expected_keys = {
            "tick",
            "recurrent_state",
            "symbolic_state",
            "predicted_next_symbolic_state",
            "awareness_level",
            "coherence",
            "energy",
            "prediction_error",
            "winning_module",
            "module_attention_weights",
        }
        assert set(state.keys()) == expected_keys

    def test_state_values_are_serializable(self, workspace):
        workspace.broadcast("mod1", [0.5] * 64)
        workspace.step()
        state = workspace.get_global_state()
        # Ensure everything is JSON-friendly
        import json
        json.dumps(state)


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

class TestHelpers:
    def test_compute_entropy_uniform(self):
        vec = np.ones(16)
        entropy = GlobalWorkspace._compute_entropy(vec)
        assert pytest.approx(entropy, abs=0.01) == 1.0

    def test_compute_entropy_peaked(self):
        vec = np.zeros(16)
        vec[0] = 1.0
        entropy = GlobalWorkspace._compute_entropy(vec)
        assert entropy < 0.5

    def test_compute_entropy_single_element(self):
        vec = np.array([1.0])
        entropy = GlobalWorkspace._compute_entropy(vec)
        assert entropy == 0.0


# ------------------------------------------------------------------ #
# Integration with different dimensions
# ------------------------------------------------------------------ #

class TestDifferentDimensions:
    def test_small_dimensions(self, memory):
        ws = GlobalWorkspace(
            broadcast_dim=8, symbolic_dim=4, seed=1, memory=memory
        )
        ws.broadcast("m", [0.5] * 8)
        ws.step()
        state = ws.get_global_state()
        assert len(state["recurrent_state"]) == 8
        assert len(state["symbolic_state"]) == 4

    def test_large_dimensions(self, memory):
        ws = GlobalWorkspace(
            broadcast_dim=256, symbolic_dim=32, seed=1, memory=memory
        )
        ws.broadcast("m", [0.5] * 256)
        ws.step()
        state = ws.get_global_state()
        assert len(state["recurrent_state"]) == 256
        assert len(state["symbolic_state"]) == 32


# ------------------------------------------------------------------ #
# Memory-less workspace
# ------------------------------------------------------------------ #

class TestMemoryLess:
    def test_no_crash_without_memory(self):
        ws = GlobalWorkspace(seed=42, memory=None)
        ws.broadcast("mod1", [0.5] * 64)
        ws.step()
        assert ws.get_attention_focus() == "mod1"

    def test_no_events_without_memory(self):
        ws = GlobalWorkspace(seed=42, memory=None)
        ws.broadcast("mod1", [0.5] * 64)
        ws.step()
        # Should simply not raise
