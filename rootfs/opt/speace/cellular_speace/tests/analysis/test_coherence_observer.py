"""Tests for CoherenceObserver — T154-A."""

import json
import tempfile
from pathlib import Path

import pytest

from speace_core.cellular_brain.analysis.coherence_observer import CoherenceObserver


@pytest.fixture
def observer():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield CoherenceObserver(project_root=tmpdir, data_root=f"{tmpdir}/coherence")


class TestCoherenceObserver:
    def test_observe_returns_structure(self, observer):
        report = observer.observe()
        assert "run_id" in report
        assert "timestamp" in report
        assert "metrics" in report
        assert "aggregate_coherence" in report
        for key in [
            "modular_coherence",
            "redundancy_efficiency",
            "causal_clarity",
            "symmetry_asymmetry_balance",
            "narrative_coherence",
            "cognitive_entropy",
            "regulation_density",
            "mutation_stability",
            "energy_efficiency",
            "functional_elegance",
        ]:
            assert key in report["metrics"]

    def test_persistence(self, observer):
        observer.observe()
        reports = observer.get_reports()
        assert len(reports) == 1
        assert "aggregate_coherence" in reports[0]

    def test_latest_report(self, observer):
        assert observer.latest_report() is None
        observer.observe()
        latest = observer.latest_report()
        assert latest is not None
        assert "metrics" in latest

    def test_modular_coherence_no_modules(self, observer):
        score = observer._modular_coherence()
        assert 0.0 <= score <= 1.0

    def test_redundancy_efficiency_empty(self, observer):
        score = observer._redundancy_efficiency()
        assert score == 1.0  # no files = no duplicates

    def test_narrative_coherence_no_data(self, observer):
        score = observer._narrative_coherence()
        assert score == 0.5

    def test_cognitive_entropy_no_history(self, observer):
        score = observer._cognitive_entropy()
        assert score == 0.5

    def test_functional_elegance_no_code(self, observer):
        score = observer._functional_elegance()
        assert score == 0.0
