import pytest

from speace_core.cellular_brain.dynamics.criticality_monitor import (
    Avalanche,
    CriticalityMonitor,
    Spike,
)


# ---------------------------------------------------------------------------
# Spike recording
# ---------------------------------------------------------------------------

class TestRecordActivation:
    def test_records_single_spike(self):
        monitor = CriticalityMonitor()
        monitor.record_activation("n1", timestamp=0.0)
        assert len(monitor._spikes) == 1
        assert monitor._spikes[0].neuron_id == "n1"

    def test_records_multiple_spikes(self):
        monitor = CriticalityMonitor()
        for i in range(5):
            monitor.record_activation(f"n{i}", timestamp=float(i))
        assert len(monitor._spikes) == 5

    def test_respects_max_history(self):
        monitor = CriticalityMonitor(max_history=3)
        for i in range(5):
            monitor.record_activation("n1", timestamp=float(i))
        assert len(monitor._spikes) == 3


# ---------------------------------------------------------------------------
# Avalanche detection
# ---------------------------------------------------------------------------

class TestDetectAvalanche:
    def test_empty_spikes_returns_empty(self):
        monitor = CriticalityMonitor()
        assert monitor.detect_avalanche() == []

    def test_single_avalanche(self):
        monitor = CriticalityMonitor(avalanche_window=10.0)
        monitor.record_activation("n1", 0.0)
        monitor.record_activation("n2", 5.0)
        monitor.record_activation("n3", 9.0)
        avs = monitor.detect_avalanche()
        assert len(avs) == 1
        assert avs[0].size == 3

    def test_multiple_avalanches(self):
        monitor = CriticalityMonitor(avalanche_window=5.0)
        # First avalanche
        monitor.record_activation("n1", 0.0)
        monitor.record_activation("n2", 4.0)
        # Gap > window
        monitor.record_activation("n3", 20.0)
        monitor.record_activation("n4", 24.0)
        avs = monitor.detect_avalanche()
        assert len(avs) == 2
        assert avs[0].size == 2
        assert avs[1].size == 2

    def test_unsorted_spikes_sorted_by_detect(self):
        monitor = CriticalityMonitor(avalanche_window=10.0)
        monitor.record_activation("n2", 5.0)
        monitor.record_activation("n1", 0.0)
        monitor.record_activation("n3", 9.0)
        avs = monitor.detect_avalanche()
        assert len(avs) == 1
        assert avs[0].size == 3

    def test_avalanche_duration(self):
        monitor = CriticalityMonitor(avalanche_window=10.0)
        monitor.record_activation("n1", 2.0)
        monitor.record_activation("n2", 8.0)
        avs = monitor.detect_avalanche()
        assert avs[0].duration == pytest.approx(6.0, 0.001)


# ---------------------------------------------------------------------------
# Branching ratio
# ---------------------------------------------------------------------------

class TestBranchingRatio:
    def test_empty_returns_zero(self):
        monitor = CriticalityMonitor()
        assert monitor.get_branching_ratio() == 0.0

    def test_single_spike_avalanche_zero(self):
        monitor = CriticalityMonitor(avalanche_window=10.0, branching_bin_size=5.0)
        monitor.record_activation("n1", 0.0)
        assert monitor.get_branching_ratio() == 0.0

    def test_constant_ratio_one(self):
        # Two bins with equal counts → ratio = 1.0
        monitor = CriticalityMonitor(avalanche_window=20.0, branching_bin_size=5.0)
        # bin 0: 2 spikes
        monitor.record_activation("n1", 0.0)
        monitor.record_activation("n2", 1.0)
        # bin 1: 2 spikes
        monitor.record_activation("n3", 5.0)
        monitor.record_activation("n4", 6.0)
        br = monitor.get_branching_ratio()
        assert br == pytest.approx(1.0, abs=0.001)

    def test_ratio_greater_than_one(self):
        # bin 0: 1 spike, bin 1: 3 spikes → ratio = 3.0
        monitor = CriticalityMonitor(avalanche_window=20.0, branching_bin_size=5.0)
        monitor.record_activation("n1", 0.0)
        monitor.record_activation("n2", 5.0)
        monitor.record_activation("n3", 6.0)
        monitor.record_activation("n4", 7.0)
        br = monitor.get_branching_ratio()
        assert br == pytest.approx(3.0, abs=0.001)

    def test_ratio_less_than_one(self):
        # bin 0: 4 spikes, bin 1: 1 spike → ratio = 0.25
        monitor = CriticalityMonitor(avalanche_window=20.0, branching_bin_size=5.0)
        for i in range(4):
            monitor.record_activation(f"n{i}", float(i))
        monitor.record_activation("n5", 5.0)
        br = monitor.get_branching_ratio()
        assert br == pytest.approx(0.25, abs=0.001)


