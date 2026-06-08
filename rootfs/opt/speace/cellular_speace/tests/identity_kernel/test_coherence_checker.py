import pytest

from speace_core.cellular_brain.identity_kernel.cross_clone_coherence_checker import (
    CrossCloneCoherenceChecker,
)


def test_single_clone_always_coherent():
    checker = CrossCloneCoherenceChecker()
    report = checker.check_coherence({"clone_a": {"species_orientation": "orient1"}})
    assert report.coherent is True
    assert report.coherence_score == 1.0
    assert report.violations == []


def test_orientation_mismatch():
    checker = CrossCloneCoherenceChecker()
    clones = {
        "clone_a": {"species_orientation": "orient1"},
        "clone_b": {"species_orientation": "orient2"},
    }
    report = checker.check_coherence(clones)
    assert report.coherent is False
    assert "species_orientation_mismatch" in report.violations
    assert report.coherence_score == 0.0


def test_quarantine_penalty():
    checker = CrossCloneCoherenceChecker()
    clones = {
        "clone_a": {"species_orientation": "orient1", "epigenome": {"quarantined": 0.0}},
        "clone_b": {"species_orientation": "orient1", "epigenome": {"quarantined": 1.0}},
    }
    report = checker.check_coherence(clones)
    assert report.coherent is False  # violations present even if score > min
    assert "clone_clone_b_quarantined" in report.violations
    assert report.coherence_score == 0.75
