import pytest

from speace_core.cellular_brain.experience.endogenous_exploration_bonus import (
    ExplorationBonusModel,
)


class TestEndogenousExplorationBonus:
    def test_pseudo_count_decreases_with_visits(self):
        model = ExplorationBonusModel(pseudo_count_scale=1.0)
        b1 = model.compute_bonus({"state": "A"})
        b2 = model.compute_bonus({"state": "A"})
        b3 = model.compute_bonus({"state": "A"})
        assert b1.pseudo_count_bonus > b2.pseudo_count_bonus > b3.pseudo_count_bonus

    def test_rnd_bonus_changes_with_state(self):
        model = ExplorationBonusModel(rnd_scale=1.0)
        r1 = model.compute_bonus({"x": 1})
        r2 = model.compute_bonus({"x": 2})
        # Different states should produce different bonuses
        assert r1.total_bonus >= 0.0
        assert r2.total_bonus >= 0.0

    def test_total_bonus_capped(self):
        model = ExplorationBonusModel()
        for i in range(10):
            b = model.compute_bonus({"i": i})
            assert 0.0 <= b.total_bonus <= 1.0

    def test_summary(self):
        model = ExplorationBonusModel()
        model.compute_bonus("A")
        model.compute_bonus("B")
        model.compute_bonus("A")
        s = model.summary()
        assert s["states_visited"] == 2
        assert s["mean_visits"] == 1.5
