from speace_core.cellular_brain.sleep.sleep_cycle_detector import (
    SleepCycleDetector,
    SleepPhase,
)
from speace_core.cellular_brain.regulation.homeostasis_engine import SystemMetrics


def _make_metrics(phi: float, energy: float, active: int):
    return SystemMetrics(
        tick=0,
        coherence_phi=phi,
        mean_energy=energy,
        active_neurons=active,
        pruned_synapses=0,
    )


def test_detector_awake_with_volatile_metrics():
    detector = SleepCycleDetector()
    metrics = [_make_metrics(0.5 + i * 0.1, 0.5, 10) for i in range(20)]
    state = detector.detect(metrics)
    assert state.phase == SleepPhase.AWAKE
    assert state.stability_score < 0.5


def test_detector_sleep_eligible_with_stable_metrics():
    detector = SleepCycleDetector(min_consecutive_stable=3)
    metrics = [_make_metrics(0.7, 0.5, 10) for _ in range(20)]
    state = detector.detect(metrics)
    assert state.phase == SleepPhase.SLEEP_ELIGIBLE
    assert state.stability_score >= 0.9


def test_detector_short_log_returns_awake():
    detector = SleepCycleDetector(stability_window=20)
    metrics = [_make_metrics(0.7, 0.5, 10) for _ in range(5)]
    state = detector.detect(metrics)
    assert state.phase == SleepPhase.AWAKE


def test_detector_empty_log():
    detector = SleepCycleDetector()
    state = detector.detect([])
    assert state.phase == SleepPhase.AWAKE
