import pytest

from speace_core.cellular_brain.drives.drive_conflict_resolver import (
    DriveConflictResolver,
)


class TestResolve:
    def test_resolve_amplifies_winner(self):
        resolver = DriveConflictResolver(winner_amplification=1.5)
        drives = {
            "self_preservation": 0.2,
            "information_exploration": 0.8,
        }
        weights = resolver.resolve(drives)
        # Winner is information_exploration
        assert weights["information_exploration"] == pytest.approx(0.8 * 1.5)

    def test_resolve_suppresses_conflicting(self):
        resolver = DriveConflictResolver()
        drives = {
            "self_preservation": 1.0,
            "information_exploration": 0.9,
        }
        weights = resolver.resolve(drives)
        # self_preservation is winner, information_exploration should be suppressed
        assert weights["information_exploration"] < drives["information_exploration"]

    def test_resolve_no_drives(self):
        resolver = DriveConflictResolver()
        assert resolver.resolve({}) == {}

    def test_resolve_uniform_when_all_zero(self):
        resolver = DriveConflictResolver()
        weights = resolver.resolve({"a": 0.0, "b": 0.0})
        assert weights["a"] == 1.0
        assert weights["b"] == 1.0

    def test_resolve_multiple_drives(self):
        resolver = DriveConflictResolver(winner_amplification=2.0)
        drives = {
            "self_preservation": 0.5,
            "energy_conservation": 0.3,
            "resource_acquisition": 1.2,
            "information_exploration": 0.4,
        }
        weights = resolver.resolve(drives)
        winner = max(weights, key=weights.get)
        assert winner == "resource_acquisition"
        assert weights["resource_acquisition"] == pytest.approx(1.2 * 2.0)

    def test_resolve_unknown_drive_no_conflict_matrix(self):
        resolver = DriveConflictResolver()
        drives = {
            "custom_drive": 1.0,
            "another_drive": 0.5,
        }
        # No entries in conflict matrix for custom_drive -> default damping 1.0
        weights = resolver.resolve(drives)
        assert weights["custom_drive"] == pytest.approx(1.0 * resolver.winner_amplification)
        assert weights["another_drive"] == pytest.approx(0.5)

    def test_resolve_non_winner_unchanged_when_no_conflict(self):
        resolver = DriveConflictResolver()
        # Create a scenario where winner is not in conflict matrix with the other
        resolver._conflict_matrix = {"a": {}}  # empty conflicts
        drives = {"a": 1.0, "b": 0.5}
        weights = resolver.resolve(drives)
        assert weights["b"] == pytest.approx(0.5)


class TestDriveBalance:
    def test_drive_balance_perfectly_balanced(self):
        resolver = DriveConflictResolver()
        drives = {
            "self_preservation": 1.0,
            "energy_conservation": 1.0,
            "resource_acquisition": 1.0,
        }
        balance = resolver.get_drive_balance(drives)
        assert balance == pytest.approx(0.0, abs=1e-3)

    def test_drive_balance_lopsided(self):
        resolver = DriveConflictResolver()
        drives = {
            "self_preservation": 1.0,
            "energy_conservation": 0.0,
            "resource_acquisition": 0.0,
        }
        balance = resolver.get_drive_balance(drives)
        assert balance == pytest.approx(1.0, abs=1e-3)

    def test_drive_balance_empty(self):
        resolver = DriveConflictResolver()
        assert resolver.get_drive_balance({}) == 0.0

    def test_drive_balance_single_drive(self):
        resolver = DriveConflictResolver()
        assert resolver.get_drive_balance({"only_drive": 1.0}) == 1.0

    def test_drive_balance_partial(self):
        resolver = DriveConflictResolver()
        drives = {
            "self_preservation": 2.0,
            "energy_conservation": 1.0,
            "resource_acquisition": 1.0,
        }
        balance = resolver.get_drive_balance(drives)
        # Not perfectly balanced, not perfectly lopsided
        assert 0.0 < balance < 1.0


class TestCustomConfiguration:
    def test_custom_amplification(self):
        resolver = DriveConflictResolver(winner_amplification=3.0)
        drives = {"a": 1.0, "b": 0.5}
        weights = resolver.resolve(drives)
        assert weights["a"] == pytest.approx(3.0)

    def test_custom_conflict_matrix(self):
        resolver = DriveConflictResolver(
            conflict_matrix={
                "a": {"b": 0.0},
            },
            winner_amplification=1.0,
        )
        drives = {"a": 1.0, "b": 1.0}
        weights = resolver.resolve(drives)
        assert weights["a"] == pytest.approx(1.0)
        assert weights["b"] == pytest.approx(0.0)
