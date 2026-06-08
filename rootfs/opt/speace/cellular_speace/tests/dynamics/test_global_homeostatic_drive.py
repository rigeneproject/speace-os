import pytest

from speace_core.cellular_brain.dynamics.global_homeostatic_drive import (
    Drive,
    GlobalHomeostaticDrive,
)


# ---------------------------------------------------------------------------
# Drive registration and basic signal
# ---------------------------------------------------------------------------

class TestDriveRegistration:
    def test_default_drives_registered(self):
        drive = GlobalHomeostaticDrive()
        assert set(drive.list_drives()) == {"exploration", "stability", "survival", "efficiency"}

    def test_register_new_drive(self):
        drive = GlobalHomeostaticDrive()
        drive.register_drive("curiosity", setpoint=0.5, weight=1.0)
        assert "curiosity" in drive.list_drives()

    def test_overwrite_existing_drive(self):
        drive = GlobalHomeostaticDrive()
        drive.register_drive("exploration", setpoint=0.8, weight=2.0)
        assert drive.get_drive_signal("exploration") == pytest.approx(-1.6, 0.01)

    def test_update_drive_changes_signal(self):
        drive = GlobalHomeostaticDrive()
        drive.update_drive("exploration", current_value=1.0)
        assert drive.get_drive_signal("exploration") == pytest.approx(0.5, 0.01)

    def test_get_drive_signal_unregistered_raises(self):
        drive = GlobalHomeostaticDrive()
        with pytest.raises(KeyError):
            drive.get_drive_signal("unknown")

    def test_update_drive_unregistered_raises(self):
        drive = GlobalHomeostaticDrive()
        with pytest.raises(KeyError):
            drive.update_drive("unknown", current_value=0.5)


# ---------------------------------------------------------------------------
# Signal computation
# ---------------------------------------------------------------------------

class TestDriveSignal:
    def test_signal_at_setpoint_is_zero(self):
        drive = GlobalHomeostaticDrive()
        drive.update_drive("exploration", current_value=0.5)
        assert drive.get_drive_signal("exploration") == pytest.approx(0.0, 0.001)

    def test_signal_above_setpoint_positive(self):
        drive = GlobalHomeostaticDrive()
        drive.update_drive("exploration", current_value=0.8)
        assert drive.get_drive_signal("exploration") > 0.0

    def test_signal_below_setpoint_negative(self):
        drive = GlobalHomeostaticDrive()
        drive.update_drive("exploration", current_value=0.2)
        assert drive.get_drive_signal("exploration") < 0.0

    def test_weight_scales_signal(self):
        drive = GlobalHomeostaticDrive()
        drive.register_drive("test", setpoint=0.5, weight=2.0)
        drive.update_drive("test", current_value=0.7)
        assert drive.get_drive_signal("test") == pytest.approx(0.4, 0.001)


# ---------------------------------------------------------------------------
# Global modulation
# ---------------------------------------------------------------------------

class TestGlobalModulation:
    def test_modulation_keys(self):
        drive = GlobalHomeostaticDrive()
        mod = drive.get_global_modulation()
        assert set(mod.keys()) == {
            "plasticity_multiplier",
            "exploration_multiplier",
            "energy_supply_multiplier",
            "stability_multiplier",
        }

    def test_step_returns_modulation(self):
        drive = GlobalHomeostaticDrive()
        mod = drive.step()
        assert isinstance(mod, dict)
        assert "plasticity_multiplier" in mod

    def test_exploration_increases_multiplier(self):
        drive = GlobalHomeostaticDrive()
        drive.update_drive("exploration", current_value=1.0)
        drive.step()
        assert drive.get_global_modulation()["exploration_multiplier"] > 1.0

    def test_stability_increases_multiplier(self):
        drive = GlobalHomeostaticDrive()
        drive.update_drive("stability", current_value=1.0)
        drive.step()
        assert drive.get_global_modulation()["stability_multiplier"] > 1.0

    def test_efficiency_deficit_increases_energy_supply(self):
        drive = GlobalHomeostaticDrive()
        drive.update_drive("efficiency", current_value=0.0)
        drive.step()
        assert drive.get_global_modulation()["energy_supply_multiplier"] > 1.0


# ---------------------------------------------------------------------------
# Drive interactions
# ---------------------------------------------------------------------------

class TestDriveInteractions:
    def test_survival_suppresses_exploration(self):
        drive = GlobalHomeostaticDrive()
        # High survival need
        drive.update_drive("survival", current_value=1.0)
        # High exploration desire
        drive.update_drive("exploration", current_value=1.0)
        drive.step()
        mod = drive.get_global_modulation()
        # Exploration multiplier should be pulled down by survival
        assert mod["exploration_multiplier"] < 1.5

    def test_low_efficiency_suppresses_plasticity(self):
        drive = GlobalHomeostaticDrive()
        # High exploration normally boosts plasticity
        drive.update_drive("exploration", current_value=1.0)
        # Very low efficiency should suppress it
        drive.update_drive("efficiency", current_value=0.0)
        drive.step()
        mod = drive.get_global_modulation()
        # Without suppression plasticity would be >1.5; with suppression it should be lower
        assert mod["plasticity_multiplier"] < 1.5

    def test_critical_low_efficiency_strongly_suppresses_plasticity(self):
        drive = GlobalHomeostaticDrive()
        drive.update_drive("exploration", current_value=1.0)
        drive.update_drive("efficiency", current_value=-0.5)
        drive.step()
        mod = drive.get_global_modulation()
        assert mod["plasticity_multiplier"] < 1.0

    def test_all_drives_at_setpoint_neutral(self):
        drive = GlobalHomeostaticDrive()
        for name in drive.list_drives():
            drive.update_drive(name, drive._drives[name].setpoint)
        drive.step()
        mod = drive.get_global_modulation()
        for key, val in mod.items():
            assert val == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# Squashing helper
# ---------------------------------------------------------------------------

class TestSquash:
    def test_zero_signal_midpoint(self):
        drive = GlobalHomeostaticDrive()
        assert drive._squash(0.0, (0.0, 2.0)) == pytest.approx(1.0, 0.001)

    def test_large_signal_caps_near_max(self):
        drive = GlobalHomeostaticDrive()
        assert drive._squash(10.0, (0.0, 2.0)) == pytest.approx(2.0, abs=0.01)

    def test_large_negative_caps_near_min(self):
        drive = GlobalHomeostaticDrive()
        assert drive._squash(-10.0, (0.0, 2.0)) == pytest.approx(0.0, abs=0.01)
