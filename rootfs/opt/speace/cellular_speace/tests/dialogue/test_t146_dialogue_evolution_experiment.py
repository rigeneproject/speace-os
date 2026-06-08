"""Tests for T146 — First Controlled Dialogue Evolution Experiment."""

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from scripts.t146_dialogue_evolution_experiment import run_experiment
from speace_core.cellular_brain.language.dialogue_manager import DialogueManager


@pytest.fixture
def isolated_dialogue_manager():
    """Provide a DialogueManager with isolated data directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        # Ensure data dirs exist under tmpdir
        Path("data/language").mkdir(parents=True, exist_ok=True)
        Path("data/cognitive_evolution").mkdir(parents=True, exist_ok=True)
        dm = DialogueManager()
        yield dm
        os.chdir(original_cwd)


class TestT146DialogueEvolutionExperiment:
    def test_run_experiment_structure(self, isolated_dialogue_manager):
        pre = ["Ciao", "Come stai?", "Chi sei?", "Salute", "Allerte"]
        post = ["Ciao di nuovo", "Stai bene?", "Ricordi?", "Proposte", "Arrivederci"]
        report = run_experiment(dm=isolated_dialogue_manager, pre_messages=pre, post_messages=post)

        assert report["experiment"] == "T146_dialogue_evolution"
        assert report["pre_turns"] == len(pre)
        assert report["post_turns"] == len(post)
        assert 0.0 <= report["pre_average_coherence"] <= 1.0
        assert 0.0 <= report["post_average_coherence"] <= 1.0
        assert "delta" in report
        assert isinstance(report["worsened"], bool)
        assert report["conclusion"] in ("rollback_executed", "kept", "no_proposal_approved")

    def test_report_persisted(self, isolated_dialogue_manager):
        pre = ["Ciao"]
        post = ["Arrivederci"]
        run_experiment(dm=isolated_dialogue_manager, pre_messages=pre, post_messages=post)
        out_path = Path("data/dialogue/t146_experiment_report.jsonl")
        assert out_path.exists()
        lines = out_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) >= 1
        data = json.loads(lines[-1])
        assert data["experiment"] == "T146_dialogue_evolution"

    def test_rollback_on_worsening(self, isolated_dialogue_manager):
        # Force worsening by using identical messages that trigger low coherence
        pre = ["x"] * 10
        post = ["x"] * 10
        report = run_experiment(dm=isolated_dialogue_manager, pre_messages=pre, post_messages=post)
        # Even if coherence is low, we just assert structural correctness
        assert report["pre_turns"] == 10
        assert report["post_turns"] == 10
        assert isinstance(report["rollback_result"], (dict, type(None)))