# ---------------------------------------------------------------------------
# Avalanche size distribution
# ---------------------------------------------------------------------------

class TestAvalancheSizeDistribution:
    def test_empty_returns_empty(self):
        monitor = CriticalityMonitor()
        assert monitor.get_avalanche_size_distribution() == {}

    def test_histogram_correct(self):
        monitor = CriticalityMonitor(avalanche_window=5.0)
        # Avalanche size 2
        monitor.record_activation("n1", 0.0)
        monitor.record_activation("n2", 3.0)
        # Avalanche size 3
        monitor.record_activation("n3", 20.0)
        monitor.record_activation("n4", 22.0)
        monitor.record_activation("n5", 24.0)
        # Avalanche size 2
        monitor.record_activation("n6", 50.0)
        monitor.record_activation("n7", 52.0)
        hist = monitor.get_avalanche_size_distribution()
        assert hist[2] == 2
        assert hist[3] == 1


# ---------------------------------------------------------------------------
# Near critical check
# ---------------------------------------------------------------------------

class TestIsNearCritical:
    def test_critical_ratio_true(self):
        monitor = CriticalityMonitor(avalanche_window=20.0, branching_bin_size=5.0)
        monitor.record_activation("n1", 0.0)
        monitor.record_activation("n2", 5.0)
        assert monitor.is_near_critical(branching_tolerance=0.1)

    def test_subcritical_false(self):
        monitor = CriticalityMonitor(avalanche_window=20.0, branching_bin_size=5.0)
        for i in range(4):
            monitor.record_activation(f"n{i}", float(i))
        monitor.record_activation("n5", 5.0)
        assert not monitor.is_near_critical(branching_tolerance=0.1)

    def test_supercritical_false(self):
        monitor = CriticalityMonitor(avalanche_window=20.0, branching_bin_size=5.0)
        monitor.record_activation("n1", 0.0)
        for i in range(3):
            monitor.record_activation(f"n{i+2}", 5.0 + i)
        assert not monitor.is_near_critical(branching_tolerance=0.1)

    def test_custom_tolerance(self):
        monitor = CriticalityMonitor(avalanche_window=20.0, branching_bin_size=5.0)
        # ratio = 3.0, tolerance = 5.0 → |3-1| = 2 <= 5 → True
        monitor.record_activation("n1", 0.0)
        for i in range(3):
            monitor.record_activation(f"n{i+2}", 5.0 + i)
        assert monitor.is_near_critical(branching_tolerance=5.0)


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------

class TestRecommendModulation:
    def test_subcritical_recommends_increase(self):
        monitor = CriticalityMonitor(avalanche_window=20.0, branching_bin_size=5.0)
        for i in range(4):
            monitor.record_activation(f"n{i}", float(i))
        monitor.record_activation("n5", 5.0)
        rec = monitor.recommend_modulation()
        assert rec["excitability_delta"] > 0.0
        assert "increase" in rec["reason"]

    def test_supercritical_recommends_decrease(self):
        monitor = CriticalityMonitor(avalanche_window=20.0, branching_bin_size=5.0)
        monitor.record_activation("n1", 0.0)
        for i in range(3):
            monitor.record_activation(f"n{i+2}", 5.0 + i)
        rec = monitor.recommend_modulation()
        assert rec["excitability_delta"] < 0.0
        assert "decrease" in rec["reason"]

    def test_critical_recommends_no_change(self):
        monitor = CriticalityMonitor(avalanche_window=20.0, branching_bin_size=5.0)
        monitor.record_activation("n1", 0.0)
        monitor.record_activation("n2", 5.0)
        rec = monitor.recommend_modulation()
        assert rec["excitability_delta"] == pytest.approx(0.0, abs=0.001)
        assert "no adjustment" in rec["reason"]

    def test_recommendation_structure(self):
        monitor = CriticalityMonitor()
        rec = monitor.recommend_modulation()
        assert set(rec.keys()) == {
            "excitability_delta",
            "target_branching_ratio",
            "current_branching_ratio",
            "reason",
        }
