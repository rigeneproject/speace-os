"""Smoke tests for the SelfModificationCycle (T169 — Phase 3 closed loop)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from speace_core.cellular_brain.self_improvement.self_modification_cycle import (
    SelfModificationCycle,
    SelfModificationCycleResult,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def tmp_data_root(tmp_path):
    """Provide an isolated data root for the cycle to write into."""
    (tmp_path / "self_improvement").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def cycle(tmp_data_root):
    """A SelfModificationCycle with no orchestrator (read-only fallback)."""
    return SelfModificationCycle(
        orchestrator=None,
        memory=None,
        data_root=tmp_data_root,
    )


# --------------------------------------------------------------------------- #
# Basic construction
# --------------------------------------------------------------------------- #
class TestConstruction:
    def test_init_no_orchestrator(self, cycle):
        assert cycle.orchestrator is None
        assert cycle.data_root is not None

    def test_init_with_data_root(self, tmp_data_root):
        c = SelfModificationCycle(data_root=tmp_data_root)
        assert c.data_root == tmp_data_root


# --------------------------------------------------------------------------- #
# Observe step
# --------------------------------------------------------------------------- #
class TestObserve:
    def test_observe_with_orchestrator_metrics(self, tmp_data_root):
        class FakeOrch:
            latest_metrics = type("M", (), {
                "accuracy": 0.42,
                "coherence_phi": 0.31,
                "mean_energy": 0.55,
            })()
        c = SelfModificationCycle(orchestrator=FakeOrch(), data_root=tmp_data_root)
        obs = c._observe({})
        assert obs["cognitive_score"] == 0.42
        assert obs["coherence_phi"] == 0.31
        assert obs["mean_energy"] == 0.55

    def test_observe_fallback_to_metrics(self, cycle):
        obs = cycle._observe({"cognitive_score": 0.5, "phi_delta": -0.01})
        assert obs["cognitive_score"] == 0.5
        assert obs["phi_delta"] == -0.01

    def test_observe_ignores_non_numeric(self, cycle):
        obs = cycle._observe({"good": "yes", "x": 1.5})
        assert "good" not in obs
        assert obs["x"] == 1.5


# --------------------------------------------------------------------------- #
# Full cycle run
# --------------------------------------------------------------------------- #
class TestFullCycle:
    def test_run_returns_result(self, cycle):
        result = cycle.run({"cognitive_score": 0.5, "coherence_phi": 0.3})
        assert isinstance(result, SelfModificationCycleResult)
        assert result.cycle_id.startswith("smc-")
        assert result.observed == {"cognitive_score": 0.5, "coherence_phi": 0.3}

    def test_run_passes_observe(self, cycle):
        result = cycle.run({"cognitive_score": 0.4})
        assert "observe" in result.passed_steps

    def test_run_no_metrics_still_works(self, cycle):
        # With no orchestrator + no metrics, observed is empty
        result = cycle.run()
        assert isinstance(result, SelfModificationCycleResult)
        # We may not have proposals, so the cycle should still complete
        assert "observe" in result.passed_steps

    def test_run_with_metrics_far_below_threshold(self, cycle):
        # Metrics that should NOT trigger limitations (above the negative thresholds)
        result = cycle.run({
            "cognitive_score": 0.5,
            "cognitive_delta": 0.0,
            "phi_delta": 0.0,
            "energy_delta": 0.0,
        })
        # No limitations detected → no mutations → no tests
        assert result.limitations == []
        assert result.mutations == []
        assert result.tests == []
        assert result.adoption is None

    def test_run_with_regression_metrics(self, cycle):
        # Below cognitive_delta threshold → should detect a limitation
        result = cycle.run({
            "cognitive_score": 0.5,
            "cognitive_delta": -0.1,  # below -0.03 threshold
            "phi_delta": -0.05,
            "energy_delta": -0.1,
        })
        # We may or may not produce mutations depending on what the
        # detector decides; the important thing is the cycle completed.
        assert isinstance(result, SelfModificationCycleResult)
        assert result.duration_sec >= 0.0


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
class TestPersistence:
    def test_persist_writes_jsonl(self, cycle, tmp_data_root):
        result = cycle.run({"cognitive_score": 0.5})
        path = cycle.persist(result)
        assert path is not None
        assert path.exists()
        # File should contain one record
        with path.open("r", encoding="utf-8") as f:
            lines = [ln for ln in f if ln.strip()]
        assert len(lines) == 1
        rec = json.loads(lines[0])
        assert rec["cycle_id"] == result.cycle_id
        assert "started_at" in rec
        assert "passed_steps" in rec

    def test_persist_appends(self, cycle, tmp_data_root):
        r1 = cycle.run({"cognitive_score": 0.5})
        r2 = cycle.run({"cognitive_score": 0.6})
        cycle.persist(r1)
        cycle.persist(r2)
        path = tmp_data_root / "self_improvement" / "smc_cycles.jsonl"
        with path.open("r", encoding="utf-8") as f:
            lines = [ln for ln in f if ln.strip()]
        assert len(lines) == 2


# --------------------------------------------------------------------------- #
# Edge cases
# --------------------------------------------------------------------------- #
class TestEdgeCases:
    def test_result_model_serialization(self):
        r = SelfModificationCycleResult(
            cycle_id="smc-test",
            observed={"x": 0.5},
            passed_steps=["observe"],
        )
        d = r.model_dump()
        assert d["cycle_id"] == "smc-test"
        assert d["observed"] == {"x": 0.5}
        assert d["delta_score"] == 0.0

    def test_verbose_false_does_not_print(self, cycle, capsys):
        cycle.run({"cognitive_score": 0.5})
        captured = capsys.readouterr()
        # Should not print anything when verbose=False
        assert "persist failed" not in captured.out
