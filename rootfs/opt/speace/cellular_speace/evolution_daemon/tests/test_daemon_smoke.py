"""Smoke tests for the evolution daemon.

These tests avoid starting the full SPEACE runtime; they verify that
the daemon cycle produces the expected JSON-Lines/JSON artefacts and
that the dashboards are importable.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Make `evolution_daemon` importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from evolution_daemon.config import DaemonConfig
from evolution_daemon.state_collector import StateCollector
from evolution_daemon.benchmark_runner import BenchmarkRunner
from evolution_daemon.arc_runner import ARCRunner
from evolution_daemon.mutation_engine import MutationEngine
from evolution_daemon.fitness_evaluator import FitnessEvaluator
from evolution_daemon.task_generator import TaskGenerator
from evolution_daemon.dna_updater import DNAUpdater
from evolution_daemon.epigenetic_controller import EpigeneticController
from evolution_daemon.knowledge_graph import SPEACEKnowledgeGraph
from evolution_daemon.engineering_plan import EngineeringPlan
from evolution_daemon.regression_reviewer import RegressionReviewer
from evolution_daemon.conflict_resolver import ConflictResolver


class DaemonSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data_root = Path(self.tmp.name)
        self.repo_root = Path(__file__).resolve().parent.parent.parent

    # ------------------------------------------------------------------ #
    def test_collector_snapshot_smoke(self) -> None:
        collector = StateCollector(self.data_root)
        snap = collector.snapshot()
        self.assertIn("snapshot_id", snap)
        self.assertIn("neuron_synapse", snap)
        self.assertIn("diagnostics", snap)

    def test_benchmark_agi_percentage(self) -> None:
        runner = BenchmarkRunner(self.data_root)
        agi = runner.compute_agi_percentage(
            {
                "adaptation_after_error": 0.8,
                "useful_neurogenesis": 0.6,
                "useful_apoptosis": 0.5,
                "differentiation_consistency": 0.4,
                "morphological_memory_trace": 0.7,
                "arc_agi_subset": 0.5,
                "regulation_stability": 0.9,
            }
        )
        self.assertGreater(agi, 0.0)
        self.assertLessEqual(agi, 100.0)

    def test_arc_runner_handles_missing_dataset(self) -> None:
        runner = ARCRunner(self.data_root, task_limit=2)
        report = runner.run_pass(task_limit=2)
        self.assertIn("status", report)
        self.assertIn(report["status"], ("missing_dataset", "completed", "failed"))

    def test_mutation_engine_emits_proposals(self) -> None:
        engine = MutationEngine(self.data_root)
        proposals = engine.propose_refactors(
            metrics={"coherence_phi": 0.2},
            diagnostics={"alert": 1, "compartments": {"runtime": {"status": "alert"}}},
        )
        self.assertGreater(len(proposals), 0)
        for p in proposals:
            self.assertFalse(p.get("auto_apply", True))

    def test_fitness_evaluator(self) -> None:
        evaluator = FitnessEvaluator(self.data_root)
        fitness = evaluator.measure(
            {"category": "refactor", "files_hint": "a.py,b.py"},
            baseline_metrics={"coherence_phi": 0.5, "accuracy": 0.5},
            candidate_metrics={"coherence_phi": 0.6, "accuracy": 0.55},
        )
        self.assertIn("fitness", fitness)
        self.assertGreaterEqual(fitness["fitness"], 0.0)
        self.assertLessEqual(fitness["fitness"], 1.0)

    def test_task_generator(self) -> None:
        gen = TaskGenerator(self.data_root)
        tasks = gen.next_iteration(agi_percentage=15.0)
        self.assertGreater(len(tasks), 0)
        for t in tasks:
            self.assertIn("task_id", t)
            self.assertEqual(t["status"], "pending")

    def test_dna_updater_proposes_only(self) -> None:
        # Use the real default genome path so the read works.
        dna = DNAUpdater(
            genome_path=self.repo_root / "speace_core" / "dna" / "genome" / "default_genome.yaml",
            proposals_log=self.data_root / "dna_proposals.jsonl",
        )
        proposals = dna.propose_updates(current_metrics={"coherence_phi": 0.2})
        for p in proposals:
            self.assertFalse(p.get("auto_apply", True))

    def test_epigenetic_controller(self) -> None:
        epi = EpigeneticController(self.data_root)
        changes = epi.apply_cycle(
            {
                "neuron_synapse": {"activation_mean": 0.9},
                "diagnostics": {
                    "compartments": {"runtime": {"status": "alert"}},
                },
            }
        )
        self.assertGreater(len(changes), 0)
        self.assertTrue(epi.get("high_activation_regime"))

    def test_knowledge_graph(self) -> None:
        kg = SPEACEKnowledgeGraph(self.data_root / "kg.jsonl")
        kg.add_node("test:n1", "test", "Node 1")
        kg.add_edge("test:n1", "module:speace_core", "tested_by")
        nodes = list(kg.iter_nodes())
        self.assertGreaterEqual(len(nodes), 1)

    def test_engineering_plan(self) -> None:
        plan = EngineeringPlan(self.data_root / "plan.json")
        out = plan.regenerate(
            agi_percentage=20.0,
            diagnostics={
                "compartments": {"cognition": {"status": "watch"}},
            },
            proposals=[{"proposal_id": "p1", "title": "T", "category": "refactor"}],
        )
        self.assertEqual(out["current_agi_percentage"], 20.0)
        self.assertGreater(len(out["milestones"]), 0)

    def test_regression_reviewer(self) -> None:
        reviewer = RegressionReviewer(self.repo_root)
        report = reviewer.review()
        self.assertIn("changed_files", report)
        self.assertIn("verdict", report)

    def test_conflict_resolver(self) -> None:
        resolver = ConflictResolver(data_root=self.data_root, repo_root=self.repo_root)
        report = resolver.scan_and_resolve()
        self.assertIn("ports", report)
        self.assertIn("python_procs", report)
        self.assertIn("summary", report)
        self.assertIn("ports_in_use", report["summary"])


if __name__ == "__main__":
    unittest.main()
