import json
from pathlib import Path

import pytest

from speace_core.cellular_brain.drives.autonomous_drive_engine import (
    AutonomousDriveEngine,
    Drive,
)


# ---------------------------------------------------------------------------
# Initialization & drive registration
# ---------------------------------------------------------------------------

class TestInitialization:
    def test_init_creates_seven_default_drives(self):
        engine = AutonomousDriveEngine()
        drives = engine.list_drives()
        assert len(drives) == 7
        for name in (
            "self_preservation",
            "energy_conservation",
            "resource_acquisition",
            "information_exploration",
            "homeostatic_equilibrium",
            "adaptive_exploration",
            "coherence_maintenance",
        ):
            assert name in drives

    def test_default_drives_start_at_setpoint(self):
        engine = AutonomousDriveEngine()
        sp = engine.get_drive("self_preservation")
        assert sp.current_value == sp.setpoint

    def test_list_drives_returns_names(self):
        engine = AutonomousDriveEngine()
        assert isinstance(engine.list_drives(), list)


class TestRegisterDrive:
    def test_register_new_drive(self):
        engine = AutonomousDriveEngine()
        engine.register_drive("novelty", setpoint=0.5, weight=1.0, activation_threshold=0.05)
        assert "novelty" in engine.list_drives()
        d = engine.get_drive("novelty")
        assert d.setpoint == 0.5
        assert d.weight == 1.0
        assert d.activation_threshold == 0.05

    def test_register_overwrite_existing(self):
        engine = AutonomousDriveEngine()
        engine.register_drive("self_preservation", setpoint=0.1, weight=0.1, activation_threshold=0.01)
        d = engine.get_drive("self_preservation")
        assert d.setpoint == 0.1


# ---------------------------------------------------------------------------
# Drive updates
# ---------------------------------------------------------------------------

class TestUpdateDrive:
    def test_update_drive(self):
        engine = AutonomousDriveEngine()
        engine.update_drive("self_preservation", 0.5)
        assert engine.get_drive("self_preservation").current_value == 0.5

    def test_update_drive_unregistered_raises(self):
        engine = AutonomousDriveEngine()
        with pytest.raises(KeyError):
            engine.update_drive("nonexistent", 1.0)


# ---------------------------------------------------------------------------
# Priority & urgency
# ---------------------------------------------------------------------------

class TestPriority:
    def test_get_drive_priority(self):
        engine = AutonomousDriveEngine()
        engine.update_drive("self_preservation", 0.6)
        # setpoint=0.9, weight=1.5  => |0.6 - 0.9| * 1.5 = 0.45
        assert engine.get_drive_priority("self_preservation") == pytest.approx(0.45)

    def test_get_drive_priority_unregistered_raises(self):
        engine = AutonomousDriveEngine()
        with pytest.raises(KeyError):
            engine.get_drive_priority("nonexistent")

    def test_get_highest_priority_drive(self):
        engine = AutonomousDriveEngine()
        engine.update_drive("self_preservation", 0.1)   # |0.1-0.9|*1.5 = 1.2
        engine.update_drive("energy_conservation", 0.7) # |0.7-0.7|*1.2 = 0
        name, urgency = engine.get_highest_priority_drive()
        assert name == "self_preservation"
        assert urgency == pytest.approx(1.2)

    def test_get_highest_priority_drive_empty(self):
        engine = AutonomousDriveEngine()
        # temporarily empty drives by clearing internal dict
        engine._drives.clear()
        assert engine.get_highest_priority_drive() is None


# ---------------------------------------------------------------------------
# Activation
# ---------------------------------------------------------------------------

class TestActivation:
    def test_drive_is_active(self):
        engine = AutonomousDriveEngine()
        engine.update_drive("self_preservation", 0.1)  # high deviation
        assert engine.get_drive("self_preservation").is_active() is True

    def test_drive_not_active(self):
        engine = AutonomousDriveEngine()
        engine.update_drive("self_preservation", 0.9)  # exactly at setpoint
        assert engine.get_drive("self_preservation").is_active() is False


# ---------------------------------------------------------------------------
# Global action tendency
# ---------------------------------------------------------------------------

