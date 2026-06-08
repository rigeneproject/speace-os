"""T-Phase 9 — MM-APR Supervision Dashboard tests."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class TestPhase9Dashboard(unittest.TestCase):
    def test_build_report_with_empty_components(self):
        """The dashboard builds a valid report even when no router,
        governor, or hook is attached."""
        from speace_core.monitoring.mmapr_dashboard import (
            MMAPRSupervisionDashboard,
        )
        dash = MMAPRSupervisionDashboard()
        report = dash.build_report()
        self.assertEqual(report.health, "ok")
        self.assertEqual(report.cycle_count, 0)
        self.assertEqual(report.veto_rate, 0.0)
        self.assertEqual(report.agent_verdicts.total, 0)
        self.assertEqual(report.memory_counts.total, 0)

    def test_ascii_rendering_contains_key_sections(self):
        """The ASCII output mentions the supervision sections from
        the design doc: Veto distribution, Memory status counts,
        Fitness trend."""
        from speace_core.monitoring.mmapr_dashboard import (
            MMAPRSupervisionDashboard,
        )
        dash = MMAPRSupervisionDashboard(
            iteration=42,
            uptime_seconds=18 * 3600 + 4 * 60,
            fitness_samples=[0.64, 0.651, 0.648, 0.659, 0.667, 0.671, 0.674],
        )
        txt = dash.render()
        self.assertIn("MM-APR Supervision Dashboard", txt)
        self.assertIn("Veto distribution", txt)
        self.assertIn("Memory status", txt)
        self.assertIn("Fitness trend", txt)
        self.assertIn("42", txt)

    def test_markdown_rendering_is_table_format(self):
        """The Markdown output is a valid table for veto distribution
        and memory counts, with the trend section as a bullet list."""
        from speace_core.monitoring.mmapr_dashboard import (
            MMAPRSupervisionDashboard,
        )
        dash = MMAPRSupervisionDashboard(
            iteration=10,
            uptime_seconds=3600,
            fitness_samples=[0.5, 0.55, 0.6],
        )
        md = dash.render_markdown()
        self.assertIn("| Class | Count |", md)
        self.assertIn("| A - Evolution |", md)
        self.assertIn("| C - Adversarial |", md)
        self.assertIn("STABLE", md)
        self.assertIn("Delta:", md)
        self.assertIn("improving", md)

    def test_save_writes_markdown_and_ascii_files(self):
        """``save()`` writes a .md and a .txt file with the report."""
        from speace_core.monitoring.mmapr_dashboard import (
            MMAPRSupervisionDashboard,
        )
        with tempfile.TemporaryDirectory() as tmp:
            dash = MMAPRSupervisionDashboard(iteration=3, uptime_seconds=120.0)
            out_base = Path(tmp) / "dashboard"
            md_path = dash.save(out_base)
            self.assertTrue(md_path.exists())
            txt_path = out_base.with_suffix(".txt")
            self.assertTrue(txt_path.exists())
            md_text = md_path.read_text(encoding="utf-8")
            self.assertIn("MM-APR Supervision Report", md_text)

    def test_dashboard_aggregates_real_router(self):
        """With a real ``HardVetoRouter`` that has been exercised,
        the dashboard reports non-zero veto counts."""
        from speace_core.cellular_brain.self_improvement.mmapr_veto_router import (
            AgentVote, HardVetoRouter, VetoClass, VetoKind, VetoVerdict,
        )
        from speace_core.monitoring.mmapr_dashboard import (
            MMAPRSupervisionDashboard,
        )
        router = HardVetoRouter()
        # Inject a fake verdict into the router's history
        v = VetoVerdict(proposal_id="p-test", cycle_id="c-test")
        v.votes.append(AgentVote(
            agent="adversarial_auditor", veto_class=VetoClass.C_ADVERSARIAL,
            kind=VetoKind.HARD_BLOCK, confidence=0.9,
        ))
        v.hard_blocked_by.append("adversarial_auditor")
        v.final_status = "hard_blocked"
        router._last_verdicts.append(v)
        dash = MMAPRSupervisionDashboard(router=router, iteration=1, uptime_seconds=10.0)
        report = dash.build_report()
        self.assertEqual(report.agent_verdicts.class_c, 1)
        self.assertEqual(report.agent_verdicts.total, 1)
        # Cycle count from router summary
        self.assertGreaterEqual(report.cycle_count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
