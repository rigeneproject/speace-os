from speace_core.cellular_brain.immune.clone_deviation_monitor import CloneDeviationMonitor


def test_compare_clone_states_finds_deviation():
    monitor = CloneDeviationMonitor()
    clones = {
        "clone_a": {"coherence_phi": 0.7, "mean_energy": 0.5, "neuron_count": 100, "mean_activation": 0.3},
        "clone_b": {"coherence_phi": 0.3, "mean_energy": 0.5, "neuron_count": 100, "mean_activation": 0.3},
    }
    report = monitor.compare_clone_states(clones)
    assert len(report.deviations) > 0
    assert report.deviations[0].metric_name == "coherence_phi"


def test_insufficient_clones():
    monitor = CloneDeviationMonitor()
    report = monitor.compare_clone_states({"clone_a": {"coherence_phi": 0.7}})
    assert len(report.deviations) == 0
    assert "Insufficient" in report.summary