class TestGlobalActionTendency:
    def test_tendency_repair_when_self_preservation_low(self):
        engine = AutonomousDriveEngine()
        engine.update_drive("self_preservation", 0.1)
        engine.update_drive("energy_conservation", 0.7)
        engine.update_drive("information_exploration", 0.5)
        assert engine.get_global_action_tendency() == "repair"

    def test_tendency_conserve_when_energy_low(self):
        engine = AutonomousDriveEngine()
        engine.update_drive("energy_conservation", 0.1)
        engine.update_drive("self_preservation", 0.9)
        assert engine.get_global_action_tendency() == "conserve"

    def test_tendency_explore_when_exploration_high(self):
        engine = AutonomousDriveEngine()
        engine.update_drive("information_exploration", 0.9)
        engine.update_drive("self_preservation", 0.9)
        engine.update_drive("energy_conservation", 0.7)
        assert engine.get_global_action_tendency() == "explore"

    def test_tendency_stabilize_when_homeostasis_low(self):
        engine = AutonomousDriveEngine()
        engine.update_drive("homeostatic_equilibrium", 0.1)
        engine.update_drive("self_preservation", 0.9)
        engine.update_drive("energy_conservation", 0.7)
        assert engine.get_global_action_tendency() == "stabilize"

    def test_tendency_acquire_when_resources_low(self):
        engine = AutonomousDriveEngine()
        engine.update_drive("resource_acquisition", 0.1)
        engine.update_drive("self_preservation", 0.9)
        engine.update_drive("energy_conservation", 0.7)
        assert engine.get_global_action_tendency() == "acquire"

    def test_tendency_integrate_when_coherence_low(self):
        engine = AutonomousDriveEngine()
        engine.update_drive("coherence_maintenance", 0.1)
        engine.update_drive("self_preservation", 0.9)
        engine.update_drive("energy_conservation", 0.7)
        assert engine.get_global_action_tendency() == "integrate"

    def test_tendency_adapt_when_adaptive_high(self):
        engine = AutonomousDriveEngine()
        engine.update_drive("adaptive_exploration", 0.9)
        engine.update_drive("self_preservation", 0.9)
        engine.update_drive("energy_conservation", 0.7)
        assert engine.get_global_action_tendency() == "adapt"


# ---------------------------------------------------------------------------
# Drive interactions
# ---------------------------------------------------------------------------

class TestInteractions:
    def test_self_preservation_suppresses_exploration(self):
        engine = AutonomousDriveEngine()
        engine.update_drive("self_preservation", 0.1)  # very high urgency
        engine.update_drive("information_exploration", 0.9)
        engine.update_drive("adaptive_exploration", 0.9)
        # Without suppression, exploration would dominate.
        # With suppression, repair should still win.
        assert engine.get_global_action_tendency() == "repair"

    def test_low_energy_suppresses_resource_acquisition(self):
        engine = AutonomousDriveEngine()
        engine.update_drive("energy_conservation", 0.1)  # very low energy
        engine.update_drive("resource_acquisition", 0.1)  # also low resources
        # Normally resource_acquisition would have urgency |0.1-0.5|*1.0 = 0.4
        # But energy_conservation urgency |0.1-0.7|*1.2 = 0.72 > threshold, so suppression
        # conserve should win over acquire
        assert engine.get_global_action_tendency() == "conserve"


# ---------------------------------------------------------------------------
# Step & sensors
# ---------------------------------------------------------------------------

