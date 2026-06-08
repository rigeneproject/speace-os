"""Tests for T165 — UtilityDriveSystem and UtilityArbitrationEngine."""

import pytest

from speace_core.cellular_brain.regulation.utility_drive_system import UtilityDriveSystem
from speace_core.cellular_brain.regulation.utility_arbitration_engine import UtilityArbitrationEngine


class TestUtilityDriveSystem:
    def test_initial_drives(self) -> None:
        ds = UtilityDriveSystem()
        for name in ds.DRIVE_NAMES:
            assert ds.get_drive(name) == 0.5

    def test_invalid_leak_raises(self) -> None:
        with pytest.raises(ValueError):
            UtilityDriveSystem(leak=1.5)

    def test_exploration_rises_with_curiosity(self) -> None:
        ds = UtilityDriveSystem(leak=0.5)
        ds.tick(curiosity_score=1.0, novelty_score=1.0, prediction_error=0.8)
        assert ds.get_drive("exploration") > 0.5

    def test_rest_rises_at_night(self) -> None:
        ds = UtilityDriveSystem(leak=0.5)
        ds.tick(energy=0.2, circadian_phase="night")
        assert ds.get_drive("rest") > 0.5

    def test_energy_conservation_rises_when_low_energy(self) -> None:
        ds = UtilityDriveSystem(leak=0.5)
        ds.tick(energy=0.1, metabolism_cost=0.8)
        assert ds.get_drive("energy_conservation") > 0.5

    def test_cross_inhibition_exploration_vs_rest(self) -> None:
        ds = UtilityDriveSystem(leak=0.0)
        # Force exploration max and rest max simultaneously
        ds._drives["exploration"] = 1.0
        ds._drives["rest"] = 1.0
        ds.tick()  # inhibition applies
        # After inhibition, they should not both remain 1.0
        assert ds.get_drive("exploration") < 1.0 or ds.get_drive("rest") < 1.0

    def test_dominant_drive(self) -> None:
        ds = UtilityDriveSystem()
        ds._drives["exploration"] = 0.9
        assert ds.get_dominant_drive() == "exploration"

    def test_history_recorded(self) -> None:
        ds = UtilityDriveSystem()
        for _ in range(5):
            ds.tick()
        assert len(ds._history) == 5

    def test_snapshot(self) -> None:
        ds = UtilityDriveSystem()
        ds.tick(curiosity_score=0.8)
        snap = ds.snapshot()
        assert "drives" in snap
        assert "dominant_drive" in snap
        assert "history_sample" in snap

    def test_clamping(self) -> None:
        ds = UtilityDriveSystem(leak=0.0)
        ds.tick(curiosity_score=2.0, novelty_score=2.0, prediction_error=2.0)
        assert 0.0 <= ds.get_drive("exploration") <= 1.0


class TestUtilityArbitrationEngine:
    def test_weights_sum_to_one(self) -> None:
        ds = UtilityDriveSystem()
        arb = UtilityArbitrationEngine(drive_system=ds)
        weights = arb.tick(organism_state="awake")
        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-6

    def test_overload_boosts_homeostasis(self) -> None:
        ds = UtilityDriveSystem()
        arb = UtilityArbitrationEngine(drive_system=ds)
        weights = arb.tick(organism_state="overloaded")
        assert weights["homeostasis_engine"] >= arb.SAFETY_MODULES["homeostasis_engine"]
        assert weights["infant_curiosity_layer"] < 0.5

    def test_resting_boosts_consolidation(self) -> None:
        ds = UtilityDriveSystem()
        arb = UtilityArbitrationEngine(drive_system=ds)
        awake_weights = arb.tick(organism_state="awake")
        resting_weights = arb.tick(organism_state="resting")
        assert resting_weights["episodic_memory_consolidation"] > awake_weights["episodic_memory_consolidation"]

    def test_exploring_boosts_curiosity(self) -> None:
        ds = UtilityDriveSystem()
        arb = UtilityArbitrationEngine(drive_system=ds)
        awake_weights = arb.tick(organism_state="awake")
        exploring_weights = arb.tick(organism_state="exploring")
        assert exploring_weights["infant_curiosity_layer"] > awake_weights["infant_curiosity_layer"]

    def test_safety_floor_enforced(self) -> None:
        ds = UtilityDriveSystem()
        arb = UtilityArbitrationEngine(drive_system=ds)
        # Force all drives to zero
        for name in ds.DRIVE_NAMES:
            ds._drives[name] = 0.0
        weights = arb.tick(organism_state="awake")
        for module, floor in arb.SAFETY_MODULES.items():
            if module in weights:
                assert weights[module] >= floor

    def test_snapshot(self) -> None:
        ds = UtilityDriveSystem()
        arb = UtilityArbitrationEngine(drive_system=ds)
        arb.tick(organism_state="awake")
        snap = arb.snapshot()
        assert "weights" in snap
        assert "drive_snapshot" in snap
        assert "safety_floors" in snap