class TestStep:
    def test_step_updates_drives(self):
        engine = AutonomousDriveEngine()
        tendency = engine.step({"cpu_usage": 0.95, "memory_usage": 0.8})
        # High cpu/memory -> inverted to low conservation score
        assert engine.get_drive("energy_conservation").current_value < 0.5

    def test_step_returns_tendency(self):
        engine = AutonomousDriveEngine()
        tendency = engine.step({"error_rate": 0.9})  # high error -> low preservation
        assert tendency in (
            "repair",
            "conserve",
            "acquire",
            "explore",
            "stabilize",
            "adapt",
            "integrate",
            "idle",
        )

    def test_step_with_no_relevant_sensors(self):
        engine = AutonomousDriveEngine()
        tendency = engine.step({"unknown_sensor": 42})
        # Drives stay at setpoints; urgencies are zero; no drive is active
        assert tendency == "idle"

    def test_sensor_inversion_error_rate(self):
        engine = AutonomousDriveEngine()
        engine.step({"error_rate": 0.9})
        assert engine.get_drive("self_preservation").current_value == pytest.approx(0.1)

    def test_sensor_inversion_cpu_usage(self):
        engine = AutonomousDriveEngine()
        engine.step({"cpu_usage": 0.8})
        assert engine.get_drive("energy_conservation").current_value == pytest.approx(0.2)

    def test_sensor_inversion_strategy_failure_rate(self):
        engine = AutonomousDriveEngine()
        engine.step({"strategy_failure_rate": 0.6})
        assert engine.get_drive("adaptive_exploration").current_value == pytest.approx(0.4)

    def test_sensor_inversion_internal_variance(self):
        engine = AutonomousDriveEngine()
        engine.step({"internal_variance": 0.5})
        assert engine.get_drive("homeostatic_equilibrium").current_value == pytest.approx(0.5)

    def test_sensor_inversion_idle_ratio(self):
        engine = AutonomousDriveEngine()
        engine.step({"idle_ratio": 0.9})
        assert engine.get_drive("energy_conservation").current_value == pytest.approx(0.9)

    def test_sensor_inversion_disk_usage(self):
        engine = AutonomousDriveEngine()
        engine.step({"disk_usage": 0.7})
        assert engine.get_drive("resource_acquisition").current_value == pytest.approx(0.3)

    def test_sensor_clamps_negative_to_zero(self):
        engine = AutonomousDriveEngine()
        engine.step({"cpu_usage": 1.5})
        assert engine.get_drive("energy_conservation").current_value == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_persist_and_load_history(self, tmp_path):
        history_file = tmp_path / "drive_history.jsonl"
        engine = AutonomousDriveEngine(history_path=str(history_file))
        engine.step({"cpu_usage": 0.5})
        engine.step({"error_rate": 0.2})
        history = engine.load_history()
        assert len(history) == 2
        assert "timestamp" in history[0]
        assert "action_tendency" in history[0]
        assert "drives" in history[0]

    def test_clear_history(self, tmp_path):
        history_file = tmp_path / "drive_history.jsonl"
        engine = AutonomousDriveEngine(history_path=str(history_file))
        engine.step({"cpu_usage": 0.5})
        assert len(engine.load_history()) == 1
        engine.clear_history()
        assert len(engine.load_history()) == 0

    def test_history_does_not_crash_on_missing_file(self, tmp_path):
        history_file = tmp_path / "missing_drive_history.jsonl"
        engine = AutonomousDriveEngine(history_path=str(history_file))
        assert engine.load_history() == []


# ---------------------------------------------------------------------------
# Snapshot & balance
# ---------------------------------------------------------------------------

class TestSnapshot:
    def test_snapshot_keys(self):
        engine = AutonomousDriveEngine()
        snap = engine.snapshot()
        assert "drives" in snap
        assert "highest_priority_drive" in snap
        assert "action_tendency" in snap
        assert "active_drive_count" in snap

    def test_snapshot_active_drive_count(self):
        engine = AutonomousDriveEngine()
        engine.update_drive("self_preservation", 0.1)
        snap = engine.snapshot()
        assert snap["active_drive_count"] >= 1

    def test_get_drive_balance_perfectly_balanced(self):
        engine = AutonomousDriveEngine()
        for name in engine.list_drives():
            engine.update_drive(name, engine.get_drive(name).setpoint)
        assert engine.get_drive_balance() == pytest.approx(0.0)

    def test_get_drive_balance_lopsided(self):
        engine = AutonomousDriveEngine()
        engine.update_drive("self_preservation", 0.0)
        for name in engine.list_drives():
            if name != "self_preservation":
                engine.update_drive(name, engine.get_drive(name).setpoint)
        assert engine.get_drive_balance() > 0.5

    def test_get_drive_balance_empty(self):
        engine = AutonomousDriveEngine()
        engine._drives.clear()
        assert engine.get_drive_balance() == 0.0


# ---------------------------------------------------------------------------
# Drive dataclass helpers
# ---------------------------------------------------------------------------

class TestDriveDataclass:
    def test_drive_to_snapshot(self):
        d = Drive(name="x", setpoint=0.5, weight=1.0, current_value=0.3, activation_threshold=0.1)
        snap = d.to_snapshot()
        assert snap["name"] == "x"
        assert snap["urgency"] == pytest.approx(0.2)
